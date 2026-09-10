from __future__ import annotations

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from difflib import SequenceMatcher

from app.services.reconciliation.models import (
    CandidateScore,
    CriterionScore,
    ForecastInput,
    TransactionInput,
)
from app.services.reconciliation.rules import ReconciliationRules


def normalize_label(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.casefold()
    normalized = re.sub(r"\b(?:cb|carte|virement|vir|prlv|prelevement)\b", " ", normalized)
    normalized = re.sub(r"\d{4,}", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def normalize_reference(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]+", "", (value or "").upper())


def score_candidate(
    transaction: TransactionInput,
    forecast: ForecastInput,
    rules: ReconciliationRules,
) -> CandidateScore | None:
    if rules.same_account_required and transaction.account_id != forecast.account_id:
        return None
    if rules.same_direction_required and transaction.direction != forecast.direction:
        return None

    date_delta = abs((transaction.tx_date - forecast.expected_date).days)
    if date_delta > rules.date_tolerance_days:
        return None

    # Convert through str to avoid binary floating-point artefacts at the
    # exact acceptance boundaries while keeping the public input API compatible.
    cent = Decimal("0.01")
    transaction_amount = abs(
        Decimal(str(transaction.amount)).quantize(cent, rounding=ROUND_HALF_UP)
    )
    forecast_amount = abs(
        Decimal(str(forecast.expected_amount)).quantize(cent, rounding=ROUND_HALF_UP)
    )
    amount_delta = abs(transaction_amount - forecast_amount)

    # The observed transaction is the fixed reference. A candidate must not
    # enlarge its own acceptance window merely by carrying a higher amount.
    reference_amount = max(transaction_amount, Decimal("0.01"))
    amount_tolerance = max(
        Decimal(str(rules.amount_tolerance_absolute)),
        reference_amount * Decimal(str(rules.amount_tolerance_relative)),
    )
    if amount_delta > amount_tolerance:
        return None

    if rules.date_tolerance_days == 0:
        date_ratio = 1.0
    else:
        date_ratio = 1.0 - (date_delta / (rules.date_tolerance_days + 1))
    date_points = rules.date_weight * max(0.0, date_ratio)

    if amount_tolerance == 0:
        amount_ratio = 1.0
    else:
        amount_ratio = float(
            Decimal("1") - (amount_delta / (amount_tolerance + Decimal("0.01")))
        )
    amount_points = rules.amount_weight * max(0.0, amount_ratio)

    actual_label = normalize_label(transaction.label)
    expected_label = normalize_label(forecast.expected_label)
    label_ratio = (
        SequenceMatcher(None, actual_label, expected_label).ratio()
        if actual_label and expected_label
        else 0.0
    )
    if (
        rules.label_similarity_minimum > 0
        and actual_label
        and expected_label
        and label_ratio < rules.label_similarity_minimum
    ):
        return None
    label_points = rules.label_weight * label_ratio

    actual_counterparty = normalize_label(transaction.counterparty)
    expected_counterparty = normalize_label(forecast.counterparty)
    counterparties_match = bool(
        actual_counterparty
        and expected_counterparty
        and actual_counterparty == expected_counterparty
    )
    counterparty_points = (
        rules.counterparty_match_bonus if counterparties_match else 0.0
    )

    actual_reference = normalize_reference(transaction.external_reference)
    expected_reference = normalize_reference(forecast.external_reference)
    references_match = bool(
        actual_reference
        and expected_reference
        and actual_reference == expected_reference
    )
    reference_points = (
        rules.external_reference_match_bonus if references_match else 0.0
    )

    categories_match = bool(
        transaction.category
        and forecast.category
        and normalize_label(transaction.category) == normalize_label(forecast.category)
    )
    category_points = rules.category_weight if categories_match else 0.0

    criteria = (
        CriterionScore(
            "account",
            0,
            0,
            f"Compte identique ({transaction.account_id})",
        ),
        CriterionScore(
            "direction",
            0,
            0,
            f"Sens identique ({transaction.direction})",
        ),
        CriterionScore(
            "date",
            round(date_points, 2),
            rules.date_weight,
            f"Écart de {date_delta} jour(s)",
        ),
        CriterionScore(
            "amount",
            round(amount_points, 2),
            rules.amount_weight,
            f"Écart de {amount_delta:.2f} €",
        ),
        CriterionScore(
            "label",
            round(label_points, 2),
            rules.label_weight,
            f"Similarité de libellé {label_ratio:.0%}",
        ),
        CriterionScore(
            "category",
            round(category_points, 2),
            rules.category_weight,
            "Catégorie identique" if categories_match else "Catégorie absente ou différente",
        ),
        CriterionScore(
            "counterparty",
            round(counterparty_points, 2),
            rules.counterparty_match_bonus,
            "Bénéficiaire/émetteur identique"
            if counterparties_match
            else "Bénéficiaire/émetteur indisponible ou différent",
        ),
        CriterionScore(
            "external_reference",
            round(reference_points, 2),
            rules.external_reference_match_bonus,
            "Référence bancaire identique"
            if references_match
            else "Référence bancaire indisponible ou différente",
        ),
    )
    total = min(100, max(0, round(sum(item.points for item in criteria))))
    return CandidateScore(
        forecast=forecast,
        score=total,
        date_delta_days=date_delta,
        amount_delta=float(amount_delta.quantize(Decimal("0.01"))),
        criteria=criteria,
    )
