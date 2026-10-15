from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.database import Database
from app.services.transactions_read_service import TransactionsReadService


class ApiDatabaseStartupTest(unittest.TestCase):
    def test_existing_database_is_migrated_before_bulk_actions(self):
        with TemporaryDirectory() as root:
            database = Database(Path(root) / "valoria.db")
            database.initialize()
            with database.connect() as conn:
                conn.execute("ALTER TABLE transactions DROP COLUMN categorization_status")
                conn.execute("ALTER TABLE transactions DROP COLUMN categorized_by")

            self.assertTrue(database.prepare_existing_database())

            with database.connect() as conn:
                columns = {row["name"] for row in conn.execute("PRAGMA table_info(transactions)")}
            self.assertIn("categorization_status", columns)
            self.assertIn("categorized_by", columns)

            service = TransactionsReadService(database)
            transaction_id = next(
                row["id"]
                for row in service.snapshot()["transactions"]
                if row["category"] == "À catégoriser"
            )
            result = service.bulk_update([transaction_id], "category", "Loisirs")
            self.assertEqual(result["updatedCount"], 1)

    def test_missing_database_is_not_created(self):
        with TemporaryDirectory() as root:
            database = Database(Path(root) / "missing.db")

            self.assertFalse(database.prepare_existing_database())
            self.assertFalse(database.path.exists())


if __name__ == "__main__":
    unittest.main()
