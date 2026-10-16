from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.services.forecast_reconciliation_service import ForecastReconciliationService
from app.services.reconciliation import reevaluate_for_occurrences


def _field(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key] if key in row.keys() else default
    except (AttributeError, KeyError, TypeError):
        return default


class RecurrenceWriteService:
    """Validate and persist recurring cash flows for every user interface."""

    ALLOWED_FREQUENCIES = {
        "Ponctuel",
        "Hebdomadaire",
        "Mensuel",
        "Trimestriel",
        "Annuel",
    }
    ALLOWED_SCENARIOS = {"Prudent", "Réaliste", "Optimiste"}
    ALLOWED_DIRECTIONS = {"Débit", "Crédit"}

    def __init__(self, database: Any) -> None:
        self.database = database

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or "").strip()
        category = str(payload.get("category") or "").strip()
        frequency = str(payload.get("frequency") or "Mensuel").strip()
        scenario = str(payload.get("scenario") or "Réaliste").strip()
        direction = str(payload.get("direction") or "").strip()
        account_id = self._positive_integer(payload.get("account_id"), "Le compte est obligatoire.")
        amount = self._positive_amount(payload.get("amount"))
        next_date = self._date(payload.get("next_date"), "La première échéance est invalide.")
        end_date = self._optional_date(payload.get("end_date"))

        if not name:
            raise ValueError("Le libellé de la récurrence est obligatoire.")
        if not category:
            raise ValueError("La catégorie est obligatoire.")
        if frequency not in self.ALLOWED_FREQUENCIES:
            raise ValueError("La fréquence sélectionnée n’est pas prise en charge.")
        if scenario not in self.ALLOWED_SCENARIOS:
            raise ValueError("Le scénario sélectionné n’est pas pris en charge.")
        if direction not in self.ALLOWED_DIRECTIONS:
            raise ValueError("Le sens Débit ou Crédit est obligatoire.")
        if end_date is not None and end_date < next_date:
            raise ValueError("La date de fin doit être postérieure à la première échéance.")

        account = next(
            (row for row in self.database.list_accounts() if int(_field(row, "id", 0) or 0) == account_id),
            None,
        )
        if account is None:
            raise ValueError("Le compte sélectionné n’existe pas.")
        if str(_field(account, "status", "")) != "Actif":
            raise ValueError("Une récurrence ne peut être créée que sur un compte actif.")

        category_row = next(
            (
                row
                for row in self.database.list_categories()
                if str(_field(row, "name", "")).strip().casefold() == category.casefold()
            ),
            None,
        )
        if category_row is None:
            raise ValueError("La catégorie sélectionnée n’existe pas.")

        category_direction = str(
            _field(category_row, "direction", "")
            or self.database.default_direction_for_kind(_field(category_row, "kind", "Dépense"))
        )
        expected_direction = "Crédit" if category_direction == "Recette" else "Débit" if category_direction == "Dépense" else direction
        if direction != expected_direction:
            raise ValueError(
                f"La catégorie « {category} » attend un {expected_direction.lower()}."
            )

        signed_amount = amount if direction == "Crédit" else -amount
        item_id = self.database.add_recurring_item(
            {
                "account_id": account_id,
                "name": name,
                "category": category,
                "amount": signed_amount,
                "frequency": frequency,
                "next_date": next_date.isoformat(),
                "end_date": end_date.isoformat() if end_date else None,
                "scenario": scenario,
                "status": "Actif",
            }
        )

        generation_end = min(end_date or next_date + timedelta(days=365), next_date + timedelta(days=365))
        ForecastReconciliationService(self.database).generate_occurrences(next_date, generation_end)

        with self.database.connect() as conn:
            occurrence_ids = [
                int(row[0])
                for row in conn.execute(
                    """
                    SELECT id
                    FROM forecast_occurrences
                    WHERE source_type = 'recurring'
                      AND source_id = ?
                      AND deleted_at IS NULL
                      AND expected_date >= ?
                      AND expected_date <= ?
                    ORDER BY expected_date
                    """,
                    (item_id, next_date.isoformat(), generation_end.isoformat()),
                ).fetchall()
            ]
            if occurrence_ids:
                reevaluate_for_occurrences(
                    conn,
                    occurrence_ids,
                    self.database.reconciliation_rules(conn),
                    reason="Nouvelle prévision récurrente",
                )

        return {
            "success": True,
            "message": f"Récurrence « {name} » créée.",
            "recurringItemId": item_id,
            "generatedOccurrences": len(occurrence_ids),
        }

    @staticmethod
    def _positive_integer(value: Any, message: str) -> int:
        try:
            result = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(message) from exc
        if result <= 0:
            raise ValueError(message)
        return result

    @staticmethod
    def _positive_amount(value: Any) -> float:
        try:
            result = abs(float(value))
        except (TypeError, ValueError) as exc:
            raise ValueError("Le montant doit être un nombre positif.") from exc
        if result <= 0:
            raise ValueError("Le montant doit être supérieur à zéro.")
        return round(result, 2)

    @staticmethod
    def _date(value: Any, message: str) -> date:
        try:
            return date.fromisoformat(str(value or ""))
        except ValueError as exc:
            raise ValueError(message) from exc

    @classmethod
    def _optional_date(cls, value: Any) -> date | None:
        if value in (None, ""):
            return None
        return cls._date(value, "La date de fin est invalide.")
