from __future__ import annotations

import unittest

from app.services.categorization_rule_service import CategorizationRuleService


class CategorizationRuleSuggestionTest(unittest.TestCase):
    def test_extracts_merchant_after_card_reference_and_date(self):
        self.assertEqual(
            CategorizationRuleService.suggest_keyword_from_label(
                "CARTE X7693 05/06 — LIDL 3011"
            ),
            "LIDL",
        )

    def test_keeps_meaningful_multiword_merchants(self):
        cases = {
            "PRLV SEPA BOUYGUES TELECOM FR": "BOUYGUES TELECOM",
            "LIBRAIRIE DU CENTRE": "LIBRAIRIE DU CENTRE",
            "D.G.F.I.P. IMPOT": "DGFIP IMPOT",
            "VIREMENT RECU DE ARRCO": "ARRCO",
            "C ET A": "C ET A",
            "SC-DELICES": "SC DELICES",
        }
        for label, expected in cases.items():
            with self.subTest(label=label):
                self.assertEqual(
                    CategorizationRuleService.suggest_keyword_from_label(label),
                    expected,
                )

    def test_beneficiary_rules_match_the_counterparty_not_the_raw_label(self):
        rule = {
            "target_deleted": None,
            "account_id": None,
            "transaction_type": None,
            "min_amount": None,
            "max_amount": None,
            "match_field": "beneficiary",
            "match_operator": "contains",
            "match_value": "LIDL",
        }
        transaction = {
            "account_id": 7,
            "amount": -72.5,
            "label": "CARTE X7693 05/06 — LIDL 3011",
            "beneficiary": "LIDL",
        }

        matches, reason = CategorizationRuleService(None).rule_matches(rule, transaction)

        self.assertTrue(matches)
        self.assertIn("Bénéficiaire", reason)


if __name__ == "__main__":
    unittest.main()
