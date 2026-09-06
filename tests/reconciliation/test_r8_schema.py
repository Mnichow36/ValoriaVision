from __future__ import annotations

import json
import sqlite3
import unittest
from uuid import uuid4

from app.database import Database, SCHEMA_VERSION
from app.migrations.r8_reconciliation import apply_r8_reconciliation_foundation


class R8ReconciliationSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.db = object.__new__(Database)
        self.db.create_schema(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def create_account(self, name: str = "Compte test") -> int:
        cur = self.conn.execute(
            """
            INSERT INTO accounts(
                name, bank, account_type, identifier,
                reference_balance, reference_date, status
            )
            VALUES (?, 'Banque test', 'Courant', ?, 0, '2026-01-01', 'Actif')
            """,
            (name, str(uuid4())),
        )
        return int(cur.lastrowid)

    def create_transaction(
        self,
        account_id: int,
        *,
        tx_date: str = "2026-06-09",
        amount: float = -109.80,
        label: str = "LOYER TEST",
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO transactions(
                account_id, tx_date, label, category, amount,
                tx_type, status, source, signature
            )
            VALUES (?, ?, ?, 'Logement', ?, 'Débit', 'Validée', 'Import bancaire', ?)
            """,
            (account_id, tx_date, label, amount, str(uuid4())),
        )
        return int(cur.lastrowid)

    def create_occurrence(
        self,
        account_id: int,
        *,
        status: str = "planned",
        transaction_id: int | None = None,
        expected_date: str = "2026-06-09",
        expected_amount: float = -109.80,
        expected_label: str = "Loyer test",
        confidence: int | None = None,
        reason: str | None = None,
        match_type: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO forecast_occurrences(
                uuid, source_type, source_id, account_id,
                expected_date, expected_amount, expected_label,
                expected_category, direction, status,
                actual_transaction_id, actual_date, actual_amount,
                amount_delta, match_confidence, match_reason,
                created_at, updated_at
            )
            VALUES (?, 'recurring', ?, ?, ?, ?, ?, 'Logement', 'debit', ?,
                    ?, ?, ?, ?, ?, ?, '2026-06-01 10:00:00', '2026-06-10 10:00:00')
            """,
            (
                str(uuid4()),
                abs(hash(str(uuid4()))) % 1_000_000_000,
                account_id,
                expected_date,
                expected_amount,
                expected_label,
                status,
                transaction_id,
                expected_date if transaction_id else None,
                expected_amount if transaction_id else None,
                0.0 if transaction_id else None,
                confidence,
                reason,
            ),
        )
        occurrence_id = int(cur.lastrowid)
        if match_type is not None:
            self.db.apply_r7_2_foundation(self.conn)
            self.conn.execute(
                "UPDATE forecast_occurrences SET match_type = ? WHERE id = ?",
                (match_type, occurrence_id),
            )
        return occurrence_id

    def test_schema_version_is_15(self) -> None:
        self.assertEqual(SCHEMA_VERSION, 15)

    def test_r8_schema_creates_expected_tables_and_unclassified_state(self) -> None:
        account_id = self.create_account()
        transaction_id = self.create_transaction(account_id)

        apply_r8_reconciliation_foundation(self.conn)

        tables = {
            row["name"]
            for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        for expected in {
            "transaction_reconciliation_state",
            "reconciliation_proposals",
            "reconciliation_proposal_members",
            "reconciliations",
            "reconciliation_members",
            "reconciliation_events",
        }:
            self.assertIn(expected, tables)

        state = self.conn.execute(
            """
            SELECT status
            FROM transaction_reconciliation_state
            WHERE transaction_id = ?
            """,
            (transaction_id,),
        ).fetchone()
        self.assertIsNotNone(state)
        self.assertEqual(state["status"], "unclassified")

    def test_legacy_confirmed_match_is_migrated_without_mutating_source_data(self) -> None:
        account_id = self.create_account()
        transaction_id = self.create_transaction(account_id)
        occurrence_id = self.create_occurrence(
            account_id,
            status="confirmed",
            transaction_id=transaction_id,
            confidence=100,
            reason="Rapprochement manuel. compte identique; montant exact",
        )

        tx_before = dict(
            self.conn.execute(
                "SELECT account_id, tx_date, label, amount, tx_type FROM transactions WHERE id = ?",
                (transaction_id,),
            ).fetchone()
        )
        occ_before = dict(
            self.conn.execute(
                "SELECT status, actual_transaction_id, expected_amount FROM forecast_occurrences WHERE id = ?",
                (occurrence_id,),
            ).fetchone()
        )

        apply_r8_reconciliation_foundation(self.conn)

        reconciliation = self.conn.execute(
            """
            SELECT *
            FROM reconciliations
            WHERE legacy_occurrence_id = ?
            """,
            (occurrence_id,),
        ).fetchone()
        self.assertIsNotNone(reconciliation)
        self.assertEqual(reconciliation["status"], "confirmed")
        self.assertEqual(reconciliation["match_type"], "manual")
        self.assertEqual(reconciliation["score"], 100)

        members = self.conn.execute(
            """
            SELECT member_type, transaction_id, occurrence_id
            FROM reconciliation_members
            WHERE reconciliation_id = ?
            ORDER BY member_type
            """,
            (reconciliation["id"],),
        ).fetchall()
        self.assertEqual(len(members), 2)
        self.assertEqual(
            {row["member_type"] for row in members},
            {"transaction", "occurrence"},
        )

        state = self.conn.execute(
            """
            SELECT status
            FROM transaction_reconciliation_state
            WHERE transaction_id = ?
            """,
            (transaction_id,),
        ).fetchone()
        self.assertEqual(state["status"], "reconciled")

        tx_after = dict(
            self.conn.execute(
                "SELECT account_id, tx_date, label, amount, tx_type FROM transactions WHERE id = ?",
                (transaction_id,),
            ).fetchone()
        )
        occ_after = dict(
            self.conn.execute(
                "SELECT status, actual_transaction_id, expected_amount FROM forecast_occurrences WHERE id = ?",
                (occurrence_id,),
            ).fetchone()
        )
        self.assertEqual(tx_after, tx_before)
        self.assertEqual(occ_after, occ_before)

    def test_legacy_auto_match_is_migrated_as_automatic(self) -> None:
        account_id = self.create_account()
        transaction_id = self.create_transaction(account_id)
        occurrence_id = self.create_occurrence(
            account_id,
            status="auto_matched",
            transaction_id=transaction_id,
            confidence=95,
            reason="compte identique +30; sens identique +25; montant exact +25",
        )

        apply_r8_reconciliation_foundation(self.conn)

        reconciliation = self.conn.execute(
            "SELECT status, match_type FROM reconciliations WHERE legacy_occurrence_id = ?",
            (occurrence_id,),
        ).fetchone()
        self.assertEqual(reconciliation["status"], "automatic")
        self.assertEqual(reconciliation["match_type"], "automatic")

    def test_legacy_to_review_is_migrated_as_proposal(self) -> None:
        account_id = self.create_account()
        transaction_id = self.create_transaction(account_id)
        occurrence_id = self.create_occurrence(
            account_id,
            status="to_review",
            transaction_id=transaction_id,
            confidence=78,
            reason="date proche; montant à vérifier",
        )

        apply_r8_reconciliation_foundation(self.conn)

        proposal = self.conn.execute(
            """
            SELECT *
            FROM reconciliation_proposals
            WHERE legacy_occurrence_id = ?
            """,
            (occurrence_id,),
        ).fetchone()
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal["status"], "proposed")
        self.assertEqual(proposal["confidence_level"], "review")
        self.assertEqual(proposal["score"], 78)

        details = json.loads(proposal["score_details_json"])
        self.assertIn("legacy_match_reason", details)

        member_count = self.conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM reconciliation_proposal_members
            WHERE proposal_id = ?
            """,
            (proposal["id"],),
        ).fetchone()["c"]
        self.assertEqual(member_count, 2)

        state = self.conn.execute(
            """
            SELECT status
            FROM transaction_reconciliation_state
            WHERE transaction_id = ?
            """,
            (transaction_id,),
        ).fetchone()
        self.assertEqual(state["status"], "has_proposal")

        legacy_status = self.conn.execute(
            "SELECT status FROM forecast_occurrences WHERE id = ?",
            (occurrence_id,),
        ).fetchone()["status"]
        self.assertEqual(legacy_status, "to_review")

    def test_migration_is_idempotent(self) -> None:
        account_id = self.create_account()
        transaction_id = self.create_transaction(account_id)
        occurrence_id = self.create_occurrence(
            account_id,
            status="confirmed",
            transaction_id=transaction_id,
            confidence=100,
            reason="test idempotence",
        )

        apply_r8_reconciliation_foundation(self.conn)
        apply_r8_reconciliation_foundation(self.conn)

        reconciliation_count = self.conn.execute(
            "SELECT COUNT(*) AS c FROM reconciliations WHERE legacy_occurrence_id = ?",
            (occurrence_id,),
        ).fetchone()["c"]
        member_count = self.conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM reconciliation_members rm
            JOIN reconciliations r ON r.id = rm.reconciliation_id
            WHERE r.legacy_occurrence_id = ?
            """,
            (occurrence_id,),
        ).fetchone()["c"]
        event_count = self.conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM reconciliation_events
            WHERE dedup_key = ?
            """,
            (f"r8:legacy-reconciliation:{occurrence_id}",),
        ).fetchone()["c"]

        self.assertEqual(reconciliation_count, 1)
        self.assertEqual(member_count, 2)
        self.assertEqual(event_count, 1)

    def test_model_supports_many_to_many_membership(self) -> None:
        account_id = self.create_account()
        tx1 = self.create_transaction(account_id, amount=-100.0, label="TX 1")
        tx2 = self.create_transaction(account_id, amount=-200.0, label="TX 2")
        occ1 = self.create_occurrence(
            account_id,
            expected_amount=-120.0,
            expected_label="Prévision 1",
        )
        occ2 = self.create_occurrence(
            account_id,
            expected_amount=-180.0,
            expected_label="Prévision 2",
        )
        apply_r8_reconciliation_foundation(self.conn)

        cur = self.conn.execute(
            """
            INSERT INTO reconciliations(
                uuid, status, match_type, score, rules_snapshot_json
            )
            VALUES (?, 'confirmed', 'manual', 100, '{}')
            """,
            (str(uuid4()),),
        )
        reconciliation_id = int(cur.lastrowid)

        for tx_id, amount, label in [
            (tx1, -100.0, "TX 1"),
            (tx2, -200.0, "TX 2"),
        ]:
            self.conn.execute(
                """
                INSERT INTO reconciliation_members(
                    reconciliation_id, member_type, transaction_id,
                    role, amount_snapshot, label_snapshot
                )
                VALUES (?, 'transaction', ?, 'actual', ?, ?)
                """,
                (reconciliation_id, tx_id, amount, label),
            )

        for occ_id, amount, label in [
            (occ1, -120.0, "Prévision 1"),
            (occ2, -180.0, "Prévision 2"),
        ]:
            self.conn.execute(
                """
                INSERT INTO reconciliation_members(
                    reconciliation_id, member_type, occurrence_id,
                    role, amount_snapshot, label_snapshot
                )
                VALUES (?, 'occurrence', ?, 'forecast', ?, ?)
                """,
                (reconciliation_id, occ_id, amount, label),
            )

        rows = self.conn.execute(
            """
            SELECT member_type, COUNT(*) AS c, ROUND(SUM(amount_snapshot), 2) AS total
            FROM reconciliation_members
            WHERE reconciliation_id = ?
            GROUP BY member_type
            """,
            (reconciliation_id,),
        ).fetchall()
        summary = {row["member_type"]: (row["c"], row["total"]) for row in rows}

        self.assertEqual(summary["transaction"], (2, -300.0))
        self.assertEqual(summary["occurrence"], (2, -300.0))

    def test_member_constraint_rejects_transaction_and_occurrence_on_same_row(self) -> None:
        account_id = self.create_account()
        transaction_id = self.create_transaction(account_id)
        occurrence_id = self.create_occurrence(account_id)
        apply_r8_reconciliation_foundation(self.conn)

        cur = self.conn.execute(
            """
            INSERT INTO reconciliations(uuid, status, match_type)
            VALUES (?, 'confirmed', 'manual')
            """,
            (str(uuid4()),),
        )

        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                """
                INSERT INTO reconciliation_members(
                    reconciliation_id, member_type, transaction_id, occurrence_id
                )
                VALUES (?, 'transaction', ?, ?)
                """,
                (int(cur.lastrowid), transaction_id, occurrence_id),
            )

    def test_database_apply_migrations_wires_r8_foundation(self) -> None:
        account_id = self.create_account()
        transaction_id = self.create_transaction(account_id)

        self.db.apply_migrations(self.conn)

        row = self.conn.execute(
            """
            SELECT status
            FROM transaction_reconciliation_state
            WHERE transaction_id = ?
            """,
            (transaction_id,),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "unclassified")


if __name__ == "__main__":
    unittest.main()
