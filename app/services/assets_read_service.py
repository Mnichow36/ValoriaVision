from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from app.services.business_rules import is_patrimonial_asset


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


def _add_months(value: date, months: int) -> date:
    index = value.year * 12 + (value.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    last_day = (date(year + (month // 12), month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(value.day, last_day))


def _parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        text = str(value).replace(" ", "").replace(",", ".")
        return float(text) if text else None
    except (TypeError, ValueError):
        return None


class AssetsReadService:
    """Expose patrimonial valuations without adding presentation-only estimates."""

    def __init__(
        self,
        database: Any,
        now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.database = database
        self.now_provider = now_provider

    def snapshot(self) -> dict[str, Any]:
        rows = [self._asset(row) for row in self.database.list_assets()]
        active_rows = [row for row in rows if row["status"] == "Actif" and self._is_patrimonial(row)]
        assets = [row for row in active_rows if row["value"] >= 0]
        liabilities = [row for row in active_rows if row["value"] < 0]
        breakdown_provider = getattr(self.database, "net_worth_breakdown", None)
        if callable(breakdown_provider):
            # Single source of truth shared with the Dashboard: net worth
            # includes the live liquidity of the accounts (decision 22/10/2026).
            breakdown = breakdown_provider()
            total_assets = _number(breakdown["assets"])
            total_liabilities = _number(breakdown["liabilities"])
            net = _number(breakdown["net_worth"])
            liquidities = _number(breakdown["liquidities"])
        else:
            total_assets = round(sum(row["value"] for row in assets), 2)
            total_liabilities = round(abs(sum(row["value"] for row in liabilities)), 2)
            net = round(total_assets - total_liabilities, 2)
            liquidities = 0.0
        insights = self._insights(active_rows, net, total_assets, total_liabilities, liquidities)
        evolution = insights["series"] if insights else self._evolution()
        if insights is None and callable(breakdown_provider) and evolution:
            # The stored valuation history does not contain account liquidity.
            # The latest point always reflects today's consolidated figures.
            evolution[-1] = {
                **evolution[-1],
                "net": net,
                "assets": total_assets,
                "liabilities": -total_liabilities,
            }
        starting_net = evolution[0]["net"] if evolution else 0
        change_percent = round((net - starting_net) / abs(starting_net) * 100, 1) if starting_net else 0.0
        families = self._families(assets, total_assets, liquidities)

        return {
            "generatedAt": self.now_provider().isoformat(),
            "currency": "EUR",
            "summary": {
                "totalAssets": total_assets,
                "totalLiabilities": total_liabilities,
                "netWorth": net,
                "liquidities": liquidities,
                "changePercent": change_percent,
                "assetCount": len(assets),
                "liabilityCount": len(liabilities),
            },
            "families": families,
            "evolution": evolution,
            "assets": assets,
            "liabilities": liabilities,
            "leadingAssetId": assets[0]["id"] if assets else None,
            "headline": insights["headline"] if insights else None,
            "categories": insights["categories"] if insights else [],
            "debts": insights["debts"] if insights else [],
        }

    def _insights(
        self,
        active_rows: list[dict[str, Any]],
        net: float,
        total_assets: float,
        total_liabilities: float,
        liquidities: float,
    ) -> dict[str, Any] | None:
        """Historique mensuel (liquidités comprises) et indicateurs : 12 mois, rendement, volatilité, dettes.

        Tout est calculé à partir des valorisations réellement saisies ; ce qui ne peut pas
        l'être honnêtement (TRI sans versements, rendement sur moins de 3 mois) reste vide.
        """
        history_provider = getattr(self.database, "asset_value_history", None)
        if not callable(history_provider):
            return None
        today = self.now_provider().astimezone().date() if self.now_provider().tzinfo else self.now_provider().date()
        histories: dict[int, list[tuple[date, float]]] = {}
        for row in history_provider():
            day = _parse_date(row["valuation_date"])
            if day is not None:
                histories.setdefault(int(row["asset_id"]), []).append((day, float(row["value"] or 0)))
        for row in active_rows:
            day = _parse_date(row["valuationDate"])
            points = histories.setdefault(row["id"], [])
            if day is not None and all(existing_day != day for existing_day, _ in points):
                points.append((day, row["value"]))
        for points in histories.values():
            points.sort(key=lambda item: item[0])

        def value_at(asset_id: int, at: date) -> float | None:
            current = None
            for day, value in histories.get(asset_id, []):
                if day <= at:
                    current = value
                else:
                    break
            return current

        liquidity_provider = getattr(self.database, "account_summary_at_date", None)

        def liquidity_at(at: date) -> float:
            if at >= today:
                return liquidities
            if not callable(liquidity_provider):
                return 0.0
            return _number(liquidity_provider(at.isoformat()).get("liquidites"))

        all_days = [day for points in histories.values() for day, _ in points if any(row["id"] == asset_id for row in active_rows for asset_id in [row["id"]])]
        account_days = []
        accounts_provider = getattr(self.database, "list_accounts", None)
        if callable(accounts_provider):
            for account in accounts_provider():
                if _field(account, "status") == "Actif":
                    day = _parse_date(_field(account, "effective_initial_date") or _field(account, "initial_date") or _field(account, "reference_date"))
                    if day is not None:
                        account_days.append(day)
        # L'historique commence quand TOUTES les sources existent : le premier actif valorisé
        # et le dernier compte ouvert. Avant, un compte pas encore ouvert compterait 0 et son
        # ouverture ressemblerait à une hausse de patrimoine.
        if account_days:
            earliest = max(max(account_days), min(all_days) if all_days else max(account_days))
        else:
            earliest = min(all_days) if all_days else today
        sampled = [_add_months(today, -offset) for offset in range(12, -1, -1)]
        sampled = [day for day in sampled if day >= earliest]
        if not sampled or sampled[0] > earliest:
            sampled.insert(0, min(earliest, today))
        if sampled[-1] != today:
            sampled.append(today)

        assets_rows = [row for row in active_rows if row["value"] >= 0]
        debt_rows = [row for row in active_rows if row["value"] < 0]

        series = []
        for day in sampled:
            asset_sum = sum(max(value, 0.0) for row in active_rows if (value := value_at(row["id"], day)) is not None and value > 0)
            debt_sum = sum(abs(value) for row in active_rows if (value := value_at(row["id"], day)) is not None and value < 0)
            cash = liquidity_at(day)
            series.append({
                "date": day.isoformat(),
                "net": round(asset_sum + max(cash, 0.0) - debt_sum - max(-cash, 0.0), 2),
                "assets": round(asset_sum + max(cash, 0.0), 2),
                "liabilities": -round(debt_sum + max(-cash, 0.0), 2),
            })
        if series:
            series[-1] = {"date": today.isoformat(), "net": net, "assets": total_assets, "liabilities": -total_liabilities}

        start_day = sampled[0]
        span_days = (today - start_day).days
        first_net = series[0]["net"] if series else 0.0
        change_amount = round(net - first_net, 2)
        change = {
            "amount": change_amount,
            "percent": round(change_amount / abs(first_net) * 100, 1) if first_net else None,
            "fromDate": start_day.isoformat(),
            "months": round(span_days / 30.44, 1),
            "complete": span_days >= 360,
        } if span_days >= 28 else None

        def continuing(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            return [row for row in rows if (value_at(row["id"], start_day) or 0) > 0]

        def growth(rows: list[dict[str, Any]]) -> tuple[float, float] | None:
            kept = continuing(rows)
            start_total = sum(value_at(row["id"], start_day) or 0 for row in kept)
            end_total = sum(value_at(row["id"], today) or 0 for row in kept)
            return (start_total, end_total) if start_total > 0 else None

        annual: dict[str, Any] = {"percent": None, "months": round(span_days / 30.44, 1), "reason": "Historique inférieur à 3 mois."}
        invested = growth(assets_rows)
        if invested and span_days >= 90:
            ratio = invested[1] / invested[0]
            annual["percent"] = round((ratio ** (365 / span_days) - 1) * 100, 1)
            annual["reason"] = ""

        categories = []
        by_category: dict[str, list[dict[str, Any]]] = {}
        for row in assets_rows:
            by_category.setdefault(row["category"], []).append(row)
        for name, rows in by_category.items():
            value = round(sum(row["value"] for row in rows), 2)
            category_series = [
                {"date": day.isoformat(), "value": round(sum(max(value_at(row["id"], day) or 0, 0.0) for row in rows), 2)}
                for day in sampled
            ]
            categories.append(self._category(name, value, total_assets, rows, category_series, growth(rows), histories, start_day, today, False))
        if liquidities > 0:
            cash_series = [{"date": day.isoformat(), "value": round(max(liquidity_at(day), 0.0), 2)} for day in sampled]
            cash_change = round(liquidities - cash_series[0]["value"], 2)
            categories.append({
                "name": "Liquidités", "value": round(liquidities, 2),
                "weight": round(liquidities / total_assets * 100, 1) if total_assets else 0.0,
                "assetIds": [], "count": 0, "isCash": True, "series": cash_series,
                "change": {"amount": cash_change, "percent": round(cash_change / cash_series[0]["value"] * 100, 1) if cash_series[0]["value"] else None},
                "volatility": None, "volatilityReason": "Non applicable aux liquidités.",
                "tri": None, "triReason": "Non applicable aux liquidités.",
            })
        categories.sort(key=lambda item: item["value"], reverse=True)

        debts = []
        for row in debt_rows:
            details = row["details"]
            balance = abs(row["value"])
            monthly = _float_or_none(details.get("monthlyPayment"))
            end = _parse_date(details.get("endDate"))
            months_left = max(0, (end.year - today.year) * 12 + end.month - today.month) if end else None
            initial = _float_or_none(details.get("initialAmount"))
            debts.append({
                "id": row["id"], "name": row["name"], "category": row["category"], "balance": round(balance, 2),
                "shareOfAssets": round(balance / total_assets * 100, 1) if total_assets else 0.0,
                "monthlyPayment": monthly, "endDate": end.isoformat() if end else None, "monthsLeft": months_left,
                "rate": _float_or_none(details.get("rate")), "initialAmount": initial,
                "repaidPercent": round((initial - balance) / initial * 100, 1) if initial and initial >= balance else None,
                "interestLeft": round(monthly * months_left - balance, 2) if monthly and months_left and monthly * months_left > balance else None,
                "series": [{"date": day.isoformat(), "value": round(abs(value_at(row["id"], day) or 0), 2)} for day in sampled],
            })
        debts.sort(key=lambda item: item["balance"], reverse=True)

        return {
            "series": series,
            "headline": {"netWorth": net, "change": change, "annualReturn": annual},
            "categories": categories,
            "debts": debts,
        }

    @staticmethod
    def _category(
        name: str,
        value: float,
        total_assets: float,
        rows: list[dict[str, Any]],
        series: list[dict[str, Any]],
        growth: tuple[float, float] | None,
        histories: dict[int, list[tuple[date, float]]],
        start_day: date,
        today: date,
        is_cash: bool,
    ) -> dict[str, Any]:
        change = None
        if growth:
            amount = round(growth[1] - growth[0], 2)
            change = {"amount": amount, "percent": round(amount / growth[0] * 100, 1)}
        distinct_days = {day for row in rows for day, _ in histories.get(row["id"], []) if start_day <= day <= today}
        volatility = None
        reason = "Moins de 7 valorisations saisies : non applicable."
        values = [point["value"] for point in series]
        if len(distinct_days) >= 7:
            returns = [values[i] / values[i - 1] - 1 for i in range(1, len(values)) if values[i - 1] > 0]
            if len(returns) >= 6:
                mean = sum(returns) / len(returns)
                variance = sum((item - mean) ** 2 for item in returns) / (len(returns) - 1)
                volatility = round(math.sqrt(variance) * math.sqrt(12) * 100, 1)
                reason = ""
        return {
            "name": name, "value": value,
            "weight": round(value / total_assets * 100, 1) if total_assets else 0.0,
            "assetIds": [row["id"] for row in rows], "count": len(rows), "isCash": is_cash, "series": series,
            "change": change, "volatility": volatility, "volatilityReason": reason,
            "tri": None, "triReason": "Versements non saisis : le TRI ne peut pas être calculé.",
        }

    @staticmethod
    def _asset(row: Any) -> dict[str, Any]:
        raw_details = _field(row, "details_json", "{}")
        try:
            details = raw_details if isinstance(raw_details, dict) else json.loads(str(raw_details or "{}"))
        except (TypeError, ValueError):
            details = {}
        return {
            "id": int(_field(row, "id", 0) or 0),
            "name": str(_field(row, "name", "Élément patrimonial") or "Élément patrimonial"),
            "category": str(_field(row, "category", "Autres actifs") or "Autres actifs"),
            "type": str(_field(row, "asset_type", "Actif") or "Actif"),
            "value": _number(_field(row, "value", 0)),
            "valuationDate": str(_field(row, "valuation_date", "") or ""),
            "valuationMode": str(_field(row, "valuation_mode", "Manuelle") or "Manuelle"),
            "status": str(_field(row, "status", "Actif") or "Actif"),
            "comment": str(_field(row, "comment", "") or ""),
            "details": {str(key): str(value) for key, value in details.items()} if isinstance(details, dict) else {},
        }

    @staticmethod
    def _is_patrimonial(row: dict[str, Any]) -> bool:
        return is_patrimonial_asset(row.get("name"), row.get("category"), row.get("type"))

    def _evolution(self) -> list[dict[str, Any]]:
        raw = {
            "net": list(self.database.patrimonio_evolution("net")),
            "assets": list(self.database.patrimonio_evolution("assets")),
            "liabilities": list(self.database.patrimonio_evolution("liabilities")),
        }
        dates = sorted({str(point.get("date") or "") for values in raw.values() for point in values if point.get("date")})[-8:]
        if not dates:
            return []
        indexed = {
            name: {str(point.get("date") or ""): _number(point.get("value")) for point in values}
            for name, values in raw.items()
        }
        return [
            {
                "date": value_date,
                "net": indexed["net"].get(value_date, 0.0),
                "assets": indexed["assets"].get(value_date, 0.0),
                "liabilities": -abs(indexed["liabilities"].get(value_date, 0.0)),
            }
            for value_date in dates
        ]

    @staticmethod
    def _families(assets: list[dict[str, Any]], total_assets: float, live_liquidities: float = 0.0) -> list[dict[str, Any]]:
        values: dict[str, float] = {}
        for asset in assets:
            values[asset["category"]] = round(values.get(asset["category"], 0) + asset["value"], 2)
        if live_liquidities > 0:
            values["Liquidités"] = round(values.get("Liquidités", 0) + live_liquidities, 2)
        return [
            {
                "name": name,
                "value": value,
                "weight": round(value / total_assets * 100, 1) if total_assets else 0.0,
                "status": "Disponible" if "liquid" in name.lower() or "compte" in name.lower() else "Actif",
            }
            for name, value in sorted(values.items(), key=lambda item: item[1], reverse=True)
        ]
