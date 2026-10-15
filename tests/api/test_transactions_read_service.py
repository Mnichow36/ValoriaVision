from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.services.transactions_read_service import TransactionsReadService


class StubDatabase:
    def __init__(self):
        self.transactions = [
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
        self.accounts = [{"id": 7, "name": "Compte courant", "bank": "Banque Test", "status": "Actif"}]
        self.categories = [{"id": 4, "name": "Revenus", "kind": "Revenu", "color": "#16a34a"}]

    def list_transactions(self):
        return self.transactions

    def list_accounts(self):
        return self.accounts

    def list_categories(self):
        return self.categories

    def get_transaction(self, transaction_id):
        return next((row for row in self.transactions if row["id"] == transaction_id), None)

    def update_transaction(self, transaction_id, data):
        self.updated = (transaction_id, data)
        row = self.get_transaction(transaction_id)
        row.update({
            "account_id": data["account_id"],
            "tx_date": data["tx_date"],
            "label": data["label"],
            "category": data["category"],
            "amount": data["amount"],
            "tx_type": "Crédit" if data["amount"] >= 0 else "Débit",
            "status": data["status"],
        })

    def update_transactions_category(self, transaction_ids, category):
        self.bulk_category = (transaction_ids, category)
        updated = 0
        for transaction_id in transaction_ids:
            row = self.get_transaction(transaction_id)
            if row is not None:
                row["category"] = category
                row["status"] = "Validée"
                updated += 1
        return updated

    def update_transactions_status(self, transaction_ids, status):
        self.bulk_status = (transaction_ids, status)
        updated = 0
        for transaction_id in transaction_ids:
            row = self.get_transaction(transaction_id)
            if row is not None:
                row["status"] = status
                updated += 1
        return updated

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
        self.assertEqual(snapshot["categories"][0]["id"], 4)
        self.assertEqual(snapshot["transactions"][0]["accountName"], "Compte courant")
        self.assertEqual(snapshot["transactions"][0]["beneficiary"], "VIREMENT REÇU")
        self.assertEqual(snapshot["transactions"][0]["ruleSuggestion"], "VIREMENT REÇU")
        self.assertEqual(snapshot["transactions"][1]["category"], "À catégoriser")
        self.assertEqual(snapshot["recentImport"]["recognizedCount"], 3)
        self.assertEqual(database.import_limit, 1)

    def test_updates_transaction_through_business_database_method(self):
        database = StubDatabase()
        service = TransactionsReadService(database)

        result = service.update(12, {
            "account_id": 7,
            "tx_date": "2026-10-12",
            "label": "Achat alimentaire",
            "category": "Revenus",
            "direction": "Débit",
            "amount": 20,
            "status": "Validée",
        })

        self.assertTrue(result["success"])
        self.assertEqual(result["transactionId"], 12)
        self.assertEqual(database.updated[1]["label"], "Achat alimentaire")
        self.assertEqual(database.updated[1]["amount"], -20.0)
        self.assertTrue(database.updated[1]["direction_explicit"])

    def test_empty_category_forces_uncategorized_status(self):
        database = StubDatabase()
        service = TransactionsReadService(database)

        service.update(11, {
            "account_id": 7,
            "tx_date": "2026-10-13",
            "label": "Virement reçu",
            "category": "",
            "direction": "Crédit",
            "amount": 125.5,
            "status": "Validée",
        })

        self.assertIsNone(database.updated[1]["category"])
        self.assertEqual(database.updated[1]["status"], "À catégoriser")

    def test_rejects_unknown_category(self):
        service = TransactionsReadService(StubDatabase())

        with self.assertRaisesRegex(ValueError, "catégorie sélectionnée"):
            service.update(11, {
                "account_id": 7,
                "tx_date": "2026-10-13",
                "label": "Virement reçu",
                "category": "Catégorie fantôme",
                "direction": "Crédit",
                "amount": 125.5,
                "status": "Validée",
            })

    def test_rejects_missing_transaction(self):
        service = TransactionsReadService(StubDatabase())

        with self.assertRaisesRegex(KeyError, "n’existe pas"):
            service.update(999, {})

    def test_applies_category_to_unique_bulk_selection(self):
        database = StubDatabase()
        service = TransactionsReadService(database)

        result = service.bulk_update([11, 12, 12], "category", "Revenus")

        self.assertTrue(result["success"])
        self.assertEqual(result["updatedCount"], 2)
        self.assertEqual(result["transactionIds"], [11, 12])
        self.assertEqual(database.bulk_category, ([11, 12], "Revenus"))
        self.assertEqual(database.get_transaction(12)["category"], "Revenus")

    def test_rejects_bulk_validation_when_a_transaction_is_uncategorized(self):
        service = TransactionsReadService(StubDatabase())

        with self.assertRaisesRegex(ValueError, "Catégorisez toutes"):
            service.bulk_update([11, 12], "validate")

    def test_validates_a_categorized_bulk_selection(self):
        database = StubDatabase()
        database.get_transaction(12)["category"] = "Revenus"
        service = TransactionsReadService(database)

        result = service.bulk_update([11, 12], "validate")

        self.assertEqual(result["updatedCount"], 2)
        self.assertEqual(database.bulk_status, ([11, 12], "Validée"))
        self.assertEqual(database.get_transaction(12)["status"], "Validée")


if __name__ == "__main__":
    unittest.main()
