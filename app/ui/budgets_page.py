from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.theme import COLORS, euro, euro_precise
from app.widgets import Card, KpiCard, PageHeader, primary_button, secondary_button
from app.ui.plotly_components import PlotlyFigureCard, empty_figure, go


class BudgetEditDialog(QDialog):
    def __init__(self, db: Database, month: str, category: str | None = None, planned: float = 0.0, threshold: float = 100.0, notes: str = "", parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.month = month
        self.setWindowTitle("Budget mensuel")
        self.setMinimumWidth(420)
        self.build(category, planned, threshold, notes)

    def build(self, category: str | None, planned: float, threshold: float, notes: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        title = QLabel("Définir un budget")
        title.setStyleSheet("font-size:20px; font-weight: bold;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.addItems(self.db.budget_categories_available())
        if category:
            self.category.setCurrentText(category)

        self.planned = QDoubleSpinBox()
        self.planned.setRange(0, 999999999)
        self.planned.setDecimals(2)
        self.planned.setSuffix(" €")
        self.planned.setValue(float(planned or 0))

        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(1, 200)
        self.threshold.setDecimals(0)
        self.threshold.setSuffix(" %")
        self.threshold.setValue(float(threshold or 100))

        self.notes = QLineEdit()
        self.notes.setText(notes or "")
        self.notes.setPlaceholderText("Note facultative")

        form.addRow("Catégorie", self.category)
        form.addRow("Prévu mensuel", self.planned)
        form.addRow("Seuil d’alerte", self.threshold)
        form.addRow("Note", self.notes)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Enregistrer")
        buttons.button(QDialogButtonBox.Cancel).setText("Annuler")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict:
        return {
            "category": self.category.currentText().strip(),
            "planned": float(self.planned.value()),
            "threshold": float(self.threshold.value()),
            "notes": self.notes.text().strip(),
        }


class ProgressBar(QFrame):
    def __init__(self, percent: float, status: str, parent=None) -> None:
        super().__init__(parent)
        self.percent = max(0, min(float(percent or 0), 140))
        self.status = status
        self.setMinimumHeight(16)
        self.setMaximumHeight(16)
        self.setStyleSheet("background:#E5E7EB; border-radius:8px;")

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QColor, QPainter

        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = COLORS["green"]
        if self.status == "Vigilance":
            color = COLORS["amber"]
        elif self.status in {"Dépassement", "Non budgété"}:
            color = COLORS["red"]
        width = self.width() * min(self.percent, 100) / 100
        painter.setBrush(QColor(color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, width, self.height(), 8, 8)


class BudgetsPage(QWidget):
    """Budgets V1 — monthly planned/actual budget monitoring."""

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.current_report: dict = {}
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(16)
        self.build()

    def build(self) -> None:
        self.month_filter = QComboBox()
        self.month_filter.setMinimumWidth(160)
        self.month_filter.currentIndexChanged.connect(self.refresh)

        add_btn = primary_button("+ Ajouter / modifier un budget")
        add_btn.clicked.connect(self.open_add_dialog)
        init_btn = secondary_button("Créer le mois suivant")
        init_btn.clicked.connect(self.create_next_month)

        self.layout.addWidget(PageHeader("Budgets", "Budgets mensuels, prévu/réalisé, écarts et alertes", [init_btn, add_btn]))

        filters = Card()
        filter_layout = QHBoxLayout(filters)
        filter_layout.setContentsMargins(18, 12, 18, 12)
        filter_layout.setSpacing(12)
        label = QLabel("Mois")
        label.setStyleSheet("font-weight: bold;")
        filter_layout.addWidget(label)
        filter_layout.addWidget(self.month_filter)
        filter_layout.addStretch(1)
        self.layout.addWidget(filters)

        self.kpi_grid = QGridLayout()
        self.kpi_grid.setSpacing(12)
        self.layout.addLayout(self.kpi_grid)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.overview_tab = self.make_scroll_tab()
        self.detail_tab = self.make_scroll_tab()
        self.alerts_tab = self.make_scroll_tab()
        self.tabs.addTab(self.overview_tab, "Vue d’ensemble")
        self.tabs.addTab(self.detail_tab, "Catégories")
        self.tabs.addTab(self.alerts_tab, "Alertes & règles")
        self.layout.addWidget(self.tabs, stretch=1)

        self.refresh_months()
        self.refresh()

    def make_scroll_tab(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        page = QWidget()
        page.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 8, 8)
        layout.setSpacing(14)
        scroll.setWidget(page)
        return scroll

    def tab_layout(self, tab: QScrollArea) -> QVBoxLayout:
        return tab.widget().layout()

    def clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())

    def refresh_months(self) -> None:
        current = self.month_filter.currentText()
        self.month_filter.blockSignals(True)
        self.month_filter.clear()
        self.month_filter.addItems(self.db.budget_months())
        if current:
            self.month_filter.setCurrentText(current)
        self.month_filter.blockSignals(False)

    def selected_month(self) -> str:
        return self.month_filter.currentText() or self.db.get_setting("current_month", "2026-06")

    def refresh(self) -> None:
        if not hasattr(self, "month_filter"):
            return
        month = self.selected_month()
        self.current_report = self.db.budget_report(month)
        self.refresh_kpis()
        self.populate_overview()
        self.populate_detail()
        self.populate_alerts()

    def refresh_kpis(self) -> None:
        while self.kpi_grid.count():
            item = self.kpi_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        report = self.current_report
        cards = [
            KpiCard("Budget prévu", euro(report["total_planned"]), f"Mois {report['month']}", "blue"),
            KpiCard("Réalisé", euro(report["total_realized"]), f"{report['usage_total']} % consommé", "green" if report["status"] == "OK" else "amber"),
            KpiCard("Reste disponible", euro(report["total_remaining"]), "Prévu - réalisé", "green" if report["total_remaining"] >= 0 else "red"),
            KpiCard("Dépassements", str(report["over_count"]), "Catégories dépassées", "red" if report["over_count"] else "blue"),
            KpiCard("Vigilances", str(report["warning_count"]), "Seuils ou non budgété", "amber" if report["warning_count"] else "blue"),
        ]
        for i, card in enumerate(cards):
            self.kpi_grid.addWidget(card, 0, i)

    def populate_overview(self) -> None:
        layout = self.tab_layout(self.overview_tab)
        self.clear_layout(layout)

        charts_row = QWidget()
        charts_layout = QGridLayout(charts_row)
        charts_layout.setContentsMargins(0, 0, 0, 0)
        charts_layout.setHorizontalSpacing(14)
        charts_layout.setVerticalSpacing(14)

        charts_layout.addWidget(
            PlotlyFigureCard(
                "Budget prévu / réalisé",
                "Vue compacte horizontale pour tenir sur la page.",
                self.plotly_budget_grouped_bar,
                min_height=315,
                chart_height=230,
            ),
            0,
            0,
        )
        charts_layout.addWidget(
            PlotlyFigureCard(
                "Taux d’utilisation",
                "Catégories les plus consommées.",
                self.plotly_budget_usage_bar,
                min_height=315,
                chart_height=230,
            ),
            0,
            1,
        )
        charts_layout.setColumnStretch(0, 1)
        charts_layout.setColumnStretch(1, 1)
        layout.addWidget(charts_row)

        summary = Card()
        s_layout = QVBoxLayout(summary)
        s_layout.setContentsMargins(18, 12, 18, 12)
        s_layout.setSpacing(8)
        status = self.current_report["status"]
        color = "#DCFCE7" if status == "OK" else "#FEF3C7" if status == "Vigilance" else "#FEE2E2"
        status_label = QLabel(
            f"<b>Statut budget : {status}</b> — "
            f"Prévu : {euro_precise(self.current_report['total_planned'])} — "
            f"Réalisé : {euro_precise(self.current_report['total_realized'])} — "
            f"Reste : {euro_precise(self.current_report['total_remaining'])}"
        )
        status_label.setWordWrap(True)
        status_label.setStyleSheet(f"background:{color}; border-radius:12px; padding:10px; color:#0F172A;")
        s_layout.addWidget(status_label)
        layout.addWidget(summary)
        layout.addStretch(1)

    def populate_detail(self) -> None:
        layout = self.tab_layout(self.detail_tab)
        self.clear_layout(layout)

        table = QTableWidget(0, 7)
        table.setHorizontalHeaderLabels(["Catégorie", "Prévu", "Réalisé", "Reste", "Utilisation", "Statut", "Action"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setFocusPolicy(Qt.NoFocus)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setMinimumHeight(460)
        table.horizontalHeader().setStretchLastSection(True)

        rows = self.current_report["rows"]
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [
                row["category"],
                euro_precise(row["planned"]),
                euro_precise(row["actual"]),
                euro_precise(row["remaining"]),
                f"{row['usage']:.1f} %",
                row["status"],
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if c in {1, 2, 3, 4}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if row["status"] == "Dépassement" and c in {3, 5}:
                    item.setForeground(Qt.red)
                table.setItem(r, c, item)

            btn = QPushButton("Modifier")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, data=row: self.open_edit_dialog(data))
            table.setCellWidget(r, 6, btn)

        table.resizeColumnsToContents()
        table.setColumnWidth(0, 220)
        layout.addWidget(table)
        layout.addStretch(1)

    def plotly_budget_grouped_bar(self):
        if go is None:
            return None
        rows = [
            row for row in self.current_report.get("rows", [])
            if float(row.get("planned", 0) or 0) > 0 or float(row.get("actual", 0) or 0) > 0
        ]
        if not rows:
            return empty_figure("Aucun budget ou réalisé à afficher.")

        rows = sorted(
            rows,
            key=lambda row: max(float(row.get("planned", 0) or 0), float(row.get("actual", 0) or 0)),
            reverse=True,
        )[:7]
        categories = [row["category"] for row in rows]
        planned = [float(row.get("planned", 0) or 0) for row in rows]
        actual = [float(row.get("actual", 0) or 0) for row in rows]

        fig = go.Figure()
        fig.add_trace(go.Bar(y=categories, x=planned, orientation="h", name="Prévu", hovertemplate="%{y}<br>Prévu : %{x:,.2f} €<extra></extra>"))
        fig.add_trace(go.Bar(y=categories, x=actual, orientation="h", name="Réalisé", hovertemplate="%{y}<br>Réalisé : %{x:,.2f} €<extra></extra>"))
        fig.update_layout(
            barmode="group",
            yaxis=dict(autorange="reversed"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        )
        fig.update_xaxes(ticksuffix=" €")
        return fig

    def plotly_budget_usage_bar(self):
        if go is None:
            return None
        rows = [
            row for row in self.current_report.get("rows", [])
            if float(row.get("planned", 0) or 0) > 0 or float(row.get("actual", 0) or 0) > 0
        ]
        if not rows:
            return empty_figure("Aucun taux d’utilisation à afficher.")

        rows = sorted(rows, key=lambda row: float(row.get("usage", 0) or 0), reverse=True)[:7]
        categories = [row["category"] for row in rows]
        usage = [round(float(row.get("usage", 0) or 0), 1) for row in rows]

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=usage,
                y=categories,
                orientation="h",
                name="Utilisation",
                hovertemplate="%{y}<br>Utilisation : %{x:.1f} %<extra></extra>",
            )
        )
        fig.add_vline(x=100, line_width=2, line_dash="dash")
        fig.update_layout(yaxis=dict(autorange="reversed"), showlegend=False)
        fig.update_xaxes(ticksuffix=" %")
        return fig

    def populate_alerts(self) -> None:
        layout = self.tab_layout(self.alerts_tab)
        self.clear_layout(layout)

        alerts = [row for row in self.current_report["rows"] if row["status"] != "OK"]
        card = Card()
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(18, 16, 18, 16)
        c_layout.setSpacing(10)

        title = QLabel("Alertes budget")
        title.setStyleSheet("font-size:18px; font-weight: bold;")
        c_layout.addWidget(title)

        if not alerts:
            ok = QLabel("Aucune alerte budget sur la période.")
            ok.setStyleSheet("background:#DCFCE7; border-radius:12px; padding:12px; font-weight: bold;")
            c_layout.addWidget(ok)
        else:
            for row in alerts:
                msg = QLabel(
                    f"<b>{row['category']} — {row['status']}</b><br>"
                    f"Prévu : {euro_precise(row['planned'])} — Réalisé : {euro_precise(row['actual'])} — "
                    f"Écart : {euro_precise(row['remaining'])}"
                )
                msg.setWordWrap(True)
                bg = "#FEE2E2" if row["status"] in {"Dépassement", "Non budgété"} else "#FEF3C7"
                msg.setStyleSheet(f"background:{bg}; border-radius:12px; padding:12px;")
                c_layout.addWidget(msg)

        rules = QLabel(
            "<b>Règles métier Budgets V1</b><br>"
            "• Réalisé = transactions débitrices du mois par catégorie.<br>"
            "• Les transferts internes et investissements sont exclus des dépenses courantes.<br>"
            "• Dépassement si réalisé > prévu.<br>"
            "• Vigilance si le seuil d’alerte de la catégorie est atteint.<br>"
            "• Non budgété si une dépense existe sans budget prévu."
        )
        rules.setWordWrap(True)
        rules.setStyleSheet("color:#475569; background:#F8FAFC; border-radius:12px; padding:12px;")
        c_layout.addWidget(rules)

        layout.addWidget(card)
        layout.addStretch(1)

    def open_add_dialog(self) -> None:
        dialog = BudgetEditDialog(self.db, self.selected_month(), parent=self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.values()
            if not data["category"]:
                QMessageBox.warning(self, "Catégorie manquante", "La catégorie est obligatoire.")
                return
            self.db.upsert_budget(self.selected_month(), data["category"], data["planned"], data["threshold"], data["notes"])
            self.refresh_months()
            self.refresh()

    def open_edit_dialog(self, row: dict) -> None:
        dialog = BudgetEditDialog(
            self.db,
            self.selected_month(),
            category=row["category"],
            planned=row["planned"],
            threshold=row["alert_threshold"],
            notes=row.get("notes", ""),
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            data = dialog.values()
            self.db.upsert_budget(self.selected_month(), data["category"], data["planned"], data["threshold"], data["notes"])
            self.refresh()

    def create_next_month(self) -> None:
        current = self.selected_month()
        year, month = [int(part) for part in current.split("-")]
        month += 1
        if month > 12:
            year += 1
            month = 1
        next_month = f"{year:04d}-{month:02d}"
        with self.db.connect() as conn:
            self.db.ensure_budget_month(conn, next_month)
        self.refresh_months()
        self.month_filter.setCurrentText(next_month)
        self.refresh()
        QMessageBox.information(self, "Budget créé", f"Le mois {next_month} est prêt.")
