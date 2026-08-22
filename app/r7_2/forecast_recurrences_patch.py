from __future__ import annotations

_PATCHED = False


def apply_r7_2_forecast_recurrences_patch() -> None:
    """Lot 5 — make forecast recurring-event management operational.

    This patch intentionally reinforces the existing forecast screen instead of
    replacing it. It fixes the first Lot 5 user recette where the dialog was
    visible but add/edit actions were not reliably persisted.
    """
    global _PATCHED
    if _PATCHED:
        return

    try:
        from uuid import uuid4
        from PySide6.QtCore import QDate, Qt
        from PySide6.QtWidgets import QCheckBox, QDateEdit, QLabel, QTableWidgetItem, QMessageBox, QPushButton
        from app.ui import forecast_page
        from app.database import Database
        from app.theme import euro, format_date_fr
    except Exception:
        return

    RecurringDialog = forecast_page.RecurringDialog
    RecurringListDialog = forecast_page.RecurringListDialog
    ForecastPage = forecast_page.ForecastPage

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

    def _normalise_frequency(value: str | None) -> str:
        text = (value or "Mensuel").strip()
        aliases = {
            "Hebdo": "Hebdomadaire",
            "Hebdomadaire": "Hebdomadaire",
            "Semaine": "Hebdomadaire",
            "Mensuel": "Mensuel",
            "Trimestriel": "Trimestriel",
            "Annuel": "Annuel",
            "Ponctuel": "Ponctuel",
            "once": "Ponctuel",
        }
        return aliases.get(text, text or "Mensuel")

    def _normalise_payload(db: Database, payload: dict) -> dict:
        data = dict(payload or {})
        data["account_id"] = data.get("account_id")
        data["name"] = (data.get("name") or "Nouvel événement prévisionnel").strip()
        data["category"] = data.get("category") or "À catégoriser"
        data["amount"] = db.normalize_amount_for_category(data.get("category"), float(data.get("amount") or 0))
        data["frequency"] = _normalise_frequency(data.get("frequency"))
        data["next_date"] = data.get("next_date") or QDate.currentDate().toString("yyyy-MM-dd")
        data["scenario"] = data.get("scenario") or "Réaliste"
        data["status"] = data.get("status") or "Actif"
        if data["frequency"] == "Ponctuel":
            data["end_date"] = data["next_date"]
        elif not data.get("end_date"):
            data["end_date"] = None
        if data.get("end_date") and data["end_date"] < data["next_date"]:
            raise ValueError("La date de fin ne peut pas être antérieure à la prochaine date.")
        return data

    def add_forecast_recurring_item_lot5(self: Database, payload: dict) -> int:
        data = _normalise_payload(self, payload)
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO recurring_items(
                    account_id, name, category, amount, frequency, next_date,
                    end_date, scenario, status, uuid, updated_at
                )
                VALUES (:account_id, :name, :category, :amount, :frequency,
                        :next_date, :end_date, :scenario, :status, :uuid,
                        CURRENT_TIMESTAMP)
                """,
                {**data, "uuid": str(uuid4())},
            )
            recurring_id = int(cur.lastrowid)
            try:
                self.audit_event(
                    conn,
                    "forecast_recurring_add",
                    "recurring_items",
                    str(recurring_id),
                    "Événement prévisionnel créé depuis le Lot 5.",
                    {"name": data["name"], "frequency": data["frequency"], "next_date": data["next_date"], "end_date": data.get("end_date")},
                )
            except Exception:
                pass
        try:
            self.seal_database_to_encrypted_vault()
        except Exception:
            pass
        return recurring_id

    def update_forecast_recurring_item_lot5(self: Database, recurring_id: int, payload: dict) -> None:
        data = _normalise_payload(self, payload)
        with self.connect() as conn:
            row = conn.execute("SELECT id FROM recurring_items WHERE id = ?", (recurring_id,)).fetchone()
            if not row:
                raise ValueError("Récurrence introuvable.")
            conn.execute(
                """
                UPDATE recurring_items
                SET account_id = :account_id,
                    name = :name,
                    category = :category,
                    amount = :amount,
                    frequency = :frequency,
                    next_date = :next_date,
                    end_date = :end_date,
                    scenario = :scenario,
                    status = :status,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :recurring_id
                """,
                {**data, "recurring_id": recurring_id},
            )
            try:
                self.audit_event(
                    conn,
                    "forecast_recurring_update",
                    "recurring_items",
                    str(recurring_id),
                    "Événement prévisionnel modifié depuis le Lot 5.",
                    {"name": data["name"], "frequency": data["frequency"], "next_date": data["next_date"], "end_date": data.get("end_date")},
                )
            except Exception:
                pass
        try:
            self.seal_database_to_encrypted_vault()
        except Exception:
            pass

    def delete_forecast_recurring_item_lot5(self: Database, recurring_id: int) -> None:
        with self.connect() as conn:
            row = conn.execute("SELECT name FROM recurring_items WHERE id = ?", (recurring_id,)).fetchone()
            if not row:
                return
            conn.execute("DELETE FROM recurring_items WHERE id = ?", (recurring_id,))
            try:
                conn.execute(
                    """
                    UPDATE forecast_occurrences
                    SET deleted_at = CURRENT_TIMESTAMP,
                        status = 'cancelled',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE source_type = 'recurring'
                      AND source_id = ?
                      AND actual_transaction_id IS NULL
                    """,
                    (recurring_id,),
                )
            except Exception:
                pass
            try:
                self.audit_event(
                    conn,
                    "forecast_recurring_delete",
                    "recurring_items",
                    str(recurring_id),
                    "Événement prévisionnel supprimé depuis le Lot 5.",
                    {"name": row["name"]},
                )
            except Exception:
                pass
        try:
            self.seal_database_to_encrypted_vault()
        except Exception:
            pass

    Database.add_forecast_recurring_item_lot5 = add_forecast_recurring_item_lot5
    Database.update_forecast_recurring_item_lot5 = update_forecast_recurring_item_lot5
    Database.delete_forecast_recurring_item_lot5 = delete_forecast_recurring_item_lot5

    def dialog_init_lot5(self, accounts, parent=None, row=None, categories=None) -> None:
        original_dialog_init(self, accounts, parent=parent, row=row, categories=categories)

        layout = self.layout()
        if layout is None or getattr(self, "_lot5_end_date_ready", False):
            return

        self.frequency.setCurrentText(_normalise_frequency(self.frequency.currentText()))
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
        try:
            self.frequency.setCurrentText(_normalise_frequency(row["frequency"]))
        except Exception:
            pass
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
        payload["frequency"] = _normalise_frequency(payload.get("frequency"))
        if hasattr(self, "end_date_enabled") and self.end_date_enabled.isChecked():
            payload["end_date"] = self.end_date.date().toString("yyyy-MM-dd")
        else:
            payload["end_date"] = None
        if payload.get("frequency") == "Ponctuel":
            payload["end_date"] = payload.get("next_date")
        if payload.get("end_date") and payload["end_date"] < payload.get("next_date", ""):
            raise ValueError("La date de fin ne peut pas être antérieure à la prochaine date.")
        return payload

    def _safe_dialog_data(dialog) -> dict | None:
        try:
            return dialog.data()
        except ValueError as exc:
            QMessageBox.warning(dialog, "Données incohérentes", str(exc))
            return None

    def open_add_recurring_dialog_lot5(self) -> None:
        dialog = RecurringDialog(self.db.list_accounts(), parent=self, categories=self.db.category_names())
        if dialog.exec() == dialog.Accepted:
            payload = _safe_dialog_data(dialog)
            if payload is None:
                return
            self.db.add_forecast_recurring_item_lot5(payload)
            QMessageBox.information(self, "Prévisionnel", "Événement prévisionnel créé.")
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
            self.db.update_forecast_recurring_item_lot5(recurring_id, payload)
            QMessageBox.information(self, "Prévisionnel", "Événement prévisionnel modifié.")
            self.refresh()

    def delete_recurring_item_lot5(self, recurring_id: int) -> None:
        row = self.db.get_recurring_item(recurring_id)
        if not row:
            return
        answer = QMessageBox.question(self, "Supprimer la récurrence", f"Supprimer la récurrence « {row['name']} » ?")
        if answer == QMessageBox.Yes:
            self.db.delete_forecast_recurring_item_lot5(recurring_id)
            QMessageBox.information(self, "Prévisionnel", "Événement prévisionnel supprimé.")
            self.refresh()

    def _selected_id(self):
        row_index = self.table.currentRow()
        if row_index < 0 and self.table.rowCount() > 0:
            row_index = 0
            self.table.selectRow(0)
        item = self.table.item(row_index, 0) if row_index >= 0 else None
        return item.data(Qt.UserRole) if item else None

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
                _normalise_frequency(row["frequency"]),
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

    def add_selected_lot5(self) -> None:
        dialog = RecurringDialog(self.db.list_accounts(), parent=self, categories=self.db.category_names())
        if dialog.exec() == dialog.Accepted:
            payload = _safe_dialog_data(dialog)
            if payload is None:
                return
            recurring_id = self.db.add_forecast_recurring_item_lot5(payload)
            self.refresh_table()
            # Select the newly created row when visible after filter.
            for r in range(self.table.rowCount()):
                item = self.table.item(r, 0)
                if item and item.data(Qt.UserRole) == recurring_id:
                    self.table.selectRow(r)
                    break
            QMessageBox.information(self, "Récurrences", "Événement prévisionnel créé.")

    def edit_selected_lot5(self) -> None:
        recurring_id = self.selected_id()
        if not recurring_id:
            QMessageBox.information(self, "Récurrences", "Sélectionnez une récurrence à modifier.")
            return
        row = self.db.get_recurring_item(recurring_id)
        if not row:
            QMessageBox.warning(self, "Récurrence introuvable", "La récurrence sélectionnée est introuvable.")
            return
        dialog = RecurringDialog(self.db.list_accounts(), parent=self, row=row, categories=self.db.category_names())
        if dialog.exec() == dialog.Accepted:
            payload = _safe_dialog_data(dialog)
            if payload is None:
                return
            self.db.update_forecast_recurring_item_lot5(recurring_id, payload)
            self.refresh_table()
            QMessageBox.information(self, "Récurrences", "Événement prévisionnel modifié.")

    def delete_selected_lot5(self) -> None:
        recurring_id = self.selected_id()
        if not recurring_id:
            QMessageBox.information(self, "Récurrences", "Sélectionnez une récurrence à supprimer.")
            return
        row = self.db.get_recurring_item(recurring_id)
        if not row:
            return
        if QMessageBox.question(self, "Supprimer la récurrence", f"Supprimer la récurrence « {row['name']} » ?") == QMessageBox.Yes:
            self.db.delete_forecast_recurring_item_lot5(recurring_id)
            self.refresh_table()
            QMessageBox.information(self, "Récurrences", "Événement prévisionnel supprimé.")

    original_list_build = RecurringListDialog.build

    def build_lot5(self) -> None:
        original_list_build(self)
        # The original dialog only had Modifier / Supprimer / Fermer. Add an
        # explicit creation action so "Gérer les récurrences" is a full CRUD hub.
        if getattr(self, "_lot5_add_button_ready", False):
            return
        add_btn = QPushButton("Ajouter")
        add_btn.clicked.connect(self.add_selected)
        try:
            actions_layout = self.edit_btn.parentWidget().layout()
            if actions_layout is not None:
                actions_layout.insertWidget(0, add_btn)
        except Exception:
            try:
                self.layout().addWidget(add_btn)
            except Exception:
                pass
        self.add_btn = add_btn
        self._lot5_add_button_ready = True

    RecurringDialog.__init__ = dialog_init_lot5
    RecurringDialog.populate_from_row = populate_from_row_lot5
    RecurringDialog.data = data_lot5

    ForecastPage.open_add_recurring_dialog = open_add_recurring_dialog_lot5
    ForecastPage.edit_recurring_item = edit_recurring_item_lot5
    ForecastPage.delete_recurring_item = delete_recurring_item_lot5

    RecurringListDialog.build = build_lot5
    RecurringListDialog.selected_id = _selected_id
    RecurringListDialog.refresh_table = refresh_table_lot5
    RecurringListDialog.add_selected = add_selected_lot5
    RecurringListDialog.edit_selected = edit_selected_lot5
    RecurringListDialog.delete_selected = delete_selected_lot5

    _PATCHED = True
