from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from app.database import Database
from app.services.budgets_read_service import BudgetsReadService


def build_database(root: str) -> Database:
    database = Database(Path(root) / "valoria.db")
    with database.connect() as conn:
        database.create_schema(conn)
        database.apply_migrations(conn)
        database.seed_if_empty(conn)
    return database


def prepare(database: Database) -> None:
    """Budget Assurances 160 € de janvier à octobre 2026, dépenses réelles ensuite."""
    with database.connect() as conn:
        conn.execute("DELETE FROM budgets")
        conn.execute("DELETE FROM transactions")
        account = conn.execute("SELECT id FROM accounts ORDER BY id LIMIT 1").fetchone()["id"]
        for number in range(1, 11):
            month = f"2026-{number:02d}"
            for category, amount in (("Assurances", 160), ("Alimentation", 450)):
                conn.execute(
                    "INSERT INTO budgets(month, category, planned_amount, initial_amount, alert_threshold, uuid) VALUES (?, ?, ?, ?, 80, ?)",
                    (month, category, amount, amount, f"{category}-{month}"),
                )
            spend = 1150 if number >= 7 else 160
            conn.execute(
                "INSERT INTO transactions(account_id, tx_date, label, amount, category, tx_type) VALUES (?, ?, 'ASSUR', ?, 'Assurances', 'Débit')",
                (account, f"{month}-05", -spend),
            )
            conn.execute(
                "INSERT INTO transactions(account_id, tx_date, label, amount, category, tx_type) VALUES (?, ?, 'COURSES', -400, 'Alimentation', 'Débit')",
                (account, f"{month}-12"),
            )


def service(database: Database) -> BudgetsReadService:
    return BudgetsReadService(database, now_provider=lambda: datetime(2026, 10, 22, 12, tzinfo=timezone.utc))


class BudgetsV2Test(unittest.TestCase):
    def setUp(self):
        self._root = TemporaryDirectory()
        self.database = build_database(self._root.name)
        prepare(self.database)

    def tearDown(self):
        self._root.cleanup()

    def assurances(self, snapshot):
        return next(item for item in snapshot["annual"]["categories"] if item["category"] == "Assurances")

    def test_annual_view_compares_cumulative_budget_and_realized(self):
        snapshot = service(self.database).snapshot("2026-10")
        row = self.assurances(snapshot)
        self.assertEqual(row["cumul"], 1600.0)
        self.assertEqual(row["realized"], 6 * 160 + 4 * 1150)
        self.assertEqual(row["monthsOver"], 4)
        self.assertTrue(row["suggestRevision"])
        self.assertEqual(snapshot["annual"]["totals"]["cumul"], 1600.0 + 4500.0)

    def test_revision_from_month_keeps_the_initial_budget(self):
        self.database.revise_budget("Assurances", 1150, "from", "2026-10", "Prime annuelle")
        row = self.assurances(service(self.database).snapshot("2026-10"))
        self.assertEqual(row["planned"][8], 160)
        self.assertEqual(row["planned"][9], 1150)
        self.assertEqual(row["planned"][11], 1150)
        self.assertEqual(row["initial"][11], 160)
        self.assertEqual(row["revisionCount"], 1)
        self.assertEqual(row["revisions"][0]["reason"], "Prime annuelle")
        self.assertEqual(row["revisions"][0]["oldAmount"], 160)

    def test_revision_for_one_month_does_not_leak_to_the_next_months(self):
        self.database.revise_budget("Assurances", 900, "month", "2026-10")
        row = self.assurances(service(self.database).snapshot("2026-10"))
        self.assertEqual(row["planned"][9], 900)
        self.assertEqual(row["planned"][10], 160)
        self.assertEqual(row["planned"][11], 160)

    def test_revision_for_the_whole_year_rewrites_the_past(self):
        self.database.revise_budget("Assurances", 500, "year", "2026-10")
        row = self.assurances(service(self.database).snapshot("2026-10"))
        self.assertEqual(row["planned"][:10], [500.0] * 10)
        self.assertEqual(row["initial"][0], 160)

    def test_rejects_negative_amounts_and_unknown_scope(self):
        with self.assertRaises(ValueError):
            self.database.revise_budget("Assurances", -1, "from", "2026-10")
        with self.assertRaises(ValueError):
            self.database.revise_budget("Assurances", 10, "forever", "2026-10")
        with self.assertRaises(ValueError):
            self.database.revise_budget("Assurances", 10, "from", "octobre")

    def test_inactive_category_leaves_totals_and_reactivates(self):
        self.database.save_budget_category("Assurances", "2026-10", active=False)
        snapshot = service(self.database).snapshot("2026-10")
        self.assertEqual(snapshot["summary"]["totalPlanned"], 450.0)
        self.assertNotIn("Assurances", [row["category"] for row in snapshot["rows"]])
        listed = {row["category"]: row for row in snapshot["settings"]["categories"]}
        self.assertFalse(listed["Assurances"]["active"])
        self.database.save_budget_category("Assurances", "2026-10", active=True)
        self.assertEqual(service(self.database).snapshot("2026-10")["summary"]["totalPlanned"], 610.0)

    def test_creating_and_removing_a_budgeted_category(self):
        self.database.save_budget_category("Loisirs", "2026-10", planned_amount=200, alert_threshold=90, mode="Saisonnier")
        snapshot = service(self.database).snapshot("2026-10")
        loisirs = next(row for row in snapshot["settings"]["categories"] if row["category"] == "Loisirs")
        self.assertEqual((loisirs["amount"], loisirs["alertThreshold"], loisirs["mode"]), (200, 90, "Saisonnier"))
        self.database.remove_budget_category("Loisirs", "2026-10")
        snapshot = service(self.database).snapshot("2026-10")
        self.assertNotIn("Loisirs", [row["category"] for row in snapshot["rows"]])
        self.assertNotIn("Loisirs", [row["category"] for row in snapshot["settings"]["categories"]])

    def test_changing_the_amount_in_settings_is_recorded_as_a_revision(self):
        self.database.save_budget_category("Alimentation", "2026-10", planned_amount=500)
        row = next(item for item in service(self.database).snapshot("2026-10")["annual"]["categories"] if item["category"] == "Alimentation")
        self.assertEqual(row["planned"][9], 500)
        self.assertEqual(row["revisionCount"], 1)

    def test_tracking_curve_projection_and_watch_list(self):
        tracking = service(self.database).snapshot("2026-10")["tracking"]
        self.assertEqual(tracking["daysInMonth"], 31)
        self.assertEqual(tracking["elapsedDays"], 22)
        self.assertEqual(tracking["daysLeft"], 9)
        self.assertEqual(len(tracking["curve"]), 31)
        self.assertIsNotNone(tracking["curve"][21]["actual"])
        self.assertIsNone(tracking["curve"][22]["actual"])
        self.assertEqual(tracking["watch"][0]["category"], "Assurances")
        self.assertTrue(tracking["watch"][0]["suggestRevision"])
        # Assurances : moyenne des 3 mois précédents = 1150 ; Alimentation : 400 réalisés.
        self.assertEqual(tracking["projection"], 1150 + 400)

    def test_default_threshold_setting(self):
        self.assertEqual(self.database.budget_default_threshold(), 80.0)
        self.database.set_budget_default_threshold(70)
        self.assertEqual(self.database.budget_default_threshold(), 70.0)
        with self.assertRaises(ValueError):
            self.database.set_budget_default_threshold(0)


if __name__ == "__main__":
    unittest.main()
