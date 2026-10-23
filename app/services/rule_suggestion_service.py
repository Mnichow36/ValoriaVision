from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any

from app.services.business_rules import is_uncategorized_transaction
from app.services.categorization_rule_service import CategorizationRuleService
from app.services.counterparty_parser import extract_counterparty, normalize_bank_label

DISMISSED_SETTING = "rule_suggestions.dismissed"
MIN_SUPPORT = 3
MIN_DISPLAY_RELIABILITY = 0.7
DEFAULT_RELIABILITY = 0.9
MAX_PREVIEW = 300


class RuleSuggestionService:
    """Propose des règles de catégorisation à partir de l'historique déjà classé.

    Principe : une contrepartie vue au moins ``MIN_SUPPORT`` fois, presque toujours
    rangée dans la même catégorie, devient une règle candidate. Rien n'est créé
    sans validation de l'utilisateur ; les opérations déjà catégorisées ne sont
    jamais modifiées.
    """

    def __init__(self, db: Any) -> None:
        self.db = db
        self.rules = CategorizationRuleService(db)

    # ------------------------------------------------------------------ lecture
    def _rows(self) -> list[Any]:
        with self.db.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT t.id, t.account_id, t.tx_date, t.label, t.beneficiary, t.category,
                           t.amount, t.status, a.name AS account_name
                    FROM transactions t
                    JOIN accounts a ON a.id = t.account_id
                    WHERE a.status = 'Actif'
                    ORDER BY t.tx_date DESC, t.id DESC
                    """
                )
            )

    @staticmethod
    def _keyword(row: Any) -> str:
        beneficiary = row["beneficiary"] if "beneficiary" in row.keys() else ""
        return (beneficiary or extract_counterparty(row["label"]) or "").strip()

    @classmethod
    def _brand(cls, row: Any) -> str:
        """Enseigne probable : premier mot de la contrepartie (« LIDL PARIS » -> « LIDL »)."""
        keyword = cls._keyword(row)
        words = keyword.split()
        if len(words) > 1 and len(normalize_bank_label(words[0])) >= 4:
            return words[0]
        return keyword

    @staticmethod
    def _usable(keyword: str) -> bool:
        normalized = normalize_bank_label(keyword)
        return len(normalized) >= 3 and not re.fullmatch(r"[0-9 ]+", normalized)

    def dismissed(self) -> set[str]:
        try:
            values = json.loads(self.db.get_setting(DISMISSED_SETTING, "[]") or "[]")
        except (TypeError, ValueError):
            values = []
        return {normalize_bank_label(str(value)) for value in values}

    def _existing_rule_values(self) -> list[tuple[str, str]]:
        return [
            (normalize_bank_label(rule["match_value"]), str(rule["target_category"] or ""))
            for rule in self.rules.active_rules()
            if rule["match_value"]
        ]

    def suggestions(self, min_reliability: float = DEFAULT_RELIABILITY) -> dict[str, Any]:
        rows = self._rows()
        groups: dict[str, list[Any]] = defaultdict(list)
        pending: dict[str, list[Any]] = defaultdict(list)
        names: dict[str, str] = {}
        for row in rows:
            keyword = self._brand(row)
            if not self._usable(keyword):
                continue
            key = normalize_bank_label(keyword)
            names.setdefault(key, keyword)
            if is_uncategorized_transaction(row["category"], row["status"]):
                pending[key].append(row)
            else:
                groups[key].append(row)

        dismissed = self.dismissed()
        existing = self._existing_rule_values()
        items: list[dict[str, Any]] = []
        discarded = 0
        for key, history in groups.items():
            if len(history) < MIN_SUPPORT or key in dismissed:
                continue
            counts = Counter(str(row["category"]).strip() for row in history)
            category, top = counts.most_common(1)[0]
            reliability = top / len(history)
            if any(value and value in key and target == category for value, target in existing):
                continue
            if reliability < MIN_DISPLAY_RELIABILITY:
                discarded += 1
                continue
            category_id = self.rules.category_id_by_name(category)
            if not category_id:
                continue
            debit_share = sum(1 for row in history if float(row["amount"] or 0) < 0) / len(history)
            flow = "Débit" if debit_share >= 0.95 else "Crédit" if debit_share <= 0.05 else None
            matches = [row for row in pending.get(key, []) if self._flow_ok(row, flow)]
            items.append(
                {
                    "key": key,
                    "matchValue": names[key].upper(),
                    "category": category,
                    "categoryId": category_id,
                    "transactionType": flow,
                    "support": len(history),
                    "agreeing": top,
                    "reliability": round(reliability, 4),
                    "recommended": reliability >= min_reliability,
                    "matches": len(matches),
                }
            )
        items.sort(key=lambda item: (not item["recommended"], -item["matches"], -item["support"], item["matchValue"]))
        recommended = [item for item in items if item["recommended"]]
        return {
            "suggestions": items,
            "discardedCount": discarded,
            "minReliability": min_reliability,
            "totalMatches": sum(item["matches"] for item in recommended),
        }

    @staticmethod
    def _flow_ok(row: Any, flow: str | None) -> bool:
        if flow is None:
            return True
        amount = float(row["amount"] or 0)
        return (amount < 0) == (flow == "Débit")

    def preview(self, match_value: str, transaction_type: str | None = None) -> list[dict[str, Any]]:
        """Opérations « À catégoriser » que la règle classerait (même logique que le moteur)."""
        needle = normalize_bank_label(match_value)
        if len(needle) < 3:
            return []
        flow = transaction_type if transaction_type in {"Débit", "Crédit"} else None
        result: list[dict[str, Any]] = []
        for row in self._rows():
            if not is_uncategorized_transaction(row["category"], row["status"]):
                continue
            if needle not in normalize_bank_label(self._keyword(row)):
                continue
            if not self._flow_ok(row, flow):
                continue
            result.append(
                {
                    "id": int(row["id"]),
                    "date": str(row["tx_date"]),
                    "label": str(row["label"] or ""),
                    "amount": round(float(row["amount"] or 0), 2),
                    "account": str(row["account_name"] or ""),
                }
            )
            if len(result) >= MAX_PREVIEW:
                break
        return result

    # ------------------------------------------------------------------ écriture
    def dismiss(self, match_value: str) -> dict[str, Any]:
        value = normalize_bank_label(match_value)
        if not value:
            raise ValueError("Contrepartie invalide.")
        current = sorted(self.dismissed() | {value})
        self.db.set_setting(DISMISSED_SETTING, json.dumps(current, ensure_ascii=False))
        return {"success": True, "message": "Suggestion ignorée."}

    def apply(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Crée les règles validées puis classe les opérations « À catégoriser » choisies."""
        if not items:
            raise ValueError("Aucune règle sélectionnée.")
        created = classified = 0
        for item in items:
            match_value = str(item.get("match_value") or "").strip()
            if not self._usable(match_value):
                raise ValueError(f"Contrepartie invalide : {match_value or '(vide)'}.")
            category_id = int(item.get("target_category_id") or 0)
            if not category_id:
                raise ValueError("La catégorie cible est obligatoire.")
            flow = item.get("transaction_type")
            self.rules.create_rule(
                {
                    "name": f"{match_value} → suggestion",
                    "description": "Créée depuis les suggestions de règles.",
                    "is_active": True,
                    "priority": 100,
                    "match_field": "beneficiary",
                    "match_operator": "contains",
                    "match_value": match_value,
                    "transaction_type": flow if flow in {"Débit", "Crédit"} else None,
                    "account_id": None,
                    "target_category_id": category_id,
                    "confidence": 100,
                }
            )
            created += 1
            allowed = {row["id"] for row in self.preview(match_value, flow)}
            wanted = [int(value) for value in item.get("transaction_ids") or [] if int(value) in allowed]
            if wanted:
                summary = self.rules.apply_rules_to_transactions(wanted, force=False)
                classified += int(summary["auto"]) + int(summary["to_review"])
        plural = "s" if created > 1 else ""
        return {
            "success": True,
            "created": created,
            "classified": classified,
            "message": f"{created} règle{plural} créée{plural}, {classified} opération{'s' if classified > 1 else ''} classée{'s' if classified > 1 else ''}.",
        }
