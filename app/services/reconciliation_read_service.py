from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Callable


STATUS_LABELS = {
    "planned": "Prévue",
    "to_review": "À vérifier",
    "partially_matched": "Partiellement rapprochée",
    "auto_matched": "Rapprochée automatiquement",
    "confirmed": "Rapprochée manuellement",
    "overdue": "En retard",
    "ignored": "Ignorée",
    "cancelled": "Annulée",
}


def _field(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key] if key in row.keys() else default
    except (AttributeError, KeyError, TypeError):
        return default


def _number(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _integer(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class ReconciliationReadService:
    """Adapt the reconciliation engine to the stable React read contract."""

    def __init__(
        self,
        database: Any,
        engine_factory: Callable[[Any], Any] | None = None,
        now_provider: Callable[[], datetime] = lambda: datetime.now().astimezone(),
    ) -> None:
        if engine_factory is None:
            # Kept lazy so this adapter can be contract-tested in isolation.
            from app.services.forecast_reconciliation_service import ForecastReconciliationService

            engine_factory = ForecastReconciliationService
        self.database = database
        self.engine_factory = engine_factory
        self.now_provider = now_provider

    def snapshot(self, account_id: int | None = None, status: str = "active") -> dict[str, Any]:
        engine = self.engine_factory(self.database)
        dataset = engine.build_reconciliation_dataset(
            account_id=account_id,
            status=status or "active",
            limit=150,
        )
        transactions = list(dataset.get("transactions") or [])
        occurrences = list(dataset.get("occurrences") or [])
        proposals = list(dataset.get("proposals") or [])
        mapped_transactions = [self._transaction(row) for row in transactions]
        mapped_occurrences = [self._occurrence(row, engine) for row in occurrences]
        mapped_suggestions = self._suggestions(engine, transactions, proposals)
        summary = dataset.get("summary") or {}
        average_score = (
            round(sum(item["score"] for item in mapped_suggestions) / len(mapped_suggestions))
            if mapped_suggestions
            else 0
        )
        rules = engine.rules_config()

        return {
            "generatedAt": self.now_provider().isoformat(),
            "currency": "EUR",
            "filters": {
                "accountId": account_id,
                "status": status or "active",
            },
            "accounts": [
                {
                    "id": int(_field(row, "id", 0) or 0),
                    "name": str(_field(row, "name", "Compte") or "Compte"),
                    "bank": str(_field(row, "bank", "") or ""),
                }
                for row in self.database.list_accounts()
                if str(_field(row, "status", "Actif") or "Actif") == "Actif"
            ],
            "statusOptions": [
                {"id": "active", "label": "À traiter"},
                {"id": "to_review", "label": "À vérifier"},
                {"id": "partially_matched", "label": "Partielles"},
                {"id": "finalized", "label": "Finalisées"},
                {"id": "all", "label": "Tous les statuts"},
            ],
            "rules": {
                "automaticThreshold": int(rules.get("auto_match_threshold") or 90),
                "reviewThreshold": int(rules.get("review_threshold") or 60),
                "dateToleranceDays": int(rules.get("date_tolerance_days") or 5),
            },
            "summary": {
                "unmatchedTransactions": len(mapped_transactions),
                "openOccurrences": int(summary.get("active") or 0),
                "automaticProposals": len(mapped_suggestions),
                "averageScore": average_score,
                "matched": int(summary.get("auto_matched") or 0) + int(summary.get("confirmed") or 0),
                "toReview": int(summary.get("to_review") or 0),
                "partial": int(summary.get("partially_matched") or 0),
            },
            "transactions": mapped_transactions,
            "occurrences": mapped_occurrences,
            "suggestions": mapped_suggestions,
        }

    def reschedulable_occurrences(self, account_id: int | None = None) -> dict[str, Any]:
        reference = self._reference_date()
        engine = self.engine_factory(self.database)
        rows = engine.list_reschedulable_occurrences(account_id, reference)
        items = []
        for row in rows:
            status = str(_field(row, "status", "planned") or "planned")
            occurrence_date = str(_field(row, "expected_date", "") or "")
            effective_status = "overdue" if status == "planned" and occurrence_date < reference.isoformat() else status
            items.append({
                "id": int(_field(row, "id", 0) or 0),
                "date": occurrence_date,
                "originalDate": str(_field(row, "original_expected_date", occurrence_date) or occurrence_date),
                "label": str(_field(row, "expected_label", "Échéance") or "Échéance"),
                "amount": _number(_field(row, "expected_amount", 0)),
                "category": str(_field(row, "expected_category", "") or "Sans catégorie"),
                "direction": str(_field(row, "direction", "") or ""),
                "accountId": _integer(_field(row, "account_id")),
                "accountName": str(_field(row, "account_name", "Compte") or "Compte"),
                "bank": str(_field(row, "bank", "") or ""),
                "frequency": str(_field(row, "recurring_frequency", "") or ""),
                "status": effective_status,
                "statusLabel": STATUS_LABELS.get(effective_status, effective_status),
                "alreadyRescheduled": bool(
                    _field(row, "original_expected_date")
                    and str(_field(row, "original_expected_date")) != occurrence_date
                ),
            })
        return {
            "referenceDate": reference.isoformat(),
            "minTargetDate": (reference + timedelta(days=1)).isoformat(),
            "items": items,
        }

    def reschedule_occurrences(
        self,
        occurrence_ids: list[int],
        target_date: str,
    ) -> dict[str, Any]:
        reference = self._reference_date()
        count, message = self.engine_factory(self.database).reschedule_occurrences(
            occurrence_ids,
            target_date,
            reference_date=reference,
        )
        return {
            "success": count > 0,
            "message": message,
            "updatedCount": int(count),
            "targetDate": target_date,
            "referenceDate": reference.isoformat(),
            "occurrenceIds": list(dict.fromkeys(int(value) for value in occurrence_ids)),
        }

    def _reference_date(self) -> date:
        current_time = self.now_provider()
        return (
            current_time.astimezone().date()
            if current_time.tzinfo is not None
            else current_time.date()
        )

    def confirm_proposal(self, proposal_id: int) -> dict[str, Any]:
        return self._action_result(self.engine_factory(self.database).confirm_proposal(proposal_id))

    def reject_proposal(self, proposal_id: int) -> dict[str, Any]:
        return self._action_result(self.engine_factory(self.database).reject_proposal(proposal_id))

    def confirm_manual_match(
        self,
        occurrence_id: int,
        transaction_id: int,
        *,
        include_overage: bool = False,
    ) -> dict[str, Any]:
        return self._action_result(
            self.engine_factory(self.database).confirm_manual_match(
                occurrence_id,
                transaction_id,
                include_overage=include_overage,
            )
        )

    @staticmethod
    def _action_result(result: tuple[Any, str]) -> dict[str, Any]:
        changed, message = result
        return {"success": bool(changed), "message": str(message or "")}

    @staticmethod
    def _transaction(row: Any) -> dict[str, Any]:
        amount = _number(_field(row, "amount", 0))
        allocated = _number(_field(row, "allocated_amount", 0))
        linked_status = str(_field(row, "linked_status", "") or "")
        return {
            "id": int(_field(row, "id", 0) or 0),
            "date": str(_field(row, "tx_date", "") or ""),
            "label": str(_field(row, "label", "Transaction") or "Transaction"),
            "beneficiary": str(_field(row, "beneficiary", "") or ""),
            "amount": amount,
            "remainingAmount": round(max(abs(amount) - allocated, 0), 2),
            "category": str(_field(row, "category", "") or "À catégoriser"),
            "accountId": int(_field(row, "account_id", 0) or 0),
            "accountName": str(_field(row, "account_name", "Compte") or "Compte"),
            "bank": str(_field(row, "bank", "") or ""),
            "linkedStatus": linked_status or None,
            "linkedStatusLabel": STATUS_LABELS.get(linked_status, linked_status) if linked_status else None,
            "linkedOccurrenceId": _integer(_field(row, "linked_occurrence_id")),
            "proposalOccurrenceId": _integer(_field(row, "proposal_occurrence_id")),
        }

    @staticmethod
    def _occurrence(row: Any, engine: Any) -> dict[str, Any]:
        status = str(_field(row, "status", "planned") or "planned")
        expected_amount = _number(_field(row, "expected_amount", 0))
        remaining = _field(row, "remaining_amount")
        return {
            "id": int(_field(row, "id", 0) or 0),
            "date": str(_field(row, "expected_date", "") or ""),
            "label": str(_field(row, "expected_label", "Prévision") or "Prévision"),
            "amount": expected_amount,
            "category": str(_field(row, "expected_category", "") or "Sans catégorie"),
            "direction": str(_field(row, "direction", "") or ""),
            "accountId": _integer(_field(row, "account_id")),
            "accountName": str(_field(row, "account_name", "Tous les comptes") or "Tous les comptes"),
            "bank": str(_field(row, "bank", "") or ""),
            "status": status,
            "statusLabel": str(engine.status_label(status) or STATUS_LABELS.get(status, status)),
            "matchedAmount": _number(_field(row, "matched_amount", 0)),
            "remainingAmount": _number(abs(expected_amount) if remaining is None else remaining),
            "overageAmount": _number(_field(row, "overage_amount", 0)),
            "matchConfidence": _integer(_field(row, "match_confidence")),
            "matchReason": str(_field(row, "match_reason", "") or ""),
        }

    @staticmethod
    def _suggestions(engine: Any, transactions: list[Any], proposals: list[Any]) -> list[dict[str, Any]]:
        saved = {
            (int(_field(row, "transaction_id", 0) or 0), int(_field(row, "occurrence_id", 0) or 0)): row
            for row in proposals
        }
        suggestions = []
        for transaction in transactions:
            candidates = list(engine.find_candidates(transaction) or [])
            if not candidates:
                continue
            candidate = candidates[0]
            occurrence = candidate["occurrence"]
            transaction_id = int(_field(transaction, "id", 0) or 0)
            occurrence_id = int(_field(occurrence, "id", 0) or 0)
            proposal = saved.get((transaction_id, occurrence_id))
            score = int(candidate.get("score") or 0)
            suggestions.append(
                {
                    "proposalId": _integer(_field(proposal, "id")) if proposal is not None else None,
                    "transactionId": transaction_id,
                    "occurrenceId": occurrence_id,
                    "score": score,
                    "reason": str(candidate.get("reason") or "Critères insuffisants."),
                    "decision": str(engine.decision_for_candidates(candidates) or "unmatched"),
                    "amountDifference": _number(
                        abs(abs(_number(_field(transaction, "amount", 0))) - abs(_number(_field(occurrence, "expected_amount", 0))))
                    ),
                }
            )
        return suggestions
