from __future__ import annotations

from collections.abc import Iterable

from app.services.reconciliation.models import CandidateScore, ForecastInput, TransactionInput
from app.services.reconciliation.rules import ReconciliationRules
from app.services.reconciliation.scoring import score_candidate


def rank_candidates(
    transaction: TransactionInput,
    forecasts: Iterable[ForecastInput],
    rules: ReconciliationRules | None = None,
) -> tuple[CandidateScore, ...]:
    rules = rules or ReconciliationRules()
    candidates = [
        candidate
        for forecast in forecasts
        if (candidate := score_candidate(transaction, forecast, rules)) is not None
    ]
    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                -item.score,
                item.date_delta_days,
                item.amount_delta,
                item.forecast.id,
            ),
        )
    )

