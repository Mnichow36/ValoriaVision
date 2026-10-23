from __future__ import annotations

import unittest
from datetime import date, timedelta
from tempfile import TemporaryDirectory

from app.services.forecast_reconciliation_service import ForecastReconciliationService
from app.services.recurrence_occurrences_service import RecurrenceOccurrencesService
from tests.api.test_reconciliation_cancel_history import build_database, make_pair


class RecurrenceOccurrencesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.database = build_database(self._tmp.name)
        self.service = RecurrenceOccurrencesService(self.database)

    def tearDown(self):
        self._tmp.cleanup()

    def future_item(self):
        items = [i for i in self.service.snapshot()["items"] if i["canEdit"] and i["date"] > date.today().isoformat()]
        self.assertTrue(items, "des occurrences futures modifiables doivent exister")
        return items[0]

    def test_snapshot_lists_every_occurrence_one_by_one(self):
        snap = self.service.snapshot()
        self.assertGreater(snap["total"], 12)
        first = snap["items"][0]
        for key in ("id", "date", "label", "amount", "accountName", "statusLabel", "canEdit", "canShift", "canDelete"):
            self.assertIn(key, first)

    def test_update_changes_only_one_occurrence_and_survives_regeneration(self):
        item = self.future_item()
        before = self.service.snapshot()["total"]
        result = self.service.update(item["id"], {"date": item["date"], "amount": -123.45, "label": "Loyer modifié", "category": "Logement"})
        self.assertTrue(result["success"], result)
        ForecastReconciliationService(self.database).generate_occurrences(date.today(), date.today() + timedelta(days=365))
        after = {i["id"]: i for i in self.service.snapshot()["items"]}
        self.assertEqual(after[item["id"]]["amount"], -123.45)
        self.assertEqual(after[item["id"]]["label"], "Loyer modifié")
        self.assertTrue(after[item["id"]]["edited"])
        self.assertEqual(len(after), before)

    def test_snapshot_exposes_all_categories_and_category_can_be_changed(self):
        item = self.future_item()
        is_income = item["amount"] > 0
        self.database.add_category("Catégorie test", kind="Revenu" if is_income else "Dépense")
        snap = self.service.snapshot()
        self.assertIn("Catégorie test", {c["name"] for c in snap["categories"]})
        for c in snap["categories"]:
            self.assertIn(c["direction"], {"Recette", "Dépense", "Neutre"})
        target = next(c for c in snap["categories"] if c["name"] == "Catégorie test")
        result = self.service.update(item["id"], {"date": item["date"], "amount": item["amount"], "label": item["label"], "category": target["name"]})
        self.assertTrue(result["success"], result)
        after = next(i for i in self.service.snapshot()["items"] if i["id"] == item["id"])
        self.assertEqual(after["category"], target["name"])

    def test_category_can_be_propagated_to_rule_and_future_siblings(self):
        item = self.future_item()
        is_income = item["amount"] > 0
        self.database.add_category("Catégorie test", kind="Revenu" if is_income else "Dépense")
        siblings = [i for i in self.service.snapshot()["items"] if i["recurrenceId"] == item["recurrenceId"] and i["id"] != item["id"] and i["canEdit"] and i["date"] >= date.today().isoformat()]
        self.assertGreater(len(siblings), 2)
        hand_edited = siblings[0]
        self.assertTrue(self.service.update(hand_edited["id"], {"date": hand_edited["date"], "amount": hand_edited["amount"], "label": "À la main", "category": hand_edited["category"]})["success"])
        result = self.service.update(item["id"], {"date": item["date"], "amount": item["amount"], "label": item["label"], "category": "Catégorie test", "apply_to_rule": True})
        self.assertTrue(result["success"], result)
        self.assertIn("recatégorisée", result["message"])
        after = {i["id"]: i for i in self.service.snapshot()["items"]}
        self.assertEqual(after[item["id"]]["category"], "Catégorie test")
        self.assertEqual(after[hand_edited["id"]]["category"], hand_edited["category"])
        for sibling in siblings[1:]:
            self.assertEqual(after[sibling["id"]]["category"], "Catégorie test")
        self.assertEqual(self.database.get_recurring_item(item["recurrenceId"])["category"], "Catégorie test")

    def test_category_is_not_propagated_without_request(self):
        item = self.future_item()
        self.database.add_category("Catégorie test", kind="Revenu" if item["amount"] > 0 else "Dépense")
        self.service.update(item["id"], {"date": item["date"], "amount": item["amount"], "label": item["label"], "category": "Catégorie test"})
        others = [i for i in self.service.snapshot()["items"] if i["recurrenceId"] == item["recurrenceId"] and i["id"] != item["id"]]
        self.assertTrue(all(i["category"] != "Catégorie test" for i in others))

    def test_update_validates_input_with_clear_messages(self):
        item = self.future_item()
        self.assertIn("libellé", self.service.update(item["id"], {"date": item["date"], "amount": -1, "label": " ", "category": ""})["message"])
        self.assertIn("nul", self.service.update(item["id"], {"date": item["date"], "amount": 0, "label": "x", "category": ""})["message"])
        self.assertIn("date", self.service.update(item["id"], {"date": "pas-une-date", "amount": -1, "label": "x", "category": ""})["message"])

    def test_shift_moves_the_date_and_keeps_the_original(self):
        item = self.future_item()
        target = (date.fromisoformat(item["date"]) + timedelta(days=4)).isoformat()
        result = self.service.shift([item["id"]], target)
        self.assertTrue(result["success"], result)
        moved = next(i for i in self.service.snapshot()["items"] if i["id"] == item["id"])
        self.assertEqual(moved["date"], target)
        self.assertEqual(moved["originalDate"], item["date"])
        self.assertTrue(moved["shifted"])

    def test_delete_then_restore_keeps_history_and_is_not_regenerated(self):
        item = self.future_item()
        self.assertTrue(self.service.delete([item["id"]])["success"])
        ForecastReconciliationService(self.database).generate_occurrences(date.today(), date.today() + timedelta(days=365))
        deleted = next(i for i in self.service.snapshot()["items"] if i["id"] == item["id"])
        self.assertEqual(deleted["status"], "cancelled")
        self.assertEqual(deleted["statusLabel"], "Supprimée")
        self.assertTrue(deleted["canRestore"])
        self.assertFalse(deleted["canEdit"])
        self.assertTrue(self.service.restore(item["id"])["success"])
        restored = next(i for i in self.service.snapshot()["items"] if i["id"] == item["id"])
        self.assertIn(restored["status"], {"planned", "overdue"})

    def test_no_forecast_can_be_dated_before_today(self):
        past = next(i for i in self.service.snapshot()["items"] if i["status"] == "overdue" and i["canShift"])
        result = self.service.update(past["id"], {"date": past["date"], "amount": -10, "label": "x", "category": ""})
        self.assertFalse(result["success"])
        self.assertIn("antérieure", result["message"])
        refused = self.service.shift([past["id"]], date.today().isoformat())
        self.assertFalse(refused["success"])
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        self.assertTrue(self.service.shift([past["id"]], tomorrow)["success"])
        moved = next(i for i in self.service.snapshot()["items"] if i["id"] == past["id"])
        self.assertEqual(moved["date"], tomorrow)
        self.assertEqual(moved["originalDate"], past["date"])

    def test_postpone_moves_overdue_occurrences_to_the_next_cadence_date(self):
        overdue = [i for i in self.service.snapshot()["items"] if i["status"] == "overdue" and i["canShift"] and i["frequency"] == "Mensuel"][:2]
        self.assertTrue(overdue)
        result = self.service.postpone([i["id"] for i in overdue])
        self.assertTrue(result["success"], result)
        after = {i["id"]: i for i in self.service.snapshot()["items"]}
        for item in overdue:
            self.assertGreater(after[item["id"]]["date"], date.today().isoformat())
            self.assertLessEqual(after[item["id"]]["date"], (date.today() + timedelta(days=31)).isoformat())
            self.assertNotEqual(after[item["id"]]["status"], "overdue")

    def test_ghost_reconciliation_state_is_repaired_and_lock_reason_explained(self):
        _, tx_id, occurrence_id = make_pair(self.database)
        with self.database.connect() as conn:
            # État fantôme : occurrence « en retard » qui référence une transaction sans lien actif.
            conn.execute("UPDATE forecast_occurrences SET status = 'overdue', actual_transaction_id = ? WHERE id = ?", (tx_id, occurrence_id))
        item = next(i for i in self.service.snapshot()["items"] if i["id"] == occurrence_id)
        self.assertTrue(item["canShift"], item)
        self.assertEqual(item["lockReason"], "")
        ForecastReconciliationService(self.database).confirm_manual_match(occurrence_id, tx_id)
        locked = next(i for i in self.service.snapshot()["items"] if i["id"] == occurrence_id)
        self.assertFalse(locked["canShift"])
        self.assertIn("rapprochement", locked["lockReason"])

    def test_reconciled_occurrence_cannot_be_edited_shifted_or_deleted(self):
        _, tx_id, occurrence_id = make_pair(self.database)
        ForecastReconciliationService(self.database).confirm_manual_match(occurrence_id, tx_id)
        item = next(i for i in self.service.snapshot()["items"] if i["id"] == occurrence_id)
        self.assertTrue(item["reconciled"])
        self.assertFalse(item["canEdit"])
        self.assertFalse(self.service.update(occurrence_id, {"date": item["date"], "amount": -1, "label": "x", "category": ""})["success"])
        self.assertFalse(self.service.shift([occurrence_id], date.today().isoformat())["success"])
        self.assertFalse(self.service.delete([occurrence_id])["success"])


if __name__ == "__main__":
    unittest.main()
