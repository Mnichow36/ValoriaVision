from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.database import Database
from app.services.assets_read_service import AssetsReadService
from app.services.budgets_read_service import BudgetsReadService
from app.services.business_rules import is_patrimonial_asset
from app.services.dashboard_read_service import DashboardReadService


def build_database(root: str) -> Database:
    database = Database(Path(root) / "valoria.db")
    with database.connect() as conn:
        database.create_schema(conn)
        database.apply_migrations(conn)
        database.seed_if_empty(conn)
        database.seed_recurring_items(conn)
    return database


class CrossScreenConsistencyTest(unittest.TestCase):
    """Les mêmes chiffres doivent être identiques sur tous les écrans (CDC P2)."""

    def test_net_worth_is_identical_on_dashboard_and_patrimoine(self):
        with TemporaryDirectory() as root:
            database = build_database(root)

            dashboard = DashboardReadService(database).snapshot()
            assets = AssetsReadService(database).snapshot()

            dashboard_net = next(k["value"] for k in dashboard["kpis"] if k["id"] == "net-worth")
            self.assertEqual(dashboard_net, assets["summary"]["netWorth"])
            self.assertEqual(
                assets["summary"]["netWorth"],
                round(assets["summary"]["totalAssets"] - assets["summary"]["totalLiabilities"], 2),
            )

    def test_net_worth_includes_live_account_liquidity_once(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            breakdown = database.net_worth_breakdown()
            live_liquidity = round(database.account_summary()["liquidites"], 2)

            self.assertEqual(breakdown["liquidities"], live_liquidity)
            with database.connect() as conn:
                rows = list(conn.execute("SELECT name, category, asset_type, value FROM assets WHERE status = 'Actif'"))
            patrimonial = [r for r in rows if is_patrimonial_asset(r["name"], r["category"], r["asset_type"])]
            other_assets = sum(r["value"] for r in patrimonial if r["value"] > 0)
            liabilities = abs(sum(r["value"] for r in patrimonial if r["value"] < 0))
            # La ligne statique « Liquidités » du jeu de démonstration
            # ne doit jamais s'ajouter aux liquidités réelles des comptes.
            self.assertAlmostEqual(
                breakdown["net_worth"], other_assets + live_liquidity - liabilities, places=2
            )

    def test_asset_families_add_up_to_the_announced_total(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            positive_families = {k: v for k, v in database.asset_summary().items() if v > 0}

            self.assertAlmostEqual(
                sum(positive_families.values()), database.net_worth_breakdown()["assets"], places=2
            )
            dashboard = DashboardReadService(database).snapshot()
            self.assertAlmostEqual(
                sum(item["value"] for item in dashboard["assets"]),
                dashboard_assets_total(database),
                places=2,
            )

    def test_dashboard_expense_kpi_equals_sum_of_all_budget_rows(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            dashboard = DashboardReadService(database).snapshot()

            expenses = next(k["value"] for k in dashboard["kpis"] if k["id"] == "expenses")
            rows_total = round(sum(row["actual"] for row in dashboard["budget"]["rows"]), 2)
            self.assertEqual(expenses, rows_total)

    def test_budgets_screen_defaults_to_the_current_month_like_the_dashboard(self):
        with TemporaryDirectory() as root:
            database = build_database(root)

            budgets = BudgetsReadService(database).snapshot()
            dashboard = DashboardReadService(database).snapshot()

            self.assertEqual(budgets["month"], date.today().strftime("%Y-%m"))
            self.assertEqual(budgets["month"], dashboard["period"])

    def test_cors_allows_put_and_delete_for_recurrences(self):
        with TemporaryDirectory() as root:
            app = create_app(build_database(root))
            client = TestClient(app)
            for method in ("POST", "PUT", "DELETE"):
                response = client.options(
                    "/api/v1/recurrences/1",
                    headers={
                        "Origin": "http://127.0.0.1:5173",
                        "Access-Control-Request-Method": method,
                        "Access-Control-Request-Headers": "content-type,x-valoria-session",
                    },
                )
                self.assertEqual(response.status_code, 200, method)


def dashboard_assets_total(database: Database) -> float:
    return round(sum(v for v in database.asset_summary().values() if v > 0), 2)


if __name__ == "__main__":
    unittest.main()
