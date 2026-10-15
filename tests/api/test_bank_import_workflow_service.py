from __future__ import annotations

import base64
import unittest
from datetime import datetime, timezone

from app.imports.import_models import ImportAnalysis, ImportDiagnostic, ImportedTransaction
from app.services.bank_import_workflow_service import BankImportWorkflowService


class StubImporter:
    def analyze(self, _path):
        return ImportAnalysis(
            file_name="releve.csv",
            valid_transactions=[
                ImportedTransaction("2026-10-10", "Salaire", 2500, source_line=2),
                ImportedTransaction("2026-10-11", "Courses", -72.5, source_line=3),
                ImportedTransaction("2026-10-12", "Doublon", -20, source_line=4),
            ],
            diagnostic=ImportDiagnostic(
                stage="normalisation",
                format_name="CSV",
                profile_name="Banque Test",
                source_account_identifiers=["FR7612345678901234567890123"],
            ),
        )


class StubCategorizer:
    def __init__(self, database):
        self.database = database

    def apply_rules_to_import_batch(self, batch_id):
        self.database.categorized_batch = batch_id
        return {"auto": 1, "to_review": 0, "to_categorize": 1}


class StubDatabase:
    def __init__(self):
        self.inserted = []
        self.updated = None
        self.categorized_batch = None

    def list_accounts(self):
        return [{
            "id": 7,
            "name": "Compte courant",
            "bank": "Banque Test",
            "identifier": "FR7612345678901234567890123",
            "status": "Actif",
        }]

    def transaction_exists(self, account_id, tx_date, label, amount):
        return label == "Doublon"

    def create_import_batch(self, file_name, account_id, **metadata):
        self.created = (file_name, account_id, metadata)
        return 41

    def insert_transaction(self, *args, **kwargs):
        self.inserted.append((args, kwargs))
        return True

    def update_import_batch(self, batch_id, imported, duplicates, errors):
        self.updated = (batch_id, imported, duplicates, errors)

    def reconciliation_summary_for_import_batch(self, batch_id):
        return {"auto": 1, "to_review": 1, "without_forecast": 0}


class BankImportWorkflowServiceTest(unittest.TestCase):
    def test_previews_then_commits_through_existing_engines(self):
        database = StubDatabase()
        service = BankImportWorkflowService(
            database,
            importer_factory=StubImporter,
            categorizer_factory=StubCategorizer,
            now_provider=lambda: datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc),
        )
        encoded = base64.b64encode(b"test bank statement").decode("ascii")

        preview = service.preview("session-a", "releve.csv", encoded, 7)

        self.assertEqual(preview["recognizedCount"], 3)
        self.assertEqual(preview["newCount"], 2)
        self.assertEqual(preview["duplicateCount"], 1)
        self.assertTrue(preview["accountConsistent"])
        self.assertEqual(preview["accountId"], 7)

        result = service.commit("session-a", preview["previewId"], 7)

        self.assertEqual(result["importedCount"], 2)
        self.assertEqual(result["duplicateCount"], 1)
        self.assertEqual(result["categorization"]["automatic"], 1)
        self.assertEqual(result["reconciliation"]["toReview"], 1)
        self.assertEqual(len(database.inserted), 2)
        self.assertEqual(database.updated, (41, 2, 1, 0))
        self.assertEqual(database.categorized_batch, 41)

    def test_rejects_preview_from_another_session(self):
        service = BankImportWorkflowService(StubDatabase(), importer_factory=StubImporter)
        encoded = base64.b64encode(b"statement").decode("ascii")
        preview = service.preview("session-a", "releve.csv", encoded, 7)

        with self.assertRaises(KeyError):
            service.commit("session-b", preview["previewId"], 7)


if __name__ == "__main__":
    unittest.main()
