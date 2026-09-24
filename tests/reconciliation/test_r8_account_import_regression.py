"""Regression checks for the TEST16 account/import dead end (#152)."""

import ast
import sqlite3
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def isolated_methods(path, class_name, method_names):
    """Load business methods without requiring Qt on the Linux CI runner."""
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    source_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    methods = [n for n in source_class.body if isinstance(n, ast.FunctionDef) and n.name in method_names]
    module = ast.fix_missing_locations(ast.Module(
        body=[ast.ClassDef(name="Subject", bases=[], keywords=[], body=methods, decorator_list=[])],
        type_ignores=[],
    ))
    namespace = {}
    exec(compile(module, str(path), "exec"), namespace)
    return namespace["Subject"]


class AccountImportRegressionTests(unittest.TestCase):
    def test_account_update_keeps_reference_balance(self):
        subject = isolated_methods("app/database.py", "Database", {"update_account"})
        conn = sqlite3.connect(":memory:")
        conn.execute("""CREATE TABLE accounts (
            id INTEGER PRIMARY KEY, name TEXT, bank TEXT, account_type TEXT,
            identifier TEXT, currency TEXT, status TEXT, updated_at TEXT,
            initial_balance REAL, reference_balance REAL, initial_date TEXT, reference_date TEXT
        )""")
        conn.execute("""INSERT INTO accounts VALUES
            (1, 'Ancien', 'SG', 'Compte courant', '123', 'EUR', 'Actif', NULL,
             123.45, 123.45, '2026-01-01', '2026-01-01')""")
        subject.connect = lambda self: conn
        subject().update_account(1, {
            "name": "Nouveau", "bank": "SG", "account_type": "Compte courant",
            "identifier": "456", "currency": "EUR", "status": "Actif",
        })
        self.assertEqual(conn.execute(
            "SELECT name, identifier, initial_balance, reference_balance FROM accounts"
        ).fetchone(), ("Nouveau", "456", 123.45, 123.45))

    def test_import_matches_rib_account_number_but_rejects_ambiguity(self):
        subject = isolated_methods("app/ui/transactions_page.py", "TransactionsPage", {
            "identifier_digits", "account_matches_detected_identifier",
            "matching_accounts_for_import", "import_account_consistency", "mask_identifier",
        })
        page = subject()
        account = {"id": 1, "name": "Compte SG", "bank": "SG", "identifier": "30003038900005038425579"}
        page.accounts = [account]
        page.detected_source_identifiers = lambda: ["50384255"]
        page.import_account_combo = type("Combo", (), {"currentData": lambda self: 1})()
        self.assertTrue(page.import_account_consistency()[0])
        page.detected_source_identifiers = lambda: ["50384256"]
        self.assertFalse(page.import_account_consistency()[0])
        page.detected_source_identifiers = lambda: ["50384255"]
        page.accounts.append(dict(account, id=2))
        self.assertFalse(page.import_account_consistency()[0])
        self.assertEqual(page.mask_identifier("50384255"), "•••• 4255")


if __name__ == "__main__":
    unittest.main()
