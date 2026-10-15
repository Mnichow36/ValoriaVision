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


if __name__ == "__main__":
    unittest.main()
