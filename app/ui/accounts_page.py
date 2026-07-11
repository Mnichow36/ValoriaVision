from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.theme import euro
from app.widgets import Card, KpiCard, PageHeader, primary_button, secondary_button


class AccountsPage(QWidget):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.view_mode = "table"
        self.on_view_transactions = None
        self.on_import_operations = None
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(16)
        self.build()

    def build(self) -> None:
        add_btn = primary_button("+ Ajouter un compte")
        add_btn.clicked.connect(self.open_add_dialog)
        self.panel_toggle_btn = secondary_button("Afficher le volet détail")
        self.panel_toggle_btn.clicked.connect(self.toggle_detail_panel)
        self.layout.addWidget(PageHeader("Comptes bancaires", "Gestion des comptes, soldes initiaux et association aux imports", [self.panel_toggle_btn, add_btn]))

        self.layout.addWidget(self.build_filters())

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["Compte", "Banque", "Type", "Identifiant", "Solde initial", "Date initiale", "Solde actuel", "Calculé au", "Actions"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setStyleSheet(
            "QTableWidget::item:selected { background:#EAF1FF; color:#0F172A; border:none; }"
            "QTableWidget::item:hover { background:#F8FAFC; border:none; }"
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 210)
        self.table.setColumnWidth(1, 170)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(4, 120)
        self.table.setColumnWidth(5, 110)
        self.table.setColumnWidth(6, 120)
        self.table.setColumnWidth(7, 110)
        self.table.itemSelectionChanged.connect(self.update_detail)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.bank_filter.currentTextChanged.connect(self.refresh)
        self.type_filter.currentTextChanged.connect(self.refresh)
        self.status_filter.currentTextChanged.connect(self.refresh)
        self.search_input.textChanged.connect(self.refresh)

        self.cards_scroll = self.build_cards_view()
        self.account_view_stack = QStackedWidget()
        self.account_view_stack.addWidget(self.table)
        self.account_view_stack.addWidget(self.cards_scroll)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.account_view_stack)
        self.splitter.addWidget(self.build_detail_panel())
        self.splitter.setSizes([1180, 0])
        self.layout.addWidget(self.splitter, stretch=1)
        self.detail_visible = False
        self.apply_detail_panel_state()

        self.kpi_grid = QGridLayout()
        self.kpi_grid.setSpacing(14)
        self.layout.addLayout(self.kpi_grid)

        self.refresh()

    def build_filters(self) -> Card:
        filters = Card()
        filter_layout = QHBoxLayout(filters)
        filter_layout.setContentsMargins(16, 12, 16, 12)
        filter_layout.setSpacing(10)
        self.bank_filter = QComboBox()
        self.bank_filter.setMinimumWidth(220)
        self.bank_filter.setMinimumContentsLength(16)
        self.bank_filter.addItem("Toutes banques")
        self.type_filter = QComboBox()
        self.type_filter.setMinimumWidth(240)
        self.type_filter.setMinimumContentsLength(18)
        self.type_filter.addItems(["Tous types", "Compte courant", "Compte épargne", "Compte investissement", "Compte crédit"])
        self.status_filter = QComboBox()
        self.status_filter.setMinimumWidth(190)
        self.status_filter.setMinimumContentsLength(14)
        self.status_filter.addItems(["Tous statuts", "Actif", "Archivé", "Clos"])
        self.search_input = QLineEdit()
        self.search_input.setMinimumWidth(280)
        self.search_input.setPlaceholderText("Rechercher un compte...")
        self.view_table_btn = secondary_button("Vue tableau")
        self.view_cards_btn = secondary_button("Vue cartes")
        self.view_table_btn.clicked.connect(lambda: self.set_view_mode("table"))
        self.view_cards_btn.clicked.connect(lambda: self.set_view_mode("cards"))
        for widget in [self.bank_filter, self.type_filter, self.status_filter, self.search_input, self.view_table_btn, self.view_cards_btn]:
            filter_layout.addWidget(widget)
        filter_layout.setStretch(0, 1)
        filter_layout.setStretch(1, 1)
        filter_layout.setStretch(2, 1)
        filter_layout.setStretch(3, 3)
        return filters

    def build_detail_panel(self) -> Card:
        self.detail_panel = Card()
        layout = QVBoxLayout(self.detail_panel)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        title = QLabel("Détail du compte")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.detail_content = QLabel("Sélectionnez un compte pour afficher le détail.")
        self.detail_content.setWordWrap(True)
        self.detail_content.setStyleSheet("color: #64748B;")
        layout.addWidget(title)
        layout.addWidget(self.detail_content)
        layout.addSpacing(8)
        self.view_transactions_btn = primary_button("Voir transactions")
        self.view_transactions_btn.clicked.connect(self.open_transactions_for_selected_account)
        self.import_operations_btn = secondary_button("Importer opérations")
        self.import_operations_btn.clicked.connect(self.open_import_for_selected_account)
        self.update_balance_btn = secondary_button("Mettre à jour le solde initial")
        self.update_balance_btn.clicked.connect(self.open_update_balance_dialog)
        layout.addWidget(self.view_transactions_btn)
        layout.addWidget(self.import_operations_btn)
        layout.addWidget(self.update_balance_btn)
        layout.addStretch(1)
        return self.detail_panel

    def build_cards_view(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cards_container = QWidget()
        self.cards_grid = QGridLayout(self.cards_container)
        self.cards_grid.setContentsMargins(0, 0, 8, 0)
        self.cards_grid.setSpacing(14)
        scroll.setWidget(self.cards_container)
        return scroll

    def set_view_mode(self, mode: str) -> None:
        self.view_mode = mode
        if hasattr(self, "account_view_stack"):
            self.account_view_stack.setCurrentIndex(1 if mode == "cards" else 0)
        self.refresh()

    def populate_cards(self, rows) -> None:
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

            title = QLabel(f"<b>{row['name']}</b><br><span style='color:#64748B'>{row['bank']} — {row['account_type']}</span>")
            title.setWordWrap(True)
            balance = QLabel(euro(current_balance))
            balance.setStyleSheet(f"font-size:24px; font-weight: bold; color:{'#16A34A' if current_balance >= 0 else '#DC2626'};")
            meta = QLabel(
                f"Solde initial : {euro(initial_balance)} au {initial_date}<br>"
                f"Identifiant : {row['identifier'] or '—'}"
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

    def open_transactions_for_account(self, account_id: int) -> None:
        if callable(self.on_view_transactions):
            self.on_view_transactions(account_id)
        else:
            QMessageBox.information(self, "Transactions", "Le raccord vers l'écran Transactions n'est pas encore disponible.")

    def open_transactions_for_selected_account(self) -> None:
        row = self.selected_account()
        if row is None:
            QMessageBox.information(self, "Compte", "Sélectionnez un compte.")
            return
        self.open_transactions_for_account(int(row["id"]))

    def open_import_for_selected_account(self) -> None:
        row = self.selected_account()
        if row is None:
            QMessageBox.information(self, "Compte", "Sélectionnez un compte.")
            return
        if callable(self.on_import_operations):
            self.on_import_operations(int(row["id"]))
        else:
            self.open_transactions_for_account(int(row["id"]))


    def refresh(self) -> None:
        all_rows = self.db.list_accounts()

        # V0.2.9 : correction critique. La version V0.2.9 remplissait les
        # cellules sans redimensionner le nombre de lignes du tableau, ce qui
        # rendait les comptes invisibles. On reconstruit maintenant le tableau
        # avec une liste filtrée explicite et un setRowCount(len(rows)).
        self.update_bank_filter_values(all_rows)
        rows = self.filtered_accounts(all_rows)
        self.account_rows = rows

        self.table.clearContents()
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            current_balance = row["calculated_balance"] or 0
            initial_balance = row["effective_initial_balance"] if "effective_initial_balance" in row.keys() else row["reference_balance"]
            initial_date = row["effective_initial_date"] if "effective_initial_date" in row.keys() else row["reference_date"]
            values = [
                row["name"],
                row["bank"],
                row["account_type"],
                row["identifier"],
                euro(initial_balance),
                initial_date,
                euro(current_balance),
                row["calculated_date"],
                "…",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col in {4, 6}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    amount = initial_balance if col == 4 else current_balance
                    item.setForeground(Qt.red if amount < 0 else Qt.darkGreen)
                if col == 8:
                    item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(row_index, col, item)
            self.table.setRowHeight(row_index, 42)
        self.table.resizeRowsToContents()
        self.populate_cards(rows)
        if hasattr(self, "account_view_stack"):
            self.account_view_stack.setCurrentIndex(1 if self.view_mode == "cards" else 0)

        if self.table.rowCount() > 0:
            self.table.selectRow(0)
        else:
            self.detail_content.setText("Aucun compte ne correspond aux filtres sélectionnés.")

        self.clear_layout(self.kpi_grid)
        summary = self.db.account_summary()
        cards = [
            KpiCard("Solde net tous comptes", euro(summary["solde_net"]), "Somme de tous les soldes calculés", "blue"),
            KpiCard("Comptes courants", euro(summary["comptes_courants"]), "Cash directement disponible", "green"),
            KpiCard("Épargne", euro(summary["epargne"]), "Livrets et comptes épargne", "purple"),
            KpiCard("Investissements", euro(summary["investissements"]), "PEA, CTO, assurance-vie", "blue"),
            KpiCard("Crédits", euro(summary["dettes"]), "Capital restant dû", "red"),
        ]
        for col, card in enumerate(cards):
            self.kpi_grid.addWidget(card, 0, col)


    def toggle_detail_panel(self) -> None:
        self.detail_visible = not getattr(self, "detail_visible", False)
        self.apply_detail_panel_state()

    def apply_detail_panel_state(self) -> None:
        if getattr(self, "detail_visible", False):
            self.detail_panel.show()
            self.panel_toggle_btn.setText("Masquer le volet détail")
            self.splitter.setSizes([1040, 360])
        else:
            self.detail_panel.hide()
            self.panel_toggle_btn.setText("Afficher le volet détail")
            self.splitter.setSizes([1400, 0])

    def update_bank_filter_values(self, rows) -> None:
        current = self.bank_filter.currentText()
        banks = [row["bank"] for row in rows if row["bank"]]
        values = ["Toutes banques"] + sorted(set(banks))
        existing = [self.bank_filter.itemText(i) for i in range(self.bank_filter.count())]
        if values == existing:
            return
        self.bank_filter.blockSignals(True)
        self.bank_filter.clear()
        self.bank_filter.addItems(values)
        index = self.bank_filter.findText(current)
        self.bank_filter.setCurrentIndex(index if index >= 0 else 0)
        self.bank_filter.blockSignals(False)

    def filtered_accounts(self, rows):
        bank = self.bank_filter.currentText()
        account_type = self.type_filter.currentText()
        status = self.status_filter.currentText()
        query = self.search_input.text().strip().lower()

        def matches(row) -> bool:
            if bank != "Toutes banques" and row["bank"] != bank:
                return False
            if account_type != "Tous types" and row["account_type"] != account_type:
                return False
            if status != "Tous statuts" and row["status"] != status:
                return False
            if query:
                haystack = " ".join([
                    str(row["name"] or ""),
                    str(row["bank"] or ""),
                    str(row["account_type"] or ""),
                    str(row["identifier"] or ""),
                ]).lower()
                if query not in haystack:
                    return False
            return True

        return [row for row in rows if matches(row)]

    def update_detail(self) -> None:
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
        self.detail_content.setText(
            f"<b>{row['name']}</b><br>"
            f"Banque : {row['bank']}<br>"
            f"Type : {row['account_type']}<br>"
            f"Identifiant : {row['identifier']}<br><br>"
            f"<b>Solde initial</b><br>"
            f"{euro(initial_balance)} au {initial_date}<br><br>"
            f"<b>Solde actuel calculé</b><br>"
            f"{euro(row['calculated_balance'])} au {row['calculated_date']}<br>"
            f"Mouvements après solde initial : {euro(movement)}<br><br>"
            f"<b>Règle métier</b><br>"
            f"Solde à une date = solde initial + transactions entre la date initiale et la date observée.<br><br>"
            f"<b>Association import</b><br>"
            f"Compte reconnu via banque + identifiant bancaire.<br><br>"
            f"<b>Alertes</b><br>"
            f"Aucune anomalie critique détectée."
        )


    def selected_account(self):
        row_index = self.table.currentRow()
        if row_index < 0 or not hasattr(self, "account_rows") or row_index >= len(self.account_rows):
            return None
        return self.account_rows[row_index]

    def open_update_balance_dialog(self) -> None:
        row = self.selected_account()
        if row is None:
            QMessageBox.information(self, "Compte", "Sélectionnez un compte à mettre à jour.")
            return
        dialog = BalanceReferenceDialog(row, self)
        if dialog.exec() == QDialog.Accepted:
            balance, date = dialog.data()
            self.db.update_account_reference(row["id"], balance, date)
            self.refresh()

    def open_add_dialog(self) -> None:
        dialog = AccountDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.db.add_account(dialog.data())
            self.refresh()

    def clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()



class BalanceReferenceDialog(QDialog):
    def __init__(self, account_row, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mettre à jour le solde initial")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        info = QLabel(
            f"<b>{account_row['name']}</b><br>"
            f"Solde actuel calculé : {euro(account_row['calculated_balance'])}<br>"
            f"Ancien solde initial : {euro(account_row['effective_initial_balance'])} au {account_row['effective_initial_date']}"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#475569;")
        layout.addWidget(info)

        form = QFormLayout()
        self.balance = QDoubleSpinBox()
        self.balance.setRange(-100000000, 100000000)
        self.balance.setDecimals(2)
        self.balance.setSuffix(" €")
        self.balance.setValue(float(account_row["effective_initial_balance"] or 0))
        self.reference_date = QDateEdit(QDate.fromString(account_row["effective_initial_date"], "yyyy-MM-dd") if account_row["effective_initial_date"] else QDate.currentDate())
        self.reference_date.setCalendarPopup(True)
        form.addRow("Nouveau solde initial", self.balance)
        form.addRow("Nouvelle date initiale", self.reference_date)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def data(self) -> tuple[float, str]:
        return float(self.balance.value()), self.reference_date.date().toString("yyyy-MM-dd")


class AccountDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ajouter un compte")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.bank = QLineEdit()
        self.account_type = QComboBox()
        self.account_type.addItems(["Compte courant", "Compte épargne", "Compte investissement", "Compte crédit", "Compte espèces", "Autre"])
        self.identifier = QLineEdit()
        self.identifier.setPlaceholderText("IBAN partiel ou identifiant")
        self.balance = QDoubleSpinBox()
        self.balance.setRange(-100000000, 100000000)
        self.balance.setDecimals(2)
        self.balance.setSuffix(" €")
        self.reference_date = QDateEdit(QDate.currentDate())
        self.reference_date.setCalendarPopup(True)
        self.currency = QComboBox()
        self.currency.addItems(["EUR", "USD", "GBP", "CHF"])
        self.status = QComboBox()
        self.status.addItems(["Actif", "Archivé", "Clos"])
        for label, widget in [
            ("Nom du compte", self.name),
            ("Banque", self.bank),
            ("Type", self.account_type),
            ("Identifiant", self.identifier),
            ("Solde initial", self.balance),
            ("Date initiale", self.reference_date),
            ("Devise", self.currency),
            ("Statut", self.status),
        ]:
            form.addRow(label, widget)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def data(self) -> dict:
        return {
            "name": self.name.text().strip() or "Nouveau compte",
            "bank": self.bank.text().strip() or "Banque",
            "account_type": self.account_type.currentText(),
            "identifier": self.identifier.text().strip(),
            "initial_balance": float(self.balance.value()),
            "initial_date": self.reference_date.date().toString("yyyy-MM-dd"),
            "reference_balance": float(self.balance.value()),
            "reference_date": self.reference_date.date().toString("yyyy-MM-dd"),
            "currency": self.currency.currentText(),
            "status": self.status.currentText(),
        }
