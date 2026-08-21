from __future__ import annotations

_PATCHED = False


def apply_r7_2_account_context_menu_patch() -> None:
    """Lot 3 — harmonise account actions through contextual menus.

    Product decision:
    - technical actions must not overload the account detail panel;
    - account edit/delete/archive actions are available from a right-click menu;
    - deletion remains strictly controlled and allowed only for accounts with no
      linked transactions/imports/recurrences/forecast occurrences.
    """
    global _PATCHED
    if _PATCHED:
        return

    try:
        from PySide6.QtCore import Qt, QPoint
        from PySide6.QtWidgets import QMenu, QTableWidget, QMessageBox
        from app.ui.accounts_page import AccountsPage
    except Exception:
        return

    original_build_detail_panel = AccountsPage.build_detail_panel
    original_refresh = AccountsPage.refresh

    def _hide_technical_detail_buttons(self) -> None:
        """Keep the detail panel informative; move technical actions to menu."""
        for attr in ("edit_account_btn", "delete_account_btn"):
            widget = getattr(self, attr, None)
            if widget is not None:
                try:
                    widget.hide()
                    widget.deleteLater()
                    setattr(self, attr, None)
                except Exception:
                    try:
                        widget.hide()
                    except Exception:
                        pass

    def build_detail_panel_contextual(self):
        panel = original_build_detail_panel(self)
        _hide_technical_detail_buttons(self)
        return panel

    def _selected_account_from_table(self, table: QTableWidget, pos: QPoint):
        row_index = table.rowAt(pos.y())
        if row_index < 0:
            return None
        try:
            table.selectRow(row_index)
            table.setCurrentCell(row_index, 0)
        except Exception:
            pass
        if not hasattr(self, "account_rows") or row_index >= len(self.account_rows):
            return None
        return self.account_rows[row_index]

    def open_account_context_menu(self, pos: QPoint) -> None:
        table = getattr(self, "table", None)
        if table is None:
            return
        row = _selected_account_from_table(self, table, pos)
        if row is None:
            return

        menu = QMenu(self)
        action_view_transactions = menu.addAction("Voir les transactions")
        action_import = menu.addAction("Importer des opérations")
        menu.addSeparator()
        action_update_balance = menu.addAction("Mettre à jour le solde initial")
        action_edit = menu.addAction("Modifier le compte")
        action_delete_archive = menu.addAction("Supprimer / archiver")

        selected = menu.exec(table.viewport().mapToGlobal(pos))
        if selected == action_view_transactions:
            callback = getattr(self, "on_view_transactions", None)
            if callback:
                callback(int(row["id"]))
            return
        if selected == action_import:
            callback = getattr(self, "on_import_operations", None)
            if callback:
                callback(int(row["id"]))
            return
        if selected == action_update_balance:
            self.open_update_balance_dialog()
            return
        if selected == action_edit:
            self.open_edit_account_dialog()
            return
        if selected == action_delete_archive:
            self.delete_or_archive_selected_account()
            return

    def _ensure_account_context_menu(self) -> None:
        table = getattr(self, "table", None)
        if table is None or getattr(self, "_r7_2_account_context_menu_ready", False):
            return
        try:
            table.setContextMenuPolicy(Qt.CustomContextMenu)
            table.customContextMenuRequested.connect(self.open_account_context_menu)
            self._r7_2_account_context_menu_ready = True
        except Exception as exc:
            QMessageBox.warning(self, "Menu contextuel", f"Impossible d'activer le menu contextuel des comptes : {exc}")

    def refresh_contextual(self):
        original_refresh(self)
        _hide_technical_detail_buttons(self)
        _ensure_account_context_menu(self)

    AccountsPage.build_detail_panel = build_detail_panel_contextual
    AccountsPage.refresh = refresh_contextual
    AccountsPage.open_account_context_menu = open_account_context_menu

    _PATCHED = True
