from __future__ import annotations

from datetime import datetime, timezone
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


class BudgetsReadService:
    """Expose monthly budget results and their supporting transactions."""

    def __init__(
        self,
        database: Any,
        now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.database = database
        self.now_provider = now_provider

    def snapshot(self, month: str | None = None) -> dict[str, Any]:
        # Default to the real current month (same rule as the Dashboard), not to
        # the historical "current_month" setting that can stay on an old month.
        default_month = getattr(self.database, "dashboard_current_month", None)
        if month is None and callable(default_month):
            month = default_month()
        report = self.database.budget_report(month)
        selected_month = str(report.get("month") or month or "")
        transactions = list(self.database.list_transactions())
        report_rows = report.get("rows") or []
        rows = [self._row(row, selected_month, transactions) for row in report_rows]
        biggest_gap_row = max(rows, key=lambda row: row["difference"], default=None)

        summary = {
            "totalPlanned": _number(report.get("total_planned")),
            "totalRealized": _number(report.get("total_realized")),
            "totalRemaining": _number(report.get("total_remaining")),
            "usageTotal": _number(report.get("usage_total")),
            "categoryCount": len(rows),
            "overCount": int(report.get("over_count") or 0),
            "warningCount": int(report.get("warning_count") or 0),
            "status": str(report.get("status") or "OK"),
            "biggestGap": _number((biggest_gap_row or {}).get("difference")),
            "biggestGapCategory": str((biggest_gap_row or {}).get("category") or "Aucun écart"),
        }
        extras: dict[str, Any] = {}
        if hasattr(self.database, "budget_year_matrix") and selected_month:
            extras = BudgetsAnalytics(self.database, self.now_provider().date()).build(selected_month, rows, summary, transactions)

        return {
            **extras,
            "generatedAt": self.now_provider().isoformat(),
            "currency": "EUR",
            "month": selected_month,
            "months": [str(item) for item in self.database.budget_months()],
            "summary": summary,
            "rows": rows,
        }

    @staticmethod
    def _row(row: dict[str, Any], month: str, transactions: list[Any]) -> dict[str, Any]:
        category = str(row.get("category") or "Sans catégorie")
        planned = _number(row.get("planned"))
        actual = _number(row.get("actual"))
        matching = [
            transaction for transaction in transactions
            if str(_field(transaction, "tx_date", "")).startswith(month)
            and str(_field(transaction, "category", "") or "À catégoriser") == category
            and _number(_field(transaction, "amount", 0)) < 0
        ]
        matching.sort(key=lambda transaction: abs(_number(_field(transaction, "amount", 0))), reverse=True)
        return {
            "id": row.get("id"),
            "category": category,
            "planned": planned,
            "actual": actual,
            "remaining": _number(row.get("remaining")),
            "difference": _number(actual - planned),
            "usage": _number(row.get("usage")),
            "alertThreshold": _number(row.get("alert_threshold")),
            "status": str(row.get("status") or "OK"),
            "notes": str(row.get("notes") or ""),
            "transactions": [
                {
                    "id": int(_field(transaction, "id", 0) or 0),
                    "date": str(_field(transaction, "tx_date", "") or ""),
                    "label": str(_field(transaction, "label", "Mouvement") or "Mouvement"),
                    "amount": _number(_field(transaction, "amount", 0)),
                }
                for transaction in matching[:3]
            ],
        }


MONTH_NAMES = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def _month_label(month: str) -> str:
    try:
        return f"{MONTH_NAMES[int(month[5:7]) - 1]} {month[:4]}"
    except (ValueError, IndexError):
        return month


class BudgetsAnalytics:
    """Suivi, comparatif annuel et paramétrage construits à partir de la matrice annuelle."""

    STATUS_ORDER = {"Dépassement": 0, "Vigilance": 1, "Non budgété": 2, "OK": 3}

    def __init__(self, database: Any, today: Any) -> None:
        self.database = database
        self.today = today

    # -- utilitaires ----------------------------------------------------
    def elapsed_months(self, year: int) -> int:
        """Nombre de mois écoulés pour l'année (le mois en cours compte en entier)."""
        if year < self.today.year:
            return 12
        if year > self.today.year:
            return 0
        return self.today.month

    @staticmethod
    def months_over(planned: list[float], actual: list[float], last_index: int) -> int:
        count = 0
        for index in range(last_index, -1, -1):
            if planned[index] > 0 and actual[index] > planned[index]:
                count += 1
            else:
                break
        return count

    @staticmethod
    def month_projection(data: dict[str, Any], index: int, day: int, days: int, start_index: int) -> float:
        """Réalisé final estimé : le plus élevé entre le réalisé et la moyenne des 3 mois précédents."""
        actual = data["actual"][index]
        history = [value for value in data["actual"][max(start_index, index - 3):index]]
        if history and any(history):
            return round(max(actual, sum(history) / len(history)), 2)
        if day <= 0:
            return actual
        return round(max(actual, actual / day * days), 2)

    # -- blocs ----------------------------------------------------------
    def build(self, month: str, report_rows: list[dict[str, Any]], summary: dict[str, Any], transactions: list[Any]) -> dict[str, Any]:
        year = int(month[:4])
        index = int(month[5:7]) - 1
        matrix = self.database.budget_year_matrix(year)
        revisions = self.database.list_budget_revisions(str(year))
        start_index = 0
        if matrix.get("start") and str(matrix["start"])[:4] == str(year):
            start_index = int(str(matrix["start"])[5:7]) - 1
        elif matrix.get("start") and str(matrix["start"])[:4] > str(year):
            start_index = 12
        return {
            "tracking": self._tracking(month, year, index, matrix, report_rows, summary, transactions, start_index),
            "annual": self._annual(month, year, matrix, revisions, start_index),
            "settings": self._settings(month, index, matrix, revisions),
        }

    def _tracking(self, month, year, index, matrix, rows, summary, transactions, start_index) -> dict[str, Any]:
        current = self.today.strftime("%Y-%m")
        first = date_first(month)
        days = days_in_month(first)
        if month < current:
            elapsed = days
        elif month == current:
            elapsed = self.today.day
        else:
            elapsed = 0
        counted = {row["category"] for row in rows}
        daily = [0.0] * days
        for transaction in transactions:
            tx_date = str(_field(transaction, "tx_date", "") or "")
            amount = _number(_field(transaction, "amount", 0))
            category = str(_field(transaction, "category", "") or "À catégoriser")
            if tx_date.startswith(month) and amount < 0 and category in counted:
                try:
                    daily[int(tx_date[8:10]) - 1] += abs(amount)
                except (ValueError, IndexError):
                    continue
        planned_total = float(summary["totalPlanned"])
        curve, running = [], 0.0
        for day in range(1, days + 1):
            running += daily[day - 1]
            curve.append({
                "day": day,
                "budget": round(planned_total * day / days, 2),
                "actual": round(running, 2) if day <= elapsed else None,
            })
        realized = float(summary["totalRealized"])
        projection: float | None
        if month < current:
            projection = realized
        elif month > current:
            projection = None
        else:
            projection = round(sum(
                self.month_projection(matrix["categories"][row["category"]], index, elapsed, days, start_index)
                if row["category"] in matrix["categories"] else row["actual"]
                for row in rows
            ), 2)
        days_left = max(0, days - elapsed) if month >= current else 0
        remaining = round(planned_total - realized, 2)
        per_day = round(remaining / days_left, 2) if remaining > 0 and days_left > 0 else None
        watch = []
        for row in sorted(rows, key=lambda item: (self.STATUS_ORDER.get(item["status"], 3), -item["usage"])):
            if row["status"] == "OK":
                continue
            data = matrix["categories"].get(row["category"])
            over = self.months_over(data["planned"], data["actual"], index) if data else 0
            watch.append({**{key: row[key] for key in ("category", "planned", "actual", "usage", "status")}, "monthsOver": over, "suggestRevision": over >= 3})
        return {
            "daysInMonth": days,
            "elapsedDays": elapsed,
            "daysLeft": days_left,
            "perDay": per_day,
            "projection": projection,
            "projectionGap": round(projection - planned_total, 2) if projection is not None else None,
            "projectionMethod": "Le plus élevé entre le réalisé et la moyenne des 3 mois précédents (rythme linéaire sans historique).",
            "curve": curve,
            "watch": watch[:5],
            "watchOthers": max(0, len(watch) - 5),
        }

    def _annual(self, month, year, matrix, revisions, start_index) -> dict[str, Any]:
        elapsed = self.elapsed_months(year)
        current_index = elapsed - 1
        dim = days_in_month(date_first(self.today.strftime("%Y-%m")))
        categories = []
        for name, data in matrix["categories"].items():
            planned, initial, actual = data["planned"], data["initial"], data["actual"]
            cumul = round(sum(planned[:elapsed]), 2)
            real = round(sum(actual[:elapsed]), 2)
            history = [item for item in revisions if item["category"] == name]
            over = self.months_over(planned, actual, current_index) if current_index >= 0 else 0
            if year == self.today.year and current_index >= 0:
                projected_month = self.month_projection(data, current_index, self.today.day, dim, start_index)
                projected = round(sum(actual[:current_index]) + projected_month + sum(planned[current_index + 1:]), 2)
            else:
                projected = round(real + sum(planned[elapsed:]), 2)
            categories.append({
                "category": name,
                "planned": planned, "initial": initial, "actual": actual,
                "annual": round(sum(planned), 2), "initialAnnual": round(sum(initial), 2),
                "cumul": cumul, "initialCumul": round(sum(initial[:elapsed]), 2),
                "realized": real, "gap": round(real - cumul, 2),
                "usage": round(real / cumul * 100, 1) if cumul else (100.0 if real else 0.0),
                "projectedYear": projected,
                "monthsOver": over,
                "suggestRevision": over >= 3,
                "revisionCount": len(history),
                "revisions": [revision_dict(item) for item in history],
            })
        categories.sort(key=lambda item: -max(item["annual"], item["realized"]))
        totals = {
            "annual": round(sum(item["annual"] for item in categories), 2),
            "initialAnnual": round(sum(item["initialAnnual"] for item in categories), 2),
            "cumul": round(sum(item["cumul"] for item in categories), 2),
            "initialCumul": round(sum(item["initialCumul"] for item in categories), 2),
            "realized": round(sum(item["realized"] for item in categories), 2),
            "projectedYear": round(sum(item["projectedYear"] for item in categories), 2),
        }
        totals["gap"] = round(totals["realized"] - totals["cumul"], 2)
        return {"year": year, "elapsedMonths": elapsed, "currentMonth": self.today.strftime("%Y-%m"), "categories": categories, "totals": totals}

    def _settings(self, month, index, matrix, revisions) -> dict[str, Any]:
        rows = []
        for name, data in matrix["categories"].items():
            if not (data["active"][index] or data["inactive"][index]):
                continue
            history = [item for item in revisions if item["category"] == name]
            rows.append({
                "category": name,
                "active": bool(data["active"][index]),
                "amount": data["rawPlanned"][index],
                "initialAmount": data["initial"][index],
                "mode": data["mode"],
                "alertThreshold": data["alertThreshold"],
                "notes": data["notes"],
                "lastRevision": _month_label(history[-1]["from_month"]) if history else None,
                "revisions": [revision_dict(item) for item in history],
            })
        rows.sort(key=lambda item: (not item["active"], -item["amount"], item["category"]))
        listed = {row["category"] for row in rows}
        available = [name for name in self.database.budget_categories_available() if name not in listed]
        return {
            "defaultAlertThreshold": self.database.budget_default_threshold(),
            "modes": list(self.database.BUDGET_MODES),
            "categories": rows,
            "available": available,
        }


def date_first(month: str):
    from datetime import date
    return date(int(month[:4]), int(month[5:7]), 1)


def days_in_month(first) -> int:
    from calendar import monthrange
    return monthrange(first.year, first.month)[1]


def revision_dict(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(item["id"]),
        "scope": str(item["scope"]),
        "fromMonth": str(item["from_month"]),
        "toMonth": str(item["to_month"]),
        "oldAmount": _number(item["old_amount"]),
        "newAmount": _number(item["new_amount"]),
        "reason": str(item.get("reason") or ""),
        "createdAt": str(item.get("created_at") or ""),
    }
