from __future__ import annotations

from datetime import date, datetime, timezone
import math
import re
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

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create an account through the existing database business boundary."""
        data = self._validated_account(payload)
        self._ensure_unique_identifier(data["identifier"])
        previous_ids = {
            int(_field(row, "id", 0) or 0)
            for row in self.database.list_accounts()
        }
        self.database.add_account(data)
        created_ids = [
            int(_field(row, "id", 0) or 0)
            for row in self.database.list_accounts()
            if int(_field(row, "id", 0) or 0) not in previous_ids
        ]
        return {
            "success": True,
            "message": "Le compte a été ajouté.",
            "accountId": max(created_ids, default=0),
        }

    def update(self, account_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        """Update account metadata without silently changing its balance anchor."""
        self._find_account(account_id)
        data = self._validated_account(payload, require_reference=False)
        self._ensure_unique_identifier(data["identifier"], account_id)
        self.database.update_account(account_id, data)
        return {
            "success": True,
            "message": "Le compte a été modifié.",
            "accountId": account_id,
        }

    def update_reference(
        self,
        account_id: int,
        balance: Any,
        reference_date: Any,
    ) -> dict[str, Any]:
        """Move the balance anchor through Database.update_account_reference."""
        self._find_account(account_id)
        normalized_balance = self._balance(balance)
        normalized_date = self._date(reference_date, "La date initiale")
        self.database.update_account_reference(account_id, normalized_balance, normalized_date)
        return {
            "success": True,
            "message": "Le solde initial a été mis à jour.",
            "accountId": account_id,
        }

    def _validated_account(
        self,
        payload: dict[str, Any],
        *,
        require_reference: bool = True,
    ) -> dict[str, Any]:
        allowed_types = {
            "Compte courant",
            "Compte épargne",
            "Compte investissement",
            "Compte crédit",
            "Compte espèces",
            "Autre",
        }
        allowed_currencies = {"EUR", "USD", "GBP", "CHF"}
        allowed_statuses = {"Actif", "Archivé", "Clos"}

        name = str(payload.get("name", "")).strip()
        bank = str(payload.get("bank", "")).strip()
        account_type = str(payload.get("account_type", "")).strip()
        identifier = str(payload.get("identifier", "")).strip()
        currency = str(payload.get("currency", "EUR")).strip().upper()
        status = str(payload.get("status", "Actif")).strip()

        if not name:
            raise ValueError("Le nom du compte est obligatoire.")
        if not bank:
            raise ValueError("La banque est obligatoire.")
        if account_type not in allowed_types:
            raise ValueError("Le type de compte n’est pas reconnu.")
        if currency not in allowed_currencies:
            raise ValueError("La devise n’est pas prise en charge.")
        if status not in allowed_statuses:
            raise ValueError("Le statut du compte n’est pas reconnu.")

        initial_balance = self._balance(payload.get("initial_balance", 0))
        initial_date = str(payload.get("initial_date", "") or "").strip()
        if require_reference:
            initial_date = self._date(initial_date, "La date initiale")
        elif initial_date:
            initial_date = self._date(initial_date, "La date initiale")

        return {
            "name": name,
            "bank": bank,
            "account_type": account_type,
            "identifier": identifier,
            "initial_balance": initial_balance,
            "initial_date": initial_date or self.now_provider().date().isoformat(),
            "reference_balance": initial_balance,
            "reference_date": initial_date or self.now_provider().date().isoformat(),
            "currency": currency,
            "status": status,
        }

    def _find_account(self, account_id: int) -> Any:
        for row in self.database.list_accounts():
            if int(_field(row, "id", 0) or 0) == account_id:
                return row
        raise KeyError("Ce compte n’existe pas.")

    def _ensure_unique_identifier(self, identifier: str, account_id: int | None = None) -> None:
        normalized = self._normalized_identifier(identifier)
        if not normalized:
            return
        for row in self.database.list_accounts():
            row_id = int(_field(row, "id", 0) or 0)
            if row_id == account_id:
                continue
            if self._normalized_identifier(str(_field(row, "identifier", "") or "")) == normalized:
                raise ValueError("Cet identifiant bancaire est déjà rattaché à un autre compte.")

    @staticmethod
    def _normalized_identifier(value: str) -> str:
        return re.sub(r"[^0-9a-z]", "", value.casefold())

    @staticmethod
    def _balance(value: Any) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Le solde initial doit être un nombre.") from exc
        if not math.isfinite(result):
            raise ValueError("Le solde initial doit être un nombre fini.")
        return round(result, 2)

    @staticmethod
    def _date(value: Any, label: str) -> str:
        normalized = str(value or "").strip()
        try:
            return date.fromisoformat(normalized).isoformat()
        except ValueError as exc:
            raise ValueError(f"{label} est obligatoire et doit être valide.") from exc

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
            "transactions": [self._transaction(item) for item in transactions[:12]],
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
