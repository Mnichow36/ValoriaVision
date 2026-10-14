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


class AccountsReadService:
    """Expose the account engine through a stable, presentation-neutral contract."""

    def __init__(
        self,
        database: Any,
        now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.database = database
        self.now_provider = now_provider

    def snapshot(self) -> dict[str, Any]:
        accounts = [self._account(row) for row in self.database.list_accounts()]
        active_accounts = [account for account in accounts if account["status"] == "Actif"]
        return {
            "generatedAt": self.now_provider().isoformat(),
            "currency": "EUR",
            "summary": {
                "accountCount": len(accounts),
                "activeCount": len(active_accounts),
                "netBalance": round(sum(account["currentBalance"] for account in active_accounts), 2),
            },
            "accounts": accounts,
        }

    def _account(self, row: Any) -> dict[str, Any]:
        account_id = int(_field(row, "id", 0) or 0)
        transactions = self.database.list_transactions(account_id=account_id)
        initial_balance = _field(
            row,
            "effective_initial_balance",
            _field(row, "initial_balance", _field(row, "reference_balance", 0)),
        )
        initial_date = _field(
            row,
            "effective_initial_date",
            _field(row, "initial_date", _field(row, "reference_date", "")),
        )
        return {
            "id": account_id,
            "name": str(_field(row, "name", "Compte") or "Compte"),
            "bank": str(_field(row, "bank", "") or ""),
            "type": str(_field(row, "account_type", "") or ""),
            "identifier": str(_field(row, "identifier", "") or ""),
            "currency": str(_field(row, "currency", "EUR") or "EUR"),
            "status": str(_field(row, "status", "Actif") or "Actif"),
            "initialBalance": _number(initial_balance),
            "initialDate": str(initial_date or ""),
            "movementTotal": _number(_field(row, "post_reference_movements", 0)),
            "currentBalance": _number(_field(row, "calculated_balance", initial_balance)),
            "currentDate": str(_field(row, "calculated_date", initial_date) or ""),
            "transactions": [self._transaction(item) for item in transactions[:6]],
        }

    @staticmethod
    def _transaction(row: Any) -> dict[str, Any]:
        return {
            "id": int(_field(row, "id", 0) or 0),
            "date": str(_field(row, "tx_date", "") or ""),
            "label": str(_field(row, "label", "Mouvement") or "Mouvement"),
            "category": str(_field(row, "category", "") or "À catégoriser"),
            "amount": _number(_field(row, "amount", 0)),
            "status": str(_field(row, "status", "") or ""),
        }
