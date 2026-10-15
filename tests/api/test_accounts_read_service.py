from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.services.accounts_read_service import AccountsReadService


class StubDatabase:
    def __init__(self):
        self.accounts = [
            {
                "id": 7,
                "name": "Compte courant",
                "bank": "Banque Test",
                "account_type": "Compte courant",
                "identifier": "FR76 4255",
                "currency": "EUR",
                "status": "Actif",
                "effective_initial_balance": 1000,
                "effective_initial_date": "2026-10-01",
                "post_reference_movements": 125.5,
                "calculated_balance": 1125.5,
                "calculated_date": "2026-10-13",
            }
        ]

    def list_accounts(self):
        return self.accounts

    def list_transactions(self, account_id=None):
        self.requested_account_id = account_id
        return [
            {
                "id": 99,
                "tx_date": "2026-10-13",
                "label": "Virement reçu",
                "category": "Revenus",
                "amount": 125.5,
                "status": "Validée",
            }
        ]

    def add_account(self, data):
        self.created = data
        self.accounts.append({
            "id": max(row["id"] for row in self.accounts) + 1,
            "effective_initial_balance": data["initial_balance"],
            "effective_initial_date": data["initial_date"],
            "post_reference_movements": 0,
            "calculated_balance": data["initial_balance"],
            "calculated_date": data["initial_date"],
            **data,
        })

    def update_account(self, account_id, data):
        self.updated = (account_id, data)
        row = next(row for row in self.accounts if row["id"] == account_id)
        row.update(data)

    def update_account_reference(self, account_id, balance, reference_date):
        self.updated_reference = (account_id, balance, reference_date)
        row = next(row for row in self.accounts if row["id"] == account_id)
        row["effective_initial_balance"] = balance
        row["effective_initial_date"] = reference_date


class AccountsReadServiceTest(unittest.TestCase):
    def test_builds_accounts_and_recent_transactions_contract(self):
        database = StubDatabase()
        service = AccountsReadService(
            database,
            now_provider=lambda: datetime(2026, 10, 13, 20, 0, tzinfo=timezone.utc),
        )

        snapshot = service.snapshot()

        self.assertEqual(snapshot["summary"]["activeCount"], 1)
        self.assertEqual(snapshot["summary"]["netBalance"], 1125.5)
        self.assertEqual(snapshot["accounts"][0]["initialBalance"], 1000.0)
        self.assertEqual(snapshot["accounts"][0]["transactions"][0]["category"], "Revenus")
        self.assertEqual(database.requested_account_id, 7)

    def test_creates_account_through_existing_database_method(self):
        database = StubDatabase()
        service = AccountsReadService(
            database,
            now_provider=lambda: datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc),
        )

        result = service.create({
            "name": "Épargne projet",
            "bank": "Banque Test",
            "account_type": "Compte épargne",
            "identifier": "FR76 9988",
            "initial_balance": 2450.25,
            "initial_date": "2026-10-15",
            "currency": "EUR",
            "status": "Actif",
        })

        self.assertTrue(result["success"])
        self.assertEqual(result["accountId"], 8)
        self.assertEqual(database.created["reference_balance"], 2450.25)
        self.assertEqual(database.created["reference_date"], "2026-10-15")

    def test_rejects_duplicate_identifier_even_with_different_spacing(self):
        service = AccountsReadService(StubDatabase())

        with self.assertRaisesRegex(ValueError, "déjà rattaché"):
            service.create({
                "name": "Doublon",
                "bank": "Autre banque",
                "account_type": "Compte courant",
                "identifier": "fr764255",
                "initial_balance": 0,
                "initial_date": "2026-10-15",
                "currency": "EUR",
                "status": "Actif",
            })

    def test_updates_metadata_without_moving_reference(self):
        database = StubDatabase()
        service = AccountsReadService(database)

        result = service.update(7, {
            "name": "Compte principal",
            "bank": "Banque Test",
            "account_type": "Compte courant",
            "identifier": "FR76 4255",
            "initial_balance": 1000,
            "initial_date": "2026-10-01",
            "currency": "EUR",
            "status": "Actif",
        })

        self.assertEqual(result["accountId"], 7)
        self.assertEqual(database.updated[1]["name"], "Compte principal")
        self.assertFalse(hasattr(database, "updated_reference"))

    def test_updates_balance_reference_separately(self):
        database = StubDatabase()
        service = AccountsReadService(database)

        result = service.update_reference(7, "1520.456", "2026-10-10")

        self.assertEqual(result["accountId"], 7)
        self.assertEqual(database.updated_reference, (7, 1520.46, "2026-10-10"))


if __name__ == "__main__":
    unittest.main()
