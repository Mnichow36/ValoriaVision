from __future__ import annotations

import json
import sqlite3
import unittest
from uuid import uuid4

from app.database import Database
from app.migrations.r8_reconciliation import apply_r8_reconciliation_foundation
from app.services.reconciliation import (
    qualify_and_persist_transaction,
    reevaluate_for_occurrences,
    reevaluate_transaction,
)


class R8ReevaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.db = object.__new__(Database)
        self.db.create_schema(self.conn)
        apply_r8_reconciliation_foundation(self.conn)
        self.account_id = int(
            self.conn.execute(
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

    def tearDown(self) -> None:
        self.conn.close()

    def transaction(self, *, amount: float = -900, label: str = "LOYER") -> int:
        return int(
            self.conn.execute(
                """
                INSERT INTO transactions(
                    account_id, tx_date, label, category, amount,
                    tx_type, status, source, signature
                )
                VALUES (?, '2026-06-09', ?, 'Logement', ?,
                        'Débit', 'Validée', 'Import bancaire', ?)
                """,
                (self.account_id, label, amount, str(uuid4())),
            ).lastrowid
        )

    def occurrence(
        self,
        *,
        amount: float = -900,
        label: str = "Loyer",
        status: str = "planned",
    ) -> int:
        return int(
            self.conn.execute(
                """
                INSERT INTO forecast_occurrences(
                    uuid, source_type, account_id, expected_date,
                    expected_amount, expected_label, expected_category,
                    direction, status
                )
                VALUES (?, 'manual', ?, '2026-06-09', ?, ?,
                        'Logement', 'debit', ?)
                """,
                (str(uuid4()), self.account_id, amount, label, status),
            ).lastrowid
        )

    def state(self, transaction_id: int) -> str:
        return str(
            self.conn.execute(
                """
                SELECT status FROM transaction_reconciliation_state
                WHERE transaction_id = ?
                """,
                (transaction_id,),
            ).fetchone()["status"]
        )

    def test_without_forecast_becomes_automatic_after_occurrence_creation(self) -> None:
        transaction_id = self.transaction()
        first = qualify_and_persist_transaction(self.conn, transaction_id)
        self.assertEqual(first.status, "without_forecast")

        occurrence_id = self.occurrence()
        summary = reevaluate_for_occurrences(
            self.conn,
            [occurrence_id],
            reason="Occurrence créée pendant le test",
        )

        self.assertEqual(summary.transaction_ids, (transaction_id,))
        self.assertEqual(summary.results[0].status, "reconciled")
        self.assertEqual(self.state(transaction_id), "reconciled")

    def test_transaction_change_invalidates_previous_match_and_audits_transition(self) -> None:
        transaction_id = self.transaction()
        self.occurrence()
        first = qualify_and_persist_transaction(self.conn, transaction_id)
        self.assertEqual(first.status, "reconciled")

        self.conn.execute(
            "UPDATE transactions SET amount = -2000 WHERE id = ?",
            (transaction_id,),
        )
        second = reevaluate_transaction(
            self.conn,
            transaction_id,
            reason="Montant de transaction modifié",
        )

        self.assertEqual(second.status, "without_forecast")
        old = self.conn.execute(
            "SELECT status, cancel_reason FROM reconciliations WHERE id = ?",
            (first.entity_id,),
        ).fetchone()
        self.assertEqual(old["status"], "cancelled")
        self.assertEqual(old["cancel_reason"], "Montant de transaction modifié")
        transition = self.conn.execute(
            """
            SELECT payload_json FROM reconciliation_events
            WHERE entity_type = 'transaction'
              AND entity_id = ?
              AND event_type = 'qualification_reevaluated'
            ORDER BY id DESC LIMIT 1
            """,
            (transaction_id,),
        ).fetchone()
        payload = json.loads(transition["payload_json"])
        self.assertEqual(payload["previous_status"], "reconciled")
        self.assertEqual(payload["new_status"], "without_forecast")

    def test_invalid_proposal_is_expired_before_new_decision(self) -> None:
        transaction_id = self.transaction()
        first_occurrence = self.occurrence(label="Loyer A")
        second_occurrence = self.occurrence(label="Loyer B")
        proposal = qualify_and_persist_transaction(self.conn, transaction_id)
        self.assertEqual(proposal.status, "has_proposal")

        self.conn.execute(
            "UPDATE forecast_occurrences SET status = 'cancelled' WHERE id = ?",
            (second_occurrence,),
        )
        result = reevaluate_for_occurrences(
            self.conn,
            [first_occurrence, second_occurrence],
            reason="Occurrence candidate annulée",
        )

        self.assertEqual(result.results[0].status, "reconciled")
        old_status = self.conn.execute(
            "SELECT status FROM reconciliation_proposals WHERE id = ?",
            (proposal.entity_id,),
        ).fetchone()[0]
        self.assertEqual(old_status, "expired")

    def test_identical_reevaluation_is_idempotent(self) -> None:
        transaction_id = self.transaction()
        occurrence_id = self.occurrence()
        qualify_and_persist_transaction(self.conn, transaction_id)

        first = reevaluate_for_occurrences(self.conn, [occurrence_id])
        reconciliation_count = self.conn.execute(
            "SELECT COUNT(*) FROM reconciliations"
        ).fetchone()[0]
        event_count = self.conn.execute(
            """
            SELECT COUNT(*) FROM reconciliation_events
            WHERE entity_type = 'transaction'
              AND entity_id = ?
              AND event_type = 'qualification_reevaluated'
            """,
            (transaction_id,),
        ).fetchone()[0]

        second = reevaluate_for_occurrences(self.conn, [occurrence_id])
        self.assertEqual(second.results[0].entity_id, first.results[0].entity_id)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM reconciliations").fetchone()[0],
            reconciliation_count,
        )
        self.assertEqual(
            self.conn.execute(
                """
                SELECT COUNT(*) FROM reconciliation_events
                WHERE entity_type = 'transaction'
                  AND entity_id = ?
                  AND event_type = 'qualification_reevaluated'
                """,
                (transaction_id,),
            ).fetchone()[0],
            event_count,
        )

    def test_occurrence_deletion_cancels_match_and_releases_transaction(self) -> None:
        transaction_id = self.transaction()
        occurrence_id = self.occurrence()
        result = qualify_and_persist_transaction(self.conn, transaction_id)
        self.assertEqual(result.status, "reconciled")

        self.conn.execute(
            "DELETE FROM forecast_occurrences WHERE id = ?",
            (occurrence_id,),
        )

        reconciliation = self.conn.execute(
            "SELECT status FROM reconciliations WHERE id = ?",
            (result.entity_id,),
        ).fetchone()
        self.assertEqual(reconciliation["status"], "cancelled")
        self.assertEqual(self.state(transaction_id), "unclassified")
        event = self.conn.execute(
            """
            SELECT id FROM reconciliation_events
            WHERE entity_type = 'reconciliation'
              AND entity_id = ?
              AND event_type = 'source_occurrence_deleted'
            """,
            (result.entity_id,),
        ).fetchone()
        self.assertIsNotNone(event)


if __name__ == "__main__":
    unittest.main()
