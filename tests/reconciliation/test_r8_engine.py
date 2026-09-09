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

    def test_date_tolerance_covers_reference_offsets_and_boundaries(self) -> None:
        for offset in (0, -1, 1, -3, 3, -5, 5):
            with self.subTest(offset=offset):
                candidate = replace(
                    self.forecast,
                    expected_date=self.transaction.tx_date + timedelta(days=offset),
                )
                self.assertIsNotNone(
                    score_candidate(self.transaction, candidate, self.rules)
                )

        for offset in (-6, 6):
            with self.subTest(offset=offset):
                outside = replace(
                    self.forecast,
                    expected_date=self.transaction.tx_date + timedelta(days=offset),
                )
                self.assertIsNone(
                    score_candidate(self.transaction, outside, self.rules)
                )

    def test_amount_tolerance_covers_absolute_and_relative_boundaries(self) -> None:
        small_transaction = replace(self.transaction, amount=-50.0)
        small_forecast = replace(self.forecast, expected_amount=-50.0)
        for amount in (-50.0, -50.99, -51.0):
            with self.subTest(tolerance="absolute", amount=amount):
                candidate = replace(small_forecast, expected_amount=amount)
                self.assertIsNotNone(
                    score_candidate(small_transaction, candidate, self.rules)
                )
        self.assertIsNone(
            score_candidate(
                small_transaction,
                replace(small_forecast, expected_amount=-51.01),
                self.rules,
            )
        )

        for amount in (-900.0, -908.99, -909.0):
            with self.subTest(tolerance="relative", amount=amount):
                candidate = replace(self.forecast, expected_amount=amount)
                self.assertIsNotNone(
                    score_candidate(self.transaction, candidate, self.rules)
                )
        self.assertIsNone(
            score_candidate(
                self.transaction,
                replace(self.forecast, expected_amount=-909.01),
                self.rules,
            )
        )

    def test_decimal_conversion_avoids_float_boundary_artifacts(self) -> None:
        transaction = replace(self.transaction, amount=-(0.1 + 0.2))
        forecast = replace(self.forecast, expected_amount=-0.3)
        exact_rules = replace(
            self.rules,
            amount_tolerance_absolute=0.0,
            amount_tolerance_relative=0.0,
        )
        candidate = score_candidate(transaction, forecast, exact_rules)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.amount_delta, 0.0)

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

    def test_date_and_amount_tolerances_are_configurable(self) -> None:
        date_candidate = replace(
            self.forecast,
            expected_date=self.transaction.tx_date + timedelta(days=2),
        )
        self.assertIsNotNone(
            score_candidate(
                self.transaction,
                date_candidate,
                replace(self.rules, date_tolerance_days=2),
            )
        )
        self.assertIsNone(
            score_candidate(
                self.transaction,
                date_candidate,
                replace(self.rules, date_tolerance_days=1),
            )
        )

        amount_candidate = replace(self.forecast, expected_amount=-902.0)
        self.assertIsNotNone(
            score_candidate(
                self.transaction,
                amount_candidate,
                replace(
                    self.rules,
                    amount_tolerance_absolute=2.0,
                    amount_tolerance_relative=0.0,
                ),
            )
        )
        self.assertIsNone(
            score_candidate(
                self.transaction,
                amount_candidate,
                replace(
                    self.rules,
                    amount_tolerance_absolute=1.99,
                    amount_tolerance_relative=0.0,
                ),
            )
        )

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
