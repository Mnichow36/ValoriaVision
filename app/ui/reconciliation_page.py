from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.services.forecast_reconciliation_service import ForecastReconciliationService, STATUS_LABELS
from app.theme import COLORS, euro
from app.widgets import Card, PageHeader, primary_button, secondary_button


class ReconciliationPage(QWidget):
    """Simplified manual forecast/reality reconciliation.

    Layout:
    - left: real bank transactions imported from statements;
    - right: forecast occurrences generated from recurring items;
    - far right: clickable KPI/status panel.
    """

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.service = ForecastReconciliationService(db)
        self.active_status_filter = "all"

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(14)
        self.build()

    def build(self) -> None:
        generate_btn = primary_button("Générer / mettre à jour")
        generate_btn.clicked.connect(self.generate_occurrences)

        match_btn = primary_button("Rapprocher les cases cochées")
        match_btn.clicked.connect(self.match_checked)

        overdue_btn = secondary_button("Marquer les retards")
        overdue_btn.clicked.connect(self.mark_overdue)

        self.layout.addWidget(
            PageHeader(
                "Rapprochements",
                "À gauche les transactions bancaires importées, à droite les récurrences prévues",
                [generate_btn, match_btn, overdue_btn],
            )
        )

        filters = Card()
        filters_layout = QHBoxLayout(filters)
        filters_layout.setContentsMargins(16, 12, 16, 12)
        filters_layout.setSpacing(10)

        self.account_filter = QComboBox()
        self.account_filter.addItem("Tous les comptes", None)
        for account in self.db.list_accounts():
            label = f"{account['bank']} — {account['name']}" if account["bank"] else account["name"]
            self.account_filter.addItem(label, account["id"])
        self.account_filter.currentIndexChanged.connect(self.refresh)

        today = date.today()
        self.start_date = QDateEdit(QDate(today.year, today.month, 1).addMonths(-2))
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("dd/MM/yyyy")
        self.start_date.dateChanged.connect(self.refresh)

        self.end_date = QDateEdit(QDate(today.year, today.month, 1).addMonths(4))
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("dd/MM/yyyy")
        self.end_date.dateChanged.connect(self.refresh)

        filters_layout.addWidget(QLabel("Compte"))
        filters_layout.addWidget(self.account_filter)
        filters_layout.addWidget(QLabel("Du"))
        filters_layout.addWidget(self.start_date)
        filters_layout.addWidget(QLabel("Au"))
        filters_layout.addWidget(self.end_date)
        filters_layout.addStretch(1)
        self.layout.addWidget(filters)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_panel = self.build_transactions_panel()
        right_panel = self.build_occurrences_panel()
        self.kpi_panel = self.build_kpi_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.addWidget(self.kpi_panel)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 5)
        splitter.setStretchFactor(2, 2)
        self.layout.addWidget(splitter, stretch=1)

        bottom_actions = QHBoxLayout()
        self.confirm_btn = secondary_button("Confirmer occurrence")
        self.confirm_btn.clicked.connect(self.confirm_occurrence)
        self.reject_btn = secondary_button("Refuser lien")
        self.reject_btn.clicked.connect(self.reject_occurrence)
        self.ignore_btn = secondary_button("Ignorer occurrence")
        self.ignore_btn.clicked.connect(self.ignore_occurrence)
        bottom_actions.addWidget(self.confirm_btn)
        bottom_actions.addWidget(self.reject_btn)
        bottom_actions.addWidget(self.ignore_btn)
        bottom_actions.addStretch(1)
        self.layout.addLayout(bottom_actions)

        self.refresh()

    def panel_title(self, title: str, subtitle: str) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size:18px; font-weight:bold; color:#0F172A;")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet("color:#64748B;")
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        return box

    def build_transactions_panel(self) -> Card:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self.panel_title("Transactions bancaires", "Opérations réelles issues des relevés/imports"))

        self.transactions_table = QTableWidget(0, 6)
        self.transactions_table.setHorizontalHeaderLabels(["✓", "Date", "Libellé", "Montant", "Catégorie", "Lien"])
        self.transactions_table.verticalHeader().setVisible(False)
        self.transactions_table.setAlternatingRowColors(True)
        self.transactions_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.transactions_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.transactions_table.verticalHeader().setDefaultSectionSize(42)
        header = self.transactions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.transactions_table.setColumnWidth(0, 42)
        self.transactions_table.setColumnWidth(1, 105)
        self.transactions_table.setColumnWidth(3, 105)
        self.transactions_table.setColumnWidth(4, 130)
        self.transactions_table.setColumnWidth(5, 95)
        layout.addWidget(self.transactions_table, stretch=1)
        return card

    def build_occurrences_panel(self) -> Card:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(self.panel_title("Récurrences prévues", "Occurrences prévisionnelles à rapprocher"))

        self.occurrences_table = QTableWidget(0, 7)
        self.occurrences_table.setHorizontalHeaderLabels(["✓", "Date", "Libellé", "Prévu", "Statut", "Réalisé", "Écart"])
        self.occurrences_table.verticalHeader().setVisible(False)
        self.occurrences_table.setAlternatingRowColors(True)
        self.occurrences_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.occurrences_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.occurrences_table.verticalHeader().setDefaultSectionSize(42)
        header = self.occurrences_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        self.occurrences_table.setColumnWidth(0, 42)
        self.occurrences_table.setColumnWidth(1, 105)
        self.occurrences_table.setColumnWidth(3, 105)
        self.occurrences_table.setColumnWidth(4, 150)
        self.occurrences_table.setColumnWidth(5, 105)
        self.occurrences_table.setColumnWidth(6, 95)
        layout.addWidget(self.occurrences_table, stretch=1)
        return card

    def build_kpi_panel(self) -> Card:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Statuts")
        title.setStyleSheet("font-size:18px; font-weight:bold; color:#0F172A;")
        hint = QLabel("Clique sur un statut pour filtrer la liste de droite.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748B;")
        layout.addWidget(title)
        layout.addWidget(hint)

        self.kpi_buttons: dict[str, QPushButton] = {}
        for key, label in [
            ("all", "Tous"),
            ("planned", "Prévue"),
            ("auto_matched", "Rapprochée auto"),
            ("confirmed", "Rapprochée manuelle"),
            ("to_review", "À vérifier"),
            ("overdue", "En retard"),
            ("ignored", "Ignorée"),
        ]:
            button = QPushButton(label)
            button.setCursor(Qt.PointingHandCursor)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, status=key: self.set_status_filter(status))
            self.kpi_buttons[key] = button
            layout.addWidget(button)

        layout.addStretch(1)
        return card

    def qdate_to_iso(self, widget: QDateEdit) -> str:
        return widget.date().toPython().isoformat()

    def set_status_filter(self, status: str) -> None:
        self.active_status_filter = status
        for key, button in self.kpi_buttons.items():
            button.setChecked(key == status)
        self.refresh_occurrences()

    def refresh(self) -> None:
        self.refresh_kpis()
        self.refresh_transactions()
        self.refresh_occurrences()

    def refresh_kpis(self) -> None:
        summary = self.service.summary()
        labels = {
            "all": sum(summary.values()),
            "planned": summary.get("planned", 0),
            "auto_matched": summary.get("auto_matched", 0),
            "confirmed": summary.get("confirmed", 0),
            "to_review": summary.get("to_review", 0),
            "overdue": summary.get("overdue", 0),
            "ignored": summary.get("ignored", 0),
        }
        for key, button in self.kpi_buttons.items():
            base = button.text().split("  ")[0]
            button.setText(f"{base}  {labels.get(key, 0)}")
            active = key == self.active_status_filter
            bg = COLORS["blue"] if active else "#FFFFFF"
            fg = "#FFFFFF" if active else COLORS["text"]
            border = COLORS["blue"] if active else COLORS["border"]
            button.setStyleSheet(
                f"QPushButton {{background:{bg}; color:{fg}; border:1px solid {border}; "
                "border-radius:12px; padding:10px 12px; text-align:left; font-weight:bold;}}"
                "QPushButton:hover {border-color:#2563EB;}"
            )

    def refresh_transactions(self) -> None:
        rows = self.service.list_imported_transactions(
            start_date=self.qdate_to_iso(self.start_date),
            end_date=self.qdate_to_iso(self.end_date),
            account_id=self.account_filter.currentData(),
        )
        self.transactions_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            checkbox = QCheckBox()
            checkbox.setProperty("tx_id", int(row["id"]))
            self.transactions_table.setCellWidget(row_index, 0, checkbox)

            linked = "Liée" if row["linked_occurrence_id"] else ""
            values = [
                row["tx_date"],
                row["label"] or "",
                euro(float(row["amount"] or 0)),
                row["category"] or "À catégoriser",
                linked,
            ]
            for col, value in enumerate(values, start=1):
                item = QTableWidgetItem(str(value))
                if col == 1:
                    item.setData(Qt.UserRole, int(row["id"]))
                if col == 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.transactions_table.setItem(row_index, col, item)

    def refresh_occurrences(self) -> None:
        rows = self.service.list_occurrences(
            status=self.active_status_filter,
            start_date=self.qdate_to_iso(self.start_date),
            end_date=self.qdate_to_iso(self.end_date),
            account_id=self.account_filter.currentData(),
        )
        self.occurrences_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            checkbox = QCheckBox()
            checkbox.setProperty("occurrence_id", int(row["id"]))
            self.occurrences_table.setCellWidget(row_index, 0, checkbox)

            values = [
                row["expected_date"],
                row["expected_label"] or "",
                euro(float(row["expected_amount"] or 0)),
                STATUS_LABELS.get(row["status"], row["status"]),
                euro(float(row["actual_amount"] or 0)) if row["actual_amount"] is not None else "",
                euro(float(row["amount_delta"] or 0)) if row["amount_delta"] is not None else "",
            ]
            for col, value in enumerate(values, start=1):
                item = QTableWidgetItem(str(value))
                if col == 1:
                    item.setData(Qt.UserRole, int(row["id"]))
                if col in {3, 5, 6}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.occurrences_table.setItem(row_index, col, item)

        self.refresh_kpis()

    def checked_transaction_id(self) -> int | None:
        found = []
        for row in range(self.transactions_table.rowCount()):
            widget = self.transactions_table.cellWidget(row, 0)
            if isinstance(widget, QCheckBox) and widget.isChecked():
                found.append(int(widget.property("tx_id")))
        if len(found) != 1:
            return None
        return found[0]

    def checked_occurrence_id(self) -> int | None:
        found = []
        for row in range(self.occurrences_table.rowCount()):
            widget = self.occurrences_table.cellWidget(row, 0)
            if isinstance(widget, QCheckBox) and widget.isChecked():
                found.append(int(widget.property("occurrence_id")))
        if len(found) != 1:
            return None
        return found[0]

    def selected_occurrence_id(self) -> int | None:
        checked = self.checked_occurrence_id()
        if checked:
            return checked
        row = self.occurrences_table.currentRow()
        if row < 0:
            return None
        item = self.occurrences_table.item(row, 1)
        return int(item.data(Qt.UserRole)) if item and item.data(Qt.UserRole) else None

    def generate_occurrences(self) -> None:
        generated = self.service.generate_occurrences(
            self.qdate_to_iso(self.start_date),
            self.qdate_to_iso(self.end_date),
        )
        overdue = self.service.mark_overdue(date.today())
        QMessageBox.information(
            self,
            "Rapprochements",
            f"{generated} occurrence(s) créée(s).\n{overdue} occurrence(s) marquée(s) en retard.",
        )
        self.refresh()

    def mark_overdue(self) -> None:
        count = self.service.mark_overdue(date.today())
        QMessageBox.information(self, "Rapprochements", f"{count} occurrence(s) passée(s) en retard.")
        self.refresh()

    def match_checked(self) -> None:
        tx_id = self.checked_transaction_id()
        occurrence_id = self.checked_occurrence_id()
        if not tx_id or not occurrence_id:
            QMessageBox.information(
                self,
                "Rapprochement manuel",
                "Coche exactement une transaction bancaire à gauche et une récurrence prévue à droite.",
            )
            return

        ok, message = self.service.confirm_manual_match(occurrence_id, tx_id)
        if ok:
            QMessageBox.information(self, "Rapprochement manuel", message)
        else:
            QMessageBox.warning(self, "Rapprochement manuel", message)
        self.refresh()

    def confirm_occurrence(self) -> None:
        occurrence_id = self.selected_occurrence_id()
        if not occurrence_id:
            QMessageBox.information(self, "Rapprochements", "Sélectionne ou coche une occurrence.")
            return
        self.service.confirm_match(occurrence_id)
        self.refresh()

    def reject_occurrence(self) -> None:
        occurrence_id = self.selected_occurrence_id()
        if not occurrence_id:
            QMessageBox.information(self, "Rapprochements", "Sélectionne ou coche une occurrence.")
            return
        self.service.reject_match(occurrence_id)
        self.refresh()

    def ignore_occurrence(self) -> None:
        occurrence_id = self.selected_occurrence_id()
        if not occurrence_id:
            QMessageBox.information(self, "Rapprochements", "Sélectionne ou coche une occurrence.")
            return
        reason, ok = QInputDialog.getText(self, "Ignorer", "Motif d'ignorance :")
        if ok:
            self.service.ignore_occurrence(occurrence_id, reason)
            self.refresh()
