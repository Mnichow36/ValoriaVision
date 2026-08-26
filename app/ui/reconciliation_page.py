from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, QPoint
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMenu,
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
from app.theme import COLORS, euro, format_date_fr
from app.widgets import Card, PageHeader, primary_button, secondary_button


class ReconciliationPage(QWidget):
    """R7.2 active reconciliation screen.

    Data is built exhaustively in ForecastReconciliationService, then filtered
    here for display. Row actions are exposed through contextual right-click menus.
    """

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.service = ForecastReconciliationService(db)
        self.active_status_filter = "active"

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(14)
        self.build()

    def build(self) -> None:
        generate_btn = primary_button("Générer / mettre à jour")
        generate_btn.clicked.connect(self.generate_occurrences)
        overdue_btn = secondary_button("Marquer les retards")
        overdue_btn.clicked.connect(self.mark_overdue)

        self.layout.addWidget(
            PageHeader(
                "Rapprochements",
                "Transactions réalisées et occurrences prévisionnelles — jeu complet puis filtres d’affichage",
                [generate_btn, overdue_btn],
            )
        )

        filters = Card()
        filters_layout = QHBoxLayout(filters)
        filters_layout.setContentsMargins(16, 12, 16, 12)
        filters_layout.setSpacing(10)

        self.account_filter = QComboBox()
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
        splitter.addWidget(self.build_transactions_panel())
        splitter.addWidget(self.build_occurrences_panel())
        self.kpi_panel = self.build_kpi_panel()
        splitter.addWidget(self.kpi_panel)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 5)
        splitter.setStretchFactor(2, 2)
        self.layout.addWidget(splitter, stretch=1)

        self.refresh_accounts()
        self.refresh()

    def panel_title(self, title: str, subtitle: str) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size:18px; font-weight:bold; color:#0F172A;")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet("color:#64748B;")
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        return box

    def build_transactions_panel(self) -> Card:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.panel_title("Transactions bancaires", "Opérations réelles non encore consommées par un rapprochement actif/final."))

        self.transactions_table = QTableWidget(0, 7)
        self.transactions_table.setHorizontalHeaderLabels(["✓", "Date", "Compte", "Libellé", "Montant", "Catégorie", "Lien"])
        self.prepare_table(self.transactions_table)
        header = self.transactions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        self.transactions_table.setColumnWidth(0, 42)
        self.transactions_table.setColumnWidth(1, 105)
        self.transactions_table.setColumnWidth(2, 135)
        self.transactions_table.setColumnWidth(4, 105)
        self.transactions_table.setColumnWidth(5, 130)
        self.transactions_table.setColumnWidth(6, 80)
        self.transactions_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.transactions_table.customContextMenuRequested.connect(self.show_transactions_context_menu)
        layout.addWidget(self.transactions_table, stretch=1)
        return card

    def build_occurrences_panel(self) -> Card:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self.panel_title("Occurrences prévisionnelles", "Par défaut : opérations restant à traiter. Les finalisées sont accessibles via les filtres de statut."))

        self.occurrences_table = QTableWidget(0, 8)
        self.occurrences_table.setHorizontalHeaderLabels(["✓", "Date", "Compte", "Libellé", "Prévu", "Statut", "Réalisé", "Écart"])
        self.prepare_table(self.occurrences_table)
        header = self.occurrences_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        header.setSectionResizeMode(7, QHeaderView.Fixed)
        self.occurrences_table.setColumnWidth(0, 42)
        self.occurrences_table.setColumnWidth(1, 105)
        self.occurrences_table.setColumnWidth(2, 135)
        self.occurrences_table.setColumnWidth(4, 105)
        self.occurrences_table.setColumnWidth(5, 150)
        self.occurrences_table.setColumnWidth(6, 105)
        self.occurrences_table.setColumnWidth(7, 95)
        self.occurrences_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.occurrences_table.customContextMenuRequested.connect(self.show_occurrences_context_menu)
        layout.addWidget(self.occurrences_table, stretch=1)
        return card

    def prepare_table(self, table: QTableWidget) -> None:
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setDefaultSectionSize(42)
        table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    def build_kpi_panel(self) -> Card:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)
        title = QLabel("Statuts")
        title.setStyleSheet("font-size:18px; font-weight:bold; color:#0F172A;")
        hint = QLabel("Clique sur un statut pour filtrer les occurrences. Les compteurs viennent de la même source que les listes.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748B;")
        layout.addWidget(title)
        layout.addWidget(hint)

        self.kpi_buttons: dict[str, QPushButton] = {}
        for key, label in [
            ("active", "À traiter"),
            ("all", "Historique complet"),
            ("planned", "Prévue"),
            ("overdue", "En retard"),
            ("to_review", "À vérifier"),
            ("auto_matched", "Rapprochée auto"),
            ("confirmed", "Rapprochée manuelle"),
            ("ignored", "Ignorée"),
            ("cancelled", "Annulée"),
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

    def refresh_accounts(self) -> None:
        current = self.account_filter.currentData() if hasattr(self, "account_filter") else None
        self.account_filter.blockSignals(True)
        self.account_filter.clear()
        self.account_filter.addItem("Tous les comptes", None)
        for account in self.db.list_accounts():
            if account["status"] != "Actif":
                continue
            label = f"{account['bank']} — {account['name']}" if account["bank"] else account["name"]
            self.account_filter.addItem(label, account["id"])
        if current is not None:
            idx = self.account_filter.findData(current)
            if idx >= 0:
                self.account_filter.setCurrentIndex(idx)
        self.account_filter.blockSignals(False)

    def set_status_filter(self, status: str) -> None:
        self.active_status_filter = status
        for key, button in self.kpi_buttons.items():
            button.setChecked(key == status)
        self.refresh_data()

    def refresh(self) -> None:
        self.refresh_accounts()
        self.refresh_data()

    def refresh_data(self) -> None:
        dataset = self.current_dataset()
        self.refresh_transactions(dataset)
        self.refresh_occurrences(dataset)
        self.refresh_kpis(dataset)

    def current_dataset(self, status: str | None = None) -> dict:
        return self.service.build_reconciliation_dataset(
            start_date=self.qdate_to_iso(self.start_date),
            end_date=self.qdate_to_iso(self.end_date),
            account_id=self.account_filter.currentData(),
            status=status or self.active_status_filter,
        )

    def refresh_kpis(self, dataset: dict | None = None) -> None:
        dataset = dataset or self.current_dataset()
        summary = dataset["summary"]
        labels = {
            "active": summary.get("active", 0),
            "all": summary.get("all", 0),
            "planned": summary.get("planned", 0),
            "overdue": summary.get("overdue", 0),
            "to_review": summary.get("to_review", 0),
            "auto_matched": summary.get("auto_matched", 0),
            "confirmed": summary.get("confirmed", 0),
            "ignored": summary.get("ignored", 0),
            "cancelled": summary.get("cancelled", 0),
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

    def refresh_transactions(self, dataset: dict | None = None) -> None:
        dataset = dataset or self.current_dataset()
        rows = dataset["transactions"]
        self.transactions_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            checkbox = QCheckBox()
            checkbox.setProperty("tx_id", int(row["id"]))
            self.transactions_table.setCellWidget(row_index, 0, checkbox)
            linked = "Liée" if row["linked_occurrence_id"] else ""
            values = [
                format_date_fr(row["tx_date"]),
                row["account_name"] or "",
                row["label"] or "",
                euro(float(row["amount"] or 0)),
                row["category"] or "À catégoriser",
                linked,
            ]
            for col, value in enumerate(values, start=1):
                item = QTableWidgetItem(str(value))
                if col == 1:
                    item.setData(Qt.UserRole, int(row["id"]))
                if col == 4:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if col == 3:
                    item.setToolTip(str(value))
                self.transactions_table.setItem(row_index, col, item)

    def refresh_occurrences(self, dataset: dict | None = None) -> None:
        dataset = dataset or self.current_dataset()
        rows = dataset["occurrences"]
        self.occurrences_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            checkbox = QCheckBox()
            checkbox.setProperty("occurrence_id", int(row["id"]))
            self.occurrences_table.setCellWidget(row_index, 0, checkbox)
            values = [
                format_date_fr(row["expected_date"]),
                row["account_name"] or "",
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
                if col in {4, 6, 7}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if col == 3:
                    item.setToolTip(str(value))
                self.occurrences_table.setItem(row_index, col, item)

    def checked_transaction_id(self) -> int | None:
        found = []
        for row in range(self.transactions_table.rowCount()):
            widget = self.transactions_table.cellWidget(row, 0)
            if isinstance(widget, QCheckBox) and widget.isChecked():
                found.append(int(widget.property("tx_id")))
        return found[0] if len(found) == 1 else None

    def checked_occurrence_id(self) -> int | None:
        found = []
        for row in range(self.occurrences_table.rowCount()):
            widget = self.occurrences_table.cellWidget(row, 0)
            if isinstance(widget, QCheckBox) and widget.isChecked():
                found.append(int(widget.property("occurrence_id")))
        return found[0] if len(found) == 1 else None

    def selected_occurrence_id(self) -> int | None:
        checked = self.checked_occurrence_id()
        if checked:
            return checked
        row = self.occurrences_table.currentRow()
        if row < 0:
            return None
        item = self.occurrences_table.item(row, 1)
        return int(item.data(Qt.UserRole)) if item and item.data(Qt.UserRole) else None

    def selected_transaction_id(self) -> int | None:
        checked = self.checked_transaction_id()
        if checked:
            return checked
        row = self.transactions_table.currentRow()
        if row < 0:
            return None
        item = self.transactions_table.item(row, 1)
        return int(item.data(Qt.UserRole)) if item and item.data(Qt.UserRole) else None

    def generate_occurrences(self) -> None:
        generated = self.service.generate_occurrences(self.qdate_to_iso(self.start_date), self.qdate_to_iso(self.end_date))
        overdue = self.service.mark_overdue(date.today())
        QMessageBox.information(self, "Rapprochements", f"{generated} occurrence(s) créée(s).\n{overdue} occurrence(s) marquée(s) en retard.")
        self.refresh()

    def mark_overdue(self) -> None:
        count = self.service.mark_overdue(date.today())
        QMessageBox.information(self, "Rapprochements", f"{count} occurrence(s) passée(s) en retard.")
        self.refresh()

    def match_checked(self) -> None:
        tx_id = self.checked_transaction_id()
        occurrence_id = self.checked_occurrence_id()
        if not tx_id or not occurrence_id:
            QMessageBox.information(self, "Rapprochement manuel", "Coche exactement une transaction bancaire à gauche et une occurrence prévue à droite.")
            return
        ok, message = self.service.confirm_manual_match(occurrence_id, tx_id)
        QMessageBox.information(self if ok else self, "Rapprochement manuel", message) if ok else QMessageBox.warning(self, "Rapprochement manuel", message)
        self.refresh()

    def cancel_occurrence_match(self) -> None:
        occurrence_id = self.selected_occurrence_id()
        if not occurrence_id:
            QMessageBox.information(self, "Rapprochements", "Sélectionne ou coche une occurrence.")
            return
        self.service.cancel_match(occurrence_id)
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

    def show_transactions_context_menu(self, pos: QPoint) -> None:
        row = self.transactions_table.rowAt(pos.y())
        if row >= 0:
            self.transactions_table.selectRow(row)
        menu = QMenu(self)
        menu.addAction("Rapprocher avec l’occurrence cochée", self.match_checked)
        menu.addSeparator()
        menu.addAction("Afficher les informations", self.show_transaction_info)
        menu.exec(self.transactions_table.viewport().mapToGlobal(pos))

    def show_occurrences_context_menu(self, pos: QPoint) -> None:
        row = self.occurrences_table.rowAt(pos.y())
        if row >= 0:
            self.occurrences_table.selectRow(row)
        menu = QMenu(self)
        menu.addAction("Rapprocher avec la transaction cochée", self.match_checked)
        menu.addAction("Annuler rapprochement", self.cancel_occurrence_match)
        menu.addAction("Ignorer l’occurrence", self.ignore_occurrence)
        menu.addSeparator()
        menu.addAction("Afficher les informations", self.show_occurrence_info)
        menu.exec(self.occurrences_table.viewport().mapToGlobal(pos))

    def show_transaction_info(self) -> None:
        tx_id = self.selected_transaction_id()
        QMessageBox.information(self, "Transaction", f"Transaction sélectionnée : {tx_id or 'aucune'}")

    def show_occurrence_info(self) -> None:
        occurrence_id = self.selected_occurrence_id()
        QMessageBox.information(self, "Occurrence", f"Occurrence sélectionnée : {occurrence_id or 'aucune'}")
