from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from app.services.dashboard_read_service import DashboardReadService


class StubDatabase:
    def dashboard_metrics(self):
        return {
            "cash": 24680.30,
            "forecast_30": 30320.0,
            "patrimoine_net": 429000.0,
            "revenus": 3200.0,
            "depenses": 2060.0,
            "month": "2026-09",
        }

    def dashboard_forecast_chart(self, horizon_days):
        self.horizon_days = horizon_days
        return {
            "labels": ["13/10", "12/11"],
            "series": {
                "Optimiste": [24680.30, 32400.0],
                "Réaliste": [24680.30, 30320.0],
                "Prudent": [24680.30, 28100.0],
            },
            "alert_level": "ok",
            "alert": "Trésorerie stable",
            "min_balance": 24100.0,
            "end_balance": 30320.0,
        }

    def budget_report(self, month):
        self.month = month
        return {
            "month": month,
            "total_planned": 2800.0,
            "total_realized": 2060.0,
            "rows": [
                {
                    "category": "Logement",
                    "planned": 1000.0,
                    "actual": 950.0,
                    "remaining": 50.0,
                    "usage": 95.0,
                    "status": "Vigilance",
                }
            ],
        }

    def asset_summary(self):
        return {"Immobilier": 250000.0, "Placements": 103000.0, "Dette": -50000.0}


class DashboardReadServiceTest(unittest.TestCase):
    def test_builds_stable_ui_contract_without_mutating_database(self):
        database = StubDatabase()
        service = DashboardReadService(
            database,
            today_provider=lambda: date(2026, 10, 13),
            now_provider=lambda: datetime(2026, 10, 13, 20, 0, tzinfo=timezone.utc),
        )

        snapshot = service.snapshot()

        self.assertEqual(snapshot["period"], "2026-09")
        self.assertEqual(snapshot["currency"], "EUR")
        self.assertEqual(snapshot["kpis"][0]["value"], 24680.30)
        self.assertEqual(snapshot["forecast"][-1]["balance"], 30320.0)
        self.assertEqual(snapshot["alerts"][0]["level"], "success")
        self.assertEqual(snapshot["budget"]["rows"][0]["category"], "Logement")
        self.assertEqual(snapshot["assets"][0], {"label": "Immobilier", "value": 250000.0})
        self.assertEqual(database.horizon_days, 60)
        self.assertEqual(database.month, "2026-09")


if __name__ == "__main__":
    unittest.main()
