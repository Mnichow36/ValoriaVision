from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QTableWidgetItem, QVBoxLayout

from app.theme import euro, format_date_fr
from app.widgets import Card, secondary_button

_PATCHED = False


def mask_account_identifier(value: Any) -> str:
    """Return a display-safe bank/account identifier.

    The full identifier must remain stored in the database because imports need
    it for account matching. The UI must never expose the raw identifier in
    lists, cards or detail panels.
    """
    text = str(value or "").strip()
    if not text:
        return "—"
    if text.startswith("****"):
        return text

    compact = re.sub(r"\s+", "", text)
    alnum = re.sub(r"[^A-Za-z0-9]", "", compact)
    if not alnum:
        return "—"

    suffix = alnum[-4:] if len(alnum) >= 4 else alnum
    return f"**** {suffix}"


def apply_r7_2_ui_privacy_patch() -> None:
    """Patch UI privacy defects for R7.2.3.

    Fixes:
    - R7.2.3-ANO-002: newly-created account identifiers displayed in clear.

    Scope:
    - Accounts table;
    - Accounts cards view;
    - Account detail panel.
    """
    global _PATCHED
    if _PATCHED:
        return

    from app.ui.accounts_page import AccountsPage

    original_refresh = AccountsPage.refresh

    def refresh_with_masked_identifiers(self):
        original_refresh(self)
        if hasattr(self, "table"):
            for row_index in range(self.table.rowCount()):
                item = self.table.item(row_index, 3)
                if item is not None:
                    item.setText(mask_account_identifier(item.text()))

    def populate_cards_masked(self, rows) -> None:
        if not hasattr(self, "cards_grid"):
            return
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for index, row in enumerate(rows):
            card = Card()
            card.setMinimumHeight(160)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(16, 14, 16, 14)
            layout.setSpacing(6)
            current_balance = float(row["calculated_balance"] or 0)
            initial_balance = row["effective_initial_balance"] if "effective_initial_balance" in row.keys() else row["reference_balance"]
            initial_date = row["effective_initial_date"] if "effective_initial_date" in row.keys() else row["reference_date"]
            masked_identifier = mask_account_identifier(row["identifier"])

            title = QLabel(f"<b>{row['name']}</b><br><span style='color:#64748B'>{row['bank']} — {row['account_type']}</span>")
            title.setWordWrap(True)
            balance = QLabel(euro(current_balance))
            balance.setStyleSheet(f"font-size:24px; font-weight: bold; color:{'#16A34A' if current_balance >= 0 else '#DC2626'};")
            meta = QLabel(
                f"Solde initial : {euro(initial_balance)} au {format_date_fr(initial_date)}<br>"
                f"Identifiant : {masked_identifier}"
            )
            meta.setWordWrap(True)
            meta.setStyleSheet("color:#64748B; font-size:12px;")
            btn = secondary_button("Voir transactions")
            btn.clicked.connect(lambda _checked=False, account_id=row["id"]: self.open_transactions_for_account(account_id))
            layout.addWidget(title)
            layout.addWidget(balance)
            layout.addWidget(meta)
            layout.addStretch(1)
            layout.addWidget(btn)

            self.cards_grid.addWidget(card, index // 3, index % 3)

        if not rows:
            empty = QLabel("Aucun compte ne correspond aux filtres sélectionnés.")
            empty.setStyleSheet("color:#64748B; padding:24px;")
            self.cards_grid.addWidget(empty, 0, 0)

    def update_detail_masked(self) -> None:
        row_index = self.table.currentRow()
        if row_index < 0 or not hasattr(self, "account_rows") or row_index >= len(self.account_rows):
            return
        if not getattr(self, "detail_visible", False):
            self.detail_visible = True
            self.apply_detail_panel_state()
        row = self.account_rows[row_index]
        movement = row["post_reference_movements"] or 0
        initial_balance = row["effective_initial_balance"] if "effective_initial_balance" in row.keys() else row["reference_balance"]
        initial_date = row["effective_initial_date"] if "effective_initial_date" in row.keys() else row["reference_date"]
        masked_identifier = mask_account_identifier(row["identifier"])
        self.detail_content.setText(
            f"<b>{row['name']}</b><br>"
            f"Banque : {row['bank']}<br>"
            f"Type : {row['account_type']}<br>"
            f"Identifiant : {masked_identifier}<br><br>"
            f"<b>Solde initial</b><br>"
            f"{euro(initial_balance)} au {format_date_fr(initial_date)}<br><br>"
            f"<b>Solde actuel calculé</b><br>"
            f"{euro(row['calculated_balance'])} au {format_date_fr(row['calculated_date'])}<br>"
            f"Mouvements après solde initial : {euro(movement)}<br><br>"
            f"<b>Règle métier</b><br>"
            f"Solde à une date = solde initial + transactions entre la date initiale et la date observée.<br><br>"
            f"<b>Association import</b><br>"
            f"Compte reconnu via banque + identifiant bancaire masqué à l’affichage.<br><br>"
            f"<b>Alertes</b><br>"
            f"Aucune anomalie critique détectée."
        )

    AccountsPage.refresh = refresh_with_masked_identifiers
    AccountsPage.populate_cards = populate_cards_masked
    AccountsPage.update_detail = update_detail_masked

    _PATCHED = True
