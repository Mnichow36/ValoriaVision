from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Callable


# Cycle de statuts validé le 22/10/2026 : Prévue, En retard, Rapprochée,
# Écart de montant, Ignorée. « Confirmé » n'existe plus côté utilisateur.
STATUS_LABELS = {
    "planned": "Prévue",
    "to_review": "À vérifier",
    "partially_matched": "Écart de montant",
    "auto_matched": "Rapprochée",
    "confirmed": "Rapprochée",
    "overdue": "En retard",
    "ignored": "Ignorée",
    "cancelled": "Annulée",
}
DISPLAY_LABELS = {
    "planned": "Prévue",
    "overdue": "En retard",
    "to_review": "À vérifier",
    "matched": "Rapprochée",
    "amount_gap": "Écart de montant",
    "ignored": "Ignorée",
    "cancelled": "Annulée",
}
ACTIVE_STATUSES = {"planned", "overdue", "to_review", "partially_matched"}
FINAL_STATUSES = {"auto_matched", "confirmed", "ignored", "cancelled"}
ACTIVE_FILTERS = {None, "", "active", "all_active"}


def display_status(status: str, remaining: float = 0.0, overage: float = 0.0) -> str:
    """Statut affiché à l'utilisateur, dérivé du statut du moteur et des montants."""

    if status in {"auto_matched", "confirmed"}:
        return "amount_gap" if remaining > 0.005 or overage > 0.005 else "matched"
    if status == "partially_matched":
        return "amount_gap"
    return status


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
        requested = status or "active"
        links_by_transaction = self._active_links_by_transaction()
        links_by_occurrence: dict[int, list[dict[str, Any]]] = {}
        for links in links_by_transaction.values():
            for link in links:
                links_by_occurrence.setdefault(link["occurrence_id"], []).append(link)

        # Les compteurs et les propositions viennent TOUJOURS de la vue « à traiter »,
        # quel que soit le filtre choisi : un filtre ne change jamais un compteur (CDC P2).
        active_dataset = engine.build_reconciliation_dataset(account_id=account_id, status="active", limit=None)
        summary = active_dataset.get("summary") or {}
        proposals = list(active_dataset.get("proposals") or [])
        active_transactions = list(active_dataset.get("transactions") or [])

        manual_candidates: dict[int, dict[str, Any]] = {}
        if requested in ACTIVE_FILTERS:
            occurrences = list(active_dataset.get("occurrences") or [])
            # Exhaustivité (CDC P1) : une opération qui a une prévision de même compte,
            # même sens et même montant, mais à une autre date, ne doit pas disparaître.
            everything_for_manual = engine.build_reconciliation_dataset(account_id=account_id, status="all", limit=None)
            manual_candidates = self._manual_date_candidates(
                engine,
                list(everything_for_manual.get("transactions") or []),
                occurrences,
                {int(_field(row, "id", 0) or 0) for row in active_transactions},
            )
            extra = [row for row in everything_for_manual.get("transactions") or []
                     if int(_field(row, "id", 0) or 0) in manual_candidates]
            transactions = sorted(
                active_transactions + extra,
                key=lambda row: (str(_field(row, "tx_date", "")), int(_field(row, "id", 0) or 0)),
                reverse=True,
            )
        elif requested == "to_review":
            review = engine.build_reconciliation_dataset(account_id=account_id, status="to_review", limit=None)
            transactions = list(review.get("transactions") or [])
            occurrences = list(review.get("occurrences") or [])
        else:
            everything = engine.build_reconciliation_dataset(account_id=account_id, status="all", limit=None)
            occurrences = [
                row for row in everything.get("occurrences") or []
                if self._occurrence_in_filter(row, requested)
            ]
            transactions = self._transactions_in_filter(
                list(everything.get("transactions") or []),
                occurrences,
                links_by_transaction,
                requested,
            )

        shown_transactions = transactions[:150]
        shown_occurrences = occurrences[:150]
        mapped_transactions = [
            self._transaction(
                row,
                links_by_transaction.get(int(_field(row, "id", 0) or 0), []),
                manual_candidates.get(int(_field(row, "id", 0) or 0)),
            )
            for row in shown_transactions
        ]
        # Les prévisions proposées pour un rapprochement manuel doivent figurer dans la liste.
        shown_ids = {int(_field(row, "id", 0) or 0) for row in shown_occurrences}
        for candidate in manual_candidates.values():
            if candidate["occurrenceId"] not in shown_ids:
                match = next((row for row in occurrences if int(_field(row, "id", 0) or 0) == candidate["occurrenceId"]), None)
                if match is not None:
                    shown_occurrences.append(match)
                    shown_ids.add(candidate["occurrenceId"])
        mapped_occurrences = [
            self._occurrence(row, engine, links_by_occurrence.get(int(_field(row, "id", 0) or 0), []))
            for row in shown_occurrences
        ]
        mapped_suggestions = self._suggestions(engine, active_transactions[:150], proposals)
        average_score = (
            round(sum(item["score"] for item in mapped_suggestions) / len(mapped_suggestions))
            if mapped_suggestions
            else 0
        )
        rules = engine.rules_config()
        is_active_view = requested in ACTIVE_FILTERS or requested == "to_review"

        return {
            "generatedAt": self.now_provider().isoformat(),
            "currency": "EUR",
            "filters": {
                "accountId": account_id,
                "status": requested,
            },
            "view": {
                "transactionsTitle": "Transactions à rapprocher" if is_active_view else "Transactions rapprochées",
                "transactionsSubtitle": (
                    "Transactions compatibles avec au moins une prévision."
                    if is_active_view
                    else "Transactions liées à une prévision ou à une récurrence."
                ),
                "occurrencesTitle": "Prévisions à traiter" if is_active_view else "Prévisions du filtre choisi",
                "occurrencesSubtitle": (
                    "Récurrences et opérations ponctuelles ouvertes."
                    if is_active_view
                    else "Statut affiché = statut filtré ; les liens annulés restent dans l’historique."
                ),
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
                {"id": "matched", "label": "Rapprochées"},
                {"id": "amount_gap", "label": "Écart de montant"},
                {"id": "ignored", "label": "Ignorées / annulées"},
                {"id": "finalized", "label": "Finalisées"},
                {"id": "all", "label": "Tous les statuts"},
            ],
            "rules": {
                "automaticThreshold": int(rules.get("auto_match_threshold") or 90),
                "reviewThreshold": int(rules.get("review_threshold") or 60),
                "dateToleranceDays": int(rules.get("date_tolerance_days") or 5),
            },
            "summary": {
                "unmatchedTransactions": len(active_transactions) + len(manual_candidates),
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

    @staticmethod
    def _occurrence_in_filter(row: Any, requested: str) -> bool:
        raw = str(_field(row, "status", "planned") or "planned")
        shown = display_status(
            raw,
            _number(_field(row, "remaining_amount", 0)),
            _number(_field(row, "overage_amount", 0)),
        )
        if requested == "all":
            return True
        if requested == "finalized":
            return raw in FINAL_STATUSES
        if requested == "matched":
            return shown == "matched"
        if requested in {"amount_gap", "partially_matched"}:
            return shown == "amount_gap"
        if requested == "ignored":
            return raw in {"ignored", "cancelled"}
        return raw == requested

    @staticmethod
    def _transactions_in_filter(
        transactions: list[Any],
        occurrences: list[Any],
        links_by_transaction: dict[int, list[dict[str, Any]]],
        requested: str,
    ) -> list[Any]:
        if requested == "all":
            return transactions
        if requested == "ignored":
            return []
        allowed = {int(_field(row, "id", 0) or 0) for row in occurrences}
        return [
            row for row in transactions
            if any(
                link["occurrence_id"] in allowed
                for link in links_by_transaction.get(int(_field(row, "id", 0) or 0), [])
            )
        ]

    MANUAL_WINDOW_DAYS = 45

    def _manual_date_candidates(
        self,
        engine: Any,
        transactions: list[Any],
        occurrences: list[Any],
        already_listed: set[int],
    ) -> dict[int, dict[str, Any]]:
        """Opérations non rapprochées dont une prévision ouverte ne diffère que par la date."""

        rules = engine.rules_config()
        result: dict[int, dict[str, Any]] = {}
        for tx in transactions:
            tx_id = int(_field(tx, "id", 0) or 0)
            amount = _number(_field(tx, "amount", 0))
            allocated = _number(_field(tx, "allocated_amount", 0))
            if tx_id in already_listed or abs(amount) - allocated <= 0.005:
                continue
            direction = "credit" if amount >= 0 else "debit"
            tx_date = self._parse_day(_field(tx, "tx_date", ""))
            if tx_date is None:
                continue
            best: tuple[int, float, Any] | None = None
            for occ in occurrences:
                if int(_field(occ, "account_id", 0) or 0) != int(_field(tx, "account_id", 0) or 0):
                    continue
                if str(_field(occ, "direction", "")) != direction:
                    continue
                expected = abs(_number(_field(occ, "expected_amount", 0)))
                tolerance = max(
                    float(rules.get("amount_tolerance_abs", 1.0)),
                    expected * float(rules.get("amount_tolerance_percent", 2.0)) / 100.0,
                )
                if abs(abs(amount) - expected) > tolerance:
                    continue
                occ_date = self._parse_day(_field(occ, "expected_date", ""))
                if occ_date is None:
                    continue
                gap = abs((tx_date - occ_date).days)
                if gap > self.MANUAL_WINDOW_DAYS:
                    continue
                key = (gap, abs(abs(amount) - expected))
                if best is None or key < (best[0], best[1]):
                    best = (gap, key[1], occ)
            if best is not None:
                gap, _, occ = best
                label = str(_field(occ, "expected_label", "Prévision") or "Prévision")
                occ_day = str(_field(occ, "expected_date", ""))
                result[tx_id] = {
                    "occurrenceId": int(_field(occ, "id", 0) or 0),
                    "label": label,
                    "date": occ_day,
                    "dayGap": gap,
                    "reason": f"Même montant et même compte que « {label} » prévue le {occ_day}, "
                              f"mais {gap} jour(s) d’écart : rapprochement manuel proposé.",
                }
        return result

    @staticmethod
    def _parse_day(value: Any):
        from datetime import date as _date
        try:
            return _date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    def _active_links_by_transaction(self) -> dict[int, list[dict[str, Any]]]:
        provider = getattr(self.database, "active_reconciliation_by_transaction", None)
        return dict(provider()) if callable(provider) else {}

    def cancel_reconciliation(self, occurrence_id: int, transaction_id: int | None = None) -> dict[str, Any]:
        """Annule un rapprochement sans jamais effacer la trace du lien."""

        engine = self.engine_factory(self.database)
        if transaction_id is not None:
            result = engine.cancel_reconciliation_link(int(occurrence_id), int(transaction_id))
        else:
            result = engine.cancel_match(int(occurrence_id))
        return self._action_result(result)

    def history(self, transaction_id: int | None = None, occurrence_id: int | None = None) -> dict[str, Any]:
        """Historique des liens (actifs et annulés) d'une transaction ou d'une prévision."""

        provider = getattr(self.database, "reconciliation_links", None)
        links = (
            provider(include_cancelled=True, transaction_id=transaction_id, occurrence_id=occurrence_id)
            if callable(provider)
            else []
        )
        return {"items": [self._history_item(link) for link in links]}

    @staticmethod
    def _link_summary(link: dict[str, Any]) -> dict[str, Any]:
        return {
            "linkId": link["link_id"],
            "transactionId": link["transaction_id"],
            "occurrenceId": link["occurrence_id"],
            "label": link["recurrence_name"] or link["occurrence_label"],
            "sourceType": link["source_type"],
            "appliedAmount": _number(link["applied_amount"]),
            "matchType": link["match_type"],
        }

    @classmethod
    def _history_item(cls, link: dict[str, Any]) -> dict[str, Any]:
        return {
            **cls._link_summary(link),
            "occurrenceLabel": link["occurrence_label"],
            "occurrenceDate": link["occurrence_date"],
            "occurrenceAmount": _number(link["occurrence_amount"]),
            "recurrenceName": link["recurrence_name"],
            "transactionLabel": link["transaction_label"],
            "transactionDate": link["transaction_date"],
            "transactionAmount": _number(link["transaction_amount"]),
            "confidence": _integer(link["confidence"]),
            "reason": link["reason"],
            "createdAt": link["created_at"],
            "cancelledAt": link["cancelled_at"],
            "active": bool(link["active"]),
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

    @classmethod
    def _transaction(
        cls,
        row: Any,
        links: list[dict[str, Any]] | None = None,
        manual_candidate: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        links = links or []
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
            "manualCandidate": manual_candidate,
            "linkedStatus": linked_status or None,
            "linkedStatusLabel": STATUS_LABELS.get(linked_status, linked_status) if linked_status else None,
            "linkedOccurrenceId": _integer(_field(row, "linked_occurrence_id")),
            "proposalOccurrenceId": _integer(_field(row, "proposal_occurrence_id")),
            "reconciled": bool(links),
            "links": [cls._link_summary(link) for link in links],
        }

    @classmethod
    def _occurrence(cls, row: Any, engine: Any, links: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        links = links or []
        status = str(_field(row, "status", "planned") or "planned")
        expected_amount = _number(_field(row, "expected_amount", 0))
        remaining = _field(row, "remaining_amount")
        shown = display_status(status, _number(remaining or 0), _number(_field(row, "overage_amount", 0)))
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
            "displayStatus": shown,
            "statusLabel": DISPLAY_LABELS.get(shown, STATUS_LABELS.get(status, status)),
            "matchMode": str(_field(row, "match_type", "") or ""),
            "reconciled": bool(links),
            "links": [cls._link_summary(link) for link in links],
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
