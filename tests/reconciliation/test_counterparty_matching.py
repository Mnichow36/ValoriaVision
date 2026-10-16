from __future__ import annotations

import unittest

from app.services.forecast_reconciliation_service import ForecastReconciliationService


class LegacyReconciliationCounterpartyTests(unittest.TestCase):
    def test_score_uses_the_same_identified_counterparty_as_bank_import(self) -> None:
        engine = object.__new__(ForecastReconciliationService)
        engine.rules_config = lambda: {
            "require_same_account": True,
            "require_same_direction": True,
            "amount_tolerance_abs": 1.0,
            "amount_tolerance_percent": 1.0,
            "date_tolerance_days": 5,
            "label_similarity_min": 60,
        }
        occurrence = {
            "id": 11,
            "account_id": 1,
            "direction": "debit",
            "expected_amount": -72.50,
            "expected_date": "2026-06-05",
            "expected_label": "LIDL",
            "expected_category": "Alimentation",
        }
        transaction = {
            "id": 7,
            "account_id": 1,
            "amount": -72.50,
            "tx_date": "2026-06-05",
            "label": "CARTE X7693 05/06 — LIDL 3011",
            "beneficiary": "LIDL",
            "category": "Alimentation",
            "source_identifier": None,
        }

        score, reason = engine.compute_match_score(occurrence, transaction)

        self.assertEqual(score, 100)
        self.assertIn("tiers identifié identique +5", reason)


if __name__ == "__main__":
    unittest.main()
