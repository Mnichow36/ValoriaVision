from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.services.budgets_read_service import BudgetsReadService


class StubDatabase:
    def budget_report(self, month=None):
        return {
            "month": month or "2026-10",
            "total_planned": 800,
            "total_realized": 920,
            "total_remaining": -120,
            "usage_total": 115,
            "over_count": 1,
            "warning_count": 0,
            "status": "Dépassement",
            "rows": [
                {
                    "id": 3,
                    "category": "Alimentation",
                    "planned": 800,
                    "actual": 920,
                    "remaining": -120,
                    "usage": 115,
                    "alert_threshold": 90,
                    "status": "Dépassement",
                    "notes": "Courses",
                }
            ],
        }

    def budget_months(self):
        return ["2026-10", "2026-09"]

    def list_transactions(self):
        return [
            {"id": 9, "tx_date": "2026-10-12", "label": "Supermarché", "category": "Alimentation", "amount": -120},
            {"id": 8, "tx_date": "2026-09-29", "label": "Ancien achat", "category": "Alimentation", "amount": -40},
        ]


class BudgetsReadServiceTest(unittest.TestCase):
    def test_builds_budget_summary_rows_and_supporting_transactions(self):
        service = BudgetsReadService(
            StubDatabase(),
            now_provider=lambda: datetime(2026, 10, 14, 14, 0, tzinfo=timezone.utc),
        )

        snapshot = service.snapshot("2026-10")

        self.assertEqual(snapshot["summary"]["categoryCount"], 1)
        self.assertEqual(snapshot["summary"]["biggestGap"], 120.0)
        self.assertEqual(snapshot["summary"]["biggestGapCategory"], "Alimentation")
        self.assertEqual(snapshot["rows"][0]["transactions"][0]["label"], "Supermarché")
        self.assertEqual(snapshot["months"], ["2026-10", "2026-09"])


if __name__ == "__main__":
    unittest.main()
