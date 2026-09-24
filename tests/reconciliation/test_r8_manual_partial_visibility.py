"""A partial candidate stays selectable even outside auto-match amount tolerance."""

import sqlite3
import unittest
from datetime import date

from app.services.forecast_reconciliation_service import ForecastReconciliationService


class ManualPartialVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.service = ForecastReconciliationService.__new__(ForecastReconciliationService)
        self.service.rules_config = lambda: {
            "date_tolerance_days": 5, "label_similarity_min": 45,
            "require_same_account": True, "require_same_direction": True,
        }
        self.occurrence = {
            "id": 1, "account_id": 1, "direction": "debit", "expected_date": "2026-09-28",
            "expected_amount": -150, "remaining_amount": 150,
            "expected_label": "TEST MULTI 150", "status": "planned",
        }
        self.transaction = {
            "id": 2, "account_id": 1, "tx_date": "2026-09-28", "amount": -100,
            "label": "TEST MULTI 100", "allocated_amount": 0, "linked_occurrence_id": None,
        }

    def test_partial_candidate_visible_only_with_relevant_account_sense_date_and_label(self):
        service = self.service
        service._eligible_transactions = lambda *args: [self.transaction]
        service._eligible_occurrences = lambda *args: [self.occurrence]
        service._eligible_proposals = lambda *args: []
        service.find_candidates = lambda tx: [{"occurrence": self.occurrence, "score": 0}]
        service.decision_for_candidates = lambda candidates: "unmatched"
        service._summary_from_occurrences = lambda rows: {"active": len(rows), "all": len(rows)}

        def visible():
            return service.build_reconciliation_dataset(
                "2026-09-21", "2026-09-30", account_id=1, status="active"
            )["transactions"]

        self.assertEqual(len(visible()), 1)
        for change in ({"account_id": 2}, {"direction": "credit"},
                       {"expected_date": "2026-10-20"}, {"expected_label": "LOYER"}):
            original = dict(self.occurrence)
            self.occurrence.update(change)
            self.assertEqual(visible(), [], change)
            self.occurrence.update(original)

    def test_second_transaction_can_consider_partially_matched_occurrence(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE accounts(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO accounts VALUES(1, 'Compte test')")
        conn.execute("""CREATE TABLE forecast_occurrences (
            id INTEGER PRIMARY KEY, account_id INTEGER, direction TEXT, expected_date TEXT,
            expected_amount REAL, expected_label TEXT, remaining_amount REAL, status TEXT,
            actual_transaction_id INTEGER, deleted_at TEXT
        )""")
        conn.execute("""INSERT INTO forecast_occurrences VALUES
            (1, 1, 'debit', '2026-09-28', -150, 'TEST MULTI 150', 50,
             'partially_matched', 2, NULL)""")
        class DB:
            def connect(self):
                return conn
        self.service.db = DB()
        self.service.compute_match_score = lambda occ, tx: (0, "hors tolérance auto")
        second = dict(self.transaction, id=3, amount=-50, label="TEST MULTI 50")
        candidates = self.service.find_candidates(second)
        self.assertEqual(len(candidates), 1)
        self.assertTrue(self.service._manual_partial_candidate(second, candidates[0]["occurrence"]))


if __name__ == "__main__":
    unittest.main()
