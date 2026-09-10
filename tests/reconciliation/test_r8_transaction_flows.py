from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from app.database import Database
from app.migrations.r8_reconciliation import apply_r8_reconciliation_foundation


class R8TransactionFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "r8-flow.db")
        with self.db.connect() as conn:
            self.db.create_schema(conn)
            apply_r8_reconciliation_foundation(conn)
            conn.execute(
                """
                INSERT INTO categories(name, kind, direction, is_system)
                VALUES ('Logement', 'Dépense', 'Dépense', 0)
                """
            )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def account(self) -> int:
        with self.db.connect() as conn:
            return int(
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

    def occurrence(self, account_id: int, *, label: str = "Loyer") -> int:
        with self.db.connect() as conn:
            return int(
                conn.execute(
                    """
                    INSERT INTO forecast_occurrences(
                        uuid, source_type, account_id, expected_date,
                        expected_amount, expected_label, expected_category,
                        direction, status
                    )
                    VALUES (?, 'manual', ?, '2026-06-09', -900, ?,
                            'Logement', 'debit', 'planned')
                    """,
                    (str(uuid4()), account_id, label),
                ).lastrowid
            )

    def create_transaction(self, account_id: int, source: str, label: str) -> int:
        amount = 900 if source == "Manuel" else -900
        created = self.db.insert_transaction(
            account_id,
            "2026-06-09",
            label,
            "Logement",
            amount,
            source,
        )
        self.assertTrue(created)
        with self.db.connect() as conn:
            return int(
                conn.execute(
                    """
                    SELECT id FROM transactions
                    WHERE account_id = ? AND source = ? AND label = ?
                    """,
                    (account_id, source, label),
                ).fetchone()["id"]
            )

    def state(self, transaction_id: int) -> str:
        with self.db.connect() as conn:
            return str(
                conn.execute(
                    """
                    SELECT status FROM transaction_reconciliation_state
                    WHERE transaction_id = ?
                    """,
                    (transaction_id,),
                ).fetchone()["status"]
            )

    def test_manual_and_import_flows_cover_all_r8_qualifications(self) -> None:
        for source in ("Import bancaire", "Manuel"):
            for scenario, expected_status, occurrence_count in (
                ("without_forecast", "without_forecast", 0),
                ("automatic", "reconciled", 1),
                ("ambiguous", "has_proposal", 2),
            ):
                with self.subTest(source=source, scenario=scenario):
                    account_id = self.account()
                    for index in range(occurrence_count):
                        self.occurrence(account_id, label=f"Loyer {index}")
                    transaction_id = self.create_transaction(
                        account_id,
                        source,
                        f"LOYER {source} {scenario}",
                    )
                    self.assertEqual(self.state(transaction_id), expected_status)

    def test_duplicate_insert_does_not_repeat_qualification(self) -> None:
        account_id = self.account()
        first = self.db.insert_transaction(
            account_id, "2026-06-09", "LOYER UNIQUE",
            "Logement", -900, "Import bancaire",
        )
        second = self.db.insert_transaction(
            account_id, "2026-06-09", "LOYER UNIQUE",
            "Logement", -900, "Import bancaire",
        )
        self.assertTrue(first)
        self.assertFalse(second)
        with self.db.connect() as conn:
            transaction_id = int(
                conn.execute(
                    "SELECT id FROM transactions WHERE account_id = ?",
                    (account_id,),
                ).fetchone()["id"]
            )
            event_count = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM reconciliation_events
                    WHERE entity_type = 'transaction'
                      AND entity_id = ?
                      AND event_type = 'qualification_calculated'
                    """,
                    (transaction_id,),
                ).fetchone()[0]
            )
        self.assertEqual(event_count, 1)


if __name__ == "__main__":
    unittest.main()
