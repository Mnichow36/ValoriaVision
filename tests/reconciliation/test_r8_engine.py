from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date, timedelta

from app.services.reconciliation import (
    ForecastInput,
    ReconciliationRules,
    TransactionInput,
    qualify,
)
from app.services.reconciliation.scoring import normalize_label, score_candidate


class R8EngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = ReconciliationRules()
        self.transaction = TransactionInput(
            id=1,
            account_id=10,
            tx_date=date(2026, 6, 9),
            amount=-900.0,
            label="PRLV LOYER DUPONT 12345678",
            direction="debit",
            category="Logement",
        )
        self.forecast = ForecastInput(
            id=101,
            account_id=10,
            expected_date=date(2026, 6, 9),
            expected_amount=-900.0,
            expected_label="Loyer Dupont",
            direction="debit",
            category="Logement",
        )

    def test_exact_candidate_is_automatic_and_explainable(self) -> None:
        result = qualify(self.transaction, [self.forecast], self.rules)
        self.assertEqual(result.status, "automatic")
        self.assertEqual(result.best_candidate.score, 100)
        self.assertEqual(
            {criterion.criterion for criterion in result.best_candidate.criteria},
            {"account", "direction", "date", "amount", "label", "category"},
        )

    def test_different_account_is_never_candidate(self) -> None:
        result = qualify(
            self.transaction,
            [replace(self.forecast, account_id=11)],
            self.rules,
        )
        self.assertEqual(result.status, "without_forecast")

    def test_opposite_direction_is_never_candidate(self) -> None:
        result = qualify(
            self.transaction,
            [replace(self.forecast, direction="credit")],
            self.rules,
        )
        self.assertEqual(result.status, "without_forecast")

    def test_date_at_tolerance_is_candidate_but_limit_plus_one_is_not(self) -> None:
        at_limit = replace(
            self.forecast,
            expected_date=self.transaction.tx_date + timedelta(days=5),
        )
        outside = replace(
            self.forecast,
            id=102,
            expected_date=self.transaction.tx_date + timedelta(days=6),
        )
        self.assertIsNotNone(score_candidate(self.transaction, at_limit, self.rules))
        self.assertIsNone(score_candidate(self.transaction, outside, self.rules))

    def test_amount_at_tolerance_is_candidate_but_above_is_not(self) -> None:
        at_limit = replace(self.forecast, expected_amount=-909.0)
        outside = replace(self.forecast, id=102, expected_amount=-909.01)
        self.assertIsNotNone(score_candidate(self.transaction, at_limit, self.rules))
        self.assertIsNone(score_candidate(self.transaction, outside, self.rules))

    def test_two_close_high_scores_require_review(self) -> None:
        second = replace(self.forecast, id=102, expected_label="Loyer Dupont résidence")
        result = qualify(self.transaction, [self.forecast, second], self.rules)
        self.assertEqual(result.status, "review")
        self.assertLess(result.ambiguity_delta, self.rules.ambiguity_min_delta)

    def test_clear_score_lead_allows_automatic(self) -> None:
        second = replace(
            self.forecast,
            id=102,
            expected_date=date(2026, 6, 12),
            expected_label="Échéance habitation",
            category=None,
        )
        result = qualify(self.transaction, [second, self.forecast], self.rules)
        self.assertEqual(result.status, "automatic")
        self.assertGreaterEqual(result.ambiguity_delta, self.rules.ambiguity_min_delta)

    def test_missing_category_does_not_eliminate_candidate(self) -> None:
        result = qualify(
            self.transaction,
            [replace(self.forecast, category=None)],
            self.rules,
        )
        self.assertIsNotNone(result.best_candidate)

    def test_thresholds_are_configurable(self) -> None:
        weak = replace(self.forecast, expected_label="Échéance mensuelle")
        strict = replace(self.rules, auto_threshold=100)
        result = qualify(self.transaction, [weak], strict)
        self.assertEqual(result.status, "review")

    def test_label_normalization_ignores_bank_prefix_accents_and_long_numbers(self) -> None:
        self.assertEqual(
            normalize_label("PRÉLÈVEMENT CAFÉ-DUPONT 12345678"),
            normalize_label("cafe dupont"),
        )

    def test_invalid_weight_total_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "somme des poids"):
            ReconciliationRules(label_weight=29)


if __name__ == "__main__":
    unittest.main()
