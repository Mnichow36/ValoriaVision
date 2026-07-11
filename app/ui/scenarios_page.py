from __future__ import annotations

from datetime import date, datetime
from calendar import monthrange

from PySide6.QtCore import QDate, QPoint, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QMenu,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.services.scenario_service import ScenarioService
from app.services.scenario_event_service import ScenarioEventService
from app.services.scenario_simulation_service import ScenarioSimulationService
from app.theme import euro
from app.ui.plotly_components import PlotlyFigureCard, empty_figure, go
from app.widgets import Card, KpiCard, PageHeader, primary_button, secondary_button


class ScenarioDialog(QDialog):
    def __init__(self, parent=None, row=None) -> None:
        super().__init__(parent)
        self.row = row
        self.setWindowTitle("Modifier le scénario" if row else "Nouveau scénario")
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name = QLineEdit()
        self.name.setPlaceholderText("Ex. Achat maison, Travaux, Baisse de revenus")
        self.description = QTextEdit()
        self.description.setMaximumHeight(90)
        self.scenario_type = QComboBox()
        self.scenario_type.addItems(ScenarioService.TYPES)
        self.start_date = QDateEdit(QDate.currentDate())
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("dd/MM/yyyy")
        self.horizon_months = QSpinBox()
        self.horizon_months.setRange(1, 600)
        self.horizon_months.setValue(12)
        self.currency = QComboBox()
        self.currency.addItems(["EUR"])

        form.addRow("Nom", self.name)
        form.addRow("Description", self.description)
        form.addRow("Type", self.scenario_type)
        form.addRow("Date de début", self.start_date)
        form.addRow("Horizon", self.horizon_months)
        form.addRow("Devise", self.currency)
        layout.addLayout(form)

        if row:
            self.populate(row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def populate(self, row) -> None:
        self.name.setText(row["name"] or "")
        self.description.setPlainText(row["description"] or "")
        self.scenario_type.setCurrentText(row["scenario_type"] or "Projet libre")
        try:
            y, m, d = [int(v) for v in (row["start_date"] or date.today().isoformat()).split("-")]
            self.start_date.setDate(QDate(y, m, d))
        except Exception:
            pass
        self.horizon_months.setValue(int(row["horizon_months"] or 12))
        self.currency.setCurrentText(row["currency_code"] or "EUR")
        if row["is_reference"]:
            self.name.setEnabled(False)
            self.scenario_type.setEnabled(False)

    def data(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "description": self.description.toPlainText().strip(),
            "scenario_type": self.scenario_type.currentText(),
            "start_date": self.start_date.date().toString("yyyy-MM-dd"),
            "horizon_months": int(self.horizon_months.value()),
            "currency_code": self.currency.currentText(),
            "is_active": True,
        }


class ScenarioEventDialog(QDialog):
    def __init__(self, db: Database, parent=None, row=None) -> None:
        super().__init__(parent)
        self.db = db
        self.row = row
        self.setWindowTitle("Modifier l’événement" if row else "Ajouter un événement")
        self.resize(560, 470)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.event_type = QComboBox()
        for key, label in ScenarioEventService.EVENT_TYPES.items():
            self.event_type.addItem(label, key)

        self.label = QLineEdit()
        self.label.setPlaceholderText("Ex. Frais de notaire, Mensualité prêt, Revenu locatif")
        self.description = QTextEdit()
        self.description.setMaximumHeight(70)
        self.event_date = QDateEdit(QDate.currentDate())
        self.event_date.setCalendarPopup(True)
        self.event_date.setDisplayFormat("dd/MM/yyyy")
        self.amount = QDoubleSpinBox()
        self.amount.setRange(0, 100000000)
        self.amount.setDecimals(2)
        self.amount.setSuffix(" €")
        self.frequency = QComboBox()
        for key, label in ScenarioEventService.FREQUENCIES.items():
            self.frequency.addItem(label, key)
        self.duration = QSpinBox()
        self.duration.setRange(0, 600)
        self.duration.setSuffix(" mois")
        self.account = QComboBox()
        self.account.addItem("Aucun compte spécifique", None)
        for acc in self.db.list_accounts():
            self.account.addItem(f"{acc['name']} — {acc['bank']}", acc["id"])

        form.addRow("Type", self.event_type)
        form.addRow("Libellé", self.label)
        form.addRow("Description", self.description)
        form.addRow("Date de début", self.event_date)
        form.addRow("Montant", self.amount)
        form.addRow("Fréquence", self.frequency)
        form.addRow("Durée", self.duration)
        form.addRow("Compte concerné", self.account)
        layout.addLayout(form)

        hint = QLabel("Un scénario reste une simulation : aucun événement ne crée de transaction réelle.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748B;")
        layout.addWidget(hint)

        if row:
            self.populate(row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def populate(self, row) -> None:
        index = self.event_type.findData(row["event_type"])
        self.event_type.setCurrentIndex(index if index >= 0 else 0)
        self.label.setText(row["label"] or "")
        self.description.setPlainText(row["description"] or "")
        try:
            y, m, d = [int(v) for v in (row["event_date"] or date.today().isoformat()).split("-")]
            self.event_date.setDate(QDate(y, m, d))
        except Exception:
            pass
        self.amount.setValue(abs(float(row["amount"] or 0)))
        index = self.frequency.findData(row["frequency"] or "once")
        self.frequency.setCurrentIndex(index if index >= 0 else 0)
        self.duration.setValue(int(row["duration_months"] or 0))
        if row["account_id"]:
            index = self.account.findData(row["account_id"])
            if index >= 0:
                self.account.setCurrentIndex(index)

    def data(self) -> dict:
        return {
            "event_type": self.event_type.currentData(),
            "label": self.label.text().strip(),
            "description": self.description.toPlainText().strip(),
            "event_date": self.event_date.date().toString("yyyy-MM-dd"),
            "amount": float(self.amount.value()),
            "currency_code": "EUR",
            "frequency": self.frequency.currentData(),
            "duration_months": int(self.duration.value()) or None,
            "account_id": self.account.currentData(),
            "is_active": True,
        }


class LoanRepaymentScheduleDialog(QDialog):
    def __init__(self, rows: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Échéancier / fréquences de remboursement")
        self.resize(720, 460)

        layout = QVBoxLayout(self)
        title = QLabel("Fréquences de remboursement")
        title.setStyleSheet("font-size:18px; font-weight: bold;")
        layout.addWidget(title)

        info = QLabel(
            "Cette vue affiche les échéances simulées à partir des événements de remboursement du scénario. "
            "Elle ne modifie aucune donnée réelle."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#64748B;")
        layout.addWidget(info)

        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(["#", "Date", "Libellé", "Fréquence", "Montant"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.setRowCount(len(rows))

        total = 0.0
        for r, row in enumerate(rows):
            total += float(row.get("amount", 0) or 0)
            values = [
                str(row.get("index", r + 1)),
                row.get("date", ""),
                row.get("label", ""),
                row.get("frequency", ""),
                euro(float(row.get("amount", 0) or 0)),
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if c in {0, 4}:
                    item.setTextAlignment(Qt.AlignCenter)
                table.setItem(r, c, item)

        layout.addWidget(table, stretch=1)

        total_label = QLabel(f"Total simulé : {euro(total)} — Nombre d’échéances : {len(rows)}")
        total_label.setStyleSheet("font-weight: bold; color:#0F172A;")
        layout.addWidget(total_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)



class ScenariosPage(QWidget):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.scenario_service = ScenarioService(db)
        self.event_service = ScenarioEventService(db)
        self.simulation_service = ScenarioSimulationService(db)
        self.current_scenario_id: int | None = None

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(14)
        self.build()

    def build(self) -> None:
        actions = [
            primary_button("+ Nouveau scénario"),
            secondary_button("Modifier"),
            secondary_button("Dupliquer"),
            secondary_button("Supprimer"),
            primary_button("+ Ajouter un événement"),
        ]
        actions[0].clicked.connect(self.add_scenario)
        actions[1].clicked.connect(self.edit_scenario)
        actions[2].clicked.connect(self.duplicate_scenario)
        actions[3].clicked.connect(self.delete_scenario)
        actions[4].clicked.connect(self.add_event)

        self.layout.addWidget(PageHeader("Scénarios", "Simulations financières personnalisées sans modifier les données réelles", actions))

        splitter = QSplitter(Qt.Vertical)

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(14)

        self.scenarios_table = QTableWidget(0, 7)
        self.scenarios_table.setHorizontalHeaderLabels(["Nom", "Type", "Début", "Horizon", "Événements", "Statut", "Référence"])
        self.scenarios_table.verticalHeader().setVisible(False)
        self.scenarios_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.scenarios_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.scenarios_table.horizontalHeader().setStretchLastSection(True)
        self.scenarios_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.scenarios_table.itemSelectionChanged.connect(self.on_scenario_selection_changed)
        top_layout.addWidget(self.scenarios_table, stretch=2)

        self.events_table = QTableWidget(0, 8)
        self.events_table.setHorizontalHeaderLabels(["Date", "Nature", "Type", "Libellé", "Montant", "Fréquence", "Durée", "Actions"])
        self.events_table.verticalHeader().setVisible(False)
        self.events_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.events_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.events_table.horizontalHeader().setStretchLastSection(True)
        self.events_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.events_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.events_table.customContextMenuRequested.connect(self.open_event_context_menu)
        top_layout.addWidget(self.events_table, stretch=3)

        splitter.addWidget(top)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(12)

        self.kpi_grid = QGridLayout()
        self.kpi_grid.setSpacing(12)
        bottom_layout.addLayout(self.kpi_grid)

        self.chart_holder = QVBoxLayout()
        bottom_layout.addLayout(self.chart_holder)

        splitter.addWidget(bottom)
        splitter.setSizes([360, 420])
        self.layout.addWidget(splitter, stretch=1)

        self.refresh()

    def refresh(self) -> None:
        self.scenario_service.ensure_reference_scenario()
        scenarios = self.scenario_service.list_scenarios()
        self.scenarios_table.blockSignals(True)
        self.scenarios_table.setRowCount(len(scenarios))
        for r, row in enumerate(scenarios):
            values = [
                row["name"],
                row["scenario_type"],
                row["start_date"],
                f"{row['horizon_months'] or 12} mois",
                str(row["event_count"]),
                "Actif" if row["is_active"] else "Inactif",
                "Oui" if row["is_reference"] else "Non",
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if c in {3, 4, 5, 6}:
                    item.setTextAlignment(Qt.AlignCenter)
                if c == 0:
                    item.setData(Qt.UserRole, int(row["id"]))
                self.scenarios_table.setItem(r, c, item)
        self.scenarios_table.blockSignals(False)
        if self.current_scenario_id:
            self.select_scenario(self.current_scenario_id)
        elif scenarios:
            self.scenarios_table.selectRow(0)
        self.refresh_events_and_results()

    def selected_scenario_id(self) -> int | None:
        row = self.scenarios_table.currentRow()
        if row < 0:
            return None
        item = self.scenarios_table.item(row, 0)
        return int(item.data(Qt.UserRole)) if item else None

    def selected_event_id(self) -> int | None:
        row = self.events_table.currentRow()
        if row < 0:
            return None
        item = self.events_table.item(row, 0)
        return int(item.data(Qt.UserRole)) if item else None

    def select_scenario(self, scenario_id: int) -> None:
        for row in range(self.scenarios_table.rowCount()):
            item = self.scenarios_table.item(row, 0)
            if item and int(item.data(Qt.UserRole)) == int(scenario_id):
                self.scenarios_table.selectRow(row)
                return

    def on_scenario_selection_changed(self) -> None:
        self.current_scenario_id = self.selected_scenario_id()
        self.refresh_events_and_results()

    def refresh_events_and_results(self) -> None:
        scenario_id = self.selected_scenario_id()
        if not scenario_id:
            return
        self.current_scenario_id = scenario_id
        events = self.event_service.list_events(scenario_id)
        self.events_table.setRowCount(len(events))
        for r, row in enumerate(events):
            values = [
                row["event_date"],
                ScenarioEventService.event_nature(row["event_type"]),
                ScenarioEventService.EVENT_TYPES.get(row["event_type"], row["event_type"]),
                row["label"],
                euro(float(row["amount"] or 0)),
                ScenarioEventService.FREQUENCIES.get(row["frequency"], row["frequency"]),
                f"{row['duration_months']} mois" if row["duration_months"] else "",
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if c == 0:
                    item.setData(Qt.UserRole, int(row["id"]))
                if c in {4, 6}:
                    item.setTextAlignment(Qt.AlignCenter)
                self.events_table.setItem(r, c, item)
            action = QWidget()
            action_layout = QHBoxLayout(action)
            action_layout.setContentsMargins(0, 0, 0, 0)
            edit_btn = QPushButton("Modifier")
            delete_btn = QPushButton("Supprimer")
            edit_btn.clicked.connect(lambda checked=False, event_id=int(row["id"]): self.edit_event(event_id))
            delete_btn.clicked.connect(lambda checked=False, event_id=int(row["id"]): self.delete_event(event_id))
            action_layout.addWidget(edit_btn)
            action_layout.addWidget(delete_btn)
            self.events_table.setCellWidget(r, 7, action)

        self.refresh_simulation()

    def refresh_simulation(self) -> None:
        scenario_id = self.selected_scenario_id()
        if not scenario_id:
            return
        scenario = self.scenario_service.get_scenario(scenario_id)
        start = self.parse_date(scenario["start_date"])
        horizon = int(scenario["horizon_months"] or 12)
        end = self.add_months(start, horizon)
        data = self.simulation_service.simulate_scenario(scenario_id, start, end, granularity="month")
        summary = data["summary"]

        self.clear_layout(self.kpi_grid)
        cards = [
            KpiCard("Trésorerie finale simulée", euro(summary["closing_balance"]), "Solde après scénario", "blue"),
            KpiCard("Point bas simulé", euro(summary["lowest_balance"]), "Minimum de la période", "red" if summary["lowest_balance"] < 5000 else "purple"),
            KpiCard("Écart vs référence", euro(summary.get("delta_vs_reference", 0.0)), "Impact net de trésorerie", "green" if summary.get("delta_vs_reference", 0.0) >= 0 else "red"),
            KpiCard("Impact mensuel moyen", euro(summary["monthly_impact"]), "Sur l’horizon", "blue"),
            KpiCard("Impact patrimoine net", euro(summary.get("net_worth_impact", 0.0)), "Actifs/passifs simulés", "purple"),
        ]
        for col, card in enumerate(cards):
            self.kpi_grid.addWidget(card, 0, col)

        self.clear_layout(self.chart_holder)
        self.chart_holder.addWidget(
            PlotlyFigureCard(
                "Simulation du scénario",
                "Crédits et débits en colonnes, solde simulé en courbe.",
                lambda data=data: self.plotly_simulation_chart(data),
                min_height=360,
                chart_height=270,
            )
        )

    def plotly_simulation_chart(self, data: dict):
        if go is None:
            return None
        if not data.get("points"):
            return empty_figure("Aucune donnée de simulation.")
        labels = data["labels"]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=labels, y=data["credits"], name="Crédits", hovertemplate="%{x}<br>Crédits : %{y:,.2f} €<extra></extra>"))
        fig.add_trace(go.Bar(x=labels, y=data["debits"], name="Débits", hovertemplate="%{x}<br>Débits : %{y:,.2f} €<extra></extra>"))
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=data["balances"],
                name="Solde simulé",
                mode="lines+markers",
                yaxis="y2",
                line=dict(width=4, shape="spline"),
                hovertemplate="%{x}<br>Solde : %{y:,.2f} €<extra></extra>",
            )
        )
        reference = data.get("reference", {})
        if reference.get("balances"):
            fig.add_trace(
                go.Scatter(
                    x=labels,
                    y=reference["balances"],
                    name="Solde référence",
                    mode="lines",
                    yaxis="y2",
                    line=dict(width=2, dash="dash"),
                    hovertemplate="%{x}<br>Référence : %{y:,.2f} €<extra></extra>",
                )
            )
        fig.update_layout(
            barmode="group",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            yaxis=dict(title="Flux", ticksuffix=" €"),
            yaxis2=dict(title="Solde", overlaying="y", side="right", ticksuffix=" €"),
            margin=dict(l=40, r=56, t=10, b=34),
        )
        return fig

    def open_event_context_menu(self, pos: QPoint) -> None:
        item = self.events_table.itemAt(pos)
        if not item:
            return
        self.events_table.selectRow(item.row())
        event_id = self.selected_event_id()
        if not event_id:
            return
        row = self.event_service.get_event(event_id)
        if not row:
            return

        menu = QMenu(self.events_table)
        edit_action = menu.addAction("Modifier l’événement")
        delete_action = menu.addAction("Supprimer l’événement")
        menu.addSeparator()

        schedule_action = menu.addAction("Voir les fréquences de remboursement")
        schedule_action.setEnabled(row["event_type"] in ScenarioEventService.LOAN_CONTEXT_TYPES)

        chosen = menu.exec(self.events_table.viewport().mapToGlobal(pos))
        if chosen == edit_action:
            self.edit_event(event_id)
        elif chosen == delete_action:
            self.delete_event(event_id)
        elif chosen == schedule_action:
            self.show_repayment_schedule(event_id)

    def show_repayment_schedule(self, event_id: int) -> None:
        rows = self.event_service.loan_repayment_schedule(event_id)
        if not rows:
            QMessageBox.information(
                self,
                "Échéancier",
                "Aucune échéance de remboursement n’est définie pour cet emprunt. "
                "Ajoutez un événement de type Mensualité d’emprunt ou Remboursement de passif.",
            )
            return
        dialog = LoanRepaymentScheduleDialog(rows, self)
        dialog.exec()

    def add_scenario(self) -> None:
        dialog = ScenarioDialog(self)
        if dialog.exec() == QDialog.Accepted:
            try:
                scenario_id = self.scenario_service.create_scenario(dialog.data())
                self.current_scenario_id = scenario_id
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "Scénario", str(exc))

    def edit_scenario(self) -> None:
        scenario_id = self.selected_scenario_id()
        if not scenario_id:
            return
        row = self.scenario_service.get_scenario(scenario_id)
        dialog = ScenarioDialog(self, row=row)
        if dialog.exec() == QDialog.Accepted:
            try:
                self.scenario_service.update_scenario(scenario_id, dialog.data())
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "Scénario", str(exc))

    def duplicate_scenario(self) -> None:
        scenario_id = self.selected_scenario_id()
        if not scenario_id:
            return
        try:
            new_id = self.scenario_service.duplicate_scenario(scenario_id)
            self.current_scenario_id = new_id
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Scénario", str(exc))

    def delete_scenario(self) -> None:
        scenario_id = self.selected_scenario_id()
        if not scenario_id:
            return
        row = self.scenario_service.get_scenario(scenario_id)
        if row["is_reference"]:
            QMessageBox.information(self, "Scénario de référence", "Le scénario de référence ne peut pas être supprimé.")
            return
        if QMessageBox.question(self, "Supprimer le scénario", f"Supprimer le scénario « {row['name']} » ?") != QMessageBox.Yes:
            return
        try:
            self.scenario_service.delete_scenario(scenario_id)
            self.current_scenario_id = None
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Scénario", str(exc))

    def add_event(self) -> None:
        scenario_id = self.selected_scenario_id()
        if not scenario_id:
            return
        row = self.scenario_service.get_scenario(scenario_id)
        if row["is_reference"]:
            QMessageBox.information(self, "Scénario de référence", "Ajoutez les hypothèses sur un scénario personnalisé, pas sur la référence.")
            return
        dialog = ScenarioEventDialog(self.db, self)
        if dialog.exec() == QDialog.Accepted:
            try:
                self.event_service.add_event(scenario_id, dialog.data())
                self.refresh_events_and_results()
            except Exception as exc:
                QMessageBox.critical(self, "Événement", str(exc))

    def edit_event(self, event_id: int | None = None) -> None:
        event_id = event_id or self.selected_event_id()
        if not event_id:
            return
        row = self.event_service.get_event(event_id)
        dialog = ScenarioEventDialog(self.db, self, row=row)
        if dialog.exec() == QDialog.Accepted:
            try:
                self.event_service.update_event(event_id, dialog.data())
                self.refresh_events_and_results()
            except Exception as exc:
                QMessageBox.critical(self, "Événement", str(exc))

    def delete_event(self, event_id: int | None = None) -> None:
        event_id = event_id or self.selected_event_id()
        if not event_id:
            return
        row = self.event_service.get_event(event_id)
        if QMessageBox.question(self, "Supprimer l’événement", f"Supprimer l’événement « {row['label']} » ?") != QMessageBox.Yes:
            return
        self.event_service.delete_event(event_id)
        self.refresh_events_and_results()

    @staticmethod
    def parse_date(value: str) -> date:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except Exception:
            return date.today()

    @staticmethod
    def add_months(day: date, months: int) -> date:
        month = day.month - 1 + months
        year = day.year + month // 12
        month = month % 12 + 1
        last = monthrange(year, month)[1]
        return date(year, month, min(day.day, last))

    def clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
