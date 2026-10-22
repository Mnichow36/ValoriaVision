from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from app.api.main import TransactionCreatePayload, create_app
from app.database import Database
from app.services.dashboard_read_service import DashboardReadService
from app.services.transactions_read_service import TransactionsReadService


def build_database(root: str) -> Database:
    database = Database(Path(root) / "valoria.db")
    with database.connect() as conn:
        database.create_schema(conn)
        database.apply_migrations(conn)
        database.seed_if_empty(conn)
        database.seed_recurring_items(conn)
    return database


def first_account(database: Database) -> int:
    with database.connect() as conn:
        return int(conn.execute("SELECT id FROM accounts WHERE status = 'Actif' ORDER BY id LIMIT 1").fetchone()["id"])


class TransactionCreationTest(unittest.TestCase):
    def payload(self, database: Database, **overrides):
        data = {
            "account_id": first_account(database),
            "tx_date": date.today().isoformat(),
            "label": "ACHAT SAISI A LA MAIN",
            "beneficiary": None,
            "category": None,
            "direction": "Débit",
            "amount": 42.5,
        }
        data.update(overrides)
        return data

    def test_manual_debit_is_created_with_a_negative_amount(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            service = TransactionsReadService(database)
            before = service.snapshot()["summary"]["transactionCount"]

            result = service.create(self.payload(database))

            self.assertTrue(result["success"])
            self.assertGreater(result["transactionId"], 0)
            snapshot = service.snapshot()
            self.assertEqual(snapshot["summary"]["transactionCount"], before + 1)
            row = next(item for item in snapshot["transactions"] if item["id"] == result["transactionId"])
            self.assertEqual(row["amount"], -42.5)
            self.assertEqual(row["source"], "Manuel")
            self.assertEqual(row["category"], "À catégoriser")

    def test_manual_credit_with_category_is_validated(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            service = TransactionsReadService(database)
            category = next(c["name"] for c in service.snapshot()["categories"] if c["name"] and c["name"] != "À catégoriser")

            result = service.create(self.payload(database, direction="Crédit", amount=100, category=category, label="REMBOURSEMENT"))

            row = next(i for i in service.snapshot()["transactions"] if i["id"] == result["transactionId"])
            self.assertEqual(row["amount"], 100.0)
            self.assertEqual(row["category"], category)
            self.assertEqual(row["status"], "Validée")

    def test_new_transaction_is_visible_on_other_screens_immediately(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            before = round(database.account_summary()["liquidites"], 2)
            TransactionsReadService(database).create(self.payload(database, direction="Crédit", amount=1000, label="VIREMENT TEST"))
            self.assertEqual(round(database.account_summary()["liquidites"], 2), round(before + 1000, 2))
            dashboard = DashboardReadService(database).snapshot()
            self.assertTrue(dashboard["kpis"])

    def test_duplicates_and_invalid_input_are_refused_with_a_clear_message(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            service = TransactionsReadService(database)
            service.create(self.payload(database))
            with self.assertRaisesRegex(ValueError, "identique"):
                service.create(self.payload(database))
            with self.assertRaisesRegex(ValueError, "libellé"):
                service.create(self.payload(database, label="  "))
            with self.assertRaisesRegex(ValueError, "supérieur à zéro"):
                service.create(self.payload(database, amount=0))
            with self.assertRaisesRegex(ValueError, "Débit ou Crédit"):
                service.create(self.payload(database, direction="Autre"))
            with self.assertRaisesRegex(ValueError, "date"):
                service.create(self.payload(database, tx_date="31/12/2026"))
            with self.assertRaisesRegex(ValueError, "compte"):
                service.create(self.payload(database, account_id=999999))
            with self.assertRaisesRegex(ValueError, "catégorie"):
                service.create(self.payload(database, category="Catégorie inconnue"))

    def test_create_route_exists_and_requires_a_session(self):
        from fastapi import HTTPException

        with TemporaryDirectory() as root:
            database = build_database(root)
            app = create_app(database)
            endpoint = next(
                route.endpoint for route in app.routes
                if route.path == "/api/v1/transactions" and "POST" in route.methods
            )
            with self.assertRaises(HTTPException) as raised:
                endpoint(TransactionCreatePayload(**self.payload(database)), None, None)
            self.assertEqual(raised.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
