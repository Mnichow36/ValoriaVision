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
        engine = self.engine_factory(self.database)
        engine.repair_occurrence_states()
        engine.generate_occurrences(today - timedelta(days=90), today + timedelta(days=365))
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
            "categories": self._categories(),
        }

    def _categories(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for row in self.database.list_categories():
            kind = str(row["kind"] or "Dépense") if "kind" in row.keys() else "Dépense"
            direction = str(row["direction"] or "") if "direction" in row.keys() else ""
            if direction not in {"Recette", "Dépense", "Neutre"}:
                direction = "Recette" if kind == "Revenu" else "Neutre" if kind == "Neutre" else "Dépense"
            result.append({"id": int(row["id"]), "name": str(row["name"] or ""), "direction": direction})
        return result

    @staticmethod
    def _item(row: Any, today: date) -> dict[str, Any]:
        status = str(row["status"] or "planned")
        expected_date = str(row["expected_date"])
        if status == "planned" and expected_date < today.isoformat():
            status = "overdue"
        original = str(row["original_expected_date"] or expected_date)
        editable = status in EDITABLE and not int(row["active_links"] or 0) and row["actual_transaction_id"] is None
        if editable:
            lock_reason = ""
        elif status in {"auto_matched", "confirmed", "partially_matched"} or row["actual_transaction_id"] is not None or int(row["active_links"] or 0):
            lock_reason = "Déjà rapprochée : annule d’abord le rapprochement dans l’écran Rapprochements."
        elif status in {"ignored", "cancelled"}:
            lock_reason = "Supprimée ou ignorée : rétablis-la d’abord."
        else:
            lock_reason = f"Statut « {STATUS_LABELS.get(status, status)} » : action impossible."
        return {
            "lockReason": lock_reason,
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
        with self.database.connect() as conn:
            before = conn.execute(
                "SELECT source_id, expected_category FROM forecast_occurrences WHERE id = ?", (int(occurrence_id),)
            ).fetchone()
        ok, message = self.engine_factory(self.database).update_occurrence(
            occurrence_id,
            expected_date=payload.get("date"),
            amount=payload.get("amount"),
            label=payload.get("label", ""),
            category=payload.get("category", ""),
            reference_date=self._today(),
        )
        if ok and payload.get("apply_to_rule") and before is not None and before["source_id"] is not None:
            new_category = " ".join(str(payload.get("category") or "").split())
            if new_category and new_category != str(before["expected_category"] or ""):
                extra = self._propagate_category(int(before["source_id"]), int(occurrence_id), new_category)
                message = f"Occurrence modifiée. {extra}" if extra.startswith("Règle mise à jour") else f"{message} {extra}"
        return self._result(ok, message)

    def _propagate_category(self, rule_id: int, occurrence_id: int, category: str) -> str:
        """Applique la catégorie à la règle et à ses autres occurrences futures non modifiées à la main."""
        today = self._today().isoformat()
        with self.database.connect() as conn:
            rule = conn.execute("SELECT amount FROM recurring_items WHERE id = ?", (rule_id,)).fetchone()
            cat = conn.execute(
                "SELECT kind, direction FROM categories WHERE LOWER(name) = LOWER(?) AND deleted_at IS NULL", (category,)
            ).fetchone()
            if rule is None or cat is None:
                return "La règle n’a pas pu être mise à jour."
            direction = str(cat["direction"] or "")
            if direction not in {"Recette", "Dépense", "Neutre"}:
                kind = str(cat["kind"] or "Dépense")
                direction = "Recette" if kind == "Revenu" else "Neutre" if kind == "Neutre" else "Dépense"
            expected = "Recette" if float(rule["amount"] or 0) >= 0 else "Dépense"
            if direction not in {expected, "Neutre"}:
                return f"La règle reste inchangée : la catégorie « {category} » ne correspond pas au sens de la règle."
            conn.execute(
                "UPDATE recurring_items SET category = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (category, rule_id)
            )
            cursor = conn.execute(
                """
                UPDATE forecast_occurrences
                SET expected_category = ?, updated_at = CURRENT_TIMESTAMP
                WHERE source_type = 'recurring' AND source_id = ? AND deleted_at IS NULL
                  AND id != ? AND COALESCE(manually_edited, 0) = 0
                  AND status IN ('planned', 'overdue', 'to_review')
                  AND expected_date >= ? AND actual_transaction_id IS NULL
                  AND NOT EXISTS (SELECT 1 FROM forecast_reconciliation_links l
                                  WHERE l.occurrence_id = forecast_occurrences.id AND l.deleted_at IS NULL)
                """,
                (category, rule_id, int(occurrence_id), today),
            )
            count = int(cursor.rowcount or 0)
            self.database.audit_event(
                conn, "recurrence_category_propagated", "recurring_item", str(rule_id),
                "Catégorie appliquée à la règle et à ses occurrences futures.",
                {"category": category, "occurrences": count},
            )
        plural = "s" if count > 1 else ""
        return f"Règle mise à jour et {count} autre{plural} occurrence{plural} future{plural} recatégorisée{plural}."

    def shift(self, occurrence_ids: list[int], target_date: str) -> dict[str, Any]:
        count, message = self.engine_factory(self.database).shift_occurrences(
            occurrence_ids, target_date, reference_date=self._today()
        )
        return self._result(count > 0, message, updatedCount=int(count))

    def postpone(self, occurrence_ids: list[int]) -> dict[str, Any]:
        count, message = self.engine_factory(self.database).postpone_to_next_occurrences(
            occurrence_ids, reference_date=self._today()
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
