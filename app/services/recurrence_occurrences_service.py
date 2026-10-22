from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Callable

from app.services.forecast_reconciliation_service import ForecastReconciliationService

# Libellés affichés dans l'onglet « Récurrences » (une ligne = une occurrence).
STATUS_LABELS = {
    "planned": "Prévue",
    "overdue": "En retard",
    "to_review": "À vérifier",
    "partially_matched": "Écart de montant",
    "auto_matched": "Rapprochée",
    "confirmed": "Rapprochée",
    "ignored": "Ignorée",
    "cancelled": "Supprimée",
}
EDITABLE = {"planned", "overdue", "to_review"}


class RecurrenceOccurrencesService:
    """Lecture et actions sur les occurrences générées par les règles de récurrence."""

    def __init__(self, database, now_provider: Callable[[], datetime] | None = None, engine_factory=ForecastReconciliationService) -> None:
        self.database = database
        self.now_provider = now_provider or datetime.now
        self.engine_factory = engine_factory

    def _today(self) -> date:
        now = self.now_provider()
        return now.astimezone().date() if now.tzinfo is not None else now.date()

    def snapshot(
        self,
        account_id: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        include_deleted: bool = True,
    ) -> dict[str, Any]:
        today = self._today()
        # Les occurrences sont générées sur 12 mois ; on s'assure qu'elles existent.
        self.engine_factory(self.database).generate_occurrences(today - timedelta(days=90), today + timedelta(days=365))
        clauses = ["o.deleted_at IS NULL", "o.source_type = 'recurring'"]
        params: list[Any] = []
        if account_id:
            clauses.append("o.account_id = ?")
            params.append(account_id)
        if start_date:
            clauses.append("o.expected_date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("o.expected_date <= ?")
            params.append(end_date)
        if not include_deleted:
            clauses.append("o.status != 'cancelled'")
        with self.database.connect() as conn:
            rows = list(
                conn.execute(
                    f"""
                    SELECT o.*, a.name AS account_name, r.frequency AS rule_frequency,
                           r.status AS rule_status,
                           (SELECT COUNT(*) FROM forecast_reconciliation_links l
                            WHERE l.occurrence_id = o.id AND l.deleted_at IS NULL) AS active_links
                    FROM forecast_occurrences o
                    LEFT JOIN accounts a ON a.id = o.account_id
                    LEFT JOIN recurring_items r ON r.id = o.source_id
                    WHERE {' AND '.join(clauses)}
                    ORDER BY o.expected_date, o.id
                    """,
                    params,
                )
            )
        items = [self._item(row, today) for row in rows]
        counts: dict[str, int] = {}
        for item in items:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        return {
            "referenceDate": today.isoformat(),
            "items": items,
            "total": len(items),
            "counts": counts,
        }

    @staticmethod
    def _item(row: Any, today: date) -> dict[str, Any]:
        status = str(row["status"] or "planned")
        expected_date = str(row["expected_date"])
        if status == "planned" and expected_date < today.isoformat():
            status = "overdue"
        original = str(row["original_expected_date"] or expected_date)
        editable = status in EDITABLE and not int(row["active_links"] or 0) and row["actual_transaction_id"] is None
        return {
            "id": int(row["id"]),
            "recurrenceId": int(row["source_id"]) if row["source_id"] is not None else None,
            "date": expected_date,
            "originalDate": original,
            "shifted": original != expected_date,
            "edited": bool(int(row["manually_edited"] or 0)),
            "label": str(row["expected_label"] or "Occurrence"),
            "category": str(row["expected_category"] or "Sans catégorie"),
            "amount": float(row["expected_amount"] or 0),
            "direction": str(row["direction"] or ""),
            "accountId": int(row["account_id"]) if row["account_id"] is not None else None,
            "accountName": str(row["account_name"] or "Compte"),
            "frequency": str(row["rule_frequency"] or ""),
            "status": status,
            "statusLabel": STATUS_LABELS.get(status, status),
            "reconciled": bool(int(row["active_links"] or 0)) or row["actual_transaction_id"] is not None,
            "canEdit": editable,
            "canShift": editable,
            "canDelete": editable,
            "canRestore": status in {"ignored", "cancelled"},
        }

    # --- actions -------------------------------------------------------
    @staticmethod
    def _result(ok: bool, message: str, **extra: Any) -> dict[str, Any]:
        return {"success": bool(ok), "message": message, **extra}

    def update(self, occurrence_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        ok, message = self.engine_factory(self.database).update_occurrence(
            occurrence_id,
            expected_date=payload.get("date"),
            amount=payload.get("amount"),
            label=payload.get("label", ""),
            category=payload.get("category", ""),
            reference_date=self._today(),
        )
        return self._result(ok, message)

    def shift(self, occurrence_ids: list[int], target_date: str) -> dict[str, Any]:
        count, message = self.engine_factory(self.database).shift_occurrences(
            occurrence_ids, target_date, reference_date=self._today()
        )
        return self._result(count > 0, message, updatedCount=int(count))

    def delete(self, occurrence_ids: list[int]) -> dict[str, Any]:
        engine = self.engine_factory(self.database)
        ids = list(dict.fromkeys(int(v) for v in occurrence_ids))
        if not ids:
            return self._result(False, "Sélectionne au moins une occurrence.")
        # Tout ou rien : on valide d'abord toutes les occurrences.
        snapshot = {item["id"]: item for item in self.snapshot()["items"]}
        for oid in ids:
            item = snapshot.get(oid)
            if not item:
                return self._result(False, "Une occurrence sélectionnée n’existe plus. Actualise la liste.")
            if not item["canDelete"]:
                return self._result(False, f"« {item['label']} » ne peut pas être supprimée (statut : {item['statusLabel']}).")
        for oid in ids:
            engine.cancel_occurrence(oid, "Supprimée depuis l’onglet Récurrences")
        plural = "s" if len(ids) > 1 else ""
        return self._result(True, f"{len(ids)} occurrence{plural} supprimée{plural}. " + ("Elles restent consultables et peuvent être rétablies." if len(ids) > 1 else "Elle reste consultable et peut être rétablie."), updatedCount=len(ids))

    def restore(self, occurrence_id: int) -> dict[str, Any]:
        ok, message = self.engine_factory(self.database).restore_occurrence(occurrence_id, self._today())
        return self._result(ok, message)
