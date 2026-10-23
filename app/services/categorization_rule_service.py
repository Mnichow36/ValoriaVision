from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from app.services.counterparty_parser import extract_counterparty, normalize_bank_label


class CategorizationRuleService:
    """Business service for automatic categorization rules.

    V0.6.8.1 implements the simple and local V1 rule engine:
    - rules are applied by ascending priority;
    - first matching active rule wins;
    - validated/manual transactions are not overwritten unless forced for a new import batch;
    - bank labels are normalized before comparison.
    """

    MATCH_FIELDS = {
        "label": "Libellé",
        "beneficiary": "Bénéficiaire / émetteur",
    }

    OPERATORS = {
        "contains": "Contient",
        "starts_with": "Commence par",
        "equals": "Égal à",
        "amount_between": "Montant entre min/max",
    }

    TRANSACTION_TYPES = ["Tous", "Débit", "Crédit"]

    STATUS_TO_CATEGORIZE = "to_categorize"
    STATUS_AUTO = "auto"
    STATUS_MANUAL = "manual"
    STATUS_REVIEW = "to_review"
    STATUS_VALIDATED = "validated"

    def __init__(self, db) -> None:
        self.db = db

    @staticmethod
    def normalize_label(value: str | None) -> str:
        return normalize_bank_label(value)

    def list_rules(self, include_deleted: bool = False) -> list:
        where = "" if include_deleted else "WHERE r.deleted_at IS NULL"
        with self.db.connect() as conn:
            return list(conn.execute(
                f"""
                SELECT r.*, c.name AS target_category, c.deleted_at AS target_deleted,
                       a.name AS account_name, a.bank AS bank
                FROM categorization_rules r
                LEFT JOIN categories c ON c.id = r.target_category_id
                LEFT JOIN accounts a ON a.id = r.account_id
                {where}
                ORDER BY r.priority ASC, r.name ASC
                """
            ))

    def active_rules(self) -> list:
        with self.db.connect() as conn:
            return list(conn.execute(
                """
                SELECT r.*, c.name AS target_category, c.deleted_at AS target_deleted,
                       a.name AS account_name, a.bank AS bank
                FROM categorization_rules r
                JOIN categories c ON c.id = r.target_category_id
                LEFT JOIN accounts a ON a.id = r.account_id
                WHERE r.deleted_at IS NULL
                  AND r.is_active = 1
                  AND c.deleted_at IS NULL
                ORDER BY r.priority ASC, r.id ASC
                """
            ))

    def get_rule(self, rule_id: int):
        with self.db.connect() as conn:
            return conn.execute(
                """
                SELECT r.*, c.name AS target_category, a.name AS account_name
                FROM categorization_rules r
                LEFT JOIN categories c ON c.id = r.target_category_id
                LEFT JOIN accounts a ON a.id = r.account_id
                WHERE r.id = ?
                """,
                (rule_id,),
            ).fetchone()

    def category_id_by_name(self, name: str | None) -> int | None:
        if not name:
            return None
        with self.db.connect() as conn:
            row = conn.execute("SELECT id FROM categories WHERE name = ? AND deleted_at IS NULL", (name,)).fetchone()
        return int(row["id"]) if row else None

    def create_rule(self, data: dict) -> int:
        payload = self.validate_payload(data)
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO categorization_rules(uuid, name, description, is_active, priority, match_field,
                                                 match_operator, match_value, transaction_type, account_id,
                                                 min_amount, max_amount, target_category_id, confidence)
                VALUES (:uuid, :name, :description, :is_active, :priority, :match_field,
                        :match_operator, :match_value, :transaction_type, :account_id,
                        :min_amount, :max_amount, :target_category_id, :confidence)
                """,
                {"uuid": str(uuid4()), **payload},
            )
            rule_id = int(cur.lastrowid)
        self.db.seal_database_to_encrypted_vault()
        return rule_id

    def update_rule(self, rule_id: int, data: dict) -> None:
        payload = self.validate_payload(data)
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE categorization_rules
                SET name = :name, description = :description, is_active = :is_active,
                    priority = :priority, match_field = :match_field, match_operator = :match_operator,
                    match_value = :match_value, transaction_type = :transaction_type, account_id = :account_id,
                    min_amount = :min_amount, max_amount = :max_amount, target_category_id = :target_category_id,
                    confidence = :confidence, updated_at = CURRENT_TIMESTAMP
                WHERE id = :rule_id
                """,
                {"rule_id": rule_id, **payload},
            )
        self.db.seal_database_to_encrypted_vault()

    def delete_rule(self, rule_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE categorization_rules SET deleted_at = CURRENT_TIMESTAMP, is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (rule_id,),
            )
        self.db.seal_database_to_encrypted_vault()

    def set_rule_active(self, rule_id: int, active: bool) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE categorization_rules SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (1 if active else 0, rule_id),
            )
        self.db.seal_database_to_encrypted_vault()

    def validate_payload(self, data: dict) -> dict:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("Le nom de la règle est obligatoire.")
        match_field = data.get("match_field") or "label"
        if match_field not in self.MATCH_FIELDS:
            match_field = "label"
        operator = data.get("match_operator") or "contains"
        if operator not in self.OPERATORS:
            operator = "contains"
        match_value = (data.get("match_value") or "").strip()
        if operator != "amount_between" and not match_value:
            raise ValueError("La valeur de recherche est obligatoire.")
        target_category_id = int(data.get("target_category_id") or 0)
        if not target_category_id:
            raise ValueError("La catégorie cible est obligatoire.")
        tx_type = data.get("transaction_type") or None
        if tx_type == "Tous":
            tx_type = None
        return {
            "name": name,
            "description": data.get("description") or "",
            "is_active": 1 if data.get("is_active", True) else 0,
            "priority": int(data.get("priority") or 100),
            "match_field": match_field,
            "match_operator": operator,
            "match_value": match_value,
            "transaction_type": tx_type,
            "account_id": data.get("account_id"),
            "min_amount": data.get("min_amount"),
            "max_amount": data.get("max_amount"),
            "target_category_id": target_category_id,
            "confidence": int(data.get("confidence") or 100),
        }

    def transaction_row(self, transaction_id: int):
        with self.db.connect() as conn:
            return conn.execute(
                """
                SELECT t.*, a.name AS account_name, a.bank AS bank
                FROM transactions t
                JOIN accounts a ON a.id = t.account_id
                WHERE t.id = ?
                """,
                (transaction_id,),
            ).fetchone()

    def rule_matches(self, rule, tx) -> tuple[bool, str]:
        if rule["target_deleted"]:
            return False, "Catégorie cible supprimée"
        if rule["account_id"] and int(rule["account_id"]) != int(tx["account_id"]):
            return False, "Compte différent"
        amount = float(tx["amount"] or 0)
        tx_type = "Crédit" if amount >= 0 else "Débit"
        if rule["transaction_type"] and rule["transaction_type"] != tx_type:
            return False, "Type de flux différent"
        abs_amount = abs(amount)
        if rule["min_amount"] is not None and abs_amount < float(rule["min_amount"]):
            return False, "Montant inférieur au minimum"
        if rule["max_amount"] is not None and abs_amount > float(rule["max_amount"]):
            return False, "Montant supérieur au maximum"

        operator = rule["match_operator"]
        if operator == "amount_between":
            return True, "Montant dans la plage"

        field_name = rule["match_field"] or "label"
        if field_name == "beneficiary":
            try:
                beneficiary = tx["beneficiary"] if "beneficiary" in tx.keys() else ""
            except (AttributeError, KeyError, TypeError):
                beneficiary = ""
            field_value = beneficiary or extract_counterparty(tx["label"])
            field_label = "Bénéficiaire"
        else:
            field_value = tx["label"] or ""
            field_label = "Libellé"
        needle = self.normalize_label(rule["match_value"])
        haystack = self.normalize_label(field_value)
        if operator == "contains" and needle in haystack:
            return True, f"{field_label} contient « {rule['match_value']} »"
        if operator == "starts_with" and haystack.startswith(needle):
            return True, f"{field_label} commence par « {rule['match_value']} »"
        if operator == "equals" and haystack == needle:
            return True, f"{field_label} égal à « {rule['match_value']} »"
        return False, "Aucune correspondance"

    def categorize_transaction(self, transaction_id: int, force: bool = False, only_rule_id: int | None = None) -> dict:
        tx = self.transaction_row(transaction_id)
        if not tx:
            return {"status": "not_found", "rule_id": None, "category": None}

        if not force:
            if tx["categorization_status"] in {self.STATUS_MANUAL, self.STATUS_VALIDATED}:
                return {"status": "skipped", "reason": "manual_or_validated", "rule_id": None, "category": tx["category"]}
            if tx["status"] == "Validée" and tx["categorized_by"] == "manual":
                return {"status": "skipped", "reason": "validated_manual", "rule_id": None, "category": tx["category"]}

        for rule in self.active_rules():
            if only_rule_id is not None and int(rule["id"]) != int(only_rule_id):
                continue
            ok, reason = self.rule_matches(rule, tx)
            if not ok:
                continue
            confidence = int(rule["confidence"] or 100)
            cat_status = self.STATUS_AUTO if confidence >= 80 else self.STATUS_REVIEW
            ui_status = "Catégorisée automatiquement" if cat_status == self.STATUS_AUTO else "À vérifier"
            with self.db.connect() as conn:
                conn.execute(
                    """
                    UPDATE transactions
                    SET category = ?, status = ?, categorization_status = ?, categorized_by = 'auto_rule',
                        categorization_rule_id = ?, categorized_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (rule["target_category"], ui_status, cat_status, int(rule["id"]), transaction_id),
                )
                conn.execute(
                    """
                    UPDATE categorization_rules
                    SET last_used_at = CURRENT_TIMESTAMP, usage_count = COALESCE(usage_count, 0) + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (int(rule["id"]),),
                )
                conn.execute(
                    """
                    INSERT INTO categorization_rule_logs(uuid, rule_id, transaction_id, import_batch_id, result_status, match_reason)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (str(uuid4()), int(rule["id"]), transaction_id, tx["import_batch_id"], cat_status, reason),
                )
            return {"status": cat_status, "rule_id": int(rule["id"]), "category": rule["target_category"], "reason": reason}

        if only_rule_id is not None:
            # Application d'une règle précise : sans correspondance, on ne touche à rien.
            return {"status": "skipped", "reason": "no_match", "rule_id": None, "category": tx["category"]}

        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE transactions
                SET category = NULL, status = 'À catégoriser', categorization_status = 'to_categorize',
                    categorized_by = 'import_default', categorization_rule_id = NULL,
                    categorized_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND (categorized_by IS NULL OR categorized_by <> 'manual')
                """,
                (transaction_id,),
            )
        return {"status": self.STATUS_TO_CATEGORIZE, "rule_id": None, "category": None}


    def apply_rules_to_transactions(self, transaction_ids: list[int], force: bool = True, only_rule_id: int | None = None) -> dict:
        summary = {
            "processed": 0,
            "auto": 0,
            "to_review": 0,
            "to_categorize": 0,
            "skipped": 0,
            "rules_used": set(),
        }
        for transaction_id in transaction_ids:
            summary["processed"] += 1
            result = self.categorize_transaction(int(transaction_id), force=force, only_rule_id=only_rule_id)
            status = result["status"]
            if status == self.STATUS_AUTO:
                summary["auto"] += 1
                if result.get("rule_id"):
                    summary["rules_used"].add(result["rule_id"])
            elif status == self.STATUS_REVIEW:
                summary["to_review"] += 1
                if result.get("rule_id"):
                    summary["rules_used"].add(result["rule_id"])
            elif status == self.STATUS_TO_CATEGORIZE:
                summary["to_categorize"] += 1
            else:
                summary["skipped"] += 1
        summary["rules_used"] = len(summary["rules_used"])
        self.db.seal_database_to_encrypted_vault()
        return summary


    def apply_rules_to_import_batch(self, import_batch_id: int) -> dict:
        summary = {
            "auto": 0,
            "to_review": 0,
            "to_categorize": 0,
            "skipped": 0,
            "rules_used": set(),
        }
        with self.db.connect() as conn:
            rows = list(conn.execute("SELECT id FROM transactions WHERE import_batch_id = ? ORDER BY id", (import_batch_id,)))
        for row in rows:
            result = self.categorize_transaction(int(row["id"]), force=True)
            status = result["status"]
            if status == self.STATUS_AUTO:
                summary["auto"] += 1
                if result.get("rule_id"):
                    summary["rules_used"].add(result["rule_id"])
            elif status == self.STATUS_REVIEW:
                summary["to_review"] += 1
                if result.get("rule_id"):
                    summary["rules_used"].add(result["rule_id"])
            elif status == self.STATUS_TO_CATEGORIZE:
                summary["to_categorize"] += 1
            else:
                summary["skipped"] += 1
        summary["rules_used"] = len(summary["rules_used"])
        self.db.seal_database_to_encrypted_vault()
        return summary

    @staticmethod
    def suggest_keyword_from_label(label: str) -> str:
        return extract_counterparty(label)

    def create_rule_from_transaction(self, transaction_id: int, target_category_id: int, options: dict | None = None) -> int:
        tx = self.transaction_row(transaction_id)
        if not tx:
            raise ValueError("Transaction introuvable.")
        options = options or {}
        try:
            beneficiary = tx["beneficiary"] if "beneficiary" in tx.keys() else ""
        except (AttributeError, KeyError, TypeError):
            beneficiary = ""
        keyword = options.get("match_value") or beneficiary or extract_counterparty(tx["label"])
        name = options.get("name") or f"{keyword} → catégorie"
        tx_type = "Crédit" if float(tx["amount"] or 0) >= 0 else "Débit"
        return self.create_rule({
            "name": name,
            "description": f"Créée depuis la transaction du {tx['tx_date']}",
            "is_active": True,
            "priority": int(options.get("priority") or 100),
            "match_field": options.get("match_field") or "beneficiary",
            "match_operator": options.get("match_operator") or "contains",
            "match_value": keyword,
            "transaction_type": options.get("transaction_type") or tx_type,
            "account_id": tx["account_id"] if options.get("account_specific", True) else None,
            "min_amount": options.get("min_amount"),
            "max_amount": options.get("max_amount"),
            "target_category_id": target_category_id,
            "confidence": int(options.get("confidence") or 100),
        })

    def rule_summary(self, rule) -> str:
        parts = []
        parts.append(f"{self.MATCH_FIELDS.get(rule['match_field'], rule['match_field'])} {self.OPERATORS.get(rule['match_operator'], rule['match_operator']).lower()} {rule['match_value']}")
        if rule["transaction_type"]:
            parts.append(rule["transaction_type"])
        if rule["account_name"]:
            parts.append(f"Compte {rule['account_name']}")
        if rule["min_amount"] is not None or rule["max_amount"] is not None:
            parts.append(f"Montant {rule['min_amount'] or 0}–{rule['max_amount'] or '∞'}")
        return " • ".join(parts)
