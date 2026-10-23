from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.database import Database
from app.services.categorization_rule_service import CategorizationRuleService
from app.services.rule_suggestion_service import RuleSuggestionService


def build_database(root: str) -> Database:
    database = Database(Path(root) / "valoria.db")
    with database.connect() as conn:
        database.create_schema(conn)
        database.apply_migrations(conn)
        database.seed_if_empty(conn)
        database.seed_recurring_items(conn)
    return database


class RuleSuggestionTest(unittest.TestCase):
    def setUp(self):
        self._root = TemporaryDirectory()
        self.database = build_database(self._root.name)
        with self.database.connect() as conn:
            self.account = int(conn.execute("SELECT id FROM accounts WHERE status = 'Actif' ORDER BY id LIMIT 1").fetchone()["id"])
            self.archived = int(conn.execute("SELECT id FROM accounts WHERE status = 'Actif' ORDER BY id DESC LIMIT 1").fetchone()["id"])
            conn.execute("DELETE FROM categorization_rules")
            conn.execute("DELETE FROM transactions")
        for name in ("Alimentation", "Shopping", "Transport"):
            if not CategorizationRuleService(self.database).category_id_by_name(name):
                self.database.add_category(name)
        day = 1
        # LIDL : 4 fois « Alimentation » (fiable) + 2 « À catégoriser » en attente.
        for _ in range(4):
            self._tx("ACHAT CB LIDL PARIS", -20, "Alimentation", day := day + 1)
        for _ in range(2):
            self._tx("ACHAT CB LIDL MONTREUIL", -35, None, day := day + 1)
        # AMAZON : 7 « Shopping » sur 9 -> 78 %, proposée mais non recommandée.
        for _ in range(7):
            self._tx("PAIEMENT AMAZON", -30, "Shopping", day := day + 1)
        for _ in range(2):
            self._tx("PAIEMENT AMAZON", -30, "Alimentation", day := day + 1)
        # SNCF : seulement 2 fois -> pas assez de recul.
        for _ in range(2):
            self._tx("PAIEMENT SNCF", -50, "Transport", day := day + 1)
        # Contrepartie ambiguë (50/50) -> écartée.
        for category in ("Shopping", "Alimentation", "Shopping", "Alimentation"):
            self._tx("PAIEMENT FNAC", -40, category, day := day + 1)

    def tearDown(self):
        self._root.cleanup()

    def _tx(self, label, amount, category, day):
        with self.database.connect() as conn:
            conn.execute(
                "INSERT INTO transactions(account_id, tx_date, label, amount, category, tx_type, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (self.account, f"2026-03-{day:02d}", label, amount, category, "Débit" if amount < 0 else "Crédit", "Validée" if category else "À catégoriser"),
            )

    def service(self):
        return RuleSuggestionService(self.database)

    def test_suggests_reliable_counterparties_with_matches(self):
        result = self.service().suggestions()
        by_name = {item["matchValue"]: item for item in result["suggestions"]}

        self.assertIn("LIDL", by_name)
        self.assertEqual(by_name["LIDL"]["category"], "Alimentation")
        self.assertEqual(by_name["LIDL"]["reliability"], 1.0)
        self.assertTrue(by_name["LIDL"]["recommended"])
        self.assertEqual(by_name["LIDL"]["matches"], 2)
        self.assertEqual(by_name["LIDL"]["transactionType"], "Débit")

        self.assertFalse(by_name["AMAZON"]["recommended"])
        self.assertAlmostEqual(by_name["AMAZON"]["reliability"], 7 / 9, places=3)
        self.assertNotIn("SNCF", by_name)            # moins de 3 occurrences
        self.assertNotIn("FNAC", by_name)            # trop ambiguë
        self.assertEqual(result["discardedCount"], 1)
        self.assertEqual(result["totalMatches"], 2)

    def test_reliability_threshold_controls_recommendation(self):
        result = self.service().suggestions(min_reliability=0.75)
        by_name = {item["matchValue"]: item for item in result["suggestions"]}
        self.assertTrue(by_name["AMAZON"]["recommended"])

    def test_preview_lists_only_uncategorized_matching_operations(self):
        preview = self.service().preview("LIDL", "Débit")
        self.assertEqual(len(preview), 2)
        self.assertTrue(all("LIDL" in row["label"] for row in preview))
        self.assertEqual(self.service().preview("LIDL", "Crédit"), [])
        self.assertEqual(self.service().preview("x"), [])

    def test_apply_creates_rule_and_classifies_only_selected_pending_operations(self):
        service = self.service()
        preview = service.preview("LIDL", "Débit")
        chosen = preview[0]["id"]
        category_id = CategorizationRuleService(self.database).category_id_by_name("Alimentation")

        result = service.apply([{
            "match_value": "LIDL",
            "target_category_id": category_id,
            "transaction_type": "Débit",
            "transaction_ids": [chosen, 999999],   # un id étranger est ignoré
        }])

        self.assertEqual(result["created"], 1)
        self.assertEqual(result["classified"], 1)
        with self.database.connect() as conn:
            done = conn.execute("SELECT category FROM transactions WHERE id = ?", (chosen,)).fetchone()
            others = conn.execute("SELECT COUNT(*) AS n FROM transactions WHERE label LIKE '%LIDL MONTREUIL%' AND category = 'Alimentation'").fetchone()
            kept = conn.execute("SELECT COUNT(*) AS n FROM transactions WHERE label LIKE '%AMAZON%' AND category = 'Alimentation'").fetchone()
        self.assertEqual(done["category"], "Alimentation")
        self.assertEqual(others["n"], 1)             # l'autre opération en attente n'a pas été cochée
        self.assertEqual(kept["n"], 2)               # les opérations déjà catégorisées ne bougent pas
        # La règle existe maintenant : LIDL ne figure plus dans les suggestions.
        names = [item["matchValue"] for item in service.suggestions()["suggestions"]]
        self.assertNotIn("LIDL", names)

    def test_dismissed_suggestion_disappears(self):
        service = self.service()
        service.dismiss("amazon")
        names = [item["matchValue"] for item in service.suggestions()["suggestions"]]
        self.assertNotIn("AMAZON", names)

    def test_apply_rejects_empty_or_invalid_input(self):
        with self.assertRaises(ValueError):
            self.service().apply([])
        with self.assertRaises(ValueError):
            self.service().apply([{"match_value": "12", "target_category_id": 1}])


if __name__ == "__main__":
    unittest.main()
