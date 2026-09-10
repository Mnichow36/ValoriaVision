from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from uuid import uuid4

from app.database import Database
from app.migrations.r8_reconciliation import apply_r8_reconciliation_foundation
from app.services.reconciliation import (
    ForecastInput,
    ReconciliationRules,
    TransactionInput,
    cancel_reconciliations_for_occurrence,
    qualify,
    qualify_and_persist_transaction,
)
from app.services.reconciliation.scoring import score_candidate


class R8ConfigurableRulesTests(unittest.TestCase):
    def transaction(self, **overrides) -> TransactionInput:
        values = {
            "id": 1,
            "account_id": 1,
            "tx_date": date(2026, 6, 10),
            "amount": -100.0,
            "label": "LOYER DUPONT",
            "direction": "debit",
            "category": "Logement",
            "counterparty": "Agence Dupont",
            "external_reference": "REF-2026-001",
        }
        values.update(overrides)
        return TransactionInput(**values)

    def forecast(self, **overrides) -> ForecastInput:
        values = {
            "id": 2,
            "account_id": 1,
            "expected_date": date(2026, 6, 10),
            "expected_amount": -100.0,
            "expected_label": "Loyer Dupont",
            "direction": "debit",
            "category": "Logement",
            "counterparty": "Agence Dupont",
            "external_reference": "REF2026001",
        }
        values.update(overrides)
        return ForecastInput(**values)

    def test_required_account_and_direction_reject_incompatible_candidates(self) -> None:
        self.assertIsNone(
            score_candidate(
                self.transaction(account_id=9),
                self.forecast(),
                ReconciliationRules(same_account_required=True),
            )
        )
        self.assertIsNone(
            score_candidate(
                self.transaction(direction="credit", amount=100),
                self.forecast(),
                ReconciliationRules(same_direction_required=True),
            )
        )

    def test_account_and_direction_requirements_can_be_disabled(self) -> None:
        candidate = score_candidate(
            self.transaction(account_id=9, direction="credit", amount=100),
            self.forecast(),
            ReconciliationRules(
                same_account_required=False,
                same_direction_required=False,
            ),
        )
        self.assertIsNotNone(candidate)

    def test_date_amount_and_label_tolerances_are_enforced(self) -> None:
        self.assertIsNone(
            score_candidate(
                self.transaction(tx_date=date(2026, 6, 20)),
                self.forecast(),
                ReconciliationRules(date_tolerance_days=5),
            )
        )
        self.assertIsNone(
            score_candidate(
                self.transaction(amount=-110),
                self.forecast(),
                ReconciliationRules(
                    amount_tolerance_absolute=1,
                    amount_tolerance_relative=0.02,
                ),
            )
        )
        self.assertIsNone(
            score_candidate(
                self.transaction(label="ÉLECTRICITÉ"),
                self.forecast(),
                ReconciliationRules(label_similarity_minimum=0.70),
            )
        )

    def test_reference_and_counterparty_are_explained_when_available(self) -> None:
        candidate = score_candidate(
            self.transaction(label="AUTRE LIBELLÉ"),
            self.forecast(expected_label="PRÉVISION"),
            ReconciliationRules(),
        )
        self.assertIsNotNone(candidate)
        details = {item.criterion: item for item in candidate.criteria}
        self.assertEqual(details["external_reference"].points, 10)
        self.assertEqual(details["counterparty"].points, 5)
        self.assertIn("identique", details["external_reference"].explanation)
        self.assertIn("identique", details["counterparty"].explanation)

    def test_thresholds_produce_auto_review_and_without_forecast(self) -> None:
        transaction = self.transaction(
            label="",
            counterparty=None,
            external_reference=None,
        )
        forecast = self.forecast(
            expected_label="",
            counterparty=None,
            external_reference=None,
        )
        candidate = score_candidate(transaction, forecast, ReconciliationRules())
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.score, 70)

        automatic = qualify(
            transaction,
            [forecast],
            ReconciliationRules(auto_threshold=70, review_threshold=60),
        )
        review = qualify(
            transaction,
            [forecast],
            ReconciliationRules(auto_threshold=90, review_threshold=60),
        )
        insufficient = qualify(
            transaction,
            [forecast],
            ReconciliationRules(auto_threshold=90, review_threshold=75),
        )

        self.assertEqual(automatic.status, "automatic")
        self.assertEqual(review.status, "review")
        self.assertEqual(insufficient.status, "without_forecast")
        self.assertIn("inférieur au seuil", insufficient.reason)

    def test_rule_settings_are_saved_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Database(Path(temp_dir) / "rules.db")
            with db.connect() as conn:
                db.create_schema(conn)
                apply_r8_reconciliation_foundation(conn)

            rules = db.set_reconciliation_settings(
                {
                    "reconciliation.auto_threshold": 92,
                    "reconciliation.review_threshold": 65,
                    "reconciliation.date_tolerance_days": 7,
                    "reconciliation.amount_tolerance_absolute": 2.5,
                    "reconciliation.amount_tolerance_relative": 0.02,
                    "reconciliation.label_similarity_minimum": 0.70,
                    "reconciliation.same_account_required": True,
                    "reconciliation.same_direction_required": True,
                    "reconciliation.date_weight": 20,
                    "reconciliation.amount_weight": 40,
                    "reconciliation.label_weight": 30,
                    "reconciliation.category_weight": 10,
                    "reconciliation.counterparty_match_bonus": 5,
                    "reconciliation.external_reference_match_bonus": 10,
                }
            )

            self.assertEqual(rules.auto_threshold, 92)
            self.assertEqual(rules.date_tolerance_days, 7)
            self.assertAlmostEqual(rules.amount_tolerance_relative, 0.02)
            self.assertAlmostEqual(rules.label_similarity_minimum, 0.70)
            self.assertEqual(db.reconciliation_rules(), rules)

    def test_invalid_weight_total_rolls_back_all_rule_edits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Database(Path(temp_dir) / "rules-invalid.db")
            with db.connect() as conn:
                db.create_schema(conn)
                apply_r8_reconciliation_foundation(conn)

            before = db.reconciliation_rules()
            with self.assertRaisesRegex(ValueError, "somme des poids"):
                db.set_reconciliation_settings(
                    {
                        "reconciliation.auto_threshold": 95,
                        "reconciliation.date_weight": 99,
                    }
                )
            self.assertEqual(db.reconciliation_rules(), before)

    def test_cancellation_releases_transaction_and_occurrence(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        db = object.__new__(Database)
        db.create_schema(conn)
        apply_r8_reconciliation_foundation(conn)
        account_id = int(
            conn.execute(
                """
                INSERT INTO accounts(
                    name, bank, account_type, identifier,
                    reference_balance, reference_date, status
                )
                VALUES ('Compte test', 'Banque test', 'Courant', ?, 0,
                        '2026-01-01', 'Actif')
                """,
                (str(uuid4()),),
            ).lastrowid
        )
        transaction_id = int(
            conn.execute(
                """
                INSERT INTO transactions(
                    account_id, tx_date, label, category, amount,
                    tx_type, status, source, signature
                )
                VALUES (?, '2026-06-10', 'LOYER', 'Logement', -100,
                        'Débit', 'Validée', 'Import bancaire', ?)
                """,
                (account_id, str(uuid4())),
            ).lastrowid
        )
        occurrence_id = int(
            conn.execute(
                """
                INSERT INTO forecast_occurrences(
                    uuid, source_type, account_id, expected_date,
                    expected_amount, expected_label, expected_category,
                    direction, status
                )
                VALUES (?, 'manual', ?, '2026-06-10', -100, 'LOYER',
                        'Logement', 'debit', 'planned')
                """,
                (str(uuid4()), account_id),
            ).lastrowid
        )
        persisted = qualify_and_persist_transaction(conn, transaction_id)
        self.assertEqual(persisted.status, "reconciled")

        released = cancel_reconciliations_for_occurrence(conn, occurrence_id)

        self.assertEqual(released, (transaction_id,))
        reconciliation = conn.execute(
            "SELECT status FROM reconciliations WHERE id = ?",
            (persisted.entity_id,),
        ).fetchone()
        state = conn.execute(
            """
            SELECT status FROM transaction_reconciliation_state
            WHERE transaction_id = ?
            """,
            (transaction_id,),
        ).fetchone()
        self.assertEqual(reconciliation["status"], "cancelled")
        self.assertEqual(state["status"], "unclassified")
        self.assertIsNotNone(
            conn.execute(
                """
                SELECT id FROM reconciliation_events
                WHERE entity_type = 'reconciliation'
                  AND entity_id = ?
                  AND event_type = 'reconciliation_cancelled'
                """,
                (persisted.entity_id,),
            ).fetchone()
        )
        conn.close()


if __name__ == "__main__":
    unittest.main()
