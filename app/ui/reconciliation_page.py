from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, QPoint
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.services.forecast_reconciliation_service import ForecastReconciliationService, STATUS_LABELS
from app.theme import COLORS, euro, format_date_fr
from app.widgets import Card, PageHeader, primary_button, secondary_button


class ReconciliationRulesDialog(QDialog):
    """Business-facing configuration for automatic reconciliation rules."""

    def __init__(self, config: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Règles de rapprochement automatique")
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Ces critères sont appliqués au moteur avant tout rapprochement. "
            "Les décisions restent explicables et annulables."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#64748B;")
        layout.addWidget(intro)
        form = QFormLayout()

        self.require_same_account = QCheckBox("Critère obligatoire")
        self.require_same_account.setChecked(bool(config["require_same_account"]))
        self.require_same_account.setEnabled(False)
        self.require_same_account.setToolTip("Protection obligatoire : un rapprochement entre deux comptes différents est interdit.")
        self.require_same_direction = QCheckBox("Critère obligatoire")
        self.require_same_direction.setChecked(bool(config["require_same_direction"]))
        self.require_same_direction.setEnabled(False)
        self.require_same_direction.setToolTip("Protection obligatoire : un débit ne peut jamais être rapproché d’un crédit.")

        self.date_tolerance_days = QSpinBox()
        self.date_tolerance_days.setRange(0, 60)
        self.date_tolerance_days.setSuffix(" jour(s)")
        self.date_tolerance_days.setValue(int(config["date_tolerance_days"]))

        self.amount_tolerance_abs = QDoubleSpinBox()
        self.amount_tolerance_abs.setRange(0, 100000)
        self.amount_tolerance_abs.setDecimals(2)
        self.amount_tolerance_abs.setSuffix(" €")
        self.amount_tolerance_abs.setValue(float(config["amount_tolerance_abs"]))

        self.amount_tolerance_percent = QDoubleSpinBox()
        self.amount_tolerance_percent.setRange(0, 100)
        self.amount_tolerance_percent.setDecimals(2)
        self.amount_tolerance_percent.setSuffix(" %")
        self.amount_tolerance_percent.setValue(float(config["amount_tolerance_percent"]))

        self.label_similarity_min = QSpinBox()
        self.label_similarity_min.setRange(0, 100)
        self.label_similarity_min.setSuffix(" %")
        self.label_similarity_min.setValue(int(config["label_similarity_min"]))

        self.auto_threshold = QSpinBox()
        self.auto_threshold.setRange(1, 100)
        self.auto_threshold.setSuffix(" %")
        self.auto_threshold.setValue(int(config["auto_threshold"]))

        self.review_threshold = QSpinBox()
        self.review_threshold.setRange(0, 99)
        self.review_threshold.setSuffix(" %")
        self.review_threshold.setValue(int(config["review_threshold"]))

        form.addRow("Même compte bancaire", self.require_same_account)
        form.addRow("Même sens Débit / Crédit", self.require_same_direction)
        form.addRow("Tolérance de date", self.date_tolerance_days)
        form.addRow("Tolérance de montant — euros", self.amount_tolerance_abs)
        form.addRow("Tolérance de montant — pourcentage", self.amount_tolerance_percent)
        form.addRow("Similarité minimale du libellé", self.label_similarity_min)
        form.addRow("Seuil Rapprochée auto", self.auto_threshold)
        form.addRow("Seuil À vérifier", self.review_threshold)
        layout.addLayout(form)

        note = QLabel(
            "Compte et sens identiques sont toujours obligatoires. Les références bancaires "
            "et catégories sont exploitées automatiquement lorsqu’elles sont disponibles."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#64748B;")
        layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def data(self) -> dict:
        return {
            "require_same_account": self.require_same_account.isChecked(),
            "require_same_direction": self.require_same_direction.isChecked(),
            "date_tolerance_days": self.date_tolerance_days.value(),
            "amount_tolerance_abs": self.amount_tolerance_abs.value(),
            "amount_tolerance_percent": self.amount_tolerance_percent.value(),
            "label_similarity_min": self.label_similarity_min.value(),
            "auto_threshold": self.auto_threshold.value(),
            "review_threshold": self.review_threshold.value(),
        }


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
        self.rules_btn = secondary_button("Paramétrer les règles")
        self.rules_btn.clicked.connect(self.open_rules_dialog)
        generate_btn = primary_button("Générer / mettre à jour")
        generate_btn.clicked.connect(self.generate_occurrences)
        overdue_btn = secondary_button("Marquer les retards")
        overdue_btn.clicked.connect(self.mark_overdue)

        self.layout.addWidget(
            PageHeader(
                "Rapprochements",
                "Transactions réalisées et occurrences prévisionnelles — jeu complet puis filtres d’affichage",
                [self.rules_btn, generate_btn, overdue_btn],
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

        # Target beta layout: two wide business lists on the first row, then
        # proposal and statuses on a second row. This keeps amounts and other
        # essential fields visible without squeezing three panels side by side.
        self.top_splitter = QSplitter(Qt.Horizontal)
        self.top_splitter.setChildrenCollapsible(False)
        self.top_splitter.addWidget(self.build_transactions_panel())
        self.top_splitter.addWidget(self.build_occurrences_panel())
        self.top_splitter.setStretchFactor(0, 1)
        self.top_splitter.setStretchFactor(1, 1)

        self.bottom_splitter = QSplitter(Qt.Horizontal)
        self.bottom_splitter.setChildrenCollapsible(False)
        self.bottom_splitter.addWidget(self.build_proposal_panel())
        self.kpi_panel = self.build_kpi_panel()
        self.bottom_splitter.addWidget(self.kpi_panel)
        self.bottom_splitter.setStretchFactor(0, 3)
        self.bottom_splitter.setStretchFactor(1, 2)

        self.main_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self.top_splitter)
        self.main_splitter.addWidget(self.bottom_splitter)
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setSizes([520, 320])
        self.layout.addWidget(self.main_splitter, stretch=1)

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
        layout.addWidget(self.panel_title("Transactions réalisées", "Opérations réelles non encore consommées par un rapprochement actif/final."))

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
        self.transactions_table.setColumnWidth(0, 34)
        self.transactions_table.setColumnWidth(1, 88)
        self.transactions_table.setColumnWidth(2, 110)
        self.transactions_table.setColumnWidth(4, 92)
        self.transactions_table.setColumnWidth(5, 105)
        self.transactions_table.setColumnWidth(6, 65)
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
        self.occurrences_table.setHorizontalHeaderLabels(["✓", "Date", "Compte", "Libellé", "Prévu", "Statut", "Réalisé", "Reste"])
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
        self.occurrences_table.setColumnWidth(0, 30)
        self.occurrences_table.setColumnWidth(1, 82)
        self.occurrences_table.setColumnWidth(2, 100)
        self.occurrences_table.setColumnWidth(4, 88)
        self.occurrences_table.setColumnWidth(5, 112)
        self.occurrences_table.setColumnWidth(6, 82)
        self.occurrences_table.setColumnWidth(7, 82)
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
        status_items = [
            ("active", "À traiter"),
            ("all", "Historique complet"),
            ("planned", "Prévue"),
            ("overdue", "En retard"),
            ("to_review", "À vérifier"),
            ("partially_matched", "Partiellement rapprochée"),
            ("auto_matched", "Rapprochée auto"),
            ("confirmed", "Rapprochée manuelle"),
            ("ignored", "Ignorée"),
            ("cancelled", "Annulée"),
        ]
        status_grid = QGridLayout()
        status_grid.setHorizontalSpacing(8)
        status_grid.setVerticalSpacing(6)
        for index, (key, label) in enumerate(status_items):
            button = QPushButton(label)
            button.setCursor(Qt.PointingHandCursor)
            button.setCheckable(True)
            button.setMinimumHeight(36)
            button.clicked.connect(lambda checked=False, status=key: self.set_status_filter(status))
            self.kpi_buttons[key] = button
            status_grid.addWidget(button, index // 2, index % 2)
        layout.addLayout(status_grid)
        layout.addStretch(1)
        return card

    def build_proposal_panel(self) -> Card:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(8)
        layout.addWidget(self.panel_title("Proposition de rapprochement", "Correspondances plausibles à valider explicitement."))
        self.proposal_feedback = QLabel("Le moteur recherche automatiquement les meilleures correspondances.")
        self.proposal_feedback.setWordWrap(True)
        self.proposal_feedback.setStyleSheet("color:#64748B;")
        layout.addWidget(self.proposal_feedback)
        self.proposals_table = QTableWidget(0, 5)
        self.proposals_table.setHorizontalHeaderLabels(["Score", "Transaction", "Prévision", "Écart", "Reste"])
        self.prepare_table(self.proposals_table)
        self.proposals_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.proposals_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.proposals_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.proposals_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.proposals_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.proposals_table.setColumnWidth(0, 64)
        self.proposals_table.setColumnWidth(3, 85)
        self.proposals_table.setColumnWidth(4, 85)
        layout.addWidget(self.proposals_table, stretch=1)
        actions = QHBoxLayout()
        validate_btn = primary_button("Valider")
        validate_btn.clicked.connect(self.confirm_selected_proposal)
        reject_btn = secondary_button("Rejeter")
        reject_btn.clicked.connect(self.reject_selected_proposal)
        actions.addWidget(validate_btn)
        actions.addWidget(reject_btn)
        actions.addStretch(1)
        layout.addLayout(actions)
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
        # Keep statuses current with one indexed UPDATE; occurrence generation is
        # intentionally reserved for the dedicated action/import workflow.
        self.service.mark_overdue(date.today())
        dataset = self.current_dataset()
        proposals = self.service.prepare_best_proposals(
            self.qdate_to_iso(self.start_date),
            self.qdate_to_iso(self.end_date),
            self.account_filter.currentData(),
            dataset["transactions"],
        )
        dataset["proposals"] = proposals
        dataset["source_counts"]["proposals_loaded"] = len(proposals)
        self.refresh_transactions(dataset)
        self.refresh_occurrences(dataset)
        self.refresh_proposals(dataset)
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
            "partially_matched": summary.get("partially_matched", 0),
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
            allocated = float(row["allocated_amount"] or 0)
            linked = "Liée" if allocated >= abs(float(row["amount"] or 0)) - 0.005 else ("Partielle" if allocated else "")
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
                {
                    "auto_matched": "Rapprochée auto",
                    "confirmed": "Rapprochée manuelle",
                    "partially_matched": "Partielle",
                }.get(row["status"], STATUS_LABELS.get(row["status"], row["status"])),
                euro(float(row["matched_amount"] or 0)) if float(row["matched_amount"] or 0) else "",
                euro(float(row["remaining_amount"] or 0)) if row["remaining_amount"] is not None else "",
            ]
            for col, value in enumerate(values, start=1):
                item = QTableWidgetItem(str(value))
                if col == 1:
                    item.setData(Qt.UserRole, int(row["id"]))
                if col in {4, 6, 7}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if col == 3:
                    item.setToolTip(str(value))
                if col == 5:
                    item.setToolTip(STATUS_LABELS.get(row["status"], row["status"]))
                self.occurrences_table.setItem(row_index, col, item)

    def refresh_proposals(self, dataset: dict | None = None) -> None:
        dataset = dataset or self.current_dataset()
        rows = dataset.get("proposals", [])
        self.proposals_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            difference = abs(float(row["tx_amount"] or 0)) - abs(float(row["expected_amount"] or 0))
            values = [
                f"{int(row['score'])}%",
                row["tx_label"] or "",
                row["expected_label"] or "",
                euro(difference),
                euro(float(row["remaining_amount"] or abs(float(row["expected_amount"] or 0)))),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.UserRole, int(row["id"]))
                if col in {0, 3, 4}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.proposals_table.setItem(row_index, col, item)
        if rows:
            best = rows[0]
            self.proposals_table.selectRow(0)
            self.proposal_feedback.setText(
                f"{len(rows)} proposition(s) calculée(s) automatiquement. "
                f"Meilleure correspondance : score {int(best['score'])}% — {best['reason']}."
            )
        else:
            self.proposal_feedback.setText("Aucune correspondance suffisamment fiable n’a été trouvée automatiquement.")

    def selected_proposal_id(self) -> int | None:
        row = self.proposals_table.currentRow()
        if row < 0:
            return None
        item = self.proposals_table.item(row, 0)
        return int(item.data(Qt.UserRole)) if item and item.data(Qt.UserRole) else None

    def confirm_selected_proposal(self) -> None:
        proposal_id = self.selected_proposal_id()
        if not proposal_id:
            QMessageBox.information(self, "Proposition", "Sélectionne une proposition à valider.")
            return
        ok, message = self.service.confirm_proposal(proposal_id)
        (QMessageBox.information if ok else QMessageBox.warning)(self, "Proposition", message)
        self.refresh()

    def reject_selected_proposal(self) -> None:
        proposal_id = self.selected_proposal_id()
        if not proposal_id:
            QMessageBox.information(self, "Proposition", "Sélectionne une proposition à rejeter.")
            return
        ok, message = self.service.reject_proposal(proposal_id)
        (QMessageBox.information if ok else QMessageBox.warning)(self, "Proposition", message)
        self.refresh()

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

    def open_rules_dialog(self) -> None:
        dialog = ReconciliationRulesDialog(self.service.rules_config(), self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            config = self.service.save_rules_config(dialog.data())
        except ValueError as exc:
            QMessageBox.warning(self, "Règles de rapprochement", str(exc))
            return
        QMessageBox.information(
            self,
            "Règles de rapprochement",
            "Règles enregistrées.\n"
            f"Rapprochée auto : score ≥ {config['auto_threshold']} %\n"
            f"À vérifier : score ≥ {config['review_threshold']} %",
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
        ok, message = self.service.cancel_match(occurrence_id)
        (QMessageBox.information if ok else QMessageBox.warning)(self, "Rapprochements", message)
        if ok:
            self.refresh()

    def ignore_occurrence(self) -> None:
        occurrence_id = self.selected_occurrence_id()
        if not occurrence_id:
            QMessageBox.information(self, "Rapprochements", "Sélectionne ou coche une occurrence.")
            return
        reason, ok = QInputDialog.getText(self, "Ignorer", "Motif d'ignorance :")
        if ok:
            changed, message = self.service.ignore_occurrence(occurrence_id, reason)
            (QMessageBox.information if changed else QMessageBox.warning)(self, "Rapprochements", message)
            if changed:
                self.refresh()

    def restore_occurrence(self) -> None:
        occurrence_id = self.selected_occurrence_id()
        if not occurrence_id:
            return
        ok, message = self.service.restore_occurrence(occurrence_id)
        (QMessageBox.information if ok else QMessageBox.warning)(self, "Rapprochements", message)
        if ok:
            self.refresh()

    def cancel_occurrence(self) -> None:
        occurrence_id = self.selected_occurrence_id()
        if not occurrence_id:
            return
        if QMessageBox.question(
            self,
            "Annuler l’occurrence",
            "Cette occurrence sera retirée de la liste À traiter mais restera dans l’historique. Continuer ?",
        ) != QMessageBox.Yes:
            return
        reason, accepted = QInputDialog.getText(self, "Annuler l’occurrence", "Motif d’annulation (facultatif) :")
        if not accepted:
            return
        ok, message = self.service.cancel_occurrence(occurrence_id, reason)
        (QMessageBox.information if ok else QMessageBox.warning)(self, "Rapprochements", message)
        if ok:
            self.refresh()

    @staticmethod
    def available_occurrence_actions(status: str, has_active_links: bool) -> list[str]:
        if status == "ignored":
            return ["restore", "info"]
        if status == "cancelled":
            return ["info"]
        actions = []
        if status in {"planned", "overdue", "to_review", "partially_matched"}:
            actions.append("match")
        if has_active_links:
            actions.append("cancel_match")
        elif status in {"planned", "overdue", "to_review"}:
            actions.extend(["ignore", "cancel_occurrence"])
        actions.append("info")
        return actions

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
        occurrence_id = self.selected_occurrence_id()
        details = self.service.occurrence_details(occurrence_id) if occurrence_id else None
        if not details:
            return
        status = str(details["occurrence"]["status"])
        has_active_links = any(bool(link["active"]) for link in details["links"])
        actions = self.available_occurrence_actions(status, has_active_links)
        menu = QMenu(self)
        action_map = {
            "match": ("Rapprocher avec la transaction cochée", self.match_checked),
            "cancel_match": ("Annuler rapprochement", self.cancel_occurrence_match),
            "ignore": ("Ignorer l’occurrence", self.ignore_occurrence),
            "restore": ("Remettre à traiter", self.restore_occurrence),
            "cancel_occurrence": ("Annuler l’occurrence", self.cancel_occurrence),
        }
        for key in actions:
            if key == "info":
                menu.addSeparator()
                menu.addAction("Afficher les informations", self.show_occurrence_info)
            else:
                label, callback = action_map[key]
                menu.addAction(label, callback)
        menu.exec(self.occurrences_table.viewport().mapToGlobal(pos))

    def show_transaction_info(self) -> None:
        tx_id = self.selected_transaction_id()
        QMessageBox.information(self, "Transaction", f"Transaction sélectionnée : {tx_id or 'aucune'}")

    def show_occurrence_info(self) -> None:
        occurrence_id = self.selected_occurrence_id()
        details = self.service.occurrence_details(occurrence_id) if occurrence_id else None
        if not details:
            QMessageBox.information(self, "Occurrence", "Aucune occurrence sélectionnée.")
            return
        occurrence = details["occurrence"]
        source = occurrence.get("recurring_name") or ("Événement ponctuel" if occurrence["source_type"] == "one_off" else occurrence["source_type"])
        lines = [
            f"Date prévue : {format_date_fr(occurrence['expected_date'])}",
            f"Compte : {occurrence.get('bank') or ''} — {occurrence.get('account_name') or 'Non affecté'}",
            f"Libellé : {occurrence.get('expected_label') or ''}",
            f"Montant prévu : {euro(float(occurrence.get('expected_amount') or 0))}",
            f"Statut : {STATUS_LABELS.get(occurrence['status'], occurrence['status'])}",
            f"Origine : {source}",
        ]
        if occurrence.get("ignored_reason"):
            lines.append(f"Motif d’ignorance : {occurrence['ignored_reason']}")
        if occurrence.get("cancelled_reason"):
            lines.append(f"Motif d’annulation : {occurrence['cancelled_reason']}")
        lines.append("")
        lines.append("Rapprochements :")
        if details["links"]:
            for link in details["links"]:
                match_label = "automatique" if link["match_type"] == "automatic" else "manuel"
                link_state = "actif" if link["active"] else "annulé"
                lines.append(
                    f"• {format_date_fr(link['tx_date'])} — {link['tx_label']} — "
                    f"{euro(float(link['tx_amount']))} ({match_label}, {link_state}, {link['created_at']})"
                )
        else:
            lines.append("• Aucun rapprochement enregistré")
        lines.append("")
        lines.append("Historique :")
        if details["history"]:
            for event in details["history"][-10:]:
                lines.append(f"• {event['created_at']} — {event['message']}")
        else:
            lines.append("• Aucun changement enregistré")
        lines.append("")
        lines.append(f"Identifiant technique : {occurrence_id}")
        QMessageBox.information(self, "Informations de l’occurrence", "\n".join(lines))
