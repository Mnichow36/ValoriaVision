from __future__ import annotations

from datetime import date, datetime, timedelta
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

    ALLOWED_HORIZONS = {15, 30, 60, 90, 180, 365}
    SAFETY_THRESHOLD_KEY = "forecast.safety_threshold"
    ALLOWED_SCENARIOS = {"Prudent", "Réaliste", "Optimiste"}

    def __init__(
        self,
        database: Any,
        now_provider: Callable[[], datetime] = lambda: datetime.now().astimezone(),
    ) -> None:
        self.database = database
        self.now_provider = now_provider

    def snapshot(
        self,
        account_id: int | None = None,
        horizon_days: int = 15,
        scenario: str = "Réaliste",
    ) -> dict[str, Any]:
        horizon = horizon_days if horizon_days in self.ALLOWED_HORIZONS else 15
        custom_scenarios = self._custom_scenario_names()
        available_scenarios = self.ALLOWED_SCENARIOS | set(custom_scenarios)
        selected_scenario = scenario if scenario in available_scenarios else "Réaliste"
        current_time = self.now_provider()
        reference_date = (
            current_time.astimezone().date()
            if current_time.tzinfo is not None
            else current_time.date()
        )
        # Règle métier : aucune prévision n'est antérieure à aujourd'hui. Le moteur part de la
        # veille (solde réel) et seules les journées à partir d'aujourd'hui sont exposées.
        engine_start = reference_date - timedelta(days=1)
        engine_start_date = engine_start.isoformat()
        engine_horizon = horizon + 1
        start_date = reference_date.isoformat()
        end_date = (reference_date + timedelta(days=horizon)).isoformat()
        built_in_forecasts = {
            name: self.database.cash_forecast(engine_start_date, engine_horizon, name, account_id=account_id)
            for name in self.ALLOWED_SCENARIOS
        }
        selected = (
            built_in_forecasts[selected_scenario]
            if selected_scenario in built_in_forecasts
            else self.database.cash_forecast(engine_start_date, engine_horizon, selected_scenario, account_id=account_id)
        )
        threshold = self.safety_threshold()
        from_today = lambda points: [p for p in points if str(p.get("date") or "") >= start_date]
        prudent = built_in_forecasts["Prudent"]
        optimistic = built_in_forecasts["Optimiste"]
        realistic = built_in_forecasts["Réaliste"]
        selected_points = from_today(selected.get("daily_points") or [])
        low_point = min(selected_points, key=lambda point: _number(point.get("balance")), default=None)
        end_point = selected_points[-1] if selected_points else None
        occurrences_by_recurrence = self._recurrence_events(selected_points)
        upcoming_recurrences = self._upcoming_recurrences(
            selected_points,
            reference_date.isoformat(),
        )
        recurrences = [
            self._recurrence(
                row,
                reference_date.isoformat(),
                occurrences_by_recurrence.get(_integer(_field(row, "id", 0)), []),
            )
            for row in self.database.list_recurring_items(active_only=False)
        ]
        recurrences.sort(
            key=lambda item: (
                item["nextOccurrenceDate"] or "9999-12-31",
                item["name"].casefold(),
            )
        )

        return {
            "generatedAt": current_time.isoformat(),
            "currency": "EUR",
            "filters": {
                "accountId": account_id,
                "accountLabel": str(selected.get("account_label") or "Tous les comptes"),
                "horizonDays": horizon,
                "scenario": selected_scenario,
                "referenceDate": reference_date.isoformat(),
                "startDate": start_date,
                "endDate": end_date,
            },
            "accounts": [self._account(row) for row in self.database.list_accounts() if str(_field(row, "status", "Actif")) != "Clos"],
            "categories": [self._category(row) for row in self.database.list_categories()],
            "recurrences": recurrences,
            "series": {
                "selected": self._series(selected_points),
                "realized": self._realized_series(_number(selected.get("starting_cash")), selected_points),
                "realistic": self._series(from_today(realistic.get("daily_points") or [])),
                "prudent": self._series(from_today(prudent.get("daily_points") or [])),
                "optimistic": self._series(from_today(optimistic.get("daily_points") or [])),
                "custom": {
                    name: self._series(
                        from_today((
                            selected
                            if name == selected_scenario
                            else self.database.cash_forecast(engine_start_date, engine_horizon, name, account_id=account_id)
                        ).get("daily_points") or [])
                    )
                    for name in custom_scenarios
                },
            },
            "summary": {
                "startingCash": _number(selected_points[0].get("balance")) if selected_points else _number(selected.get("starting_cash")),
                "lowBalance": _number((low_point or {}).get("balance")) if low_point else _number(selected.get("min_balance")),
                "lowDate": str((low_point or {}).get("date") or start_date),
                "endBalance": _number(selected.get("end_balance")),
                "endDate": str((end_point or {}).get("date") or start_date),
                "totalIn": _number(selected.get("total_in")),
                "totalOut": _number(selected.get("total_out")),
                "prudentDifference": _number(_number(selected.get("end_balance")) - _number(prudent.get("end_balance"))),
                "safetyThreshold": threshold,
                "daysBelowThreshold": sum(1 for point in selected_points if _number(point.get("balance")) < threshold),
                "totalDays": len(selected_points),
                "overdueOccurrences": self._overdue_count(start_date, account_id),
                "alert": str(selected.get("alert") or "Prévision disponible"),
            },
            "upcoming": [self._event(event) for event in upcoming_recurrences],
        }

    def _overdue_count(self, reference_date: str, account_id: int | None) -> int:
        """Prévisions de récurrence antérieures à aujourd'hui, non réalisées : à décaler ou reporter."""
        connect = getattr(self.database, "connect", None)
        if connect is None:
            return 0
        try:
            with connect() as conn:
                query = (
                    "SELECT COUNT(*) FROM forecast_occurrences "
                    "WHERE source_type = 'recurring' AND deleted_at IS NULL "
                    "AND status IN ('planned', 'overdue') AND actual_transaction_id IS NULL "
                    "AND expected_date < ?"
                )
                params: list[Any] = [reference_date]
                if account_id is not None:
                    query += " AND account_id = ?"
                    params.append(account_id)
                return int(conn.execute(query, params).fetchone()[0] or 0)
        except Exception:  # base de test minimale ou table absente
            return 0

    def safety_threshold(self) -> float:
        getter = getattr(self.database, "get_setting", None)
        if getter is None:
            return 0.0
        try:
            return max(0.0, float(str(getter(self.SAFETY_THRESHOLD_KEY, "0") or "0").replace(",", ".")))
        except ValueError:
            return 0.0

    def update_safety_threshold(self, value: Any) -> dict[str, Any]:
        try:
            amount = round(float(str(value).replace(",", ".")), 2)
        except (TypeError, ValueError):
            raise ValueError("Le seuil de sécurité doit être un nombre.")
        if amount < 0 or amount > 10_000_000:
            raise ValueError("Le seuil de sécurité doit être compris entre 0 et 10 000 000 €.")
        self.database.set_setting(self.SAFETY_THRESHOLD_KEY, str(amount))
        return {"success": True, "message": f"Seuil de sécurité fixé à {amount:,.2f} €.".replace(",", " "), "safetyThreshold": amount}

    def simulate(self, payload: dict[str, Any]) -> dict[str, Any]:
        """« Et si ? » : compare la trésorerie avec et sans une opération hypothétique (rien n'est enregistré)."""
        current_time = self.now_provider()
        today = current_time.astimezone().date() if current_time.tzinfo is not None else current_time.date()
        kind = str(payload.get("kind") or "Dépense")
        if kind not in {"Dépense", "Recette"}:
            raise ValueError("Le type doit être Dépense ou Recette.")
        try:
            amount = round(float(str(payload.get("amount")).replace(",", ".")), 2)
        except (TypeError, ValueError):
            raise ValueError("Le montant est invalide.")
        if amount <= 0:
            raise ValueError("Le montant doit être supérieur à 0.")
        try:
            day = date.fromisoformat(str(payload.get("date") or ""))
        except ValueError:
            raise ValueError("La date est invalide.")
        if day <= today:
            raise ValueError("La date simulée doit être postérieure à aujourd’hui.")
        horizon_days = (day - today).days + 60
        if horizon_days > 730:
            raise ValueError("La simulation est limitée à 2 ans.")
        account_id = payload.get("account_id")
        account_id = int(account_id) if account_id not in (None, "", "all") else None
        if account_id is not None:
            account = next((row for row in self.database.list_accounts() if _integer(_field(row, "id", 0)) == account_id), None)
            if account is None or str(_field(account, "status", "")) != "Actif":
                raise ValueError("Le compte simulé doit être un compte actif.")
        scenario = str(payload.get("scenario") or "Réaliste")
        if scenario not in self.ALLOWED_SCENARIOS | set(self._custom_scenario_names()):
            scenario = "Réaliste"
        forecast = self.database.cash_forecast(today.isoformat(), horizon_days, scenario, account_id=account_id)
        points = [(str(point["date"]), _number(point.get("balance"))) for point in forecast.get("daily_points", [])]
        threshold = self.safety_threshold()
        signed = -amount if kind == "Dépense" else amount

        def metrics(effective_day: date | None) -> dict[str, Any]:
            values = [
                (point_day, balance + (signed if effective_day is not None and point_day >= effective_day.isoformat() else 0.0))
                for point_day, balance in points
            ]
            below = [point_day for point_day, balance in values if threshold > 0 and balance < threshold]
            low_day, low = min(values, key=lambda item: item[1]) if values else (today.isoformat(), 0.0)
            return {
                "values": values,
                "daysBelow": len(below),
                "firstBelow": below[0] if below else None,
                "lastBelow": below[-1] if below else None,
                "minBalance": round(low, 2),
                "minDate": low_day,
                "finalBalance": round(values[-1][1], 2) if values else 0.0,
            }

        without = metrics(None)
        with_op = metrics(day)
        def worsens(trial: dict[str, Any]) -> bool:
            if trial["daysBelow"] > without["daysBelow"]:
                return True
            return trial["daysBelow"] > 0 and trial["minBalance"] < without["minBalance"] - 0.005

        suggestion = None
        if threshold > 0 and worsens(with_op):
            for offset in range(1, 61):
                candidate = day + timedelta(days=offset)
                if candidate.isoformat() > points[-1][0]:
                    break
                trial = metrics(candidate)
                if not worsens(trial):
                    suggestion = {"date": candidate.isoformat(), "minBalance": trial["minBalance"], "daysBelow": trial["daysBelow"]}
                    break
        passes = not worsens(with_op)
        verdict = "ok" if passes else "ko"
        if threshold <= 0:
            verdict = "no_threshold"
        label = str(payload.get("label") or "").strip() or ("Dépense simulée" if kind == "Dépense" else "Recette simulée")
        return {
            "kind": kind,
            "label": label,
            "date": day.isoformat(),
            "amount": amount,
            "accountId": account_id,
            "scenario": scenario,
            "threshold": threshold,
            "verdict": verdict,
            "passes": passes,
            "without": {key: value for key, value in without.items() if key != "values"},
            "with": {key: value for key, value in with_op.items() if key != "values"},
            "suggestion": suggestion,
            "series": [
                {"date": point_day, "without": _number(base), "with": _number(sim[1])}
                for (point_day, base), sim in zip(without["values"], with_op["values"])
            ],
        }

    @staticmethod
    def _account(row: Any) -> dict[str, Any]:
        return {
            "id": _integer(_field(row, "id", 0)),
            "name": str(_field(row, "name", "Compte") or "Compte")
            + ("" if str(_field(row, "status", "Actif") or "Actif") == "Actif" else f" ({str(_field(row, 'status', '')).lower()})"),
            "bank": str(_field(row, "bank", "") or ""),
            "type": str(_field(row, "account_type", "") or ""),
            "status": str(_field(row, "status", "Actif") or "Actif"),
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

    def _recurrence(
        self,
        row: Any,
        reference_date: str,
        forecast_occurrences: list[dict[str, Any]],
    ) -> dict[str, Any]:
        signed_amount = _number(_field(row, "amount", 0))
        next_scheduled_date = self._next_recurrence_date(row, reference_date)
        visible_dates = sorted(
            str(event.get("date") or "")
            for event in forecast_occurrences
            if str(event.get("date") or "")
        )
        rescheduled_dates = sorted(
            str(event.get("date") or "")
            for event in forecast_occurrences
            if str(event.get("source") or "") == "Récurrence décalée"
            and str(event.get("date") or "")
        )
        next_occurrence_date = visible_dates[0] if visible_dates else next_scheduled_date
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
            "nextScheduledDate": next_scheduled_date,
            "nextRescheduledDate": rescheduled_dates[0] if rescheduled_dates else "",
            "forecastOccurrenceCount": len(forecast_occurrences),
            "rescheduledOccurrenceCount": len(rescheduled_dates),
            "endDate": str(_field(row, "end_date", "") or ""),
            "scenario": str(_field(row, "scenario", "Réaliste") or "Réaliste"),
            "status": str(_field(row, "status", "Actif") or "Actif"),
        }

    @staticmethod
    def _recurrence_events(points: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
        events_by_recurrence: dict[int, list[dict[str, Any]]] = {}
        for point in points:
            point_date = str(point.get("date") or "")
            for event in point.get("events") or []:
                source = str(event.get("source") or "")
                recurring_id = _integer(event.get("recurring_id"))
                if recurring_id <= 0 or not source.startswith("Récurrence"):
                    continue
                normalized = dict(event)
                normalized["date"] = str(event.get("date") or point_date)
                events_by_recurrence.setdefault(recurring_id, []).append(normalized)
        return events_by_recurrence

    @staticmethod
    def _upcoming_recurrences(
        points: list[dict[str, Any]],
        reference_date: str,
    ) -> list[dict[str, Any]]:
        upcoming: list[dict[str, Any]] = []
        for point in points:
            point_date = str(point.get("date") or "")
            if point_date < reference_date:
                continue
            for event in point.get("events") or []:
                if not str(event.get("source") or "").startswith("Récurrence"):
                    continue
                normalized = dict(event)
                normalized["date"] = str(event.get("date") or point_date)
                upcoming.append(normalized)
        return sorted(
            upcoming,
            key=lambda event: (
                str(event.get("date") or ""),
                str(event.get("name") or "").casefold(),
                _number(event.get("amount")),
            ),
        )

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

    def _custom_scenario_names(self) -> list[str]:
        """Return active custom scenarios without requiring them in lightweight test doubles."""
        try:
            with self.database.connect() as conn:
                rows = conn.execute(
                    """
                    SELECT name
                    FROM scenarios
                    WHERE deleted_at IS NULL
                      AND is_active = 1
                      AND is_reference = 0
                    ORDER BY updated_at DESC, name
                    """
                )
                return [
                    str(row["name"]).strip()
                    for row in rows
                    if str(row["name"] or "").strip()
                ]
        except (AttributeError, KeyError, TypeError):
            return []

    @staticmethod
    def _series(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
        series: list[dict[str, Any]] = []
        for point in points:
            raw_events = point.get("events") or []
            events = [ForecastReadService._event(event) for event in raw_events]
            inflow = _number(
                point.get("in")
                if point.get("in") is not None
                else sum(_number(event.get("amount")) for event in raw_events if _number(event.get("amount")) > 0)
            )
            outflow = _number(
                point.get("out")
                if point.get("out") is not None
                else abs(sum(_number(event.get("amount")) for event in raw_events if _number(event.get("amount")) < 0))
            )
            series.append({
                "date": str(point.get("date") or ""),
                "label": str(point.get("label") or ""),
                "balance": _number(point.get("balance")),
                "inflow": inflow,
                "outflow": outflow,
                "net": _number(point.get("net")) if point.get("net") is not None else _number(inflow - outflow),
                "events": events,
            })
        return series

    @staticmethod
    def _realized_series(starting_cash: float, points: list[dict[str, Any]]) -> list[dict[str, Any]]:
        balance = starting_cash
        series = []
        for point in points:
            actual_net = sum(
                _number(event.get("amount"))
                for event in point.get("events") or []
                if not str(event.get("source") or "").startswith("Récurrence")
            )
            balance += actual_net
            realized_in = sum(_number(event.get("amount")) for event in point.get("events") or [] if not str(event.get("source") or "").startswith("Récurrence") and _number(event.get("amount")) > 0)
            realized_out = abs(sum(_number(event.get("amount")) for event in point.get("events") or [] if not str(event.get("source") or "").startswith("Récurrence") and _number(event.get("amount")) < 0))
            series.append({
                "date": str(point.get("date") or ""),
                "label": str(point.get("label") or ""),
                "balance": _number(balance),
                "inflow": _number(realized_in),
                "outflow": _number(realized_out),
                "net": _number(realized_in - realized_out),
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
