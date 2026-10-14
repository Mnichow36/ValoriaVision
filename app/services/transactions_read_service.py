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


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _is_uncategorized(row: Any) -> bool:
    category = str(_field(row, "category", "") or "").strip().lower()
    status = str(_field(row, "status", "") or "").strip().lower()
    return not category or category == "à catégoriser" or status == "à catégoriser"


def _requires_review(row: Any) -> bool:
    if _is_uncategorized(row):
        return True
    status = str(_field(row, "status", "") or "").strip().lower()
    return status in {"à revoir", "a revoir", "à confirmer", "a confirmer"}


class TransactionsReadService:
    """Expose the transaction journal through a stable read-only contract."""

    def __init__(
        self,
        database: Any,
        now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.database = database
        self.now_provider = now_provider

    def snapshot(self) -> dict[str, Any]:
        raw_transactions = list(self.database.list_transactions())
        transactions = [self._transaction(row) for row in raw_transactions]
        accounts = [self._account(row) for row in self.database.list_accounts()]
        categories = [self._category(row) for row in self.database.list_categories()]
        recent_imports = list(self.database.list_recent_import_batches(1))
        categorized_count = sum(1 for row in raw_transactions if not _is_uncategorized(row))
        review_count = sum(1 for row in raw_transactions if _requires_review(row))
        transaction_count = len(transactions)

        return {
            "generatedAt": self.now_provider().isoformat(),
            "currency": "EUR",
            "summary": {
                "transactionCount": transaction_count,
                "categorizedCount": categorized_count,
                "categorizedPercent": round((categorized_count / transaction_count) * 100) if transaction_count else 100,
                "reviewCount": review_count,
            },
            "accounts": accounts,
            "categories": categories,
            "transactions": transactions,
            "recentImport": self._recent_import(recent_imports[0]) if recent_imports else None,
        }

    @staticmethod
    def _account(row: Any) -> dict[str, Any]:
        return {
            "id": _integer(_field(row, "id", 0)),
            "name": str(_field(row, "name", "Compte") or "Compte"),
            "bank": str(_field(row, "bank", "") or ""),
            "status": str(_field(row, "status", "Actif") or "Actif"),
        }

    @staticmethod
    def _category(row: Any) -> dict[str, Any]:
        return {
            "name": str(_field(row, "name", "") or ""),
            "kind": str(_field(row, "kind", "") or ""),
            "color": str(_field(row, "color", "") or ""),
        }

    @staticmethod
    def _transaction(row: Any) -> dict[str, Any]:
        return {
            "id": _integer(_field(row, "id", 0)),
            "date": str(_field(row, "tx_date", "") or ""),
            "accountId": _integer(_field(row, "account_id", 0)),
            "accountName": str(_field(row, "account_name", "Compte") or "Compte"),
            "bank": str(_field(row, "bank", "") or ""),
            "label": str(_field(row, "label", "Mouvement") or "Mouvement"),
            "category": str(_field(row, "category", "") or "À catégoriser"),
            "status": str(_field(row, "status", "") or "À catégoriser"),
            "amount": _number(_field(row, "amount", 0)),
            "type": str(_field(row, "tx_type", "") or ""),
            "source": str(_field(row, "source", "") or ""),
            "importBatchId": _integer(_field(row, "import_batch_id", 0)) or None,
        }

    @staticmethod
    def _recent_import(row: Any) -> dict[str, Any]:
        imported = _integer(_field(row, "imported_count", 0))
        duplicates = _integer(_field(row, "duplicate_count", 0))
        errors = _integer(_field(row, "error_count", 0))
        return {
            "id": _integer(_field(row, "id", 0)),
            "fileName": str(_field(row, "file_name", "Import bancaire") or "Import bancaire"),
            "accountName": str(_field(row, "account_name", "Compte") or "Compte"),
            "importedCount": imported,
            "duplicateCount": duplicates,
            "errorCount": errors,
            "recognizedCount": imported + duplicates + errors,
            "linkedTransactions": _integer(_field(row, "linked_transactions", 0)),
            "status": str(_field(row, "status", "") or ""),
            "createdAt": str(_field(row, "created_at", "") or ""),
        }
