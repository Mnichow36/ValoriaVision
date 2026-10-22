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
