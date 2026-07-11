from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from typing import Any

from app.services.forecast_chart_service import ForecastChartService
from app.services.scenario_event_service import ScenarioEventService
from app.services.scenario_service import ScenarioService


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


class ScenarioSimulationService:
    """Apply a personalized scenario on top of the reference forecast."""

    def __init__(self, db) -> None:
        self.db = db
        self.scenarios = ScenarioService(db)
        self.events = ScenarioEventService(db)
        self.forecast_chart = ForecastChartService(db)

    def simulate_scenario(
        self,
        scenario_id: int,
        start_date: date,
        end_date: date,
        account_id: int | None = None,
        granularity: str = "month",
        compare_with_reference: bool = True,
        baseline_scenario: str = "Réaliste",
    ) -> dict[str, Any]:
        scenario = self.scenarios.get_scenario(scenario_id)
        if not scenario:
            raise ValueError("Scénario introuvable.")

        reference = self.forecast_chart.build_cashflow_chart_series(
            start_date,
            end_date,
            account_id=account_id,
            granularity=granularity,
            scenario=baseline_scenario,
        )

        if scenario["is_reference"]:
            return {
                **reference,
                "scenario": {
                    "id": int(scenario["id"]),
                    "name": scenario["name"],
                    "type": scenario["scenario_type"],
                    "is_reference": True,
                },
                "summary": {
                    "opening_balance": reference["starting_cash"],
                    "closing_balance": reference["end_balance"],
                    "lowest_balance": reference["min_balance"],
                    "total_credits": reference["total_credits"],
                    "total_debits": reference["total_debits"],
                    "delta_vs_reference": 0.0,
                    "cash_impact": 0.0,
                    "monthly_impact": 0.0,
                    "asset_impact": 0.0,
                    "liability_impact": 0.0,
                    "net_worth_impact": 0.0,
                    "scenario_credits": 0.0,
                    "scenario_debits": 0.0,
                },
                "alerts": self._alerts(reference["min_balance"]),
            }

        points = [dict(point) for point in reference.get("points", [])]
        scenario_events = self.events.list_events(scenario_id)
        event_instances = self._expand_events(scenario_events, start_date, end_date, granularity)

        # Patrimonial impact must follow each generated occurrence, not only
        # the base event row. This is essential for recurring loan repayments:
        # every monthly repayment reduces the passive/debt impact.
        asset_impact = 0.0
        liability_impact = 0.0
        by_period: dict[str, list[dict]] = {}
        for instance in event_instances:
            event_type = instance.get("event_type")
            amount = abs(float(instance.get("raw_amount", 0) or 0))
            if event_type in ScenarioEventService.ASSET_INCREASE_TYPES:
                asset_impact += amount
            elif event_type in ScenarioEventService.ASSET_DECREASE_TYPES:
                asset_impact -= amount
            elif event_type in ScenarioEventService.LIABILITY_INCREASE_TYPES:
                liability_impact += amount
            elif event_type in ScenarioEventService.LIABILITY_DECREASE_TYPES:
                liability_impact -= amount
            by_period.setdefault(instance["period"], []).append(instance)

        cumulative_delta = 0.0
        total_scenario_credits = 0.0
        total_scenario_debits = 0.0
        previous_closing = float(reference["starting_cash"] or 0)
        for point in points:
            period = point["period"]
            opening = previous_closing
            scenario_credits = 0.0
            scenario_debits = 0.0
            events_for_period = by_period.get(period, [])
            scenario_display_events = []

            for event in events_for_period:
                credit = float(event.get("credit", 0) or 0)
                debit = float(event.get("debit", 0) or 0)
                scenario_credits += credit
                scenario_debits += debit
                if credit or debit:
                    scenario_display_events.append(event["display_event"])

            total_scenario_credits += scenario_credits
            total_scenario_debits += scenario_debits
            cumulative_delta += scenario_credits - scenario_debits

            reference_closing = float(point["closing_balance"] or 0)
            closing = reference_closing + cumulative_delta
            point["reference_closing_balance"] = round(reference_closing, 2)
            point["credits"] = round(float(point["credits"] or 0) + scenario_credits, 2)
            point["debits"] = round(float(point["debits"] or 0) + scenario_debits, 2)
            point["scenario_credits"] = round(scenario_credits, 2)
            point["scenario_debits"] = round(scenario_debits, 2)
            point["opening_balance"] = round(opening, 2)
            point["closing_balance"] = round(closing, 2)
            point["delta_balance"] = round(cumulative_delta, 2)
            point["net"] = round(point["credits"] - point["debits"], 2)
            point["events"] = list(point.get("events", [])) + scenario_display_events
            point["flow_count"] = len(point["events"])
            previous_closing = closing

        labels = [point["label"] for point in points]
        balances = [point["closing_balance"] for point in points]
        credits = [point["credits"] for point in points]
        debits = [point["debits"] for point in points]
        lowest = min(balances) if balances else reference["min_balance"]
        closing = balances[-1] if balances else reference["end_balance"]
        delta_vs_reference = closing - reference["end_balance"]
        months = max(1, self._month_span(start_date, end_date))
        summary = {
            "opening_balance": reference["starting_cash"],
            "closing_balance": round(closing, 2),
            "lowest_balance": round(lowest, 2),
            "total_credits": round(sum(credits), 2),
            "total_debits": round(sum(debits), 2),
            "scenario_credits": round(total_scenario_credits, 2),
            "scenario_debits": round(total_scenario_debits, 2),
            "delta_vs_reference": round(delta_vs_reference, 2),
            "cash_impact": round(delta_vs_reference, 2),
            "monthly_impact": round(delta_vs_reference / months, 2),
            "asset_impact": round(asset_impact, 2),
            "liability_impact": round(liability_impact, 2),
            "net_worth_impact": round(asset_impact - liability_impact, 2),
        }

        return {
            "granularity": granularity,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "account_id": account_id,
            "account_label": reference.get("account_label", "Tous les comptes"),
            "scenario": {
                "id": int(scenario["id"]),
                "name": scenario["name"],
                "type": scenario["scenario_type"],
                "is_reference": False,
            },
            "scenario_id": scenario_id,
            "points": points,
            "labels": labels,
            "credits": credits,
            "debits": debits,
            "balances": balances,
            "starting_cash": reference["starting_cash"],
            "end_balance": closing,
            "min_balance": lowest,
            "total_credits": summary["total_credits"],
            "total_debits": summary["total_debits"],
            "flow_count": sum(point["flow_count"] for point in points),
            "reference": reference,
            "summary": summary,
            "alerts": self._alerts(lowest),
        }

    def _expand_events(self, events: list, start_date: date, end_date: date, granularity: str) -> list[dict]:
        instances: list[dict] = []
        for event in events:
            if not event["is_active"] or event["deleted_at"]:
                continue
            current = self._parse_date(event["event_date"])
            if current is None:
                continue
            event_end = self._event_end_date(event, current)
            if event_end > end_date:
                event_end = end_date
            frequency = event["frequency"] or "once"
            if frequency == "once":
                if start_date <= current <= end_date:
                    instances.append(self._event_instance(event, current, granularity))
                continue

            while current <= event_end:
                if current >= start_date:
                    instances.append(self._event_instance(event, current, granularity))
                if frequency == "monthly":
                    current = self._add_months(current, 1)
                elif frequency == "yearly":
                    current = self._add_months(current, 12)
                else:
                    break
        return instances

    def _event_instance(self, event, occurrence: date, granularity: str) -> dict:
        event_type = event["event_type"]
        amount = abs(float(event["amount"] or 0))
        credit = 0.0
        debit = 0.0
        if event_type in ScenarioEventService.CASH_CREDIT_TYPES:
            credit = amount
        elif event_type in ScenarioEventService.CASH_DEBIT_TYPES:
            debit = amount
        elif event_type == "custom":
            signed = float(event["amount"] or 0)
            if signed >= 0:
                credit = signed
            else:
                debit = abs(signed)
        period = occurrence.isoformat() if granularity == "day" else occurrence.strftime("%Y-%m")
        signed_amount = credit - debit
        return {
            "period": period,
            "event_type": event_type,
            "raw_amount": amount,
            "credit": credit,
            "debit": debit,
            "display_event": {
                "name": event["label"],
                "label": event["label"],
                "amount": signed_amount,
                "source": "scenario",
                "account": "Scénario",
                "scenario_event_id": int(event["id"]),
                "category": event_type,
                "date": occurrence.isoformat(),
                "description": event["description"] or "",
            },
        }

    def _event_end_date(self, event, start: date) -> date:
        if event["end_date"]:
            parsed = self._parse_date(event["end_date"])
            if parsed:
                return parsed
        duration = int(event["duration_months"] or 0)
        if duration:
            return self._add_months(start, max(0, duration - 1))
        if event["frequency"] == "once":
            return start
        return date(2099, 12, 31)

    @staticmethod
    def _parse_date(value) -> date | None:
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except Exception:
            return None

    @staticmethod
    def _add_months(day: date, months: int) -> date:
        month = day.month - 1 + months
        year = day.year + month // 12
        month = month % 12 + 1
        last = monthrange(year, month)[1]
        return date(year, month, min(day.day, last))

    @staticmethod
    def _month_span(start_date: date, end_date: date) -> int:
        return max(1, (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1)

    @staticmethod
    def _alerts(lowest_balance: float) -> list[dict[str, str]]:
        if lowest_balance < 0:
            return [{"level": "critical", "message": "Le point bas de trésorerie passe sous 0 €."}]
        if lowest_balance < 2000:
            return [{"level": "warning", "message": "Le point bas de trésorerie descend sous 2 000 €."}]
        if lowest_balance < 5000:
            return [{"level": "warning", "message": "Le point bas de trésorerie descend sous 5 000 €."}]
        return [{"level": "ok", "message": "Aucune alerte critique sur la période simulée."}]
