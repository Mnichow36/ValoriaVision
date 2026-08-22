from __future__ import annotations

_PATCHED = False


def apply_r7_2_forecast_recurrences_patch() -> None:
    """Lot 5 — improve forecast recurring-event management.

    Goals:
    - make the existing "Gérer les récurrences" workflow more complete;
    - expose an optional end date in add/edit dialogs;
    - display end dates in the recurring list;
    - preserve existing forecast chart behavior.
    """
    global _PATCHED
    if _PATCHED:
        return

    try:
        from PySide6.QtCore import QDate, Qt
        from PySide6.QtWidgets import QCheckBox, QDateEdit, QLabel, QTableWidgetItem, QMessageBox
        from app.ui import forecast_page
        from app.theme import euro, format_date_fr
    except Exception:
        return

    RecurringDialog = forecast_page.RecurringDialog
    RecurringListDialog = forecast_page.RecurringListDialog

    original_dialog_init = RecurringDialog.__init__
    original_populate = RecurringDialog.populate_from_row
    original_data = RecurringDialog.data

    def _parse_qdate(value: str | None) -> QDate:
        try:
            text = str(value or "").strip()
            if not text:
                return QDate.currentDate()
            y, m, d = [int(v) for v in text.split("-")]
            return QDate(y, m, d)
        except Exception:
            return QDate.currentDate()

    def dialog_init_lot5(self, accounts, parent=None, row=None, categories=None) -> None:
        original_dialog_init(self, accounts, parent=parent, row=row, categories=categories)

        layout = self.layout()
        if layout is None or getattr(self, "_lot5_end_date_ready", False):
            return

        self.end_date_enabled = QCheckBox("Date de fin")
        self.end_date_enabled.setToolTip("Limiter la génération de cette récurrence à une date donnée.")
        self.end_date = QDateEdit(QDate.currentDate().addMonths(12))
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("dd/MM/yyyy")
        self.end_date.setEnabled(False)
        self.end_date_enabled.toggled.connect(self.end_date.setEnabled)

        if row is not None:
            end_value = ""
            try:
                end_value = row["end_date"] or ""
            except Exception:
                end_value = ""
            if end_value:
                self.end_date_enabled.setChecked(True)
                self.end_date.setEnabled(True)
                self.end_date.setDate(_parse_qdate(end_value))

        hint = QLabel(
            "Lot 5 : une date de fin évite qu’une récurrence continue indéfiniment. "
            "Pour un événement unique, choisissez la fréquence Ponctuel."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748B; background:#F8FAFC; border-radius:10px; padding:8px;")

        insert_at = max(0, layout.count() - 1)
        layout.insertWidget(insert_at, self.end_date_enabled)
        layout.insertWidget(insert_at + 1, self.end_date)
        layout.insertWidget(insert_at + 2, hint)
        self._lot5_end_date_ready = True

    def populate_from_row_lot5(self, row) -> None:
        original_populate(self, row)
        if hasattr(self, "end_date_enabled") and hasattr(self, "end_date"):
            try:
                end_value = row["end_date"] or ""
            except Exception:
                end_value = ""
            if end_value:
                self.end_date_enabled.setChecked(True)
                self.end_date.setEnabled(True)
                self.end_date.setDate(_parse_qdate(end_value))
            else:
                self.end_date_enabled.setChecked(False)
                self.end_date.setEnabled(False)

    def data_lot5(self) -> dict:
        payload = original_data(self)
        if hasattr(self, "end_date_enabled") and self.end_date_enabled.isChecked():
            end_date = self.end_date.date().toString("yyyy-MM-dd")
            if end_date < payload.get("next_date", ""):
                raise ValueError("La date de fin ne peut pas être antérieure à la prochaine date.")
            payload["end_date"] = end_date
        else:
            payload["end_date"] = None
        if payload.get("frequency") == "Ponctuel":
            payload["end_date"] = payload.get("next_date")
        return payload

    def _safe_dialog_data(dialog) -> dict | None:
        try:
            return dialog.data()
        except ValueError as exc:
            QMessageBox.warning(dialog, "Données incohérentes", str(exc))
            return None

    # Patch ForecastPage and RecurringListDialog places where dialog.data() is used,
    # so validation errors remain friendly instead of raising a raw exception.
    original_open_add = forecast_page.ForecastPage.open_add_recurring_dialog
    original_edit_page = forecast_page.ForecastPage.edit_recurring_item
    original_edit_list = RecurringListDialog.edit_selected

    def open_add_recurring_dialog_lot5(self) -> None:
        accounts = self.db.list_accounts()
        dialog = RecurringDialog(accounts, parent=self, categories=self.db.category_names())
        if dialog.exec() == dialog.Accepted:
            payload = _safe_dialog_data(dialog)
            if payload is None:
                return
            self.db.add_recurring_item(payload)
            self.refresh()

    def edit_recurring_item_lot5(self, recurring_id: int) -> None:
        row = self.db.get_recurring_item(recurring_id)
        if not row:
            QMessageBox.warning(self, "Récurrence introuvable", "La récurrence sélectionnée est introuvable.")
            return
        dialog = RecurringDialog(self.db.list_accounts(), parent=self, row=row, categories=self.db.category_names())
        if dialog.exec() == dialog.Accepted:
            payload = _safe_dialog_data(dialog)
            if payload is None:
                return
            self.db.update_recurring_item(recurring_id, payload)
            self.refresh()

    def edit_selected_lot5(self) -> None:
        recurring_id = self.selected_id()
        if not recurring_id:
            return
        row = self.db.get_recurring_item(recurring_id)
        dialog = RecurringDialog(self.db.list_accounts(), parent=self, row=row, categories=self.db.category_names())
        if dialog.exec() == dialog.Accepted:
            payload = _safe_dialog_data(dialog)
            if payload is None:
                return
            self.db.update_recurring_item(recurring_id, payload)
            self.refresh_table()

    def refresh_table_lot5(self) -> None:
        rows = self.rows()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Nom", "Compte", "Catégorie", "Montant", "Fréquence",
            "Prochaine date", "Date de fin", "Scénario", "Statut"
        ])
        self.table.setRowCount(0)
        for r, row in enumerate(rows):
            self.table.insertRow(r)
            end_date = "—"
            try:
                if row["end_date"]:
                    end_date = format_date_fr(row["end_date"])
            except Exception:
                pass
            values = [
                row["name"],
                row["account_name"] or "Tous comptes",
                row["category"] or "Autre",
                euro(float(row["amount"] or 0)),
                row["frequency"],
                format_date_fr(row["next_date"]),
                end_date,
                row["scenario"],
                row["status"],
            ]
            for c, value in enumerate(values):
                clean_value = str(value).replace("\n", " ").replace("\r", " ").replace("�", "")
                item = QTableWidgetItem(clean_value)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if c == 0:
                    item.setData(Qt.UserRole, row["id"])
                if c == 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    try:
                        item.setForeground(Qt.red if float(row["amount"] or 0) < 0 else Qt.darkGreen)
                    except Exception:
                        pass
                self.table.setItem(r, c, item)
        if rows:
            self.table.selectRow(0)

    RecurringDialog.__init__ = dialog_init_lot5
    RecurringDialog.populate_from_row = populate_from_row_lot5
    RecurringDialog.data = data_lot5
    forecast_page.ForecastPage.open_add_recurring_dialog = open_add_recurring_dialog_lot5
    forecast_page.ForecastPage.edit_recurring_item = edit_recurring_item_lot5
    RecurringListDialog.edit_selected = edit_selected_lot5
    RecurringListDialog.refresh_table = refresh_table_lot5

    _PATCHED = True
