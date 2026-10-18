from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable


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


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


class ForecastReadService:
    """Expose daily cash projections without coupling React to SQLite rows."""

    ALLOWED_HORIZONS = {30, 60, 90}
    ALLOWED_SCENARIOS = {"Prudent", "Réaliste", "Optimiste"}

    def __init__(
        self,
        database: Any,
        now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.database = database
        self.now_provider = now_provider

    def snapshot(
        self,
        account_id: int | None = None,
        horizon_days: int = 90,
        scenario: str = "Réaliste",
    ) -> dict[str, Any]:
        horizon = horizon_days if horizon_days in self.ALLOWED_HORIZONS else 90
        selected_scenario = scenario if scenario in self.ALLOWED_SCENARIOS else "Réaliste"
        start_date = self.database.default_forecast_start_date()
        selected = self.database.cash_forecast(start_date, horizon, selected_scenario, account_id=account_id)
        prudent = self.database.cash_forecast(start_date, horizon, "Prudent", account_id=account_id)
        optimistic = self.database.cash_forecast(start_date, horizon, "Optimiste", account_id=account_id)
        selected_points = selected.get("daily_points") or []
        low_point = min(selected_points, key=lambda point: _number(point.get("balance")), default=None)
        end_point = selected_points[-1] if selected_points else None
        recurrences = [
            self._recurrence(row, start_date)
            for row in self.database.list_recurring_items(active_only=False)
        ]
        recurrences.sort(
            key=lambda item: (
                item["nextOccurrenceDate"] or "9999-12-31",
                item["name"].casefold(),
            )
        )

        return {
            "generatedAt": self.now_provider().isoformat(),
            "currency": "EUR",
            "filters": {
                "accountId": account_id,
                "accountLabel": str(selected.get("account_label") or "Tous les comptes"),
                "horizonDays": horizon,
                "scenario": selected_scenario,
                "startDate": str(start_date),
            },
            "accounts": [self._account(row) for row in self.database.list_accounts() if str(_field(row, "status", "")) == "Actif"],
            "categories": [self._category(row) for row in self.database.list_categories()],
            "recurrences": recurrences,
            "series": {
                "selected": self._series(selected_points),
                "realized": self._realized_series(_number(selected.get("starting_cash")), selected_points),
                "prudent": self._series(prudent.get("daily_points") or []),
                "optimistic": self._series(optimistic.get("daily_points") or []),
            },
            "summary": {
                "startingCash": _number(selected.get("starting_cash")),
                "lowBalance": _number(selected.get("min_balance")),
                "lowDate": str((low_point or {}).get("date") or start_date),
                "endBalance": _number(selected.get("end_balance")),
                "endDate": str((end_point or {}).get("date") or start_date),
                "totalIn": _number(selected.get("total_in")),
                "totalOut": _number(selected.get("total_out")),
                "prudentDifference": _number(_number(selected.get("end_balance")) - _number(prudent.get("end_balance"))),
                "alert": str(selected.get("alert") or "Prévision disponible"),
            },
            "upcoming": [self._event(event) for event in (selected.get("upcoming") or [])[:4]],
        }

    @staticmethod
    def _account(row: Any) -> dict[str, Any]:
        return {
            "id": _integer(_field(row, "id", 0)),
            "name": str(_field(row, "name", "Compte") or "Compte"),
            "bank": str(_field(row, "bank", "") or ""),
            "type": str(_field(row, "account_type", "") or ""),
        }

    @staticmethod
    def _category(row: Any) -> dict[str, Any]:
        kind = str(_field(row, "kind", "Dépense") or "Dépense")
        direction = str(_field(row, "direction", "") or "")
        if direction not in {"Recette", "Dépense", "Neutre"}:
            direction = "Recette" if kind == "Revenu" else "Neutre" if kind == "Neutre" else "Dépense"
        return {
            "id": _integer(_field(row, "id", 0)),
            "name": str(_field(row, "name", "") or ""),
            "direction": direction,
            "color": str(_field(row, "color", "#64748B") or "#64748B"),
        }

    def _recurrence(self, row: Any, reference_date: str) -> dict[str, Any]:
        signed_amount = _number(_field(row, "amount", 0))
        next_occurrence_date = self._next_recurrence_date(row, reference_date)
        return {
            "id": _integer(_field(row, "id", 0)),
            "accountId": _integer(_field(row, "account_id", 0)),
            "accountName": str(_field(row, "account_name", "Compte") or "Compte"),
            "bank": str(_field(row, "bank", "") or ""),
            "name": str(_field(row, "name", "Récurrence") or "Récurrence"),
            "category": str(_field(row, "category", "Prévisionnel") or "Prévisionnel"),
            "direction": "Crédit" if signed_amount >= 0 else "Débit",
            "amount": abs(signed_amount),
            "frequency": str(_field(row, "frequency", "Mensuel") or "Mensuel"),
            "nextDate": str(_field(row, "next_date", "") or ""),
            "nextOccurrenceDate": next_occurrence_date,
            "endDate": str(_field(row, "end_date", "") or ""),
            "scenario": str(_field(row, "scenario", "Réaliste") or "Réaliste"),
            "status": str(_field(row, "status", "Actif") or "Actif"),
        }

    def _next_recurrence_date(self, row: Any, reference_date: str) -> str:
        try:
            candidate = date.fromisoformat(str(_field(row, "next_date", "") or ""))
            reference = date.fromisoformat(str(reference_date))
        except ValueError:
            return ""

        end_value = str(_field(row, "end_date", "") or "")
        try:
            end_date = date.fromisoformat(end_value) if end_value else None
        except ValueError:
            end_date = None
        frequency = str(_field(row, "frequency", "Mensuel") or "Mensuel")
        one_off = frequency in {"Ponctuel", "Une fois", "Ponctuel / une seule fois"}

        if one_off and candidate <= reference:
            return ""
        while candidate <= reference:
            advanced = self.database.add_period(candidate, frequency)
            if advanced <= candidate:
                return ""
            candidate = advanced
        if end_date is not None and candidate > end_date:
            return ""
        return candidate.isoformat()

    @staticmethod
    def _series(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "date": str(point.get("date") or ""),
                "label": str(point.get("label") or ""),
                "balance": _number(point.get("balance")),
                "events": [
                    ForecastReadService._event(event)
                    for event in point.get("events") or []
                ],
            }
            for point in points
        ]

    @staticmethod
    def _realized_series(starting_cash: float, points: list[dict[str, Any]]) -> list[dict[str, Any]]:
        balance = starting_cash
        series = []
        for point in points:
            actual_net = sum(
                _number(event.get("amount"))
                for event in point.get("events") or []
                if str(event.get("source") or "") != "Récurrence"
            )
            balance += actual_net
            series.append({
                "date": str(point.get("date") or ""),
                "label": str(point.get("label") or ""),
                "balance": _number(balance),
                "events": [],
            })
        return series

    @staticmethod
    def _event(event: dict[str, Any]) -> dict[str, Any]:
        return {
            "date": str(event.get("date") or ""),
            "name": str(event.get("name") or "Échéance"),
            "category": str(event.get("category") or "Prévisionnel"),
            "amount": _number(event.get("amount")),
            "source": str(event.get("source") or ""),
            "account": str(event.get("account") or "Compte"),
            "scenario": str(event.get("scenario") or "Tous"),
            "originalDate": str(event.get("original_date") or ""),
            "recurringId": (
                _integer(event.get("recurring_id"))
                if event.get("recurring_id") is not None
                else None
            ),
        }
