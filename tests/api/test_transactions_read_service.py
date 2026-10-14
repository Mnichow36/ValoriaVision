from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.services.transactions_read_service import TransactionsReadService


class StubDatabase:
    def list_transactions(self):
        return [
            {
                "id": 11,
                "account_id": 7,
                "account_name": "Compte courant",
                "bank": "Banque Test",
                "tx_date": "2026-10-13",
                "label": "Virement reçu",
                "category": "Revenus",
                "amount": 125.5,
                "tx_type": "Crédit",
                "status": "Validée",
                "source": "Import bancaire",
                "import_batch_id": 3,
            },
            {
                "id": 12,
                "account_id": 7,
                "account_name": "Compte courant",
                "bank": "Banque Test",
                "tx_date": "2026-10-12",
                "label": "Achat à vérifier",
                "category": None,
                "amount": -20,
                "tx_type": "Débit",
                "status": "À catégoriser",
                "source": "Import bancaire",
                "import_batch_id": 3,
            },
        ]

    def list_accounts(self):
        return [{"id": 7, "name": "Compte courant", "bank": "Banque Test", "status": "Actif"}]

    def list_categories(self):
        return [{"name": "Revenus", "kind": "Revenu", "color": "#16a34a"}]

    def list_recent_import_batches(self, limit):
        self.import_limit = limit
        return [{
            "id": 3,
            "file_name": "releve.csv",
            "account_name": "Compte courant",
            "imported_count": 2,
            "duplicate_count": 1,
            "error_count": 0,
            "linked_transactions": 2,
            "status": "Importé",
            "created_at": "2026-10-13 20:00:00",
        }]


class TransactionsReadServiceTest(unittest.TestCase):
    def test_builds_transaction_journal_and_quality_contract(self):
        database = StubDatabase()
        service = TransactionsReadService(
            database,
            now_provider=lambda: datetime(2026, 10, 13, 20, 0, tzinfo=timezone.utc),
        )

        snapshot = service.snapshot()

        self.assertEqual(snapshot["summary"]["transactionCount"], 2)
        self.assertEqual(snapshot["summary"]["categorizedPercent"], 50)
        self.assertEqual(snapshot["summary"]["reviewCount"], 1)
        self.assertEqual(snapshot["transactions"][0]["accountName"], "Compte courant")
        self.assertEqual(snapshot["transactions"][1]["category"], "À catégoriser")
        self.assertEqual(snapshot["recentImport"]["recognizedCount"], 3)
        self.assertEqual(database.import_limit, 1)


if __name__ == "__main__":
    unittest.main()
