from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable

from app.services.business_rules import is_uncategorized_transaction


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


class SettingsReadService:
    """Single React adapter for settings already owned by Python services.

    This adapter deliberately does not reimplement category, automatic
    categorisation or security rules. It exposes their existing owners through
    one stable contract so the R8 settings screen cannot drift from the desktop
    application.
    """

    def __init__(
        self,
        database: Any,
        categorization_service_factory: Callable[[Any], Any] | None = None,
        now_provider: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if categorization_service_factory is None:
            from app.services.categorization_rule_service import CategorizationRuleService

            categorization_service_factory = CategorizationRuleService
        self.database = database
        self.categorization = categorization_service_factory(database)
        self.now_provider = now_provider

    def snapshot(self) -> dict[str, Any]:
        report = self.database.data_quality_report()
        security = self.database.security_audit_report()
        categories = list(self.database.category_usage_summary())
        accounts = list(self.database.list_accounts())
        rules = list(self.categorization.list_rules())

        return {
            "generatedAt": self.now_provider().isoformat(),
            "general": {
                "currency": str(self.database.get_setting("currency", "EUR") or "EUR"),
                "locale": str(self.database.get_user_preference("locale.default", "fr") or "fr"),
                "currentMonth": str(self.database.get_setting("current_month", "") or ""),
                "databaseSizeKb": _number(report.get("db_size_kb")),
                "schemaVersion": str(report.get("schema_version") or ""),
                "integrity": str(report.get("sqlite_integrity") or "inconnu"),
                "lastBackup": str(self.database.get_setting("last_backup_path", "") or ""),
            },
            "categories": [self._category(row) for row in categories],
            "rules": [self._rule(row) for row in rules],
            "pendingCount": len(self._pending_transactions()),
            "options": {
                "accounts": [
                    {
                        "id": int(_field(row, "id", 0) or 0),
                        "name": str(_field(row, "name", "Compte") or "Compte"),
                        "bank": str(_field(row, "bank", "") or ""),
                    }
                    for row in accounts
                    if str(_field(row, "status", "Actif") or "Actif") == "Actif"
                ],
                "categories": [
                    {"id": int(_field(row, "id", 0) or 0), "name": str(_field(row, "name", "") or "")}
                    for row in categories
                ],
                "matchFields": [
                    {"id": key, "label": label}
                    for key, label in self.categorization.MATCH_FIELDS.items()
                ],
                "operators": [
                    {"id": key, "label": label}
                    for key, label in self.categorization.OPERATORS.items()
                ],
                "transactionTypes": list(self.categorization.TRANSACTION_TYPES),
            },
            "balances": {
                "accounts": [self._balance(row) for row in accounts],
                "summary": {
                    "accountCount": int(report.get("accounts") or 0),
                    "orphanTransactions": int(report.get("orphan_transactions") or 0),
                    "orphanImportLinks": int(report.get("orphan_import_links") or 0),
                    "revenuesGap": _number(report.get("revenues_gap")),
                    "expensesGap": _number(report.get("expenses_gap")),
                },
            },
            "security": {
                "encryptedVault": bool(security.get("sqlite_encrypted")),
                "encryptedBackups": bool(security.get("backups_encrypted")),
                "masterPassword": bool(security.get("master_password_enabled")),
                "algorithm": str(security.get("master_password_algorithm") or ""),
                "keyStorage": str(security.get("key_storage") or ""),
                "sessionTimeoutMinutes": int(security.get("session_timeout_minutes") or 10),
                "lastBackup": str(security.get("last_backup_path") or ""),
            },
            "ownership": [
                {"feature": "Catégories", "owner": "Database.category_usage_summary", "mode": "édition partagée"},
                {"feature": "Règles auto", "owner": "CategorizationRuleService", "mode": "édition partagée"},
                {"feature": "Soldes", "owner": "Comptes + Rapprochements", "mode": "contrôle et renvoi"},
                {"feature": "Sécurité", "owner": "AuthService + audit local", "mode": "réglage partagé"},
            ],
        }

    def update_general(self, values: dict[str, Any]) -> dict[str, Any]:
        currency = str(values.get("currency") or "EUR").strip().upper()
        if currency != "EUR":
            raise ValueError("La bêta locale prend actuellement en charge la devise EUR.")
        month = str(values.get("current_month") or "").strip()
        if month and not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
            raise ValueError("Le mois courant doit respecter le format AAAA-MM.")
        timeout = int(values.get("session_timeout_minutes") or 10)
        if timeout < 1 or timeout > 120:
            raise ValueError("Le verrouillage de session doit être compris entre 1 et 120 minutes.")

        self.database.set_setting("currency", currency)
        if month:
            self.database.set_setting("current_month", month)
        self.database.set_setting("security.session_timeout_minutes", str(timeout))
        self._seal()
        return {"success": True, "message": "Paramètres généraux enregistrés."}

    def save_category(self, values: dict[str, Any], category_id: int | None = None) -> dict[str, Any]:
        payload = {
            "name": str(values.get("name") or "").strip(),
            "kind": str(values.get("kind") or "Dépense"),
            "color": str(values.get("color") or "#64748B"),
            "budget_enabled": bool(values.get("budget_enabled", True)),
            "direction": str(values.get("direction") or "Dépense"),
        }
        if not payload["name"]:
            raise ValueError("Le nom de catégorie est obligatoire.")
        if category_id is None:
            created_id = int(self.database.add_category(**payload))
            return {"success": True, "message": "Catégorie créée.", "id": created_id}
        self.database.update_category(category_id, **payload)
        return {"success": True, "message": "Catégorie mise à jour.", "id": category_id}

    def delete_category(self, category_id: int) -> dict[str, Any]:
        for row in self.database.category_usage_summary():
            if int(_field(row, "id", 0) or 0) == int(category_id) and bool(_field(row, "is_system", 0)):
                raise ValueError("Une catégorie système ne peut pas être supprimée.")
        self.database.delete_category(category_id)
        return {"success": True, "message": "Catégorie supprimée."}

    def save_rule(self, values: dict[str, Any], rule_id: int | None = None) -> dict[str, Any]:
        payload = {
            "name": values.get("name"),
            "description": values.get("description") or "",
            "is_active": bool(values.get("is_active", True)),
            "priority": values.get("priority") or 100,
            "match_field": values.get("match_field") or "label",
            "match_operator": values.get("match_operator") or "contains",
            "match_value": values.get("match_value") or "",
            "transaction_type": values.get("transaction_type") or None,
            "account_id": values.get("account_id") or None,
            "min_amount": values.get("min_amount"),
            "max_amount": values.get("max_amount"),
            "target_category_id": values.get("target_category_id"),
            "confidence": values.get("confidence") or 100,
        }
        if rule_id is None:
            created_id = int(self.categorization.create_rule(payload))
            return {"success": True, "message": "Règle créée.", "id": created_id}
        self.categorization.update_rule(rule_id, payload)
        return {"success": True, "message": "Règle mise à jour.", "id": rule_id}

    def create_rule_from_transaction(
        self,
        transaction_id: int,
        target_category_id: int,
        match_value: str | None = None,
    ) -> dict[str, Any]:
        if target_category_id <= 0:
            raise ValueError("La catégorie cible est obligatoire.")
        clean_match_value = str(match_value or "").strip()
        if match_value is not None and not clean_match_value:
            raise ValueError("Le libellé à rechercher est obligatoire.")
        options = {"match_value": clean_match_value} if clean_match_value else None
        created_id = int(
            self.categorization.create_rule_from_transaction(
                transaction_id,
                target_category_id,
                options,
            )
        )
        return {
            "success": True,
            "message": "Règle créée pour les prochaines opérations similaires.",
            "id": created_id,
        }

    def set_rule_active(self, rule_id: int, active: bool) -> dict[str, Any]:
        self.categorization.set_rule_active(rule_id, active)
        return {
            "success": True,
            "message": "Règle activée." if active else "Règle mise en pause.",
            "id": rule_id,
        }

    def delete_rule(self, rule_id: int) -> dict[str, Any]:
        if self.categorization.get_rule(rule_id) is None:
            raise ValueError("Règle introuvable.")
        self.categorization.delete_rule(rule_id)
        return {"success": True, "message": "Règle supprimée.", "id": rule_id}

    def _pending_transactions(self) -> list[Any]:
        """Opérations « À catégoriser » encore ouvertes (comptes actifs, hors saisies manuelles validées)."""
        with self.database.connect() as conn:
            rows = list(conn.execute(
                """
                SELECT t.*, a.name AS account_name, a.bank AS bank
                FROM transactions t
                JOIN accounts a ON a.id = t.account_id
                WHERE a.status = 'Actif'
                ORDER BY t.tx_date DESC, t.id DESC
                """
            ))
        locked = {"manual", "validated"}
        return [
            row for row in rows
            if is_uncategorized_transaction(_field(row, "category"), _field(row, "status"))
            and _field(row, "categorization_status") not in locked
        ]

    def pending_preview(self, rule_id: int | None = None) -> dict[str, Any]:
        """Simulation : opérations en attente que les règles actives (ou une seule) classeraient.

        Rien n'est modifié. Les opérations déjà catégorisées ne sont jamais concernées.
        """
        rules = list(self.categorization.active_rules())
        if rule_id is not None:
            rules = [rule for rule in rules if int(rule["id"]) == int(rule_id)]
            if not rules:
                raise ValueError("Cette règle est inactive ou introuvable.")
        pending = self._pending_transactions()
        items: list[dict[str, Any]] = []
        by_rule: dict[int, dict[str, Any]] = {}
        for transaction in pending:
            for rule in rules:
                ok, _ = self.categorization.rule_matches(rule, transaction)
                if not ok:
                    continue
                current_id = int(rule["id"])
                entry = by_rule.setdefault(current_id, {
                    "ruleId": current_id,
                    "ruleName": str(rule["name"] or ""),
                    "summary": str(self.categorization.rule_summary(rule)),
                    "category": str(rule["target_category"] or ""),
                    "count": 0,
                })
                entry["count"] += 1
                items.append({
                    "id": int(transaction["id"]),
                    "date": str(transaction["tx_date"] or ""),
                    "label": str(transaction["label"] or ""),
                    "amount": _number(transaction["amount"]),
                    "account": str(transaction["account_name"] or ""),
                    "ruleId": current_id,
                    "category": str(rule["target_category"] or ""),
                })
                break
        matched = len(items)
        return {
            "pendingCount": len(pending),
            "matchedCount": matched,
            "unmatchedCount": len(pending) - matched,
            "byRule": sorted(by_rule.values(), key=lambda entry: (-entry["count"], entry["ruleName"])),
            "items": items,
        }

    def apply_pending(self, transaction_ids: list[int], rule_id: int | None = None) -> dict[str, Any]:
        """Classe les opérations choisies, parmi celles que la simulation proposait."""
        allowed = {item["id"] for item in self.pending_preview(rule_id)["items"]}
        wanted = [int(value) for value in transaction_ids if int(value) in allowed]
        if not wanted:
            raise ValueError("Aucune opération à classer.")
        summary = self.categorization.apply_rules_to_transactions(wanted, force=False, only_rule_id=rule_id)
        classified = int(summary["auto"]) + int(summary["to_review"])
        self._seal()
        plural = "s" if classified > 1 else ""
        return {
            "success": True,
            "classified": classified,
            "toReview": int(summary["to_review"]),
            "message": f"{classified} opération{plural} classée{plural}.",
        }

    def preview_rules(self) -> dict[str, Any]:
        rules = list(self.categorization.active_rules())
        with self.database.connect() as conn:
            transactions = list(conn.execute(
                """
                SELECT t.*, a.name AS account_name, a.bank AS bank
                FROM transactions t
                JOIN accounts a ON a.id = t.account_id
                ORDER BY t.tx_date DESC, t.id DESC
                """
            ))
        matched = []
        by_rule: dict[int, int] = {}
        for transaction in transactions:
            for rule in rules:
                ok, _ = self.categorization.rule_matches(rule, transaction)
                if not ok:
                    continue
                rule_id = int(_field(rule, "id", 0) or 0)
                by_rule[rule_id] = by_rule.get(rule_id, 0) + 1
                if len(matched) < 5:
                    matched.append({
                        "transactionId": int(_field(transaction, "id", 0) or 0),
                        "label": str(_field(transaction, "label", "Transaction") or "Transaction"),
                        "ruleId": rule_id,
                        "category": str(_field(rule, "target_category", "") or ""),
                    })
                break
        return {
            "success": True,
            "message": f"{sum(by_rule.values())} transaction(s) correspondraient aux règles actives.",
            "matchedCount": sum(by_rule.values()),
            "byRule": [{"ruleId": key, "count": value} for key, value in sorted(by_rule.items())],
            "samples": matched,
        }

    def _seal(self) -> None:
        seal = getattr(self.database, "seal_database_to_encrypted_vault", None)
        if callable(seal):
            seal()

    def _category(self, row: Any) -> dict[str, Any]:
        return {
            "id": int(_field(row, "id", 0) or 0),
            "name": str(_field(row, "name", "") or ""),
            "kind": str(_field(row, "kind", "Dépense") or "Dépense"),
            "direction": str(_field(row, "direction", "Dépense") or "Dépense"),
            "color": str(_field(row, "color", "#64748B") or "#64748B"),
            "budgetEnabled": bool(_field(row, "budget_enabled", 0)),
            "isSystem": bool(_field(row, "is_system", 0)),
            "usage": {
                "transactions": int(_field(row, "tx_count", 0) or 0),
                "recurrences": int(_field(row, "recurring_count", 0) or 0),
                "budgets": int(_field(row, "budget_count", 0) or 0),
            },
        }

    def _rule(self, row: Any) -> dict[str, Any]:
        return {
            "id": int(_field(row, "id", 0) or 0),
            "name": str(_field(row, "name", "") or ""),
            "description": str(_field(row, "description", "") or ""),
            "active": bool(_field(row, "is_active", 0)),
            "priority": int(_field(row, "priority", 100) or 100),
            "matchField": str(_field(row, "match_field", "label") or "label"),
            "matchOperator": str(_field(row, "match_operator", "contains") or "contains"),
            "matchValue": str(_field(row, "match_value", "") or ""),
            "transactionType": str(_field(row, "transaction_type", "Tous") or "Tous"),
            "accountId": int(_field(row, "account_id")) if _field(row, "account_id") is not None else None,
            "accountName": str(_field(row, "account_name", "Tous les comptes") or "Tous les comptes"),
            "minAmount": _number(_field(row, "min_amount")) if _field(row, "min_amount") is not None else None,
            "maxAmount": _number(_field(row, "max_amount")) if _field(row, "max_amount") is not None else None,
            "targetCategoryId": int(_field(row, "target_category_id", 0) or 0),
            "targetCategory": str(_field(row, "target_category", "Sans catégorie") or "Sans catégorie"),
            "confidence": int(_field(row, "confidence", 100) or 100),
            "usageCount": int(_field(row, "usage_count", 0) or 0),
            "lastUsedAt": str(_field(row, "last_used_at", "") or ""),
            "summary": str(self.categorization.rule_summary(row)),
        }

    @staticmethod
    def _balance(row: Any) -> dict[str, Any]:
        return {
            "id": int(_field(row, "id", 0) or 0),
            "name": str(_field(row, "name", "Compte") or "Compte"),
            "bank": str(_field(row, "bank", "") or ""),
            "status": str(_field(row, "status", "Actif") or "Actif"),
            "initialBalance": _number(_field(row, "effective_initial_balance", _field(row, "initial_balance", 0))),
            "initialDate": str(_field(row, "effective_initial_date", _field(row, "initial_date", "")) or ""),
            "movementTotal": _number(_field(row, "post_reference_movements", 0)),
            "currentBalance": _number(_field(row, "calculated_balance", 0)),
            "currentDate": str(_field(row, "calculated_date", "") or ""),
        }
