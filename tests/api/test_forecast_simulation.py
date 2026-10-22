from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone

from app.services.forecast_read_service import ForecastReadService


class SimDatabase:
    """Solde 1 000 € qui reçoit 500 € le jour J+10 ; seuil réglable."""

    def __init__(self, threshold="800"):
        self.threshold = threshold
        self.today = date(2026, 10, 22)

    def get_setting(self, key, default=None):
        return self.threshold

    def list_accounts(self):
        return [
            {"id": 1, "name": "Courant", "status": "Actif"},
            {"id": 2, "name": "Vieux", "status": "Archivé"},
        ]

    def list_scenarios(self):
        return []

    def cash_forecast(self, start_date, horizon_days, scenario, account_id=None):
        start = date.fromisoformat(start_date)
        points = []
        for offset in range(horizon_days + 1):
            balance = 1000 + (500 if offset >= 10 else 0)
            points.append({"date": (start + timedelta(days=offset)).isoformat(), "balance": balance})
        return {"daily_points": points}


def service(threshold="800"):
    return ForecastReadService(SimDatabase(threshold), now_provider=lambda: datetime(2026, 10, 22, 12, tzinfo=timezone.utc))


class ForecastSimulationTest(unittest.TestCase):
    def payload(self, **overrides):
        data = {"kind": "Dépense", "date": "2026-10-25", "amount": 500, "account_id": None, "label": "Achat"}
        data.update(overrides)
        return data

    def test_expense_below_threshold_is_refused_and_a_later_date_is_suggested(self):
        result = service().simulate(self.payload())
        self.assertEqual(result["verdict"], "ko")
        self.assertEqual(result["without"]["daysBelow"], 0)
        self.assertEqual(result["with"]["minBalance"], 500)
        self.assertEqual(result["with"]["daysBelow"], 7)
        self.assertEqual(result["suggestion"]["date"], "2026-11-01")
        self.assertEqual(result["suggestion"]["daysBelow"], 0)

    def test_small_expense_passes(self):
        result = service().simulate(self.payload(amount=100))
        self.assertEqual(result["verdict"], "ok")
        self.assertIsNone(result["suggestion"])

    def test_income_never_worsens(self):
        self.assertEqual(service().simulate(self.payload(kind="Recette"))["verdict"], "ok")

    def test_without_threshold_the_verdict_is_neutral(self):
        self.assertEqual(service("0").simulate(self.payload())["verdict"], "no_threshold")

    def test_already_below_threshold_and_worsened_is_refused(self):
        result = service("2000").simulate(self.payload(amount=100))
        self.assertEqual(result["verdict"], "ko")
        self.assertGreater(result["without"]["daysBelow"], 0)

    def test_income_when_already_below_threshold_does_not_worsen(self):
        self.assertEqual(service("2000").simulate(self.payload(kind="Recette"))["verdict"], "ok")

    def test_validation(self):
        for bad in ({"date": "2026-10-22"}, {"amount": 0}, {"kind": "X"}, {"account_id": 2}, {"date": "pas une date"}):
            with self.assertRaises(ValueError):
                service().simulate(self.payload(**bad))


if __name__ == "__main__":
    unittest.main()
