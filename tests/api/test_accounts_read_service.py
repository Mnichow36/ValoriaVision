from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.services.accounts_read_service import AccountsReadService


class StubDatabase:
    def list_accounts(self):
        return [
            {
                "id": 7,
                "name": "Compte courant",
                "bank": "Banque Test",
                "account_type": "Compte courant",
                "identifier": "**** 4255",
                "currency": "EUR",
                "status": "Actif",
                "effective_initial_balance": 1000,
                "effective_initial_date": "2026-10-01",
                "post_reference_movements": 125.5,
                "calculated_balance": 1125.5,
                "calculated_date": "2026-10-13",
            }
        ]

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


if __name__ == "__main__":
    unittest.main()
