from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import HTTPException

from app.api.main import TransactionBulkPayload, create_app
from app.database import Database
from app.services.transactions_read_service import TransactionsReadService


class ApiDatabaseStartupTest(unittest.TestCase):
    def test_existing_database_is_migrated_before_bulk_actions(self):
        with TemporaryDirectory() as root:
            database = Database(Path(root) / "valoria.db")
            with database.connect() as conn:
                database.create_schema(conn)
                database.apply_migrations(conn)
                database.seed_if_empty(conn)
                database.seed_recurring_items(conn)
                conn.execute("ALTER TABLE transactions DROP COLUMN categorization_status")
                conn.execute("ALTER TABLE transactions DROP COLUMN categorized_by")
                conn.execute("ALTER TABLE transactions DROP COLUMN beneficiary")

            self.assertTrue(database.prepare_existing_database())

            with database.connect() as conn:
                columns = {row["name"] for row in conn.execute("PRAGMA table_info(transactions)")}
            self.assertIn("categorization_status", columns)
            self.assertIn("categorized_by", columns)
            self.assertIn("beneficiary", columns)
            with database.connect() as conn:
                beneficiary_count = conn.execute(
                    "SELECT COUNT(*) AS item_count FROM transactions WHERE beneficiary IS NOT NULL AND TRIM(beneficiary) <> ''"
                ).fetchone()["item_count"]
            self.assertGreater(beneficiary_count, 0)

            service = TransactionsReadService(database)
            transaction_id = next(
                row["id"]
                for row in service.snapshot()["transactions"]
                if row["category"] == "À catégoriser"
            )
            result = service.bulk_update([transaction_id], "category", "Loisirs")
            self.assertEqual(result["updatedCount"], 1)

    def test_bulk_route_uses_the_local_session_headers(self):
        with TemporaryDirectory() as root:
            database = Database(Path(root) / "valoria.db")
            with database.connect() as conn:
                database.create_schema(conn)
                database.apply_migrations(conn)

            app = create_app(database)
            endpoint = next(
                route.endpoint
                for route in app.routes
                if route.path == "/api/v1/transactions/actions/bulk"
            )
            with self.assertRaises(HTTPException) as raised:
                endpoint(TransactionBulkPayload(
                    transaction_ids=[1],
                    action="validate",
                ), None, None)

            self.assertEqual(raised.exception.status_code, 401)

    def test_missing_database_is_not_created(self):
        with TemporaryDirectory() as root:
            database = Database(Path(root) / "missing.db")

            self.assertFalse(database.prepare_existing_database())
            self.assertFalse(database.path.exists())


if __name__ == "__main__":
    unittest.main()
