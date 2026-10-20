from __future__ import annotations

import sqlite3
import unittest
from contextlib import contextmanager

from app.database import Database


class InMemoryPresetDatabase(Database):
    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE TABLE user_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT 'global',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            )
            """
        )
        self.seal_count = 0

    @contextmanager
    def connect(self):
        try:
            yield self.connection
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise

    def seal_database_to_encrypted_vault(self):
        self.seal_count += 1
        return None


class ForecastScenarioPresetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = InMemoryPresetDatabase()

    def tearDown(self) -> None:
        self.database.connection.close()

    def test_defaults_are_distinct_and_adjust_only_recurring_forecasts(self):
        presets = {item["name"]: item for item in self.database.forecast_scenario_presets()}

        self.assertEqual(presets["Réaliste"]["incomePercent"], 100.0)
        self.assertEqual(presets["Prudent"]["incomePercent"], 90.0)
        self.assertEqual(presets["Prudent"]["expensePercent"], 110.0)
        self.assertEqual(presets["Optimiste"]["incomePercent"], 110.0)
        self.assertEqual(presets["Optimiste"]["expensePercent"], 95.0)

        source_events = [
            {"source": "Récurrence", "name": "Salaire", "amount": 1000.0},
            {"source": "Récurrence décalée", "name": "Loyer", "amount": -200.0},
            {"source": "Transaction future", "name": "Virement saisi", "amount": -50.0},
            {"source": "Scénario", "name": "Projet libre", "amount": -75.0},
        ]
        prudent = self.database.apply_forecast_scenario_preset(source_events, "Prudent")
        optimistic = self.database.apply_forecast_scenario_preset(source_events, "Optimiste")

        self.assertEqual([event["amount"] for event in prudent], [900.0, -220.0, -50.0, -75.0])
        self.assertEqual([event["amount"] for event in optimistic], [1100.0, -190.0, -50.0, -75.0])
        self.assertEqual(source_events[0]["amount"], 1000.0)
        self.assertEqual(prudent[0]["original_amount"], 1000.0)
        self.assertEqual(prudent[0]["scenario_adjustment_percent"], 90.0)

    def test_saved_percentages_are_persisted_and_used(self):
        saved = self.database.update_forecast_scenario_preset("Réaliste", 82.5, 118)

        self.assertEqual(saved["incomePercent"], 82.5)
        self.assertEqual(saved["expensePercent"], 118.0)
        self.assertEqual(self.database.seal_count, 1)
        adjusted = self.database.apply_forecast_scenario_preset(
            [
                {"source": "Récurrence", "amount": 200.0},
                {"source": "Récurrence", "amount": -100.0},
            ],
            "Réaliste",
        )
        self.assertEqual(adjusted[0]["amount"], 165.0)
        self.assertEqual(adjusted[1]["amount"], -118.0)

    def test_invalid_values_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "compris entre 0 et 300"):
            self.database.update_forecast_scenario_preset("Prudent", -1, 100)
        with self.assertRaisesRegex(ValueError, "n’existe pas"):
            self.database.update_forecast_scenario_preset("Inconnu", 100, 100)


if __name__ == "__main__":
    unittest.main()
