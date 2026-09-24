"""Explicit manual overage preserves the ordinary capped allocation."""
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from app.database import Database
from app.migrations.r8_reconciliation import apply_r8_reconciliation_foundation
from app.services.forecast_reconciliation_service import ForecastReconciliationService


class ManualOverageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "overage.db")
        with self.db.connect() as conn:
            self.db.create_schema(conn)
            apply_r8_reconciliation_foundation(conn)
            account = conn.execute(
                """INSERT INTO accounts(name, bank, account_type, identifier,
                    reference_balance, reference_date, status)
                    VALUES ('Compte test', 'Banque test', 'Courant', ?, 0,
                    '2026-01-01', 'Actif')""", (str(uuid4()),)
            )
            self.account_id = int(account.lastrowid)
            occurrence = conn.execute(
                """INSERT INTO forecast_occurrences(uuid, source_type, account_id,
                    expected_date, expected_amount, expected_label, expected_category,
                    direction, status)
                    VALUES (?, 'manual', ?, '2026-10-10', -150,
                    'TEST DÉPASSEMENT', 'Alimentation', 'debit', 'planned')""",
                (str(uuid4()), self.account_id),
            )
            self.occurrence_id = int(occurrence.lastrowid)
            self.first_id = self.add_transaction(conn, -100)
            self.second_id = self.add_transaction(conn, -70)
        self.service = ForecastReconciliationService(self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def add_transaction(self, conn, amount):
        return int(conn.execute(
            """INSERT INTO transactions(account_id, tx_date, label, category,
                amount, tx_type, status, source, signature)
                VALUES (?, '2026-10-10', 'TEST DÉPASSEMENT', 'Alimentation',
                ?, 'Débit', 'Validée', 'Manuel', ?)""",
            (self.account_id, amount, str(uuid4())),
        ).lastrowid)

    def state(self):
        with self.db.connect() as conn:
            return conn.execute(
                """SELECT status, matched_amount, remaining_amount, overage_amount
                   FROM forecast_occurrences WHERE id = ?""",
                (self.occurrence_id,),
            ).fetchone()

    def test_default_caps_and_explicit_choice_keeps_twenty_euros_overage(self):
        ok, message = self.service.confirm_manual_match(self.occurrence_id, self.first_id)
        self.assertEqual(ok, 1, message)
        self.assertEqual(self.state()["status"], "partially_matched")
        options = self.service.manual_allocation_options(self.occurrence_id, self.second_id)
        self.assertEqual(options["transaction_remaining"], 70)
        self.assertEqual(options["occurrence_remaining"], 50)
        self.assertEqual(options["overage"], 20)

        ok, message = self.service.confirm_manual_match(self.occurrence_id, self.second_id)
        self.assertEqual(ok, 1, message)
        self.assertEqual(self.state()["matched_amount"], 150)
        self.assertEqual(self.state()["overage_amount"], 0)
        self.assertEqual(
            self.service.manual_allocation_options(self.occurrence_id, self.second_id)["transaction_remaining"], 20
        )

        self.assertTrue(self.service.cancel_reconciliation_link(self.occurrence_id, self.second_id)[0])
        ok, message = self.service.confirm_manual_match(
            self.occurrence_id, self.second_id, include_overage=True
        )
        self.assertEqual(ok, 1, message)
        state = self.state()
        self.assertEqual(state["status"], "confirmed")
        self.assertEqual(state["matched_amount"], 170)
        self.assertEqual(state["remaining_amount"], 0)
        self.assertEqual(state["overage_amount"], 20)
        self.assertEqual(
            self.service.manual_allocation_options(self.occurrence_id, self.second_id)["transaction_remaining"], 0
        )


if __name__ == "__main__":
    unittest.main()
