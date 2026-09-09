from __future__ import annotations

import json
import sqlite3
import unittest
from uuid import uuid4

from app.database import Database
from app.migrations.r8_reconciliation import apply_r8_reconciliation_foundation
from app.services.reconciliation import (
    ReconciliationRules,
    qualify_and_persist_transaction,
)


class R8PersistenceTests(unittest.TestCase):
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

    def transaction(self, *, source: str = "Import bancaire", label: str = "LOYER") -> int:
        return int(
            self.conn.execute(
                """
                INSERT INTO transactions(
                    account_id, tx_date, label, category, amount,
                    tx_type, status, source, signature
                )
                VALUES (?, '2026-06-09', ?, 'Logement', -900,
                        'Débit', 'Validée', ?, ?)
                """,
                (self.account_id, label, source, str(uuid4())),
            ).lastrowid
        )

    def occurrence(
        self,
        *,
        label: str = "Loyer",
        expected_date: str = "2026-06-09",
        amount: float = -900,
    ) -> int:
        return int(
            self.conn.execute(
                """
                INSERT INTO forecast_occurrences(
                    uuid, source_type, account_id, expected_date,
                    expected_amount, expected_label, expected_category,
                    direction, status
                )
                VALUES (?, 'recurring', ?, ?, ?, ?, 'Logement', 'debit', 'planned')
                """,
                (
                    str(uuid4()),
                    self.account_id,
                    expected_date,
                    amount,
                    label,
                ),
            ).lastrowid
        )

    def state(self, transaction_id: int) -> sqlite3.Row:
        return self.conn.execute(
            """
            SELECT status, reason
            FROM transaction_reconciliation_state
            WHERE transaction_id = ?
            """,
            (transaction_id,),
        ).fetchone()

    def test_without_forecast_is_persisted_and_audited(self) -> None:
        transaction_id = self.transaction()
        persisted = qualify_and_persist_transaction(self.conn, transaction_id)
        self.assertEqual(persisted.status, "without_forecast")
        self.assertEqual(self.state(transaction_id)["status"], "without_forecast")
        event_count = self.conn.execute(
            """
            SELECT COUNT(*) FROM reconciliation_events
            WHERE entity_type = 'transaction'
              AND entity_id = ?
              AND event_type = 'qualification_calculated'
            """,
            (transaction_id,),
        ).fetchone()[0]
        self.assertEqual(event_count, 1)

    def test_repeated_without_forecast_reevaluation_is_fully_audited(self) -> None:
        transaction_id = self.transaction()
        qualify_and_persist_transaction(self.conn, transaction_id)
        qualify_and_persist_transaction(self.conn, transaction_id)
        event_count = self.conn.execute(
            """
            SELECT COUNT(*) FROM reconciliation_events
            WHERE entity_type = 'transaction'
              AND entity_id = ?
              AND event_type = 'qualification_calculated'
            """,
            (transaction_id,),
        ).fetchone()[0]
        self.assertEqual(event_count, 2)

    def test_automatic_result_creates_reconciliation_members_and_snapshots(self) -> None:
        transaction_id = self.transaction()
        occurrence_id = self.occurrence()
        persisted = qualify_and_persist_transaction(self.conn, transaction_id)
        self.assertEqual(persisted.status, "reconciled")
        self.assertEqual(self.state(transaction_id)["status"], "reconciled")
        reconciliation = self.conn.execute(
            "SELECT * FROM reconciliations WHERE id = ?",
            (persisted.entity_id,),
        ).fetchone()
        self.assertEqual(reconciliation["status"], "automatic")
        self.assertEqual(reconciliation["score"], 100)
        self.assertIn("amount_tolerance_absolute", reconciliation["rules_snapshot_json"])
        details = json.loads(reconciliation["score_details_json"])
        self.assertEqual(details["score"], 100)
        members = self.conn.execute(
            """
            SELECT member_type, transaction_id, occurrence_id
            FROM reconciliation_members
            WHERE reconciliation_id = ?
            ORDER BY member_type
            """,
            (persisted.entity_id,),
        ).fetchall()
        self.assertEqual(len(members), 2)
        self.assertEqual(
            {row["transaction_id"] for row in members if row["transaction_id"]},
            {transaction_id},
        )
        self.assertEqual(
            {row["occurrence_id"] for row in members if row["occurrence_id"]},
            {occurrence_id},
        )
        event_count = self.conn.execute(
            """
            SELECT COUNT(*) FROM reconciliation_events
            WHERE entity_type = 'reconciliation'
              AND entity_id = ?
              AND event_type = 'reconciliation_created_auto'
            """,
            (persisted.entity_id,),
        ).fetchone()[0]
        self.assertEqual(event_count, 1)

    def test_ambiguous_result_creates_one_proposal_with_all_candidates(self) -> None:
        transaction_id = self.transaction()
        first = self.occurrence(label="Loyer")
        second = self.occurrence(label="Loyer")
        persisted = qualify_and_persist_transaction(self.conn, transaction_id)
        self.assertEqual(persisted.status, "has_proposal")
        self.assertEqual(self.state(transaction_id)["status"], "has_proposal")
        proposal = self.conn.execute(
            "SELECT * FROM reconciliation_proposals WHERE id = ?",
            (persisted.entity_id,),
        ).fetchone()
        self.assertEqual(proposal["status"], "proposed")
        self.assertLess(proposal["ambiguity_delta"], 10)
        occurrence_members = self.conn.execute(
            """
            SELECT occurrence_id
            FROM reconciliation_proposal_members
            WHERE proposal_id = ? AND member_type = 'occurrence'
            """,
            (persisted.entity_id,),
        ).fetchall()
        self.assertEqual({row[0] for row in occurrence_members}, {first, second})

    def test_reevaluation_expires_previous_proposal_without_source_mutation(self) -> None:
        transaction_id = self.transaction()
        self.occurrence(label="Loyer")
        self.occurrence(label="Loyer")
        tx_before = tuple(
            self.conn.execute(
                "SELECT account_id, tx_date, amount, label FROM transactions WHERE id = ?",
                (transaction_id,),
            ).fetchone()
        )
        first = qualify_and_persist_transaction(self.conn, transaction_id)
        self.conn.execute(
            "UPDATE forecast_occurrences SET status = 'cancelled'"
        )
        second = qualify_and_persist_transaction(self.conn, transaction_id)
        self.assertEqual(first.status, "has_proposal")
        self.assertEqual(second.status, "without_forecast")
        old_status = self.conn.execute(
            "SELECT status FROM reconciliation_proposals WHERE id = ?",
            (first.entity_id,),
        ).fetchone()[0]
        self.assertEqual(old_status, "expired")
        expiration_event = self.conn.execute(
            """
            SELECT payload_json FROM reconciliation_events
            WHERE entity_type = 'proposal'
              AND entity_id = ?
              AND event_type = 'proposal_expired'
            """,
            (first.entity_id,),
        ).fetchone()
        self.assertIsNotNone(expiration_event)
        self.assertEqual(
            json.loads(expiration_event["payload_json"])["transaction_id"],
            transaction_id,
        )
        tx_after = tuple(
            self.conn.execute(
                "SELECT account_id, tx_date, amount, label FROM transactions WHERE id = ?",
                (transaction_id,),
            ).fetchone()
        )
        self.assertEqual(tx_after, tx_before)

    def test_repeating_automatic_qualification_does_not_duplicate_reconciliation(self) -> None:
        transaction_id = self.transaction()
        self.occurrence()
        first = qualify_and_persist_transaction(self.conn, transaction_id)
        second = qualify_and_persist_transaction(self.conn, transaction_id)
        self.assertEqual(second.entity_id, first.entity_id)
        count = self.conn.execute(
            """
            SELECT COUNT(*) FROM reconciliations
            WHERE status IN ('automatic', 'confirmed')
            """
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_manual_and_import_sources_share_the_same_entry_point(self) -> None:
        imported = self.transaction(source="Import bancaire", label="LOYER IMPORT")
        manual = self.transaction(source="Manuel", label="LOYER MANUEL")
        imported_result = qualify_and_persist_transaction(self.conn, imported)
        manual_result = qualify_and_persist_transaction(self.conn, manual)
        self.assertEqual(imported_result.status, "without_forecast")
        self.assertEqual(manual_result.status, "without_forecast")

    def test_failure_rolls_back_partial_persistence(self) -> None:
        transaction_id = self.transaction()
        self.occurrence()
        initial_state = self.state(transaction_id)["status"]
        self.conn.execute(
            """
            CREATE TRIGGER fail_occurrence_member_for_rollback_test
            BEFORE INSERT ON reconciliation_members
            WHEN NEW.member_type = 'occurrence'
            BEGIN
                SELECT RAISE(ABORT, 'forced rollback test');
            END
            """
        )

        with self.assertRaisesRegex(sqlite3.IntegrityError, "forced rollback test"):
            qualify_and_persist_transaction(self.conn, transaction_id)

        self.assertEqual(self.state(transaction_id)["status"], initial_state)
        reconciliation_count = self.conn.execute(
            """
            SELECT COUNT(*)
            FROM reconciliations r
            JOIN reconciliation_members rm ON rm.reconciliation_id = r.id
            WHERE rm.transaction_id = ?
            """,
            (transaction_id,),
        ).fetchone()[0]
        self.assertEqual(reconciliation_count, 0)
        event_count = self.conn.execute(
            """
            SELECT COUNT(*) FROM reconciliation_events
            WHERE entity_type = 'reconciliation'
            """
        ).fetchone()[0]
        self.assertEqual(event_count, 0)


if __name__ == "__main__":
    unittest.main()
