from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QDate, Qt, QPoint
from PySide6.QtWidgets import (
    QFrame,
    QComboBox,
    QDialog,
    QInputDialog,
    QMenu,
    QFileDialog,
    QDateEdit,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.services.business_rules import is_uncategorized_transaction
from app.services.categorization_rule_service import CategorizationRuleService
from app.imports.import_service import BankImportService, ImportedTransaction
from app.imports.csv_parser import payload_to_json
from app.theme import euro, format_date_fr, qdate_to_iso
from app.widgets import Card, PageHeader, StepLabel, primary_button, secondary_button


class ImportPreviewDialog(QDialog):
    """Large modal used to review imported bank operations before validation."""

    def __init__(
        self,
        parent: QWidget,
        file_name: str,
        account_label: str,
        rows: list[ImportedTransaction],
        duplicate_flags: list[bool],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aperçu détaillé de l'import")
        self.resize(1080, 680)
        self.setMinimumSize(920, 560)
        self.rows = rows
        self.duplicate_flags = duplicate_flags
        self.confirm_requested = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title = QLabel("Aperçu détaillé de l'import")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        subtitle = QLabel(f"{file_name} — {len(rows)} opérations détectées — Compte : {account_label}")
        subtitle.setStyleSheet("color:#64748B; font-size: 14px;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.summary_label = QLabel(self.build_summary())
        self.summary_label.setStyleSheet(
            "background:#F8FAFC; border:1px solid #DDE7F3; border-radius:14px; "
            "padding:12px; color:#475569; font-weight: bold;"
        )
        layout.addWidget(self.summary_label)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Sélection",
            "Date",
            "Libellé",
            "Débit",
            "Crédit",
            "Montant",
            "Catégorie proposée",
            "Statut",
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setDefaultSectionSize(44)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        header.setSectionResizeMode(7, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 84)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 100)
        self.table.setColumnWidth(5, 110)
        self.table.setColumnWidth(6, 160)
        self.table.setColumnWidth(7, 100)
        self.table.setStyleSheet(
            "QTableWidget { background:white; border:1px solid #DDE7F3; border-radius:14px; }"
            "QHeaderView::section { background:#F1F5F9; color:#475569; padding:10px; font-weight: bold; }"
        )
        layout.addWidget(self.table, stretch=1)
        self.populate_table()

        buttons = QHBoxLayout()
        cancel_btn = secondary_button("Annuler")
        back_btn = secondary_button("Retour")
        confirm_btn = primary_button("Confirmer l'import")
        cancel_btn.clicked.connect(self.reject)
        back_btn.clicked.connect(self.reject)
        confirm_btn.clicked.connect(self.confirm)
        buttons.addWidget(cancel_btn)
        buttons.addStretch(1)
        buttons.addWidget(back_btn)
        buttons.addWidget(confirm_btn)
        layout.addLayout(buttons)

    def build_summary(self) -> str:
        new_count = sum(1 for flag in self.duplicate_flags if not flag)
        duplicate_count = sum(1 for flag in self.duplicate_flags if flag)
        credits = sum(tx.amount for tx in self.rows if tx.amount > 0)
        debits = sum(tx.amount for tx in self.rows if tx.amount < 0)
        analysis = getattr(getattr(self, "parent", lambda: None)(), "import_service", None)
        last_analysis = getattr(analysis, "last_analysis", None)
        errors = len(getattr(last_analysis, "rejected_lines", []) or []) if last_analysis else 0
        profile = getattr(getattr(last_analysis, "diagnostic", None), "profile_name", "") if last_analysis else ""
        profile_text = f"   •   Profil : {profile}" if profile else ""
        return (
            f"Nouvelles : {new_count}   •   Doublons : {duplicate_count}   •   Erreurs : {errors}{profile_text}   |   "
            f"Crédits : {euro(credits)}   •   Débits : {euro(abs(debits))}   •   Solde net : {euro(credits + debits)}"
        )

    def populate_table(self) -> None:
        self.table.setRowCount(0)
        for row_index, tx in enumerate(self.rows):
            self.table.insertRow(row_index)
            is_duplicate = self.duplicate_flags[row_index]
            debit = euro(abs(tx.amount)) if tx.amount < 0 else ""
            credit = euro(tx.amount) if tx.amount > 0 else ""
            status = "Doublon" if is_duplicate else "Nouveau"
            values = ["", format_date_fr(tx.tx_date), tx.label, debit, credit, euro(tx.amount), tx.category or "À proposer", status]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                    item.setCheckState(Qt.CheckState.Unchecked if is_duplicate else Qt.CheckState.Checked)
                    item.setTextAlignment(Qt.AlignCenter)
                elif col in {3, 4, 5, 7}:
                    item.setTextAlignment(Qt.AlignCenter)
                if col == 2:
                    item.setToolTip(tx.label)
                if col in {3, 5} and tx.amount < 0:
                    item.setForeground(Qt.red)
                if col in {4, 5} and tx.amount > 0:
                    item.setForeground(Qt.green)
                if col == 7:
                    item.setForeground(Qt.darkYellow if is_duplicate else Qt.darkGreen)
                self.table.setItem(row_index, col, item)

    def selected_rows(self) -> list[ImportedTransaction]:
        selected: list[ImportedTransaction] = []
        for row_index, tx in enumerate(self.rows):
            item = self.table.item(row_index, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                selected.append(tx)
        return selected

    def confirm(self) -> None:
        if not self.selected_rows():
            QMessageBox.information(self, "Import", "Aucune opération sélectionnée pour l'import.")
            return
        self.confirm_requested = True
        self.accept()



class TransactionDialog(QDialog):
    def __init__(self, accounts, categories: list[str] | None = None, parent=None, row=None) -> None:
        super().__init__(parent)
        self.row = row
        self.setWindowTitle("Modifier la transaction" if row else "Nouvelle transaction")
        self.setMinimumWidth(520)
        self.accounts = accounts
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.account = QComboBox()
        for account_row in accounts:
            self.account.addItem(f"{account_row['name']} — {account_row['bank']}", account_row["id"])

        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("dd/MM/yyyy")

        self.label = QLineEdit()
        self.label.setPlaceholderText("Libellé de l'opération")

        self.category = QComboBox()
        self.category.addItems([""] + list(categories or []))

        self.direction = QComboBox()
        self.direction.addItems(["Débit", "Crédit"])

        self.amount = QDoubleSpinBox()
        self.amount.setRange(0, 100000000)
        self.amount.setDecimals(2)
        self.amount.setSuffix(" €")

        self.status = QComboBox()
        self.status.addItems(["Validée", "À catégoriser", "Catégorisée automatiquement", "À vérifier"])

        for label, widget in [
            ("Compte", self.account),
            ("Date", self.date),
            ("Libellé", self.label),
            ("Catégorie", self.category),
            ("Sens", self.direction),
            ("Montant", self.amount),
            ("Statut", self.status),
        ]:
            form.addRow(label, widget)

        layout.addLayout(form)
        help_label = QLabel("Tous les champs sont modifiables. Saisissez le montant en valeur absolue puis choisissez explicitement Débit ou Crédit.")
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color:#64748B;")
        layout.addWidget(help_label)

        if row is not None:
            self.populate(row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def populate(self, row) -> None:
        self.account.setCurrentIndex(max(0, self.account.findData(row["account_id"])))
        try:
            y, m, d = [int(v) for v in str(row["tx_date"]).split("-")]
            self.date.setDate(QDate(y, m, d))
        except Exception:
            self.date.setDate(QDate.currentDate())
        self.label.setText(row["label"] or "")
        if row["category"]:
            index = self.category.findText(row["category"])
            if index < 0:
                self.category.addItem(row["category"])
                index = self.category.findText(row["category"])
            self.category.setCurrentIndex(index)
        amount = float(row["amount"] or 0)
        direction = row["tx_type"] if "tx_type" in row.keys() and row["tx_type"] else ("Crédit" if amount >= 0 else "Débit")
        self.direction.setCurrentText(direction)
        self.amount.setValue(abs(amount))
        self.status.setCurrentText(row["status"] or "Validée")

    def data(self) -> dict:
        return {
            "account_id": self.account.currentData(),
            "tx_date": self.date.date().toString("yyyy-MM-dd"),
            "label": self.label.text().strip() or "Nouvelle opération",
            "category": self.category.currentText() or None,
            "amount": -abs(float(self.amount.value())) if self.direction.currentText() == "Débit" else abs(float(self.amount.value())),
            "tx_type": self.direction.currentText(),
            "direction_explicit": True,
            "status": self.status.currentText(),
        }


class TransactionsPage(QWidget):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.import_service = BankImportService()
        self.preview_rows: list[ImportedTransaction] = []
        self.current_import_path: Path | None = None
        self.accounts = []
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(14)
        self.build()

    def build(self) -> None:
        self.new_transaction_btn = primary_button("+ Nouvelle transaction")
        self.new_transaction_btn.clicked.connect(self.open_add_transaction_dialog)
        self.import_btn = primary_button("Importer")
        self.export_btn = secondary_button("Exporter")
        self.import_btn.clicked.connect(self.choose_file)
        actions = [self.new_transaction_btn, self.import_btn, self.export_btn]
        self.layout.addWidget(PageHeader("Transactions", "Gestion des opérations bancaires et imports", actions))

        self.tabs = QTabWidget()
        self.table_all = self.create_table()
        self.table_uncat = self.create_table()
        self.table_recurring = self.create_table()
        self.tabs.addTab(self.table_all, "Toutes les transactions")
        self.tabs.addTab(self.table_uncat, "À catégoriser (2)")
        self.tabs.addTab(self.table_recurring, "Récurrentes")
        self.layout.addWidget(self.build_filters())

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.build_transactions_area())
        self.splitter.addWidget(self.build_import_panel())
        self.import_panel_scroll.setVisible(False)
        self.splitter.setSizes([1450, 0])
        self.layout.addWidget(self.splitter, stretch=1)
        self.import_panel_visible = False

        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: #64748B; font-weight: bold; padding-left: 4px;")
        self.layout.addWidget(self.stats_label)
        self.refresh()

    def open_import_panel(self) -> None:
        if getattr(self, "import_panel_visible", False):
            return
        self.import_panel_visible = True
        self.import_panel_scroll.setVisible(True)
        self.import_panel.show()
        self.splitter.setSizes([980, 440])

    def close_import_panel(self) -> None:
        self.import_panel_visible = False
        self.import_panel_scroll.setVisible(False)
        self.splitter.setSizes([1450, 0])

    def build_filters(self) -> Card:
        filters = Card()
        filter_layout = QHBoxLayout(filters)
        filter_layout.setContentsMargins(16, 12, 16, 12)
        filter_layout.setSpacing(10)
        self.account_filter = QComboBox()
        self.account_filter.setMinimumWidth(280)
        self.account_filter.setMinimumContentsLength(18)
        self.account_filter.currentIndexChanged.connect(self.refresh_table_only)
        self.category_filter = QComboBox()
        self.category_filter.setMinimumWidth(230)
        self.category_filter.setMinimumContentsLength(18)
        self.refresh_category_filter_options()
        self.category_filter.currentIndexChanged.connect(self.refresh_table_only)
        self.period_filter_active = False
        period_from_label = QLabel("Du")
        period_from_label.setStyleSheet("color:#64748B; font-weight:bold;")
        self.period_from = QDateEdit(QDate.currentDate().addMonths(-1))
        self.period_from.setCalendarPopup(True)
        self.period_from.setDisplayFormat("dd/MM/yyyy")
        self.period_from.setMinimumWidth(130)
        self.period_from.dateChanged.connect(self.activate_period_filter)
        period_to_label = QLabel("Au")
        period_to_label.setStyleSheet("color:#64748B; font-weight:bold;")
        self.period_to = QDateEdit(QDate.currentDate())
        self.period_to.setCalendarPopup(True)
        self.period_to.setDisplayFormat("dd/MM/yyyy")
        self.period_to.setMinimumWidth(130)
        self.period_to.dateChanged.connect(self.activate_period_filter)
        self.period_reset_btn = secondary_button("Toutes dates")
        self.period_reset_btn.clicked.connect(self.reset_period_filter)
        self.search_input = QLineEdit()
        self.search_input.setMinimumWidth(300)
        self.search_input.setPlaceholderText("Rechercher une opération, un libellé...")
        self.search_input.textChanged.connect(self.refresh_table_only)
        filters_btn = secondary_button("Filtres")
        for widget in [
            self.account_filter, self.category_filter,
            period_from_label, self.period_from, period_to_label, self.period_to, self.period_reset_btn,
            self.search_input, filters_btn
        ]:
            filter_layout.addWidget(widget)
        filter_layout.setStretch(0, 2)
        filter_layout.setStretch(1, 1)
        filter_layout.setStretch(7, 3)
        return filters

    def build_transactions_area(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.bulk_bar = Card()
        self.bulk_bar.setVisible(False)
        bulk_layout = QHBoxLayout(self.bulk_bar)
        bulk_layout.setContentsMargins(14, 10, 14, 10)
        bulk_layout.setSpacing(10)
        self.selection_label = QLabel("0 transaction sélectionnée")
        self.selection_label.setStyleSheet("font-weight: bold; color:#0F172A;")
        edit_btn = secondary_button("Modifier")
        edit_btn.clicked.connect(self.open_edit_transaction_dialog)
        categorize_btn = secondary_button("Catégoriser")
        categorize_btn.clicked.connect(self.bulk_change_category)
        validate_btn = secondary_button("Marquer validée")
        validate_btn.clicked.connect(lambda: self.bulk_change_status("Validée"))
        pending_btn = secondary_button("À catégoriser")
        pending_btn.clicked.connect(lambda: self.bulk_change_status("À catégoriser"))
        delete_btn = secondary_button("Supprimer")
        delete_btn.clicked.connect(self.bulk_delete_transactions)
        clear_btn = secondary_button("Désélectionner")
        clear_btn.clicked.connect(self.clear_all_checks)
        bulk_layout.addWidget(self.selection_label)
        bulk_layout.addStretch(1)
        for btn in [edit_btn, categorize_btn, validate_btn, pending_btn, delete_btn, clear_btn]:
            bulk_layout.addWidget(btn)
        layout.addWidget(self.bulk_bar)
        layout.addWidget(self.tabs)
        return container

    def create_table(self) -> QTableWidget:
        table = QTableWidget(0, 8)
        table.setHorizontalHeaderLabels(["☐", "Date", "Compte", "Libellé", "Catégorie", "Montant", "Type", "Statut"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(lambda pos, tbl=table: self.open_table_context_menu(tbl, pos))
        table.itemChanged.connect(self.on_table_item_changed)
        table.horizontalHeader().sectionClicked.connect(lambda index, tbl=table: self.on_header_clicked(tbl, index))
        table.horizontalHeader().setStretchLastSection(True)
        table.setColumnWidth(0, 42)
        table.setColumnWidth(1, 105)
        table.setColumnWidth(2, 150)
        table.setColumnWidth(3, 280)
        table.setColumnWidth(4, 130)
        table.setColumnWidth(5, 100)
        table.setColumnWidth(6, 80)
        table.verticalHeader().setDefaultSectionSize(42)
        return table

    def build_import_panel(self) -> QScrollArea:
        """Scrollable right-side import assistant.

        V0.2.3 correction: the panel can contain more information than the
        available screen height. The whole content is now scrollable, and the
        recent imports are displayed as readable cards rather than a compressed
        table.
        """
        scroll = QScrollArea()
        self.import_panel_scroll = scroll
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setMinimumWidth(455)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        panel = Card()
        self.import_panel = panel
        panel.setMinimumWidth(430)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("Importer des opérations")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        close_btn = QPushButton("×")
        close_btn.setFixedSize(34, 34)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("Fermer le volet import")
        close_btn.setStyleSheet(
            "QPushButton { background:#F8FAFC; border:1px solid #CBD5E1; border-radius:17px; "
            "font-size:20px; font-weight: bold; color:#475569; } "
            "QPushButton:hover { background:#EEF2FF; color:#2563EB; }"
        )
        close_btn.clicked.connect(self.close_import_panel)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(close_btn)
        layout.addLayout(header)

        subtitle = QLabel("CSV, OFX, QIF, XLSX — aperçu en fenêtre dédiée")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #64748B;")
        layout.addWidget(subtitle)

        layout.addWidget(StepLabel(1, "Sélectionner un fichier", True))
        choose_btn = primary_button("Choisir un fichier bancaire")
        choose_btn.clicked.connect(self.choose_file)
        layout.addWidget(choose_btn)

        layout.addWidget(StepLabel(2, "Choisir le compte", True))
        self.import_account_combo = QComboBox()
        self.import_account_combo.currentIndexChanged.connect(self.refresh_import_analysis)
        layout.addWidget(self.import_account_combo)

        layout.addWidget(StepLabel(3, "Analyse du fichier", True))
        self.import_status = QLabel("Aucun fichier sélectionné.")
        self.import_status.setWordWrap(True)
        self.import_status.setMinimumHeight(64)
        self.import_status.setStyleSheet(
            "background:#F8FAFC; border:1px solid #DDE7F3; border-radius:12px; "
            "padding:12px; color:#475569; font-weight: bold;"
        )
        layout.addWidget(self.import_status)

        self.import_summary = QLabel("Nouvelles : 0\nDoublons : 0\nErreurs : 0")
        self.import_summary.setWordWrap(True)
        self.import_summary.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.import_summary.setMinimumHeight(84)
        self.import_summary.setStyleSheet(
            "background:#F8FAFC; border:1px solid #DDE7F3; border-radius:12px; "
            "padding:12px; color:#475569; font-weight: bold;"
        )
        layout.addWidget(self.import_summary)

        self.preview_detail_btn = secondary_button("Voir l’aperçu détaillé")
        self.preview_detail_btn.clicked.connect(self.open_preview_dialog)
        self.preview_detail_btn.setEnabled(False)
        layout.addWidget(self.preview_detail_btn)

        self.validate_import_btn = primary_button("4. Importer les opérations")
        self.validate_import_btn.clicked.connect(self.validate_import_direct)
        self.validate_import_btn.setEnabled(False)
        layout.addWidget(self.validate_import_btn)

        layout.addSpacing(10)
        history_title = QLabel("Derniers imports")
        history_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(history_title)

        history_hint = QLabel("Les lots importés restent visibles ici. Utilisez l’ascenseur pour consulter l’historique complet.")
        history_hint.setWordWrap(True)
        history_hint.setStyleSheet("color:#64748B; font-size:12px;")
        layout.addWidget(history_hint)

        self.import_history_container = QWidget()
        self.import_history_layout = QVBoxLayout(self.import_history_container)
        self.import_history_layout.setContentsMargins(0, 0, 0, 0)
        self.import_history_layout.setSpacing(10)
        layout.addWidget(self.import_history_container)

        layout.addStretch(1)
        scroll.setWidget(panel)
        return scroll

    def refresh_category_filter_options(self) -> None:
        if not hasattr(self, "category_filter"):
            return
        current = self.category_filter.currentText()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("Toutes catégories")
        for name in self.current_category_names():
            self.category_filter.addItem(name)
        if current:
            idx = self.category_filter.findText(current)
            if idx >= 0:
                self.category_filter.setCurrentIndex(idx)
        self.category_filter.blockSignals(False)

    def refresh(self) -> None:
        self.accounts = self.db.list_accounts()
        current_id = self.account_filter.currentData() if hasattr(self, "account_filter") else None
        self.account_filter.blockSignals(True)
        self.import_account_combo.blockSignals(True)
        self.account_filter.clear()
        self.import_account_combo.clear()
        self.account_filter.addItem("Tous les comptes", None)
        for account in self.accounts:
            identifier = self.mask_identifier(account["identifier"])
            label = f"{account['name']} — {account['bank']}"
            import_label = f"{identifier} — {account['name']} — {account['bank']}"
            self.account_filter.addItem(label, account["id"])
            self.import_account_combo.addItem(import_label, account["id"])
        if current_id:
            idx = self.account_filter.findData(current_id)
            if idx >= 0:
                self.account_filter.setCurrentIndex(idx)
        self.account_filter.blockSignals(False)
        self.import_account_combo.blockSignals(False)
        self.refresh_category_filter_options()
        self.refresh_table_only()
        self.refresh_import_history()

    def refresh_table_only(self) -> None:
        if not hasattr(self, "account_filter"):
            return
        account_id = self.account_filter.currentData()
        search = self.search_input.text().strip()
        rows = self.db.list_transactions(search=search, account_id=account_id)
        rows = self.apply_period_filter(rows)
        category = self.category_filter.currentText()
        if category != "Toutes catégories":
            rows = [row for row in rows if (row["category"] or "") == category]
        uncat = [row for row in rows if is_uncategorized_transaction(row["category"], row["status"])]
        recurring_rows = self.filtered_recurring_items(account_id, category)
        recurring_rows = self.apply_recurring_period_filter(recurring_rows)
        self.populate_table(self.table_all, rows)
        self.populate_table(self.table_uncat, uncat)
        self.populate_recurring_table(self.table_recurring, recurring_rows)
        self.tabs.setTabText(1, f"À catégoriser ({len(uncat)})")
        self.tabs.setTabText(2, f"Récurrentes ({len(recurring_rows)})")
        total_debits = sum(row["amount"] for row in rows if row["amount"] < 0)
        total_credits = sum(row["amount"] for row in rows if row["amount"] > 0)
        self.stats_label.setText(
            f"Affichage de {len(rows)} opérations  •  Débits : {euro(abs(total_debits))}  •  Crédits : {euro(total_credits)}  •  Solde période : {euro(total_credits + total_debits)}"
        )

    def activate_period_filter(self) -> None:
        self.period_filter_active = True
        self.refresh_table_only()

    def reset_period_filter(self) -> None:
        self.period_filter_active = False
        self.refresh_table_only()

    def selected_period_range(self, rows=None) -> tuple[str | None, str | None]:
        if not getattr(self, "period_filter_active", False):
            return None, None
        start = qdate_to_iso(self.period_from.date()) if hasattr(self, "period_from") else None
        end = qdate_to_iso(self.period_to.date()) if hasattr(self, "period_to") else None
        if start and end and start > end:
            start, end = end, start
        return start, end

    def apply_period_filter(self, rows):
        start, end = self.selected_period_range(rows)
        if not start and not end:
            return list(rows)
        return [
            row for row in rows
            if (not start or str(row["tx_date"]) >= start)
            and (not end or str(row["tx_date"]) <= end)
        ]

    def apply_recurring_period_filter(self, rows):
        start, end = self.selected_period_range([])
        if not start and not end:
            return list(rows)
        return [
            row for row in rows
            if (not start or str(row["next_date"]) >= start)
            and (not end or str(row["next_date"]) <= end)
        ]

    def select_account_filter(self, account_id: int | None) -> None:
        self.refresh()
        if account_id is None:
            self.account_filter.setCurrentIndex(0)
            return
        index = self.account_filter.findData(account_id)
        if index >= 0:
            self.account_filter.setCurrentIndex(index)
        self.refresh_table_only()

    def filtered_recurring_items(self, account_id: int | None, category: str):
        rows = self.db.list_recurring_items(active_only=False)
        if account_id:
            rows = [row for row in rows if row["account_id"] == account_id]
        if category != "Toutes catégories":
            rows = [row for row in rows if (row["category"] or "") == category]
        return rows

    def populate_recurring_table(self, table: QTableWidget, rows) -> None:
        """Populate the Transactions > Récurrentes tab from recurring_items.

        This tab must display the recurrence models, not a heuristic subset of
        existing transactions. These rows are not selectable for transaction
        bulk actions because they are maintenance rules, not posted operations.
        """
        table.blockSignals(True)
        table.setRowCount(0)
        for row_index, row in enumerate(rows):
            table.insertRow(row_index)
            amount = float(row["amount"] or 0)
            values = [
                "",
                format_date_fr(row["next_date"]),
                row["account_name"] or "Compte",
                row["name"],
                row["category"] or "Prévisionnel",
                euro(amount),
                row["frequency"],
                row["status"],
            ]
            table.setRowHeight(row_index, 42)
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                # Recurrence rows carry their recurring_items identifier. They
                # are not transaction IDs, so the dedicated context menu below
                # routes them to RecurringDialog instead of TransactionDialog.
                item.setData(Qt.UserRole, int(row["id"]))
                if col == 0:
                    item.setFlags(Qt.ItemIsEnabled)
                    item.setText("")
                    item.setTextAlignment(Qt.AlignCenter)
                if col in {5, 6, 7}:
                    item.setTextAlignment(Qt.AlignCenter)
                if col == 5:
                    item.setForeground(Qt.green if amount > 0 else Qt.red)
                table.setItem(row_index, col, item)
        table.blockSignals(False)


    def populate_table(self, table: QTableWidget, rows) -> None:
        table.blockSignals(True)
        table.setRowCount(0)
        for row_index, row in enumerate(rows):
            table.insertRow(row_index)
            status = row["status"]
            values = [
                "",
                format_date_fr(row["tx_date"]),
                row["account_name"],
                row["label"],
                row["category"] or "À catégoriser",
                euro(row["amount"]),
                row["tx_type"],
                status,
            ]
            table.setRowHeight(row_index, 42)
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, row["id"])
                if col == 0:
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    item.setCheckState(Qt.Unchecked)
                    item.setTextAlignment(Qt.AlignCenter)
                if col in {5, 6, 7}:
                    item.setTextAlignment(Qt.AlignCenter)
                if col == 5:
                    item.setForeground(Qt.green if row["amount"] > 0 else Qt.red)
                if col == 7 and status == "À catégoriser":
                    item.setForeground(Qt.darkYellow)
                table.setItem(row_index, col, item)
        table.blockSignals(False)



    def selected_transaction_ids(self) -> list[int]:
        ids: list[int] = []
        seen: set[int] = set()
        for table in [self.table_all, self.table_uncat]:
            for row_index in range(table.rowCount()):
                item = table.item(row_index, 0)
                if item and item.checkState() == Qt.Checked:
                    tx_id = item.data(Qt.UserRole)
                    if tx_id is not None and int(tx_id) not in seen:
                        seen.add(int(tx_id))
                        ids.append(int(tx_id))
        return ids

    def on_table_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 0:
            self.update_bulk_bar()

    def update_bulk_bar(self) -> None:
        if not hasattr(self, "bulk_bar"):
            return
        count = len(self.selected_transaction_ids())
        self.bulk_bar.setVisible(count > 0)
        plural = "s" if count > 1 else ""
        self.selection_label.setText(f"{count} transaction{plural} sélectionnée{plural}")

    def on_header_clicked(self, table: QTableWidget, index: int) -> None:
        if index != 0:
            return
        checked_count = sum(
            1 for row_index in range(table.rowCount())
            if table.item(row_index, 0) and table.item(row_index, 0).checkState() == Qt.Checked
        )
        target = Qt.Unchecked if checked_count == table.rowCount() and table.rowCount() else Qt.Checked
        table.blockSignals(True)
        for row_index in range(table.rowCount()):
            item = table.item(row_index, 0)
            if item:
                item.setCheckState(target)
        table.blockSignals(False)
        self.update_bulk_bar()

    def clear_all_checks(self) -> None:
        for table in [self.table_all, self.table_uncat]:
            table.blockSignals(True)
            for row_index in range(table.rowCount()):
                item = table.item(row_index, 0)
                if item:
                    item.setCheckState(Qt.Unchecked)
            table.blockSignals(False)
        self.update_bulk_bar()

    def open_table_context_menu(self, table: QTableWidget, pos: QPoint) -> None:
        row_index = table.rowAt(pos.y())
        if row_index < 0:
            return

        if table is self.table_recurring:
            table.selectRow(row_index)
            item = table.item(row_index, 0)
            recurring_id = int(item.data(Qt.UserRole)) if item and item.data(Qt.UserRole) else None
            if not recurring_id:
                QMessageBox.warning(self, "Récurrence", "La récurrence sélectionnée est introuvable.")
                return
            menu = QMenu(self)
            action_edit = menu.addAction("Modifier cette transaction")
            action_delete = menu.addAction("Supprimer cette récurrence")
            selected = menu.exec(table.viewport().mapToGlobal(pos))
            if selected == action_edit:
                self.open_edit_recurring_dialog(recurring_id)
            elif selected == action_delete:
                self.delete_recurring_item(recurring_id)
            return

        item = table.item(row_index, 0)
        if item and not self.selected_transaction_ids():
            item.setCheckState(Qt.Checked)

        menu = QMenu(self)
        action_edit = menu.addAction("Modifier cette transaction")
        action_category = menu.addAction("Modifier la catégorie de la sélection")
        action_apply_rules = menu.addAction("Appliquer les règles automatiques à la sélection")
        action_create_rule = menu.addAction("Créer une règle depuis cette transaction")
        action_valid = menu.addAction("Marquer comme validée")
        action_pending = menu.addAction("Marquer à catégoriser")
        menu.addSeparator()
        action_delete = menu.addAction("Supprimer la sélection")
        if len(self.selected_transaction_ids()) != 1:
            action_edit.setEnabled(False)
            action_create_rule.setEnabled(False)
        selected = menu.exec(table.viewport().mapToGlobal(pos))
        if selected == action_edit:
            self.open_edit_transaction_dialog()
        elif selected == action_category:
            self.bulk_change_category()
        elif selected == action_apply_rules:
            self.apply_rules_to_selected()
        elif selected == action_create_rule:
            self.create_rule_from_selected_transaction()
        elif selected == action_valid:
            self.bulk_change_status("Validée")
        elif selected == action_pending:
            self.bulk_change_status("À catégoriser")
        elif selected == action_delete:
            self.bulk_delete_transactions()

    def create_rule_from_selected_transaction(self) -> None:
        ids = self.selected_transaction_ids()
        if len(ids) != 1:
            QMessageBox.information(self, "Règle automatique", "Sélectionnez une seule transaction.")
            return
        categories = [
            name for name in self.db.category_names()
            if name and name != "À catégoriser"
        ]
        if not categories:
            QMessageBox.information(self, "Règle automatique", "Créez d’abord une catégorie cible.")
            return
        category, ok = QInputDialog.getItem(
            self,
            "Créer une règle",
            "Catégorie cible :",
            categories,
            0,
            False,
        )
        if not ok:
            return
        service = CategorizationRuleService(self.db)
        category_id = service.category_id_by_name(category)
        if not category_id:
            QMessageBox.warning(self, "Règle automatique", "Catégorie introuvable.")
            return
        try:
            rule_id = service.create_rule_from_transaction(ids[0], category_id)
            service.categorize_transaction(ids[0], force=True)
            QMessageBox.information(self, "Règle créée", f"Règle automatique créée et appliquée.\\nID : {rule_id}")
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Règle automatique", str(exc))

    def current_category_names(self) -> list[str]:
        """Return active categories from Settings > Catégories."""
        return self.db.category_names()

    def bulk_change_category(self) -> None:
        ids = self.selected_transaction_ids()
        if not ids:
            QMessageBox.information(self, "Actions groupées", "Cochez au moins une transaction.")
            return

        # V0.6.8.1 — the bulk category dialog must use the managed categories
        # table, not a historical hard-coded list.
        categories = ["À catégoriser"] + [
            name for name in self.db.category_names()
            if name and name != "À catégoriser"
        ]
        if not categories:
            QMessageBox.information(self, "Catégories", "Aucune catégorie active disponible.")
            return

        category, ok = QInputDialog.getItem(
            self,
            "Catégoriser",
            "Nouvelle catégorie :",
            categories,
            0,
            False,
        )
        if not ok:
            return

        value = None if category == "À catégoriser" else category
        updated = self.db.update_transactions_category(ids, value)
        QMessageBox.information(self, "Catégorisation", f"{updated} transaction(s) mise(s) à jour.")
        self.refresh()

    def bulk_change_status(self, status: str) -> None:
        ids = self.selected_transaction_ids()
        if not ids:
            QMessageBox.information(self, "Actions groupées", "Cochez au moins une transaction.")
            return
        updated = self.db.update_transactions_status(ids, status)
        QMessageBox.information(self, "Statut", f"{updated} transaction(s) mise(s) à jour.")
        self.refresh()

    def bulk_delete_transactions(self, ids: list[int] | None = None) -> None:
        ids = ids or self.selected_transaction_ids()
        if not ids:
            QMessageBox.information(self, "Actions groupées", "Cochez au moins une transaction.")
            return
        confirm = QMessageBox.question(
            self,
            "Suppression groupée",
            f"Vous allez supprimer {len(ids)} transaction(s).\\n\\nCette action est irréversible. Confirmer ?",
        )
        if confirm != QMessageBox.Yes:
            return
        deleted = self.db.delete_transactions(ids)
        QMessageBox.information(self, "Suppression", f"{deleted} transaction(s) supprimée(s).")
        self.refresh()


    def open_add_transaction_dialog(self) -> None:
        self.accounts = self.db.list_accounts()
        if not self.accounts:
            QMessageBox.information(self, "Transaction", "Créez d'abord un compte bancaire.")
            return
        dialog = TransactionDialog(self.accounts, self.db.category_names(), self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.data()
            self.db.insert_transaction(
                data["account_id"],
                data["tx_date"],
                data["label"],
                data["category"],
                data["amount"],
                "Manuel",
                preserve_direction=True,
            )
            self.refresh()


    def open_edit_recurring_dialog(self, recurring_id: int) -> None:
        from app.ui.forecast_page import RecurringDialog

        row = self.db.get_recurring_item(recurring_id)
        if not row:
            QMessageBox.warning(self, "Modifier", "Récurrence introuvable.")
            return
        dialog = RecurringDialog(
            self.db.list_accounts(),
            parent=self,
            row=row,
            categories=self.db.category_names(),
        )
        if dialog.exec() == QDialog.Accepted:
            self.db.update_recurring_item(recurring_id, dialog.data())
            QMessageBox.information(self, "Modifier", "Récurrence mise à jour.")
            self.refresh()

    def delete_recurring_item(self, recurring_id: int) -> None:
        row = self.db.get_recurring_item(recurring_id)
        if not row:
            QMessageBox.warning(self, "Récurrence", "Récurrence introuvable.")
            return
        if QMessageBox.question(
            self,
            "Supprimer la récurrence",
            f"Supprimer la récurrence « {row['name']} » ?",
        ) == QMessageBox.Yes:
            self.db.delete_recurring_item(recurring_id)
            self.refresh()


    def open_edit_transaction_dialog(self) -> None:
        ids = self.selected_transaction_ids()
        if not ids:
            table = self.tabs.currentWidget()
            if isinstance(table, QTableWidget) and table.currentRow() >= 0:
                item = table.item(table.currentRow(), 0)
                tx_id = item.data(Qt.UserRole) if item else None
                ids = [int(tx_id)] if tx_id else []
        if len(ids) != 1:
            QMessageBox.information(self, "Modifier", "Sélectionnez une seule transaction à modifier.")
            return
        row = self.db.get_transaction(ids[0])
        if not row:
            QMessageBox.warning(self, "Modifier", "Transaction introuvable.")
            return
        dialog = TransactionDialog(self.db.list_accounts(), self.db.category_names(), self, row=row)
        if dialog.exec() == QDialog.Accepted:
            try:
                self.db.update_transaction(ids[0], dialog.data())
                QMessageBox.information(self, "Modifier", "Transaction mise à jour.")
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "Modifier", str(exc))

    def apply_rules_to_selected(self) -> None:
        ids = self.selected_transaction_ids()
        if not ids:
            QMessageBox.information(self, "Règles automatiques", "Cochez au moins une transaction.")
            return
        summary = CategorizationRuleService(self.db).apply_rules_to_transactions(ids, force=True)
        QMessageBox.information(
            self,
            "Règles automatiques",
            f"Transactions traitées : {summary['processed']}\\n"
            f"Catégorisées automatiquement : {summary['auto']}\\n"
            f"À vérifier : {summary['to_review']}\\n"
            f"À catégoriser : {summary['to_categorize']}\\n"
            f"Ignorées : {summary['skipped']}"
        )
        self.refresh()


    def delete_selected_transaction(self) -> None:
        ids = self.selected_transaction_ids()
        if not ids:
            table = self.tabs.currentWidget()
            if isinstance(table, QTableWidget) and table.currentRow() >= 0:
                item = table.item(table.currentRow(), 0)
                tx_id = item.data(Qt.UserRole) if item else None
                ids = [int(tx_id)] if tx_id else []
        if not ids:
            QMessageBox.information(self, "Transaction", "Sélectionnez ou cochez au moins une transaction à supprimer.")
            return
        self.bulk_delete_transactions(ids)

    def detected_source_identifiers(self) -> list[str]:
        analysis = getattr(self.import_service, "last_analysis", None)
        diagnostic = getattr(analysis, "diagnostic", None)
        return list(getattr(diagnostic, "source_account_identifiers", []) or [])

    @staticmethod
    def identifier_digits(value: str | None) -> str:
        import re
        return re.sub(r"\D+", "", str(value or ""))

    def account_matches_detected_identifier(self, account, detected_identifiers: list[str]) -> bool:
        account_digits = self.identifier_digits(account["identifier"] if "identifier" in account.keys() else "")
        if len(account_digits) < 6:
            return False
        for detected in detected_identifiers:
            detected_digits = self.identifier_digits(detected)
            if len(detected_digits) < 8:
                continue
            if account_digits == detected_digits:
                return True
            if detected_digits.endswith(account_digits) and len(account_digits) >= 6:
                return True
            if account_digits.endswith(detected_digits) and len(detected_digits) >= 6:
                return True
        return False

    def matching_accounts_for_import(self) -> list:
        detected = self.detected_source_identifiers()
        if not detected:
            return []
        return [account for account in self.accounts if self.account_matches_detected_identifier(account, detected)]

    def auto_select_detected_account(self) -> None:
        matches = self.matching_accounts_for_import()
        if len(matches) == 1:
            index = self.import_account_combo.findData(matches[0]["id"])
            if index >= 0:
                self.import_account_combo.setCurrentIndex(index)

    def import_account_consistency(self) -> tuple[bool, str]:
        detected = self.detected_source_identifiers()
        if not detected:
            return True, ""
        account_id = self.import_account_combo.currentData()
        selected = next((a for a in self.accounts if a["id"] == account_id), None)
        matches = self.matching_accounts_for_import()
        shown = ", ".join(detected[:3])
        if selected and self.account_matches_detected_identifier(selected, detected):
            return True, f"Compte source détecté : {shown}. Compte cible cohérent."
        if matches:
            labels = ", ".join(f"{row['name']} — {row['bank']}" for row in matches[:3])
            return False, (
                f"Import bloqué : le fichier semble appartenir au compte {shown}.\n"
                f"Compte Valoria correspondant détecté : {labels}.\n"
                "Sélectionnez ce compte avant l'import."
            )
        return False, (
            f"Import bloqué : le fichier contient l'identifiant de compte {shown},\n"
            "mais aucun compte Valoria ne possède cet identifiant.\n"
            "Créez ou mettez à jour le compte correspondant avant l'import."
        )

    def ensure_import_account_consistency(self) -> bool:
        ok, message = self.import_account_consistency()
        if not ok:
            QMessageBox.warning(self, "Compte bancaire incohérent", message)
        return ok

    def choose_file(self) -> None:
        self.open_import_panel()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importer un fichier bancaire",
            str(Path(__file__).resolve().parents[2] / "data"),
            "Fichiers bancaires (*.csv *.ofx *.qif *.xlsx);;Tous les fichiers (*.*)",
        )
        if not path:
            return
        self.current_import_path = Path(path)
        self.preview_rows = []
        self.import_status.setText(f"Fichier : {self.current_import_path.name}\nAnalyse en cours...")
        self.import_summary.setText("Nouvelles : 0\nDoublons : 0\nErreurs : 0")
        self.preview_detail_btn.setEnabled(False)
        if hasattr(self, "validate_import_btn"):
            self.validate_import_btn.setEnabled(False)
        try:
            analysis = self.import_service.analyze(path)
            self.preview_rows = analysis.valid_transactions
            self.auto_select_detected_account()
            self.refresh_import_analysis()
            if analysis.valid_transactions:
                self.preview_detail_btn.setEnabled(True)
                if hasattr(self, "validate_import_btn"):
                    self.validate_import_btn.setEnabled(True)
            else:
                QMessageBox.warning(self, "Analyse du fichier", analysis.diagnostic.short_message())
        except Exception as exc:
            # R7.2: the selected file remains visible even when analysis fails.
            self.import_status.setText(f"Fichier : {self.current_import_path.name}\nAnalyse impossible : {exc}")
            QMessageBox.critical(self, "Import impossible", str(exc))

    def duplicate_flags(self) -> list[bool]:
        account_id = self.import_account_combo.currentData()
        if not account_id:
            return [False for _ in self.preview_rows]
        return [self.db.transaction_exists(account_id, tx.tx_date, tx.label, tx.amount) for tx in self.preview_rows]

    def refresh_import_analysis(self) -> None:
        if not hasattr(self, "import_status"):
            return
        analysis = getattr(self.import_service, "last_analysis", None)
        flags = self.duplicate_flags() if self.preview_rows else []
        duplicate_count = sum(1 for flag in flags if flag)
        new_count = len(self.preview_rows) - duplicate_count
        error_count = len(getattr(analysis, "rejected_lines", []) or []) if analysis else 0
        file_name = self.current_import_path.name if self.current_import_path else "fichier sélectionné"
        diagnostic_text = analysis.diagnostic.short_message() if analysis else "Analyse terminée."
        account_ok, account_message = self.import_account_consistency()
        account_line = f"\n{account_message}" if account_message else ""
        self.import_status.setText(
            f"Fichier : {file_name}\n"
            f"Opérations détectées : {len(self.preview_rows)}\n"
            f"{diagnostic_text}{account_line}\n"
            "Contrôlez les lignes avec l’aperçu détaillé avant validation."
        )
        self.import_summary.setText(
            f"Nouvelles : {new_count}\n"
            f"Doublons : {duplicate_count}\n"
            f"Erreurs : {error_count}"
        )
        self.preview_detail_btn.setEnabled(bool(self.preview_rows))
        if hasattr(self, "validate_import_btn"):
            self.validate_import_btn.setEnabled(bool(self.preview_rows and new_count >= 0 and account_ok))

    def open_preview_dialog(self) -> None:
        if not self.preview_rows:
            QMessageBox.information(self, "Import", "Sélectionnez d'abord un fichier bancaire.")
            return
        account_id = self.import_account_combo.currentData()
        if not account_id:
            QMessageBox.warning(self, "Compte manquant", "Sélectionnez un compte bancaire.")
            return
        if not self.ensure_import_account_consistency():
            return
        account_label = self.import_account_combo.currentText()
        file_name = self.current_import_path.name if self.current_import_path else "import"
        dialog = ImportPreviewDialog(self, file_name, account_label, self.preview_rows, self.duplicate_flags())
        if dialog.exec() == QDialog.Accepted and dialog.confirm_requested:
            self.validate_import(dialog.selected_rows())

    def validate_import_direct(self) -> None:
        """Import the currently analysed file without reopening the preview window.

        V0.3.1 correction:
        - the preview button is only for visual control;
        - the import button performs the import directly after confirmation;
        - this avoids ambiguity where clicking “Importer” reopened the preview dialog.
        """
        if not self.preview_rows:
            QMessageBox.information(self, "Import", "Sélectionnez d'abord un fichier bancaire.")
            return
        account_id = self.import_account_combo.currentData()
        if not account_id:
            QMessageBox.warning(self, "Compte manquant", "Sélectionnez un compte bancaire.")
            return
        if not self.ensure_import_account_consistency():
            return

        flags = self.duplicate_flags()
        new_count = sum(1 for flag in flags if not flag)
        duplicate_count = sum(1 for flag in flags if flag)
        file_name = self.current_import_path.name if self.current_import_path else "fichier sélectionné"

        confirm = QMessageBox.question(
            self,
            "Confirmer l'import",
            f"Importer le fichier : {file_name}\n"
            f"Compte : {self.import_account_combo.currentText()}\n\n"
            f"Nouvelles opérations : {new_count}\n"
            f"Doublons détectés : {duplicate_count}\n\n"
            "Les doublons seront ignorés automatiquement.",
        )
        if confirm != QMessageBox.Yes:
            return

        rows_to_import = [tx for tx, is_duplicate in zip(self.preview_rows, flags) if not is_duplicate]
        self.validate_import(rows_to_import)

    def validate_import(self, rows_to_import: Iterable[ImportedTransaction] | None = None) -> None:
        selected_rows = list(rows_to_import) if rows_to_import is not None else list(self.preview_rows)
        if not selected_rows:
            QMessageBox.information(self, "Import", "Aucune opération sélectionnée pour l'import.")
            return
        account_id = self.import_account_combo.currentData()
        if not account_id:
            QMessageBox.warning(self, "Compte manquant", "Sélectionnez un compte bancaire.")
            return
        if not self.ensure_import_account_consistency():
            return
        analysis = getattr(self.import_service, "last_analysis", None)
        diagnostic = getattr(analysis, "diagnostic", None)
        batch_id = self.db.create_import_batch(
            getattr(self, "current_import_path", Path("import")).name,
            account_id,
            parser_profile=getattr(diagnostic, "profile_name", None),
            diagnostic_summary=diagnostic.short_message() if diagnostic else None,
            header_line=getattr(diagnostic, "header_line", None),
        )
        imported = 0
        duplicates = 0
        errors = len(getattr(analysis, "rejected_lines", []) or []) if analysis else 0
        for tx in selected_rows:
            ok = self.db.insert_transaction(
                account_id, tx.tx_date, tx.label, tx.category, tx.amount, "Import bancaire", batch_id,
                currency=tx.currency or "EUR",
                source_line=tx.source_line,
                source_profile=tx.source_profile,
                raw_payload=payload_to_json(tx.raw_payload),
                source_identifier=tx.source_identifier,
            )
            if ok:
                imported += 1
            else:
                duplicates += 1
        self.db.update_import_batch(batch_id, imported, duplicates, errors)
        categorization_summary = CategorizationRuleService(self.db).apply_rules_to_import_batch(batch_id)
        reconciliation_summary = self.db.reconciliation_summary_for_import_batch(batch_id)
        QMessageBox.information(
            self,
            "Import terminé",
            f"{imported} opérations importées. {duplicates} doublons ignorés.\n\n"
            f"Catégorisées automatiquement : {categorization_summary['auto']}\n"
            f"À vérifier : {categorization_summary['to_review']}\n"
            f"À catégoriser : {categorization_summary['to_categorize']}\n\n"
            f"Rapprochements automatiques : {reconciliation_summary['auto']}\n"
            f"Rapprochements à vérifier : {reconciliation_summary['to_review']}\n"
            f"Sans prévision : {reconciliation_summary['without_forecast']}"
        )
        self.preview_rows = []
        self.current_import_path = None
        self.import_status.setText("Import validé avec catégorisation automatique.")
        self.import_summary.setText(
            f"Nouvelles : {imported}\n"
            f"Doublons : {duplicates}\n"
            f"Auto : {categorization_summary['auto']}\n"
            f"À vérifier : {categorization_summary['to_review']}\n"
            f"À catégoriser : {categorization_summary['to_categorize']}\n"
            f"Rapprochés : {reconciliation_summary['auto']}\n"
            f"Rapp. à vérifier : {reconciliation_summary['to_review']}\n"
            f"Erreurs : {errors}"
        )
        self.preview_detail_btn.setEnabled(False)
        if hasattr(self, "validate_import_btn"):
            self.validate_import_btn.setEnabled(False)
        self.refresh()

    def refresh_import_history(self) -> None:
        if not hasattr(self, "import_history_layout"):
            return

        while self.import_history_layout.count():
            item = self.import_history_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        rows = self.db.list_recent_import_batches(8)
        if not rows:
            empty = QLabel("Aucun import récent.")
            empty.setWordWrap(True)
            empty.setStyleSheet(
                "background:#F8FAFC; border:1px dashed #CBD5E1; border-radius:12px; "
                "padding:14px; color:#64748B; font-weight: bold;"
            )
            self.import_history_layout.addWidget(empty)
            return

        for batch in rows:
            card = Card()
            card.setStyleSheet(
                "QFrame#Card { background:#FFFFFF; border:1px solid #DDE7F3; border-radius:14px; }"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(8)

            created = str(batch["created_at"] or "")[:16]
            file_name = str(batch["file_name"] or "Fichier importé")
            account = self.format_import_account_reference(batch)
            ops = int(batch["linked_transactions"] or 0)
            imported = int(batch["imported_count"] or 0)
            duplicates = int(batch["duplicate_count"] or 0)
            errors = int(batch["error_count"] or 0)
            status = str(batch["status"] or "Importé")

            file_label = QLabel(file_name)
            file_label.setWordWrap(True)
            file_label.setToolTip(file_name)
            file_label.setStyleSheet("font-weight: bold; color:#0F172A; font-size:13px;")
            card_layout.addWidget(file_label)

            meta = QLabel(f"{created}<br>Compte : {account}")
            meta.setWordWrap(True)
            meta.setStyleSheet("color:#64748B; font-size:12px; font-weight: bold;")
            card_layout.addWidget(meta)

            details = QLabel(
                f"Statut : {status}\n"
                f"Opérations liées : {ops}  •  Importées : {imported}\n"
                f"Doublons : {duplicates}  •  Erreurs : {errors}"
            )
            details.setWordWrap(True)
            details.setStyleSheet("color:#475569; font-size:12px;")
            card_layout.addWidget(details)

            actions = QHBoxLayout()
            actions.addStretch(1)
            if status == "Annulé" or ops == 0:
                badge = QLabel("Annulé")
                badge.setStyleSheet(
                    "background:#F1F5F9; color:#64748B; border-radius:9px; padding:6px 10px; font-weight: bold;"
                )
                actions.addWidget(badge)
            else:
                cancel_btn = QPushButton("Annuler cet import")
                cancel_btn.setCursor(Qt.PointingHandCursor)
                cancel_btn.setStyleSheet(
                    "QPushButton { background:#FFFFFF; border:1px solid #E5E7EB; border-radius:10px; "
                    "padding:7px 10px; font-weight: bold; } "
                    "QPushButton:hover { background:#FEF2F2; border-color:#FCA5A5; color:#DC2626; }"
                )
                cancel_btn.clicked.connect(lambda _checked=False, bid=batch["id"]: self.cancel_import(bid))
                actions.addWidget(cancel_btn)
            card_layout.addLayout(actions)
            self.import_history_layout.addWidget(card)


    @staticmethod
    def mask_identifier(identifier: str | None) -> str:
        """Return a readable, privacy-safe bank identifier for import history."""
        value = str(identifier or "").strip()
        if not value:
            return "Identifiant bancaire non renseigné"
        compact = value.replace(" ", "")
        if len(compact) <= 12:
            return value
        return f"{compact[:6]}…{compact[-6:]}"

    def format_import_account_reference(self, batch) -> str:
        identifier = self.mask_identifier(batch["account_identifier"] if "account_identifier" in batch.keys() else "")
        account_name = batch["account_name"] or "Compte"
        bank = batch["bank"] or "Banque"
        return f"{identifier} — {account_name} — {bank}"


    def cancel_import(self, batch_id: int) -> None:
        batch = self.db.get_import_batch(batch_id)
        if not batch:
            QMessageBox.warning(self, "Import introuvable", "Ce lot d'import n'existe plus.")
            return
        if batch["status"] == "Annulé":
            QMessageBox.information(self, "Import déjà annulé", "Ce lot d'import est déjà annulé.")
            return
        count = int(batch["linked_transactions"] or 0)
        message = (
            "Voulez-vous vraiment annuler cet import ?\n\n"
            f"Fichier : {batch['file_name']}\n"
            f"Compte : {batch['account_name']} — {batch['bank']}\n"
            f"Opérations supprimées : {count}\n\n"
            "Les opérations ajoutées manuellement ne seront pas impactées."
        )
        answer = QMessageBox.question(
            self,
            "Annuler le dernier import",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        deleted = self.db.cancel_import_batch(batch_id)
        QMessageBox.information(self, "Import annulé", f"{deleted} opérations importées ont été supprimées.")
        self.refresh_table_only()
        self.refresh_import_history()
