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
        report = self.database.budget_report(month)
        selected_month = str(report.get("month") or month or "")
        transactions = list(self.database.list_transactions())
        report_rows = report.get("rows") or []
        rows = [self._row(row, selected_month, transactions) for row in report_rows]
        biggest_gap_row = max(rows, key=lambda row: row["difference"], default=None)

        return {
            "generatedAt": self.now_provider().isoformat(),
            "currency": "EUR",
            "month": selected_month,
            "months": [str(item) for item in self.database.budget_months()],
            "summary": {
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
            },
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
