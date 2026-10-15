from __future__ import annotations

from datetime import date, datetime, timezone
import math
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
    """Expose the transaction journal through a stable application contract."""

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

    def update(self, transaction_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate an edit then delegate every business side effect to Database."""
        row = self.database.get_transaction(transaction_id)
        if row is None:
            raise KeyError("Cette transaction n’existe pas.")

        account_id = _integer(payload.get("account_id"))
        if not any(_integer(_field(account, "id", 0)) == account_id for account in self.database.list_accounts()):
            raise ValueError("Le compte sélectionné n’existe pas.")

        transaction_date = str(payload.get("tx_date", "") or "").strip()
        try:
            transaction_date = date.fromisoformat(transaction_date).isoformat()
        except ValueError as exc:
            raise ValueError("La date de transaction est obligatoire et doit être valide.") from exc

        label = str(payload.get("label", "") or "").strip()
        if not label:
            raise ValueError("Le libellé de la transaction est obligatoire.")

        category = str(payload.get("category", "") or "").strip()
        if category.casefold() == "à catégoriser".casefold():
            category = ""
        categories = {
            str(_field(item, "name", "") or "").strip()
            for item in self.database.list_categories()
        }
        if category and category not in categories:
            raise ValueError("La catégorie sélectionnée n’existe pas.")

        direction = str(payload.get("direction", "") or "").strip()
        if direction not in {"Débit", "Crédit"}:
            raise ValueError("Le sens doit être Débit ou Crédit.")
        try:
            absolute_amount = abs(float(payload.get("amount", 0)))
        except (TypeError, ValueError) as exc:
            raise ValueError("Le montant doit être un nombre.") from exc
        if not math.isfinite(absolute_amount):
            raise ValueError("Le montant doit être un nombre fini.")
        amount = -absolute_amount if direction == "Débit" else absolute_amount

        status = str(payload.get("status", "") or "").strip()
        allowed_statuses = {
            "Validée",
            "À catégoriser",
            "Catégorisée automatiquement",
            "À vérifier",
            "À revoir",
            "À confirmer",
            "Règle auto",
            "Rapprochée",
            str(_field(row, "status", "") or "").strip(),
        }
        if not category:
            status = "À catégoriser"
        elif status not in allowed_statuses:
            raise ValueError("Le statut sélectionné n’est pas reconnu.")

        self.database.update_transaction(transaction_id, {
            "account_id": account_id,
            "tx_date": transaction_date,
            "label": label,
            "category": category or None,
            "amount": round(amount, 2),
            "direction_explicit": True,
            "status": status,
        })
        return {
            "success": True,
            "message": "La transaction a été mise à jour.",
            "transactionId": transaction_id,
        }

    def bulk_update(
        self,
        transaction_ids: list[int],
        action: str,
        category: str | None = None,
    ) -> dict[str, Any]:
        """Apply one explicit, bounded bulk action through existing DB methods."""
        ids = list(dict.fromkeys(_integer(value) for value in transaction_ids if _integer(value) > 0))
        if not ids:
            raise ValueError("Sélectionnez au moins une transaction.")
        if len(ids) > 500:
            raise ValueError("Le traitement en lot est limité à 500 transactions.")

        rows = []
        for transaction_id in ids:
            row = self.database.get_transaction(transaction_id)
            if row is None:
                raise KeyError(f"La transaction n°{transaction_id} n’existe pas.")
            rows.append(row)

        if action == "category":
            clean_category = str(category or "").strip()
            categories = {
                str(_field(item, "name", "") or "").strip()
                for item in self.database.list_categories()
            }
            if not clean_category or clean_category not in categories:
                raise ValueError("Choisissez une catégorie existante.")
            updated = self.database.update_transactions_category(ids, clean_category)
            message = f"{updated} transaction(s) catégorisée(s)."
        elif action == "validate":
            uncategorized = [
                row
                for row in rows
                if not str(_field(row, "category", "") or "").strip()
                or str(_field(row, "category", "") or "").strip().casefold() == "à catégoriser".casefold()
            ]
            if uncategorized:
                raise ValueError(
                    "Catégorisez toutes les transactions sélectionnées avant de les valider."
                )
            updated = self.database.update_transactions_status(ids, "Validée")
            message = f"{updated} transaction(s) validée(s)."
        else:
            raise ValueError("L’action groupée demandée n’est pas reconnue.")

        return {
            "success": True,
            "message": message,
            "updatedCount": int(updated),
            "transactionIds": ids,
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
