from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.services.assets_read_service import AssetsReadService


class InsightsDatabase:
    def list_assets(self):
        return [
            {"id": 1, "name": "PEA", "category": "Placements financiers", "asset_type": "PEA", "value": 11000, "valuation_date": "2026-10-01", "valuation_mode": "Manuelle", "status": "Actif", "comment": "", "details_json": "{}"},
            {"id": 2, "name": "Résidence", "category": "Immobilier", "asset_type": "Maison", "value": 200000, "valuation_date": "2026-10-01", "valuation_mode": "Manuelle", "status": "Actif", "comment": "", "details_json": "{}"},
            {"id": 3, "name": "Prêt", "category": "Crédit immobilier", "asset_type": "Crédit immobilier", "value": -100000, "valuation_date": "2026-10-01", "valuation_mode": "Manuelle", "status": "Actif", "comment": "",
             "details_json": '{"monthlyPayment": "1000", "endDate": "2028-10-31", "initialAmount": "150000"}'},
        ]

    def asset_value_history(self):
        rows = []
        for index, month in enumerate(["2026-04-01", "2026-05-01", "2026-06-01", "2026-07-01", "2026-08-01", "2026-09-01", "2026-10-01"]):
            rows.append({"asset_id": 1, "valuation_date": month, "value": 10000 + index * 150 * (1 if index % 2 else -1) + index * 200})
        rows.append({"asset_id": 1, "valuation_date": "2026-10-01", "value": 11000})
        rows.append({"asset_id": 2, "valuation_date": "2026-04-01", "value": 200000})
        rows.append({"asset_id": 3, "valuation_date": "2026-04-01", "value": -110000})
        rows.append({"asset_id": 3, "valuation_date": "2026-10-01", "value": -100000})
        return rows

    def list_accounts(self):
        return [{"id": 1, "status": "Actif", "initial_date": "2026-04-01"}]

    def account_summary_at_date(self, target_date):
        return {"liquidites": 5000.0}

    def net_worth_breakdown(self):
        return {"assets": 216000.0, "liabilities": 100000.0, "liquidities": 5000.0, "net_worth": 116000.0}

    def patrimonio_evolution(self, mode="net"):
        return []


def service():
    return AssetsReadService(InsightsDatabase(), now_provider=lambda: datetime(2026, 10, 22, 12, tzinfo=timezone.utc))


class AssetsInsightsTest(unittest.TestCase):
    def test_history_includes_liquidities_and_ends_on_todays_net_worth(self):
        snapshot = service().snapshot()
        series = snapshot["evolution"]
        self.assertEqual(series[0]["date"], "2026-04-01")
        self.assertEqual(series[0]["net"], 200000 + 10000 + 5000 - 110000)
        self.assertEqual(series[-1]["net"], 116000.0)

    def test_twelve_month_change_is_flagged_incomplete_when_history_is_short(self):
        change = service().snapshot()["headline"]["change"]
        self.assertFalse(change["complete"])
        self.assertEqual(change["amount"], round(116000 - 105000, 2))
        self.assertAlmostEqual(change["months"], 6.7, places=1)

    def test_annual_return_ignores_cash_and_annualizes(self):
        annual = service().snapshot()["headline"]["annualReturn"]
        self.assertIsNotNone(annual["percent"])
        self.assertGreater(annual["percent"], 0)

    def test_categories_expose_cash_without_performance_metrics_and_no_tri(self):
        categories = {item["name"]: item for item in service().snapshot()["categories"]}
        self.assertEqual(set(categories), {"Placements financiers", "Immobilier", "Liquidités"})
        self.assertTrue(categories["Liquidités"]["isCash"])
        self.assertIsNone(categories["Liquidités"]["volatility"])
        self.assertIsNone(categories["Placements financiers"]["tri"])
        self.assertIn("Versements", categories["Placements financiers"]["triReason"])
        self.assertIsNotNone(categories["Placements financiers"]["volatility"])
        self.assertIsNone(categories["Immobilier"]["volatility"])

    def test_debt_detail_uses_entered_fields_only(self):
        debt = service().snapshot()["debts"][0]
        self.assertEqual(debt["balance"], 100000.0)
        self.assertEqual(debt["monthlyPayment"], 1000.0)
        self.assertEqual(debt["monthsLeft"], 24)
        self.assertEqual(debt["repaidPercent"], 33.3)
        self.assertIsNone(debt["rate"])
        self.assertIsNone(debt["interestLeft"])  # 1000 x 24 < 100000 : aucun intérêt déductible


if __name__ == "__main__":
    unittest.main()
