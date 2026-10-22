from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from app.services.forecast_read_service import ForecastReadService


class StubDatabase:
    def default_forecast_start_date(self):
        return "2026-10-14"

    @staticmethod
    def add_period(source, frequency):
        if frequency == "Ponctuel":
            return source.replace(year=source.year + 100)
        month = source.month + (3 if frequency == "Trimestriel" else 12 if frequency == "Annuel" else 1)
        year = source.year + (month - 1) // 12
        return date(year, (month - 1) % 12 + 1, min(source.day, 28))

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

    def list_recurring_items(self, active_only=False):
        return [{
            "id": 42,
            "account_id": 7,
            "account_name": "Courant",
            "bank": "SG",
            "name": "Salaire",
            "category": "Salaire",
            "amount": 300,
            "frequency": "Mensuel",
            "next_date": "2026-06-06",
            "end_date": None,
            "scenario": "Réaliste",
            "status": "Actif",
        }]

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
                    {
                        "source": "Récurrence",
                        "name": "Salaire",
                        "category": "Revenus",
                        "amount": 150,
                        "account": "Courant",
                        "scenario": "Réaliste",
                        "recurring_id": 42,
                    },
                    {
                        "source": "Récurrence décalée",
                        "name": "Salaire déplacé",
                        "category": "Revenus",
                        "amount": 30,
                        "account": "Courant",
                        "scenario": "Réaliste",
                        "recurring_id": 42,
                        "original_date": "2026-09-15",
                    },
                    {
                        "source": "Transaction future",
                        "name": "LIDL",
                        "category": "Alimentation",
                        "amount": 50,
                        "account": "Courant",
                        "scenario": "Tous",
                        "recurring_id": None,
                    },
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
                "recurring_id": 42,
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
        self.assertEqual(snapshot["filters"]["referenceDate"], "2026-10-14")
        self.assertEqual(snapshot["filters"]["startDate"], "2026-10-14")
        self.assertEqual(snapshot["filters"]["endDate"], "2027-01-12")
        self.assertEqual(snapshot["summary"]["endBalance"], 1000.0)
        self.assertEqual(snapshot["summary"]["prudentDifference"], 100.0)
        self.assertEqual(snapshot["series"]["realized"][-1]["balance"], 850.0)
        self.assertEqual(
            [event["source"] for event in snapshot["upcoming"]],
            ["Récurrence", "Récurrence décalée"],
        )
        self.assertEqual(
            [event["name"] for event in snapshot["upcoming"]],
            ["Salaire", "Salaire déplacé"],
        )
        self.assertEqual(snapshot["upcoming"][1]["originalDate"], "2026-09-15")
        self.assertEqual(len(snapshot["accounts"]), 1)
        self.assertEqual(snapshot["categories"][0]["name"], "Logement")
        self.assertEqual(snapshot["categories"][1]["direction"], "Recette")
        self.assertEqual(snapshot["recurrences"][0]["id"], 42)
        self.assertEqual(snapshot["recurrences"][0]["direction"], "Crédit")
        self.assertEqual(snapshot["recurrences"][0]["nextDate"], "2026-06-06")
        self.assertEqual(snapshot["recurrences"][0]["nextOccurrenceDate"], "2026-10-15")
        self.assertEqual(snapshot["recurrences"][0]["nextScheduledDate"], "2026-11-06")
        self.assertEqual(snapshot["recurrences"][0]["nextRescheduledDate"], "2026-10-15")
        self.assertEqual(snapshot["recurrences"][0]["forecastOccurrenceCount"], 2)
        self.assertEqual(snapshot["recurrences"][0]["rescheduledOccurrenceCount"], 1)
        self.assertEqual(snapshot["series"]["selected"][-1]["inflow"], 230.0)
        self.assertEqual(snapshot["series"]["selected"][-1]["outflow"], 0.0)
        self.assertEqual(snapshot["series"]["selected"][-1]["net"], 230.0)
        self.assertEqual(snapshot["series"]["realized"][-1]["inflow"], 50.0)
        self.assertEqual(snapshot["series"]["realized"][-1]["net"], 50.0)
        self.assertEqual(snapshot["series"]["realistic"][-1]["balance"], 1000.0)
        self.assertEqual(snapshot["series"]["custom"], {})
        self.assertEqual(snapshot["series"]["selected"][-1]["events"][0]["source"], "Récurrence")
        self.assertEqual(snapshot["series"]["selected"][-1]["events"][0]["recurringId"], 42)
        self.assertEqual(snapshot["series"]["selected"][-1]["events"][1]["source"], "Récurrence décalée")
        self.assertEqual(snapshot["series"]["selected"][-1]["events"][1]["originalDate"], "2026-09-15")
        self.assertEqual(snapshot["series"]["selected"][-1]["events"][2]["recurringId"], None)
        self.assertEqual(snapshot["upcoming"][0]["recurringId"], 42)

    def test_returns_every_recurrence_in_the_selected_horizon(self):
        database = StubDatabase()
        base_forecast = database.cash_forecast

        def cash_forecast(start_date, horizon_days, scenario, account_id=None):
            result = base_forecast(start_date, horizon_days, scenario, account_id=account_id)
            if scenario == "Réaliste":
                for index in range(5):
                    result["daily_points"][-1]["events"].append({
                        "date": "2026-10-15",
                        "name": f"Échéance {index}",
                        "category": "Logement",
                        "amount": -10 - index,
                        "source": "Récurrence",
                        "account": "Courant",
                        "scenario": "Réaliste",
                        "recurring_id": 42,
                    })
            return result

        database.cash_forecast = cash_forecast
        snapshot = ForecastReadService(
            database,
            now_provider=lambda: datetime(2026, 10, 14, 14, 0, tzinfo=timezone.utc),
        ).snapshot(horizon_days=15, scenario="Réaliste")

        self.assertEqual(len(snapshot["upcoming"]), 7)
        self.assertEqual(
            {event["name"] for event in snapshot["upcoming"] if event["name"].startswith("Échéance")},
            {f"Échéance {index}" for index in range(5)},
        )

    def test_falls_back_to_supported_filter_values(self):
        snapshot = ForecastReadService(
            StubDatabase(),
            now_provider=lambda: datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc),
        ).snapshot(horizon_days=45, scenario="Inconnu")
        self.assertEqual(snapshot["filters"]["horizonDays"], 15)
        self.assertEqual(snapshot["filters"]["scenario"], "Réaliste")
        self.assertEqual(snapshot["filters"]["startDate"], "2026-10-18")
        self.assertEqual(snapshot["filters"]["endDate"], "2026-11-02")

    def test_no_forecast_point_before_today_and_safety_threshold(self):
        class ThresholdDatabase(StubDatabase):
            settings = {"forecast.safety_threshold": "900"}

            def get_setting(self, key, default=""):
                return self.settings.get(key, default)

            def set_setting(self, key, value):
                self.settings[key] = value

        database = ThresholdDatabase()
        service = ForecastReadService(database, now_provider=lambda: datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc))
        snapshot = service.snapshot(horizon_days=15)
        for key in ("selected", "realized", "realistic", "prudent", "optimistic"):
            self.assertTrue(all(point["date"] >= "2026-10-15" for point in snapshot["series"][key]), key)
        self.assertEqual(snapshot["filters"]["startDate"], "2026-10-15")
        self.assertEqual(snapshot["summary"]["safetyThreshold"], 900.0)
        self.assertEqual(snapshot["summary"]["daysBelowThreshold"], 0)
        self.assertEqual(service.update_safety_threshold("1 500".replace(" ", ""))["safetyThreshold"], 1500.0)
        self.assertEqual(service.snapshot(horizon_days=15)["summary"]["daysBelowThreshold"], 1)
        with self.assertRaises(ValueError):
            service.update_safety_threshold("abc")
        with self.assertRaises(ValueError):
            service.update_safety_threshold(-5)


if __name__ == "__main__":
    unittest.main()
