from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class StableUiRegressionTests(unittest.TestCase):
    def source(self, relative_path: str) -> str:
        value = (ROOT / relative_path).read_text(encoding="utf-8")
        ast.parse(value, filename=relative_path)
        return value

    def test_dashboard_uses_neutral_greeting(self) -> None:
        source = self.source("app/ui/dashboard_page.py")
        self.assertNotIn("Bonjour François", source)
        self.assertIn('"Bonjour 👋"', source)

    def test_accounts_ellipsis_and_right_click_open_actions(self) -> None:
        source = self.source("app/ui/accounts_page.py")
        self.assertIn("self.table.setContextMenuPolicy(Qt.CustomContextMenu)", source)
        self.assertIn("self.table.customContextMenuRequested.connect(self.open_table_context_menu)", source)
        self.assertIn("self.table.cellClicked.connect(self.open_actions_cell)", source)
        for label in (
            "Voir les transactions",
            "Importer des opérations",
            "Mettre à jour le solde initial",
        ):
            self.assertIn(label, source)

    def test_transaction_dialog_preserves_explicit_direction(self) -> None:
        ui_source = self.source("app/ui/transactions_page.py")
        database_source = self.source("app/database.py")
        self.assertIn('self.direction.addItems(["Débit", "Crédit"])', ui_source)
        self.assertIn('"direction_explicit": True', ui_source)
        self.assertIn("preserve_direction=True", ui_source)
        self.assertIn("preserve_direction: bool = False", database_source)
        self.assertIn('not data.get("direction_explicit", False)', database_source)


    def test_reconciliation_screen_keeps_r725b_proposal_workflow(self) -> None:
        source = self.source("app/ui/reconciliation_page.py")
        for label in (
            "Transactions réalisées",
            "Occurrences prévisionnelles",
            "Proposition de rapprochement",
            "Valider",
            "Rejeter",
            "Partiellement rapproché",
        ):
            self.assertIn(label, source)



if __name__ == "__main__":
    unittest.main()
