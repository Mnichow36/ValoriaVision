from __future__ import annotations

_PATCHED = False


def apply_r7_2_forecast_recurrences_patch() -> None:
    """Lot 5 — operational forecast recurring-event management.

    The first Lot 5 iterations only enhanced the historical dialog. User recette
    showed that add/edit actions were still not reliably persisted. This patch
    therefore installs a dedicated Lot 5 management dialog and dedicated database
    methods for add/update/delete actions.
    """
    global _PATCHED
    if _PATCHED:
        return

    try:
        from uuid import uuid4
        from PySide6.QtCore import QDate, Qt
        from PySide6.QtWidgets import (
            QCheckBox,
            QComboBox,
            QDateEdit,
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QFormLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMessageBox,
            QPushButton,
            QTableWidget,
            QTableWidgetItem,
            QVBoxLayout,
        )
        from app.database import Database
        from app.ui import forecast_page
        from app.theme import euro, format_date_fr
    except Exception:
        return

    ForecastPage = forecast_page.ForecastPage

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
        mapping = {
            "Hebdo": "Hebdomadaire",
            "Hebdomadaire": "Hebdomadaire",
            "Semaine": "Hebdomadaire",
            "Mensuel": "Mensuel",
            "Trimestriel": "Trimestriel",
            "Annuel": "Annuel",
            "Ponctuel": "Ponctuel",
            "once": "Ponctuel",
        }
        return mapping.get(text, text or "Mensuel")

    def _normalise_payload(db: Database, payload: dict) -> dict:
        data = dict(payload or {})
        data["name"] = (data.get("name") or "Nouvel événement prévisionnel").strip()
        data["category"] = data.get("category") or "À catégoriser"
        data["amount"] = db.normalize_amount_for_category(data.get("category"), float(data.get("amount") or 0))
        data["frequency"] = _normalise_frequency(data.get("frequency"))
        data["next_date"] = data.get("next_date") or QDate.currentDate().toString("yyyy-MM-dd")
        data["scenario"] = data.get("scenario") or "Réaliste"
        data["status"] = data.get("status") or "Actif"
        data["account_id"] = data.get("account_id")
        if data["frequency"] == "Ponctuel":
            data["end_date"] = data["next_date"]
        elif data.get("end_date"):
            data["end_date"] = str(data["end_date"])
        else:
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
            if row is None:
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
            if row is None:
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

    class Lot5RecurringEditDialog(QDialog):
        def __init__(self, db: Database, parent=None, row=None) -> None:
            super().__init__(parent)
            self.db = db
            self.row = row
            self.setWindowTitle("Modifier un événement prévisionnel" if row else "Ajouter un événement prévisionnel")
            self.setMinimumWidth(640)
            self._build()
            if row is not None:
                self._populate(row)

        def _build(self) -> None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(18, 16, 18, 16)
            form = QFormLayout()

            self.account = QComboBox()
            self.account.addItem("Aucun compte spécifique", None)
            for acc in self.db.list_accounts():
                if acc["status"] == "Actif":
                    self.account.addItem(f"{acc['name']} — {acc['bank']}", acc["id"])

            self.name = QLineEdit()
            self.name.setPlaceholderText("Ex. Loyer, salaire, prime exceptionnelle")

            self.category = QComboBox()
            self.category.addItems(self.db.category_names() or ["À catégoriser"])

            self.amount = QDoubleSpinBox()
            self.amount.setRange(0, 100000000)
            self.amount.setDecimals(2)
            self.amount.setSuffix(" €")

            self.frequency = QComboBox()
            self.frequency.addItems(["Ponctuel", "Mensuel", "Hebdomadaire", "Trimestriel", "Annuel"])
            self.frequency.setCurrentText("Mensuel")

            self.next_date = QDateEdit(QDate.currentDate())
            self.next_date.setCalendarPopup(True)
            self.next_date.setDisplayFormat("dd/MM/yyyy")

            self.end_date_enabled = QCheckBox("Limiter avec une date de fin")
            self.end_date = QDateEdit(QDate.currentDate().addMonths(12))
            self.end_date.setCalendarPopup(True)
            self.end_date.setDisplayFormat("dd/MM/yyyy")
            self.end_date.setEnabled(False)
            self.end_date_enabled.toggled.connect(self.end_date.setEnabled)

            self.scenario = QComboBox()
            self.scenario.addItems(["Prudent", "Réaliste", "Optimiste"])
            self.scenario.setCurrentText("Réaliste")

            self.status = QComboBox()
            self.status.addItems(["Actif", "Inactif"])

            form.addRow("Compte", self.account)
            form.addRow("Nom", self.name)
            form.addRow("Catégorie", self.category)
            form.addRow("Montant", self.amount)
            form.addRow("Fréquence", self.frequency)
            form.addRow("Prochaine date", self.next_date)
            form.addRow("Date de fin", self.end_date_enabled)
            form.addRow("", self.end_date)
            form.addRow("Scénario", self.scenario)
            form.addRow("Statut", self.status)
            layout.addLayout(form)

            hint = QLabel("Pour un événement unique, choisissez Ponctuel. La date de fin sera alors égale à la date de l’événement.")
            hint.setWordWrap(True)
            hint.setStyleSheet("color:#64748B; background:#F8FAFC; border-radius:10px; padding:8px;")
            layout.addWidget(hint)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)

        def _populate(self, row) -> None:
            idx = self.account.findData(row["account_id"])
            self.account.setCurrentIndex(idx if idx >= 0 else 0)
            self.name.setText(row["name"] or "")
            cat_idx = self.category.findText(row["category"] or "")
            if cat_idx >= 0:
                self.category.setCurrentIndex(cat_idx)
            self.amount.setValue(abs(float(row["amount"] or 0)))
            self.frequency.setCurrentText(_normalise_frequency(row["frequency"]))
            self.next_date.setDate(_parse_qdate(row["next_date"]))
            end_value = row["end_date"] if "end_date" in row.keys() else None
            if end_value and _normalise_frequency(row["frequency"]) != "Ponctuel":
                self.end_date_enabled.setChecked(True)
                self.end_date.setEnabled(True)
                self.end_date.setDate(_parse_qdate(end_value))
            self.scenario.setCurrentText(row["scenario"] or "Réaliste")
            self.status.setCurrentText(row["status"] or "Actif")

        def data(self) -> dict:
            frequency = _normalise_frequency(self.frequency.currentText())
            next_date = self.next_date.date().toString("yyyy-MM-dd")
            end_date = None
            if frequency == "Ponctuel":
                end_date = next_date
            elif self.end_date_enabled.isChecked():
                end_date = self.end_date.date().toString("yyyy-MM-dd")
            payload = {
                "account_id": self.account.currentData(),
                "name": self.name.text().strip() or "Nouvel événement prévisionnel",
                "category": self.category.currentText(),
                "amount": float(self.amount.value()),
                "frequency": frequency,
                "next_date": next_date,
                "end_date": end_date,
                "scenario": self.scenario.currentText(),
                "status": self.status.currentText(),
            }
            return _normalise_payload(self.db, payload)

    class Lot5RecurringManagerDialog(QDialog):
        def __init__(self, db: Database, parent_page=None) -> None:
            super().__init__(parent_page)
            self.db = db
            self.parent_page = parent_page
            self.setWindowTitle("Gérer les récurrences")
            self.resize(1100, 620)
            self.setMinimumSize(920, 520)
            self._build()
            self.refresh_table()

        def _build(self) -> None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(20, 18, 20, 18)
            layout.setSpacing(12)

            title = QLabel("Récurrences et événements prévisionnels")
            title.setStyleSheet("font-size:22px; font-weight:bold; color:#0F172A;")
            layout.addWidget(title)

            subtitle = QLabel("Ajoutez, modifiez ou supprimez les événements utilisés par la courbe prévisionnelle.")
            subtitle.setStyleSheet("color:#64748B;")
            layout.addWidget(subtitle)

            filters = QHBoxLayout()
            filters.addWidget(QLabel("Compte"))
            self.account_filter = QComboBox()
            self.account_filter.addItem("Tous les comptes", None)
            for acc in self.db.list_accounts():
                if acc["status"] == "Actif":
                    self.account_filter.addItem(f"{acc['name']} — {acc['bank']}", acc["id"])
            self.account_filter.currentIndexChanged.connect(self.refresh_table)
            filters.addWidget(self.account_filter)
            filters.addStretch(1)
            layout.addLayout(filters)

            self.table = QTableWidget(0, 9)
            self.table.setHorizontalHeaderLabels([
                "Nom", "Compte", "Catégorie", "Montant", "Fréquence",
                "Prochaine date", "Date de fin", "Scénario", "Statut",
            ])
            self.table.verticalHeader().setVisible(False)
            self.table.setAlternatingRowColors(True)
            self.table.setSelectionBehavior(QTableWidget.SelectRows)
            self.table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.table.setStyleSheet(
                "QTableWidget { background:#FFFFFF; alternate-background-color:#F8FAFC; border:1px solid #E5E7EB; border-radius:12px; }"
                "QHeaderView::section { background:#F8FAFC; color:#64748B; font-weight:bold; border:none; border-bottom:1px solid #E5E7EB; padding:8px; }"
            )
            self.table.doubleClicked.connect(self.edit_selected)
            layout.addWidget(self.table, stretch=1)

            actions = QHBoxLayout()
            self.add_btn = QPushButton("Ajouter")
            self.edit_btn = QPushButton("Modifier")
            self.delete_btn = QPushButton("Supprimer")
            self.close_btn = QPushButton("Fermer")
            self.add_btn.clicked.connect(self.add_item)
            self.edit_btn.clicked.connect(self.edit_selected)
            self.delete_btn.clicked.connect(self.delete_selected)
            self.close_btn.clicked.connect(self.accept)
            actions.addWidget(self.add_btn)
            actions.addWidget(self.edit_btn)
            actions.addWidget(self.delete_btn)
            actions.addStretch(1)
            actions.addWidget(self.close_btn)
            layout.addLayout(actions)

        def _rows(self):
            rows = self.db.list_recurring_items(active_only=False)
            account_id = self.account_filter.currentData()
            if account_id is None:
                return rows
            return [row for row in rows if row["account_id"] == account_id]

        def refresh_table(self) -> None:
            rows = self._rows()
            self.table.setRowCount(0)
            for r, row in enumerate(rows):
                self.table.insertRow(r)
                end_date = row["end_date"] if "end_date" in row.keys() else None
                values = [
                    row["name"] or "",
                    row["account_name"] or "Tous comptes",
                    row["category"] or "",
                    euro(float(row["amount"] or 0)),
                    _normalise_frequency(row["frequency"]),
                    format_date_fr(row["next_date"]),
                    format_date_fr(end_date) if end_date else "—",
                    row["scenario"] or "",
                    row["status"] or "",
                ]
                for c, value in enumerate(values):
                    item = QTableWidgetItem(str(value).replace("\n", " ").replace("\r", " "))
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    if c == 0:
                        item.setData(Qt.UserRole, row["id"])
                    if c == 3:
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    self.table.setItem(r, c, item)
            if rows:
                self.table.selectRow(0)

        def selected_id(self):
            row_index = self.table.currentRow()
            if row_index < 0:
                return None
            item = self.table.item(row_index, 0)
            return item.data(Qt.UserRole) if item else None

        def _refresh_parent(self) -> None:
            if self.parent_page is not None and hasattr(self.parent_page, "refresh"):
                self.parent_page.refresh()

        def add_item(self) -> None:
            dialog = Lot5RecurringEditDialog(self.db, self)
            if dialog.exec() == QDialog.Accepted:
                try:
                    created_id = self.db.add_forecast_recurring_item_lot5(dialog.data())
                except Exception as exc:
                    QMessageBox.warning(self, "Création impossible", str(exc))
                    return
                self.refresh_table()
                for r in range(self.table.rowCount()):
                    item = self.table.item(r, 0)
                    if item and item.data(Qt.UserRole) == created_id:
                        self.table.selectRow(r)
                        break
                self._refresh_parent()
                QMessageBox.information(self, "Récurrences", "Événement prévisionnel créé.")

        def edit_selected(self) -> None:
            recurring_id = self.selected_id()
            if not recurring_id:
                QMessageBox.information(self, "Récurrences", "Sélectionnez une ligne à modifier.")
                return
            row = self.db.get_recurring_item(recurring_id)
            if not row:
                QMessageBox.warning(self, "Récurrence introuvable", "La récurrence sélectionnée est introuvable.")
                return
            dialog = Lot5RecurringEditDialog(self.db, self, row=row)
            if dialog.exec() == QDialog.Accepted:
                try:
                    self.db.update_forecast_recurring_item_lot5(recurring_id, dialog.data())
                except Exception as exc:
                    QMessageBox.warning(self, "Modification impossible", str(exc))
                    return
                self.refresh_table()
                self._refresh_parent()
                QMessageBox.information(self, "Récurrences", "Événement prévisionnel modifié.")

        def delete_selected(self) -> None:
            recurring_id = self.selected_id()
            if not recurring_id:
                QMessageBox.information(self, "Récurrences", "Sélectionnez une ligne à supprimer.")
                return
            row = self.db.get_recurring_item(recurring_id)
            name = row["name"] if row else "cet événement"
            if QMessageBox.question(self, "Supprimer", f"Supprimer « {name} » ?") != QMessageBox.Yes:
                return
            self.db.delete_forecast_recurring_item_lot5(recurring_id)
            self.refresh_table()
            self._refresh_parent()
            QMessageBox.information(self, "Récurrences", "Événement prévisionnel supprimé.")

    def open_recurring_list_dialog_lot5(self: ForecastPage) -> None:
        dialog = Lot5RecurringManagerDialog(self.db, self)
        dialog.exec()
        self.refresh()

    def open_add_recurring_dialog_lot5(self: ForecastPage) -> None:
        dialog = Lot5RecurringEditDialog(self.db, self)
        if dialog.exec() == QDialog.Accepted:
            try:
                self.db.add_forecast_recurring_item_lot5(dialog.data())
            except Exception as exc:
                QMessageBox.warning(self, "Création impossible", str(exc))
                return
            QMessageBox.information(self, "Prévisionnel", "Événement prévisionnel créé.")
            self.refresh()

    def edit_recurring_item_lot5(self: ForecastPage, recurring_id: int) -> None:
        row = self.db.get_recurring_item(recurring_id)
        if not row:
            QMessageBox.warning(self, "Récurrence introuvable", "La récurrence sélectionnée est introuvable.")
            return
        dialog = Lot5RecurringEditDialog(self.db, self, row=row)
        if dialog.exec() == QDialog.Accepted:
            try:
                self.db.update_forecast_recurring_item_lot5(recurring_id, dialog.data())
            except Exception as exc:
                QMessageBox.warning(self, "Modification impossible", str(exc))
                return
            QMessageBox.information(self, "Prévisionnel", "Événement prévisionnel modifié.")
            self.refresh()

    def delete_recurring_item_lot5(self: ForecastPage, recurring_id: int) -> None:
        row = self.db.get_recurring_item(recurring_id)
        if not row:
            return
        if QMessageBox.question(self, "Supprimer", f"Supprimer « {row['name']} » ?") != QMessageBox.Yes:
            return
        self.db.delete_forecast_recurring_item_lot5(recurring_id)
        QMessageBox.information(self, "Prévisionnel", "Événement prévisionnel supprimé.")
        self.refresh()

    ForecastPage.open_recurring_list_dialog = open_recurring_list_dialog_lot5
    ForecastPage.open_add_recurring_dialog = open_add_recurring_dialog_lot5
    ForecastPage.edit_recurring_item = edit_recurring_item_lot5
    ForecastPage.delete_recurring_item = delete_recurring_item_lot5

    _PATCHED = True
