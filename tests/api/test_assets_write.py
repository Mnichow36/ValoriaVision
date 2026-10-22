from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.database import Database


class AssetWriteTest(unittest.TestCase):
    def test_persists_nature_specific_details_and_normalizes_a_liability(self):
        with TemporaryDirectory() as root:
            database = Database(Path(root) / "valoria.db")
            with database.connect() as connection:
                database.create_schema(connection)
                database.apply_migrations(connection)

            asset_id = database.add_asset({
                "name": "Crédit résidence",
                "category": "Crédit immobilier",
                "asset_type": "Crédit immobilier",
                "value": 120000,
                "valuation_date": "2026-10-21",
                "valuation_mode": "Manuelle",
                "comment": "Offre signée",
                "details_json": {"lender": "Banque locale", "endDate": "2044-06-01"},
                "status": "Actif",
            })

            row = database.get_asset(asset_id)
            self.assertIsNotNone(row)
            self.assertEqual(row["value"], -120000)
            self.assertEqual(json.loads(row["details_json"])["lender"], "Banque locale")

            database.delete_asset(asset_id)
            self.assertIsNone(database.get_asset(asset_id))


if __name__ == "__main__":
    unittest.main()
