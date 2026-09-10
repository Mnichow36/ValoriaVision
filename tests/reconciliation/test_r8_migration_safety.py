from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from app.database import Database
from tools.validate_r8_migration import R8_TABLES, validate_database


class R8MigrationSafetyTests(unittest.TestCase):
    def build_r7_2_fixture(self, path: Path, *, populated: bool = True) -> None:
        db = object.__new__(Database)
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            db.create_schema(conn)

            # create_schema builds the current application schema. Removing the
            # R8-only objects gives us a synthetic, non-personal R7.2 source.
            triggers = [
                row[0]
                for row in conn.execute(
                    """
                    SELECT name FROM sqlite_master
                    WHERE type = 'trigger' AND name LIKE 'trg_r8_%'
                    """
                ).fetchall()
            ]
            for trigger in triggers:
                conn.execute(f'DROP TRIGGER "{trigger}"')
            for table in (
                "reconciliation_proposal_members",
                "reconciliation_members",
                "transaction_reconciliation_state",
                "reconciliation_events",
                "reconciliation_proposals",
                "reconciliations",
            ):
                conn.execute(f'DROP TABLE IF EXISTS "{table}"')

            if not populated:
                conn.commit()
                return

            account_id = int(
                conn.execute(
                    """
                    INSERT INTO accounts(
                        name, bank, account_type, identifier,
                        reference_balance, reference_date, status
                    )
                    VALUES ('Compte synthétique', 'Banque test', 'Courant', ?,
                            1000, '2026-01-01', 'Actif')
                    """,
                    (str(uuid4()),),
                ).lastrowid
            )

            linked_statuses = ("auto_matched", "confirmed", "to_review")
            for index, status in enumerate(linked_statuses, start=1):
                transaction_id = int(
                    conn.execute(
                        """
                        INSERT INTO transactions(
                            account_id, tx_date, label, category, amount,
                            tx_type, status, source, signature
                        )
                        VALUES (?, ?, ?, 'Test', ?, 'Débit', 'Validée',
                                'Fixture synthétique', ?)
                        """,
                        (
                            account_id,
                            f"2026-06-{index:02d}",
                            f"TRANSACTION {status}",
                            -100.0 * index,
                            str(uuid4()),
                        ),
                    ).lastrowid
                )
                conn.execute(
                    """
                    INSERT INTO forecast_occurrences(
                        uuid, source_type, source_id, account_id,
                        expected_date, expected_amount, expected_label,
                        expected_category, direction, status,
                        actual_transaction_id, match_confidence
                    )
                    VALUES (?, 'recurring', ?, ?, ?, ?, ?, 'Test', 'debit',
                            ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        index,
                        account_id,
                        f"2026-06-{index:02d}",
                        -100.0 * index,
                        f"PRÉVISION {status}",
                        status,
                        transaction_id,
                        95 if status == "auto_matched" else 100 if status == "confirmed" else 75,
                    ),
                )

            for index, status in enumerate(
                ("planned", "overdue", "ignored", "cancelled"),
                start=10,
            ):
                conn.execute(
                    """
                    INSERT INTO forecast_occurrences(
                        uuid, source_type, source_id, account_id,
                        expected_date, expected_amount, expected_label,
                        expected_category, direction, status
                    )
                    VALUES (?, 'recurring', ?, ?, ?, -50, ?, 'Test', 'debit', ?)
                    """,
                    (
                        str(uuid4()),
                        index,
                        account_id,
                        f"2026-07-{index:02d}",
                        f"PRÉVISION {status}",
                        status,
                    ),
                )
            conn.commit()

    def test_representative_r7_2_backup_migration_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "synthetic_r7_2.db"
            self.build_r7_2_fixture(source)
            source_before = source.read_bytes()

            report = validate_database(source)

            self.assertTrue(report["success"], report)
            self.assertEqual(source.read_bytes(), source_before)
            self.assertTrue(report["backup_created_before_migration"])
            self.assertEqual(report["backup_integrity"], "ok")
            self.assertTrue(report["backup_sha256_verified"])
            self.assertTrue(report["rollback_tested"])
            self.assertEqual(report["rollback_integrity"], "ok")
            self.assertTrue(report["rollback_matches_source"])
            self.assertTrue(report["counts_reconciled"])
            self.assertTrue(report["no_orphan_members"])
            self.assertEqual(report["changed_legacy_tables"], [])
            self.assertTrue(report["idempotent"])
            self.assertEqual(report["source_counts"]["transactions"], 3)
            self.assertEqual(report["source_counts"]["occurrences"], 7)
            self.assertEqual(report["migrated_counts"]["reconciliations"], 2)
            self.assertEqual(report["migrated_counts"]["proposals"], 1)
            self.assertNotIn(source.name, report["source_identifier"])

    def test_empty_r7_2_database_is_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "empty_r7_2.db"
            self.build_r7_2_fixture(source, populated=False)

            report = validate_database(source)

            self.assertTrue(report["success"], report)
            self.assertEqual(report["source_counts"]["transactions"], 0)
            self.assertEqual(report["source_counts"]["occurrences"], 0)
            self.assertTrue(R8_TABLES.issubset(set(report["r8_counts"])))


if __name__ == "__main__":
    unittest.main()
