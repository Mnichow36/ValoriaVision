from __future__ import annotations

from collections.abc import Iterable

from app.services.reconciliation.candidate_service import rank_candidates
from app.services.reconciliation.models import ForecastInput, QualificationResult, TransactionInput
from app.services.reconciliation.rules import ReconciliationRules


def qualify(
    transaction: TransactionInput,
    forecasts: Iterable[ForecastInput],
    rules: ReconciliationRules | None = None,
) -> QualificationResult:
    rules = rules or ReconciliationRules()
    candidates = rank_candidates(transaction, forecasts, rules)
    if not candidates:
        return QualificationResult(
            status="without_forecast",
            transaction_id=transaction.id,
            best_candidate=None,
            candidates=(),
            ambiguity_delta=None,
            reason="Aucune prévision plausible",
        )

    best = candidates[0]
    delta = float(best.score - candidates[1].score) if len(candidates) > 1 else 100.0
    if best.score >= rules.auto_threshold and delta >= rules.ambiguity_min_delta:
        return QualificationResult(
            status="automatic",
            transaction_id=transaction.id,
            best_candidate=best,
            candidates=candidates,
            ambiguity_delta=delta,
            reason="Candidat unique ou nettement supérieur au seuil automatique",
        )

    reason = (
        "Plusieurs candidats sont trop proches"
        if len(candidates) > 1 and delta < rules.ambiguity_min_delta
        else "Score nécessitant une validation utilisateur"
    )
    return QualificationResult(
        status="review",
        transaction_id=transaction.id,
        best_candidate=best,
        candidates=candidates,
        ambiguity_delta=delta,
        reason=reason,
    )

