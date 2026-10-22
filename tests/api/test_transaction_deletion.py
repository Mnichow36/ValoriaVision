from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory

from app.services.forecast_reconciliation_service import ForecastReconciliationService
from app.services.transactions_read_service import TransactionsReadService
from tests.api.test_reconciliation_cancel_history import build_database, make_pair


class TransactionDeletionTest(unittest.TestCase):
    def test_delete_several_transactions(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            service = TransactionsReadService(database)
            ids = [t["id"] for t in service.snapshot()["transactions"][:3]]
            before = service.snapshot()["summary"]["transactionCount"]
            result = service.bulk_update(ids, "delete")
            self.assertEqual(result["updatedCount"], 3)
            self.assertIn("3 transactions supprimées", result["message"])
            self.assertEqual(service.snapshot()["summary"]["transactionCount"], before - 3)

    def test_delete_reconciled_transaction_frees_the_occurrence(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            _, tx_id, occurrence_id = make_pair(database)
            engine = ForecastReconciliationService(database)
            engine.confirm_manual_match(occurrence_id, tx_id)
            TransactionsReadService(database).bulk_update([tx_id], "delete")
            with database.connect() as conn:
                occ = conn.execute("SELECT status, actual_transaction_id FROM forecast_occurrences WHERE id = ?", (occurrence_id,)).fetchone()
                active = conn.execute("SELECT COUNT(*) FROM forecast_reconciliation_links WHERE occurrence_id = ? AND deleted_at IS NULL", (occurrence_id,)).fetchone()[0]
            self.assertIn(occ["status"], {"planned", "overdue"})
            self.assertIsNone(occ["actual_transaction_id"])
            self.assertEqual(active, 0)

    def test_delete_unknown_or_empty_selection_is_refused(self):
        with TemporaryDirectory() as root:
            service = TransactionsReadService(build_database(root))
            with self.assertRaises(ValueError):
                service.bulk_update([], "delete")
            with self.assertRaises(KeyError):
                service.bulk_update([999999], "delete")


if __name__ == "__main__":
    unittest.main()
