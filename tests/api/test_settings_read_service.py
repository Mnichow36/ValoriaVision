from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.services.settings_read_service import SettingsReadService


class StubConnection:
    def __init__(self, transactions):
        self.transactions = transactions

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query):
        return self.transactions


class StubDatabase:
    def __init__(self):
        self.settings = {
            "currency": "EUR",
            "current_month": "2026-10",
            "security.session_timeout_minutes": "10",
        }
        self.saved = []
        self.categories = [
            {
                "id": 4,
                "name": "Revenus",
                "kind": "Revenu",
                "direction": "Recette",
                "color": "#16A34A",
                "budget_enabled": 0,
                "is_system": 0,
                "tx_count": 3,
                "recurring_count": 1,
                "budget_count": 0,
            }
        ]

    def get_setting(self, key, default=""):
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        self.settings[key] = value
        self.saved.append((key, value))

    def get_user_preference(self, key, default=""):
        return "fr" if key == "locale.default" else default

    def data_quality_report(self):
        return {
            "db_size_kb": 512.5,
            "schema_version": 19,
            "sqlite_integrity": "ok",
            "accounts": 1,
            "orphan_transactions": 0,
            "orphan_import_links": 0,
            "revenues_gap": 0,
            "expenses_gap": 0,
        }

    def security_audit_report(self):
        return {
            "sqlite_encrypted": True,
            "backups_encrypted": True,
            "master_password_enabled": True,
            "master_password_algorithm": "PBKDF2",
            "key_storage": "coffre OS",
            "session_timeout_minutes": self.settings["security.session_timeout_minutes"],
            "last_backup_path": "backup.vvb",
        }

    def category_usage_summary(self):
        return self.categories

    def list_accounts(self):
        return [
            {
                "id": 1,
                "name": "Compte courant",
                "bank": "Banque A",
                "status": "Actif",
                "effective_initial_balance": 1000,
                "effective_initial_date": "2026-10-01",
                "post_reference_movements": 250,
                "calculated_balance": 1250,
                "calculated_date": "2026-10-14",
            }
        ]

    def add_category(self, **payload):
        self.saved.append(("add_category", payload))
        return 9

    def update_category(self, category_id, **payload):
        self.saved.append(("update_category", category_id, payload))

    def delete_category(self, category_id):
        self.saved.append(("delete_category", category_id))

    def seal_database_to_encrypted_vault(self):
        self.saved.append(("sealed", True))

    def connect(self):
        return StubConnection([
            {"id": 21, "label": "Salaire octobre", "account_id": 1, "amount": 3000}
        ])


class StubCategorizationService:
    MATCH_FIELDS = {"label": "Libellé"}
    OPERATORS = {"contains": "Contient"}
    TRANSACTION_TYPES = ["Tous", "Débit", "Crédit"]

    def __init__(self, database):
        self.database = database
        self.saved = []
        self.rule = {
            "id": 7,
            "name": "Salaire mensuel",
            "description": "",
            "is_active": 1,
            "priority": 1,
            "match_field": "label",
            "match_operator": "contains",
            "match_value": "SALAIRE",
            "transaction_type": None,
            "account_id": None,
            "account_name": None,
            "min_amount": None,
            "max_amount": None,
            "target_category_id": 4,
            "target_category": "Revenus",
            "target_deleted": None,
            "confidence": 100,
        }

    def list_rules(self):
        return [self.rule]

    def active_rules(self):
        return [self.rule]

    def rule_summary(self, row):
        return "Libellé contient SALAIRE"

    def rule_matches(self, rule, transaction):
        return "salaire" in transaction["label"].lower(), "libellé"

    def create_rule(self, payload):
        self.saved.append(("create", payload))
        return 12

    def update_rule(self, rule_id, payload):
        self.saved.append(("update", rule_id, payload))

    def create_rule_from_transaction(self, transaction_id, target_category_id, options=None):
        self.saved.append(("from_transaction", transaction_id, target_category_id, options))
        return 13

    def set_rule_active(self, rule_id, active):
        self.saved.append(("active", rule_id, active))


class SettingsReadServiceTest(unittest.TestCase):
    def make_service(self):
        database = StubDatabase()
        categorization = StubCategorizationService(database)
        service = SettingsReadService(
            database,
            categorization_service_factory=lambda db: categorization,
            now_provider=lambda: datetime(2026, 10, 14, 18, 0, tzinfo=timezone.utc),
        )
        return service, database, categorization

    def test_builds_unified_snapshot_from_existing_owners(self):
        service, _, _ = self.make_service()

        snapshot = service.snapshot()

        self.assertEqual(snapshot["general"]["currentMonth"], "2026-10")
        self.assertEqual(snapshot["categories"][0]["usage"]["transactions"], 3)
        self.assertEqual(snapshot["rules"][0]["summary"], "Libellé contient SALAIRE")
        self.assertEqual(snapshot["balances"]["accounts"][0]["currentBalance"], 1250.0)
        self.assertTrue(snapshot["security"]["encryptedVault"])
        self.assertEqual(snapshot["ownership"][2]["mode"], "contrôle et renvoi")

    def test_delegates_edits_without_reimplementing_business_rules(self):
        service, database, categorization = self.make_service()

        general = service.update_general({
            "currency": "EUR",
            "current_month": "2026-11",
            "session_timeout_minutes": 15,
        })
        category = service.save_category({
            "name": "Transport",
            "kind": "Dépense",
            "direction": "Dépense",
            "color": "#2563EB",
            "budget_enabled": True,
        })
        rule = service.save_rule({
            "name": "Train",
            "match_value": "SNCF",
            "target_category_id": 4,
        })
        remembered = service.create_rule_from_transaction(21, 4, "LIDL")

        self.assertTrue(general["success"])
        self.assertIn(("security.session_timeout_minutes", "15"), database.saved)
        self.assertEqual(category["id"], 9)
        self.assertEqual(rule["id"], 12)
        self.assertEqual(remembered["id"], 13)
        self.assertEqual(categorization.saved[0][0], "create")
        self.assertEqual(
            categorization.saved[-1],
            ("from_transaction", 21, 4, {"match_value": "LIDL"}),
        )

    def test_previews_rules_without_writing_transactions(self):
        service, database, _ = self.make_service()

        preview = service.preview_rules()

        self.assertEqual(preview["matchedCount"], 1)
        self.assertEqual(preview["samples"][0]["category"], "Revenus")
        self.assertFalse(any(item[0] == "transaction" for item in database.saved))


if __name__ == "__main__":
    unittest.main()
