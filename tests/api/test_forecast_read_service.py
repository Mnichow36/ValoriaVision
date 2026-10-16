from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.services.forecast_read_service import ForecastReadService


class StubDatabase:
    def default_forecast_start_date(self):
        return "2026-10-14"

    def list_accounts(self):
        return [
            {"id": 7, "name": "Courant", "bank": "SG", "account_type": "Compte courant", "status": "Actif"},
            {"id": 8, "name": "Clos", "bank": "SG", "account_type": "Compte courant", "status": "Clos"},
        ]

    def list_categories(self):
        return [
            {"id": 3, "name": "Logement", "kind": "Dépense", "direction": "Dépense", "color": "#2563EB"},
            {"id": 4, "name": "Salaire", "kind": "Revenu", "direction": "Recette", "color": "#16A34A"},
        ]

    def cash_forecast(self, start_date, horizon_days, scenario, account_id=None):
        end_balance = {"Prudent": 900, "Réaliste": 1000, "Optimiste": 1200}[scenario]
        return {
            "starting_cash": 800,
            "min_balance": 750,
            "end_balance": end_balance,
            "account_label": "SG — Courant",
            "alert": "Aucune alerte critique",
            "total_in": 300,
            "total_out": 100,
            "daily_points": [
                {"date": "2026-10-14", "label": "14/10", "balance": 800, "events": []},
                {"date": "2026-10-15", "label": "15/10", "balance": end_balance, "events": [
                    {"source": "Récurrence", "amount": 150},
                    {"source": "Transaction future", "amount": 50},
                ]},
            ],
            "upcoming": [{
                "date": "2026-10-15",
                "name": "Salaire",
                "category": "Revenus",
                "amount": 300,
                "source": "Récurrence",
                "account": "Courant",
                "scenario": "Réaliste",
            }],
        }


class ForecastReadServiceTest(unittest.TestCase):
    def test_builds_scenarios_realized_series_and_upcoming_events(self):
        service = ForecastReadService(
            StubDatabase(),
            now_provider=lambda: datetime(2026, 10, 14, 14, 0, tzinfo=timezone.utc),
        )

        snapshot = service.snapshot(account_id=7, horizon_days=90, scenario="Réaliste")

        self.assertEqual(snapshot["filters"]["accountId"], 7)
        self.assertEqual(snapshot["summary"]["endBalance"], 1000.0)
        self.assertEqual(snapshot["summary"]["prudentDifference"], 100.0)
        self.assertEqual(snapshot["series"]["realized"][-1]["balance"], 850.0)
        self.assertEqual(snapshot["upcoming"][0]["name"], "Salaire")
        self.assertEqual(len(snapshot["accounts"]), 1)
        self.assertEqual(snapshot["categories"][0]["name"], "Logement")
        self.assertEqual(snapshot["categories"][1]["direction"], "Recette")

    def test_falls_back_to_supported_filter_values(self):
        snapshot = ForecastReadService(StubDatabase()).snapshot(horizon_days=45, scenario="Inconnu")
        self.assertEqual(snapshot["filters"]["horizonDays"], 90)
        self.assertEqual(snapshot["filters"]["scenario"], "Réaliste")


if __name__ == "__main__":
    unittest.main()
