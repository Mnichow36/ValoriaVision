from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.services.assets_read_service import AssetsReadService


class StubDatabase:
    def list_assets(self):
        return [
            {"id": 1, "name": "Résidence", "category": "Immobilier", "asset_type": "Maison", "value": 250000, "valuation_date": "2026-10-01", "valuation_mode": "Manuelle", "status": "Actif", "comment": ""},
            {"id": 2, "name": "Compte courant", "category": "Comptes bancaires", "asset_type": "Liquidités", "value": 25000, "valuation_date": "2026-10-10", "valuation_mode": "Calculée", "status": "Actif", "comment": "Disponible"},
            {"id": 3, "name": "Crédit résidence", "category": "Crédit immobilier", "asset_type": "Passif", "value": -120000, "valuation_date": "2026-10-01", "valuation_mode": "Manuelle", "status": "Actif", "comment": ""},
            {"id": 4, "name": "Ancien placement", "category": "PEA", "asset_type": "Placement", "value": 9000, "valuation_date": "2025-01-01", "valuation_mode": "Manuelle", "status": "Archivé", "comment": ""},
        ]

    def patrimonio_evolution(self, mode="net"):
        values = {
            "net": [140000, 155000],
            "assets": [260000, 275000],
            "liabilities": [120000, 120000],
        }
        return [
            {"date": "2026-09-01", "value": values[mode][0]},
            {"date": "2026-10-01", "value": values[mode][1]},
        ]


class AssetsReadServiceTest(unittest.TestCase):
    def test_builds_real_summary_families_and_evolution(self):
        service = AssetsReadService(
            StubDatabase(),
            now_provider=lambda: datetime(2026, 10, 14, 22, 0, tzinfo=timezone.utc),
        )

        snapshot = service.snapshot()

        self.assertEqual(snapshot["summary"]["totalAssets"], 275000.0)
        self.assertEqual(snapshot["summary"]["totalLiabilities"], 120000.0)
        self.assertEqual(snapshot["summary"]["netWorth"], 155000.0)
        self.assertEqual(snapshot["summary"]["liquidities"], 25000.0)
        self.assertEqual(snapshot["leadingAssetId"], 1)
        self.assertEqual(snapshot["families"][0]["name"], "Immobilier")
        self.assertEqual(snapshot["evolution"][-1]["liabilities"], -120000.0)
        self.assertEqual(len(snapshot["assets"]), 2)


if __name__ == "__main__":
    unittest.main()
