from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from app.database import Database
from app.services.dashboard_read_service import DashboardReadService


def build_database(root: str) -> Database:
    database = Database(Path(root) / "valoria.db")
    with database.connect() as conn:
        database.create_schema(conn)
        database.apply_migrations(conn)
        database.seed_if_empty(conn)
        database.seed_recurring_items(conn)
    return database


class DashboardInteractiveTest(unittest.TestCase):
    def setUp(self):
        self._root = TemporaryDirectory()
        self.database = build_database(self._root.name)
        self.today = date.today()
        self.month = self.today.strftime("%Y-%m")
        with self.database.connect() as conn:
            ids = [int(row["id"]) for row in conn.execute("SELECT id FROM accounts WHERE status = 'Actif' ORDER BY id LIMIT 2")]
            self.a, self.b = ids[0], ids[1]
            conn.execute("DELETE FROM transactions")
            day = f"{self.month}-02"
            for account, label, amount, category in (
                (self.a, "LOYER", -800, "Logement"),
                (self.a, "COURSES", -120, "Alimentation"),
                (self.b, "ASSURANCE", -300, "Assurances"),
                (self.b, "MYSTERE", -250, "À catégoriser"),
                (self.b, "PETIT", -20, None),
            ):
                conn.execute(
                    "INSERT INTO transactions(account_id, tx_date, label, amount, category, tx_type) VALUES (?, ?, ?, ?, ?, 'Débit')",
                    (account, day, label, amount, category),
                )

    def tearDown(self):
        self._root.cleanup()

    def service(self):
        return DashboardReadService(self.database, today_provider=lambda: self.today, now_provider=lambda: datetime.now(timezone.utc))

    def test_account_filter_limits_flows_and_categories_but_not_net_worth(self):
        everything = self.service().snapshot()
        only_a = self.service().snapshot(self.a)
        kpi = lambda snapshot, key: next(item["value"] for item in snapshot["kpis"] if item["id"] == key)
        self.assertEqual(kpi(everything, "expenses"), 800 + 120 + 300 + 250 + 20)
        self.assertEqual(kpi(only_a, "expenses"), 920)
        self.assertEqual({row["label"] for row in only_a["expensesByCategory"]}, {"Logement", "Alimentation"})
        self.assertEqual(kpi(only_a, "net-worth"), kpi(everything, "net-worth"))
        self.assertFalse(only_a["budgetComparable"])
        self.assertTrue(everything["budgetComparable"])
        self.assertEqual(only_a["filters"]["accountId"], self.a)

    def test_month_filter_and_validation(self):
        previous = (self.today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        empty = self.service().snapshot(None, previous)
        self.assertEqual(empty["period"], previous)
        self.assertEqual(empty["expensesByCategory"], [])
        with self.assertRaises(ValueError):
            self.service().snapshot(None, "octobre")

    def test_quality_and_alerts_are_real_and_navigable(self):
        snapshot = self.service().snapshot()
        quality = snapshot["quality"]
        self.assertEqual(quality["uncategorized"], 2)
        self.assertEqual(quality["uncategorizedLarge"], 1)
        self.assertEqual(quality["categorizedPercent"], 60.0)
        targets = {alert["target"] for alert in snapshot["alerts"]}
        self.assertIn("transactions", targets)
        alert = next(item for item in snapshot["alerts"] if item["target"] == "transactions")
        self.assertEqual(alert["title"], "2 transactions à catégoriser")
        self.assertEqual(snapshot["toProcess"], len([a for a in snapshot["alerts"] if a["level"] != "success"]))
        self.assertTrue(snapshot["accounts"])

    def test_safety_threshold_breach_becomes_an_alert(self):
        self.database.set_setting("forecast.safety_threshold", "100000000")
        snapshot = self.service().snapshot()
        alert = next(item for item in snapshot["alerts"] if item["target"] == "forecast")
        self.assertEqual(alert["title"], "Solde sous le seuil de sécurité")

    def test_upcoming_lists_future_movements_only(self):
        snapshot = self.service().snapshot()
        self.assertLessEqual(len(snapshot["upcoming"]), 5)
        for item in snapshot["upcoming"]:
            self.assertGreaterEqual(item["date"], self.today.isoformat())


if __name__ == "__main__":
    unittest.main()
