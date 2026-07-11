from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any


FRENCH_MONTHS = {
    1: "Janv.",
    2: "Févr.",
    3: "Mars",
    4: "Avr.",
    5: "Mai",
    6: "Juin",
    7: "Juil.",
    8: "Août",
    9: "Sept.",
    10: "Oct.",
    11: "Nov.",
    12: "Déc.",
}


@dataclass(frozen=True)
class ForecastChartRequest:
    start_date: date
    end_date: date
    account_id: int | None = None
    scenario_id: int | None = None
    granularity: str = "month"
    scenario: str = "Réaliste"


class ForecastChartService:
    """Central service for forecast chart data.

    The widget must not read transactions by itself. This service uses the
    existing Valoria Vision forecast engine (`Database.cash_forecast`) as the
    source of truth, then prepares a chart-friendly series.

    Output points are compatible with a combined chart:
    credits bars + debits bars + closing balance line.
    """

    def __init__(self, db) -> None:
        self.db = db

    def build_cashflow_chart_series(
        self,
        start_date: date,
        end_date: date,
        account_id: int | None = None,
        scenario_id: int | None = None,
        granularity: str = "month",
        scenario: str = "Réaliste",
    ) -> dict[str, Any]:
        if end_date < start_date:
            end_date = start_date
        granularity = "day" if granularity == "day" else "month"
        horizon_days = max(0, (end_date - start_date).days)

        # Source of truth: current forecast engine.
        forecast = self.db.cash_forecast(
            start_date.isoformat(),
            horizon_days,
            scenario,
            account_id=account_id,
        )
        daily_points = list(forecast.get("daily_points", []))

        if granularity == "day":
            points = [self._daily_point(point, previous_balance=forecast["starting_cash"] if idx == 0 else daily_points[idx - 1]["balance"]) for idx, point in enumerate(daily_points)]
        else:
            points = self._monthly_points(daily_points, forecast["starting_cash"])

        return {
            "granularity": granularity,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "account_id": account_id,
            "account_label": forecast.get("account_label", "Tous les comptes"),
            "scenario": scenario,
            "scenario_id": scenario_id,
            "points": points,
            "labels": [point["label"] for point in points],
            "credits": [point["credits"] for point in points],
            "debits": [point["debits"] for point in points],
            "balances": [point["closing_balance"] for point in points],
            "starting_cash": forecast["starting_cash"],
            "end_balance": forecast["end_balance"],
            "min_balance": forecast["min_balance"],
            "total_credits": round(sum(point["credits"] for point in points), 2),
            "total_debits": round(sum(point["debits"] for point in points), 2),
            "flow_count": sum(point["flow_count"] for point in points),
            "forecast": forecast,
        }

    def _daily_point(self, point: dict[str, Any], previous_balance: float) -> dict[str, Any]:
        events = list(point.get("events", []))
        credits = float(point.get("in", 0) or 0)
        debits = float(point.get("out", 0) or 0)
        closing = float(point.get("balance", previous_balance) or previous_balance)
        opening = float(previous_balance or 0)
        split = self._split_events(events)
        return {
            "period": str(point.get("date", "")),
            "period_start": str(point.get("date", "")),
            "period_end": str(point.get("date", "")),
            "label": str(point.get("label", point.get("date", ""))),
            "credits": round(credits, 2),
            "debits": round(debits, 2),
            "opening_balance": round(opening, 2),
            "closing_balance": round(closing, 2),
            "real_credits": split["real_credits"],
            "real_debits": split["real_debits"],
            "forecast_credits": split["forecast_credits"],
            "forecast_debits": split["forecast_debits"],
            "net": round(credits - debits, 2),
            "flow_count": len(events),
            "has_alert": closing < 0,
            "events": events,
        }

    def _monthly_points(self, daily_points: list[dict[str, Any]], starting_cash: float) -> list[dict[str, Any]]:
        if not daily_points:
            return []

        grouped: dict[str, list[dict[str, Any]]] = {}
        for point in daily_points:
            key = str(point.get("date", ""))[:7]
            grouped.setdefault(key, []).append(point)

        points: list[dict[str, Any]] = []
        previous_balance = float(starting_cash or 0)
        for key in sorted(grouped):
            days = grouped[key]
            first_day = days[0]
            last_day = days[-1]
            events: list[dict] = []
            credits = 0.0
            debits = 0.0
            for day in days:
                events.extend(day.get("events", []))
                credits += float(day.get("in", 0) or 0)
                debits += float(day.get("out", 0) or 0)
            opening = previous_balance
            closing = float(last_day.get("balance", opening) or opening)
            previous_balance = closing
            split = self._split_events(events)
            year, month = [int(part) for part in key.split("-")]
            points.append({
                "period": key,
                "period_start": str(first_day.get("date", key)),
                "period_end": str(last_day.get("date", key)),
                "label": f"{FRENCH_MONTHS.get(month, key)} {year}",
                "credits": round(credits, 2),
                "debits": round(debits, 2),
                "opening_balance": round(opening, 2),
                "closing_balance": round(closing, 2),
                "real_credits": split["real_credits"],
                "real_debits": split["real_debits"],
                "forecast_credits": split["forecast_credits"],
                "forecast_debits": split["forecast_debits"],
                "net": round(credits - debits, 2),
                "flow_count": len(events),
                "has_alert": closing < 0,
                "events": events,
            })
        return points

    def _split_events(self, events: list[dict[str, Any]]) -> dict[str, float]:
        real_credits = real_debits = forecast_credits = forecast_debits = 0.0
        for event in events:
            amount = float(event.get("amount", 0) or 0)
            source = str(event.get("source", "")).lower()
            is_real = "transaction" in source and "future" not in source
            # Current engine labels planned manual future transactions and
            # recurrences. This split is ready for future explicit real/forecast
            # sources without duplicating business rules in the widget.
            if is_real:
                if amount > 0:
                    real_credits += amount
                elif amount < 0:
                    real_debits += abs(amount)
            else:
                if amount > 0:
                    forecast_credits += amount
                elif amount < 0:
                    forecast_debits += abs(amount)
        return {
            "real_credits": round(real_credits, 2),
            "real_debits": round(real_debits, 2),
            "forecast_credits": round(forecast_credits, 2),
            "forecast_debits": round(forecast_debits, 2),
        }
