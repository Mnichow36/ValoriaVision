from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.database import Database
from app.services.forecast_reconciliation_service import ForecastReconciliationService


class LegacyReconciliationMigrationTests(unittest.TestCase):
    def test_existing_database_is_upgraded_before_reconciliation_screen_queries(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database = Database(Path(temp_dir) / "legacy.db")
            with database.connect() as connection:
                database.create_schema(connection)
                database.apply_migrations(connection)
                tables = {
                    row["name"]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }

            self.assertIn("forecast_reconciliation_links", tables)
            self.assertIn("forecast_reconciliation_proposals", tables)

            service = ForecastReconciliationService(database)
            proposals = service.prepare_best_proposals(
                start_date=date(2026, 1, 1),
                end_date=date(2027, 1, 1),
            )
            self.assertEqual([], proposals)


if __name__ == "__main__":
    unittest.main()
