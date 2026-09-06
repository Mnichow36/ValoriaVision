from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.database import Database
from tools.validate_r8_migration import validate_database


class R8MigrationValidatorTests(unittest.TestCase):
    def test_validator_uses_copy_preserves_source_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "r7_2.db"
            db = object.__new__(Database)
            with sqlite3.connect(source) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON")
                db.create_schema(conn)
                account_id = conn.execute(
                    """
                    INSERT INTO accounts(
                        name, bank, account_type, reference_balance,
                        reference_date, initial_balance, status
                    ) VALUES ('Compte anonymisé', 'Banque test', 'Courant',
                              1000, '2026-01-01', 1000, 'Actif')
                    """
                ).lastrowid
                transaction_id = conn.execute(
                    """
                    INSERT INTO transactions(
                        account_id, tx_date, label, amount, tx_type, source
                    ) VALUES (?, '2026-06-09', 'LOYER TEST', -900, 'Débit', 'Import')
                    """,
                    (account_id,),
                ).lastrowid
                conn.execute(
                    """
                    INSERT INTO forecast_occurrences(
                        uuid, source_type, account_id, expected_date,
                        expected_amount, expected_label, direction, status,
                        actual_transaction_id, match_confidence
                    ) VALUES (
                        'occ-test', 'recurring', ?, '2026-06-09',
                        -900, 'Loyer test', 'debit', 'confirmed', ?, 100
                    )
                    """,
                    (account_id, transaction_id),
                )
                conn.commit()

            source_before = source.read_bytes()
            report = validate_database(source)

            self.assertTrue(report["success"])
            self.assertEqual(source.read_bytes(), source_before)
            self.assertEqual(report["integrity_before"], "ok")
            self.assertEqual(report["integrity_after"], "ok")
            self.assertEqual(report["changed_legacy_tables"], [])
            self.assertTrue(report["idempotent"])
            self.assertTrue(report["all_r8_tables_created"])
            self.assertEqual(report["r8_counts"]["reconciliations"], 1)

    def test_validator_rejects_encrypted_or_non_sqlite_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "valoria_vision.vvdb"
            source.write_bytes(b"not a sqlite database")
            with self.assertRaisesRegex(ValueError, "n'est pas une base SQLite"):
                validate_database(source)


if __name__ == "__main__":
    unittest.main()

