from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.database import Database
from app.services.categorization_rule_service import CategorizationRuleService
from app.services.settings_read_service import SettingsReadService


def build_database(root: str) -> Database:
    database = Database(Path(root) / "valoria.db")
    with database.connect() as conn:
        database.create_schema(conn)
        database.apply_migrations(conn)
        database.seed_if_empty(conn)
        database.seed_recurring_items(conn)
    return database


class PendingRulesTest(unittest.TestCase):
    def setUp(self):
        self._root = TemporaryDirectory()
        self.database = build_database(self._root.name)
        self.rules = CategorizationRuleService(self.database)
        with self.database.connect() as conn:
            self.account = int(conn.execute("SELECT id FROM accounts WHERE status = 'Actif' ORDER BY id LIMIT 1").fetchone()["id"])
            conn.execute("DELETE FROM categorization_rules")
            conn.execute("DELETE FROM transactions")
        for name in ("Alimentation", "Transport"):
            if not self.rules.category_id_by_name(name):
                self.database.add_category(name)
        self.food = self.rules.category_id_by_name("Alimentation")
        self.transport = self.rules.category_id_by_name("Transport")
        self.lidl_rule = self._rule("LIDL", self.food, priority=100)
        self.sncf_rule = self._rule("SNCF", self.transport, priority=110)
        self.pending_lidl = self._tx("ACHAT CB LIDL PARIS", -20, None)
        self.pending_lidl_2 = self._tx("ACHAT CB LIDL LYON", -25, None)
        self.pending_sncf = self._tx("PAIEMENT SNCF", -50, None)
        self.pending_other = self._tx("VIREMENT INCONNU", -10, None)
        self.done_lidl = self._tx("ACHAT CB LIDL DEJA", -30, "Transport")
        self.service = SettingsReadService(self.database)

    def tearDown(self):
        self._root.cleanup()

    def _rule(self, value, category_id, priority):
        return self.rules.create_rule({
            "name": f"{value} test", "is_active": True, "priority": priority,
            "match_field": "label", "match_operator": "contains", "match_value": value,
            "target_category_id": category_id, "confidence": 100,
        })

    def _tx(self, label, amount, category):
        with self.database.connect() as conn:
            cur = conn.execute(
                "INSERT INTO transactions(account_id, tx_date, label, amount, category, tx_type, status) VALUES (?, '2026-03-05', ?, ?, ?, ?, ?)",
                (self.account, label, amount, category, "Débit", "Validée" if category else "À catégoriser"),
            )
            return int(cur.lastrowid)

    def _category_of(self, tx_id):
        with self.database.connect() as conn:
            return conn.execute("SELECT category FROM transactions WHERE id = ?", (tx_id,)).fetchone()["category"]

    def test_preview_only_covers_pending_operations(self):
        preview = self.service.pending_preview()
        ids = {item["id"] for item in preview["items"]}
        self.assertEqual(preview["pendingCount"], 4)
        self.assertEqual(preview["matchedCount"], 3)
        self.assertEqual(preview["unmatchedCount"], 1)
        self.assertNotIn(self.done_lidl, ids)
        self.assertEqual({entry["count"] for entry in preview["byRule"]}, {2, 1})

    def test_preview_for_single_rule(self):
        preview = self.service.pending_preview(self.sncf_rule)
        self.assertEqual([item["id"] for item in preview["items"]], [self.pending_sncf])

    def test_apply_classifies_selected_only_and_never_touches_done(self):
        result = self.service.apply_pending([self.pending_lidl, self.done_lidl, self.pending_other])
        self.assertEqual(result["classified"], 1)
        self.assertEqual(self._category_of(self.pending_lidl), "Alimentation")
        self.assertIsNone(self._category_of(self.pending_lidl_2))
        self.assertEqual(self._category_of(self.done_lidl), "Transport")
        self.assertIsNone(self._category_of(self.pending_other))

    def test_apply_single_rule_ignores_other_rules(self):
        self.service.apply_pending([self.pending_lidl, self.pending_sncf], self.sncf_rule)
        self.assertEqual(self._category_of(self.pending_sncf), "Transport")
        self.assertIsNone(self._category_of(self.pending_lidl))

    def test_apply_without_candidate_is_refused(self):
        with self.assertRaises(ValueError):
            self.service.apply_pending([self.done_lidl])

    def test_usage_count_and_delete_rule(self):
        self.service.apply_pending([self.pending_lidl])
        rules = {rule["id"]: rule for rule in self.service.snapshot()["rules"]}
        self.assertEqual(rules[self.lidl_rule]["usageCount"], 1)
        self.assertEqual(rules[self.sncf_rule]["usageCount"], 0)
        self.service.delete_rule(self.sncf_rule)
        self.assertNotIn(self.sncf_rule, {rule["id"] for rule in self.service.snapshot()["rules"]})
        self.assertEqual(self.service.snapshot()["pendingCount"], 3)

    def test_system_category_cannot_be_deleted(self):
        system = next(c for c in self.service.snapshot()["categories"] if c["isSystem"])
        with self.assertRaises(ValueError):
            self.service.delete_category(system["id"])


if __name__ == "__main__":
    unittest.main()
