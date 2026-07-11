from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.theme import euro
from app.widgets import Card, KpiCard, PageHeader, primary_button, secondary_button
from app.ui.plotly_components import PlotlyFigureCard, empty_figure, go


class AssetsPage(QWidget):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(14)
        self.build()

    def build(self) -> None:
        add_btn = primary_button("+ Ajouter un élément")
        add_btn.clicked.connect(self.open_add_dialog)
        self.layout.addWidget(PageHeader("Patrimoine", "Vue globale, actifs, passifs, évolution et synthèses dédiées", [add_btn]))

        self.kpi_grid = QGridLayout()
        self.kpi_grid.setSpacing(12)
        self.layout.addLayout(self.kpi_grid)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.build_global_tab(), "Vue globale")
        self.tabs.addTab(self.build_table_tab("Actifs"), "Actifs")
        self.tabs.addTab(self.build_table_tab("Passifs"), "Passifs")
        self.tabs.addTab(self.build_evolution_tab(), "Évolution")
        self.tabs.addTab(self.build_summary_tab(), "Synthèse intelligente")
        self.tabs.addTab(self.build_top_assets_tab(), "Top actifs")
        self.layout.addWidget(self.tabs, stretch=1)
        self.refresh()

    def build_global_tab(self) -> QWidget:
        """Global view kept intentionally light.

        V0.4.11 moves Synthèse intelligente and Top actifs into dedicated tabs
        so the user can access them without scrolling through the global page.
        """
        page = QWidget()
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 14, 0, 0)
        layout.setSpacing(16)

        self.donut_holder = QVBoxLayout()
        donut_container = QWidget()
        donut_container.setLayout(self.donut_holder)
        layout.addWidget(donut_container, 0, 0)

        self.evolution_holder = QVBoxLayout()
        evolution_container = QWidget()
        evolution_container.setLayout(self.evolution_holder)
        layout.addWidget(evolution_container, 0, 1)

        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setRowStretch(0, 1)
        return page

    def build_summary_tab(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 14, 8, 0)
        layout.setSpacing(16)

        self.summary_panel = self.build_summary_panel()
        layout.addWidget(self.summary_panel)
        layout.addStretch(1)
        scroll.setWidget(content)
        return scroll

    def build_top_assets_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 14, 0, 0)
        layout.setSpacing(16)

        self.top_assets_card = self.build_top_assets_panel()
        layout.addWidget(self.top_assets_card)

        self.top_assets_table = self.create_table()
        self.top_assets_table.setMinimumHeight(360)
        self.top_assets_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.top_assets_table, stretch=1)
        return page

    def build_right_column(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)
        content_layout.setSpacing(16)

        self.summary_panel = self.build_summary_panel()
        content_layout.addWidget(self.summary_panel)
        content_layout.addWidget(self.build_top_assets_panel())
        content_layout.addStretch(1)

        scroll.setWidget(content)
        return scroll

    def build_top_assets_panel(self) -> Card:
        self.top_assets_card = Card()
        self.top_assets_card.setMinimumHeight(180)
        self.top_assets_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout = QVBoxLayout(self.top_assets_card)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)

        title = QLabel("Top actifs")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color:#0F172A;")
        layout.addWidget(title)

        self.top_assets_content = QLabel()
        self.top_assets_content.setWordWrap(True)
        self.top_assets_content.setStyleSheet("color:#64748B; font-size:13px;")
        self.top_assets_content.setMinimumHeight(52)
        layout.addWidget(self.top_assets_content)

        detail_btn = secondary_button("Voir le détail du patrimoine")
        detail_btn.setMinimumHeight(42)
        layout.addWidget(detail_btn, alignment=Qt.AlignRight)
        return self.top_assets_card

    def build_table_tab(self, mode: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 14, 0, 0)
        table = self.create_table()
        if mode == "Actifs":
            self.assets_table = table
        else:
            self.passifs_table = table
        layout.addWidget(table)
        return page

    def build_evolution_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 14, 0, 0)
        self.evolution_tab_holder = QVBoxLayout()
        layout.addLayout(self.evolution_tab_holder)
        return page

    def build_summary_panel(self) -> Card:
        self.summary_card = Card()
        self.summary_card.setMinimumHeight(280)
        self.summary_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.summary_layout = QVBoxLayout(self.summary_card)
        self.summary_layout.setContentsMargins(24, 22, 24, 22)
        self.summary_layout.setSpacing(16)

        title = QLabel("Synthèse intelligente")
        title.setStyleSheet("font-size: 22px; font-weight: bold; color:#0F172A;")
        self.summary_layout.addWidget(title)

        subtitle = QLabel("Lecture rapide de votre situation patrimoniale")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#64748B; font-size:13px;")
        self.summary_layout.addWidget(subtitle)

        # Les insights sont affichés en pleine largeur, sur une ligne de cartes.
        # Chaque carte peut retourner à la ligne sans être tronquée.
        self.insight_container = QHBoxLayout()
        self.insight_container.setSpacing(14)
        self.summary_layout.addLayout(self.insight_container)

        history_btn = secondary_button("Voir historique")
        history_btn.setMinimumHeight(42)
        self.summary_layout.addWidget(history_btn, alignment=Qt.AlignRight)
        return self.summary_card

    def make_insight(self, icon: str, title: str, text: str, color: str) -> QWidget:
        row = QFrame()
        row.setObjectName("InsightCard")
        row.setMinimumHeight(112)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        row.setStyleSheet(
            "QFrame#InsightCard {"
            "background:#F8FAFC; border:1px solid #E5E7EB; border-radius:16px;"
            "}"
        )
        layout = QHBoxLayout(row)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        badge = QLabel(icon)
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedSize(36, 36)
        badge.setStyleSheet(f"background:{color}; color:white; border-radius:18px; font-weight: bold; font-size:15px;")

        texts = QVBoxLayout()
        texts.setSpacing(6)
        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-weight: bold; color:#0F172A; font-size:14px; border:none; background:transparent;")

        detail_label = QLabel(text)
        detail_label.setWordWrap(True)
        detail_label.setStyleSheet("color:#64748B; font-size:13px; border:none; background:transparent;")

        texts.addWidget(title_label)
        texts.addWidget(detail_label)
        texts.addStretch(1)
        layout.addWidget(badge, alignment=Qt.AlignTop)
        layout.addLayout(texts, stretch=1)
        return row

    def create_table(self) -> QTableWidget:
        table = QTableWidget(0, 7)
        table.setHorizontalHeaderLabels(["Élément", "Catégorie", "Type", "Valeur", "Poids", "Variation", "Statut"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setFocusPolicy(Qt.NoFocus)
        table.setShowGrid(False)
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        table.verticalHeader().setDefaultSectionSize(42)
        table.setColumnWidth(1, 170)
        table.setColumnWidth(2, 130)
        table.setColumnWidth(3, 120)
        table.setStyleSheet(
            "QTableWidget {"
            "background:#FFFFFF;"
            "alternate-background-color:#F8FAFC;"
            "gridline-color:#E5E7EB;"
            "selection-background-color:#EAF1FF;"
            "selection-color:#0F172A;"
            "border:none;"
            "}"
            "QTableWidget::item {"
            "border:none;"
            "padding:8px 6px;"
            "}"
            "QTableWidget::item:selected {"
            "background:#EAF1FF;"
            "color:#0F172A;"
            "border:none;"
            "outline:none;"
            "}"
            "QTableWidget::item:hover {"
            "background:#F8FAFC;"
            "border:none;"
            "outline:none;"
            "}"
            "QTableWidget::item:focus {"
            "border:none;"
            "outline:none;"
            "}"
            "QHeaderView::section {"
            "background:#F8FAFC;"
            "color:#64748B;"
            "font-weight: bold;"
            "border:none;"
            "border-bottom:1px solid #E5E7EB;"
            "padding:10px 8px;"
            "}"
        )
        return table

    def refresh(self) -> None:
        self.clear_layout(self.kpi_grid)
        summary = self.db.asset_summary()
        active = sum(v for v in summary.values() if v > 0)
        passive = abs(sum(v for v in summary.values() if v < 0))
        net = active - passive
        liquidites = sum(v for k, v in summary.items() if "Liquid" in k or "Compte" in k)
        cards = [
            KpiCard("Patrimoine net", euro(net), "+ 6,3 % vs mois dernier", "blue"),
            KpiCard("Actifs", euro(active), "Biens + placements", "green"),
            KpiCard("Passifs", euro(passive), "Crédits et dettes", "red"),
            KpiCard("Liquidités", euro(liquidites), "Cash mobilisable", "purple"),
        ]
        for col, card in enumerate(cards):
            self.kpi_grid.addWidget(card, 0, col)

        self.clear_layout(self.donut_holder)
        positives = {k: v for k, v in summary.items() if v > 0}
        self.donut_holder.addWidget(
            PlotlyFigureCard(
                "Répartition des actifs",
                "Actifs réels par famille patrimoniale.",
                lambda positives=positives: self.plotly_assets_donut(positives),
                min_height=330,
                chart_height=245,
            )
        )

        self.clear_layout(self.evolution_holder)
        evolution_labels, evolution_series = self.build_patrimoine_evolution_series()
        self.evolution_holder.addWidget(
            PlotlyFigureCard(
                "Évolution du patrimoine net",
                "Courbe calculée depuis l'historique réel des valorisations.",
                lambda labels=evolution_labels, series=evolution_series: self.plotly_evolution_chart(labels, series),
                min_height=330,
                chart_height=245,
            )
        )

        if hasattr(self, "evolution_tab_holder"):
            self.clear_layout(self.evolution_tab_holder)
            self.evolution_tab_holder.addWidget(
                PlotlyFigureCard(
                    "Évolution du patrimoine net",
                    "Historique réel issu des valorisations enregistrées.",
                    lambda labels=evolution_labels, series=evolution_series: self.plotly_evolution_chart(labels, series),
                    min_height=430,
                    chart_height=340,
                )
            )

        self.clear_layout(self.insight_container)
        real_estate_ratio = positives.get("Immobilier", 0) / active * 100 if active else 0
        debt_ratio = passive / active * 100 if active else 0
        self.insight_container.addWidget(self.make_insight("I", "Patrimoine majoritairement immobilier", f"{real_estate_ratio:.0f} % des actifs sont concentrés en immobilier.", "#2563EB"))
        self.insight_container.addWidget(self.make_insight("€", "Liquidités confortables", f"{euro(liquidites)} mobilisables à court terme.", "#16A34A"))
        self.insight_container.addWidget(self.make_insight("!", "Endettement à surveiller", f"Passifs : {euro(passive)}, soit {debt_ratio:.0f} % des actifs.", "#F59E0B"))

        rows = self.db.list_assets()
        self.populate_table(self.assets_table, [r for r in rows if r["value"] >= 0], total=active)
        self.populate_table(self.passifs_table, [r for r in rows if r["value"] < 0], total=passive)
        self.update_top_assets(rows, active)


    def plotly_assets_donut(self, data: dict):
        if go is None:
            return None
        clean = {k: abs(float(v or 0)) for k, v in data.items() if float(v or 0) > 0}
        if not clean:
            return empty_figure("Aucun actif positif à afficher.")
        fig = go.Figure(
            go.Pie(
                labels=list(clean.keys()),
                values=list(clean.values()),
                hole=0.58,
                sort=False,
                textinfo="percent",
                hovertemplate="%{label}<br>%{value:,.2f} €<extra></extra>",
            )
        )
        fig.update_layout(showlegend=True, legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02))
        return fig

    def plotly_evolution_chart(self, labels: list[str], series: dict[str, list[float]]):
        if go is None:
            return None
        if not labels or not series:
            return empty_figure("Aucune évolution patrimoniale à afficher.")
        fig = go.Figure()
        for name, values in series.items():
            fig.add_trace(
                go.Scatter(
                    x=labels,
                    y=[float(value or 0) for value in values],
                    mode="lines+markers",
                    name=name,
                    line=dict(width=4, shape="spline"),
                    hovertemplate=f"%{{x}}<br>{name} : %{{y:,.2f}} €<extra></extra>",
                )
            )
        fig.update_yaxes(ticksuffix=" €")
        fig.update_layout(showlegend=False)
        return fig

    def build_patrimoine_evolution_series(self) -> tuple[list[str], dict[str, list[float]]]:
        history = self.db.patrimonio_evolution("net")
        if not history:
            return ["Aujourd'hui"], {"Patrimoine net": [0.0]}

        # Keep the chart readable: show the latest 8 valuation dates.
        history = history[-8:]
        labels = [self.short_date_label(str(point["date"])) for point in history]
        values = [float(point["value"] or 0) for point in history]
        return labels, {"Patrimoine net": values}

    @staticmethod
    def short_date_label(value: str) -> str:
        months = {
            "01": "Jan", "02": "Fév", "03": "Mar", "04": "Avr",
            "05": "Mai", "06": "Juin", "07": "Juil", "08": "Août",
            "09": "Sep", "10": "Oct", "11": "Nov", "12": "Déc",
        }
        parts = value.split("-")
        if len(parts) >= 2:
            return f"{months.get(parts[1], parts[1])} {parts[0][2:]}"
        return value


    def update_top_assets(self, rows, active_total: float = 0) -> None:
        positives = [r for r in rows if r["value"] > 0]
        positives = sorted(positives, key=lambda r: r["value"], reverse=True)

        if not positives:
            self.top_assets_content.setText("Aucun actif enregistré.")
            if hasattr(self, "top_assets_table"):
                self.top_assets_table.setRowCount(0)
            return

        top_four = positives[:4]
        html_parts = []
        for index, row in enumerate(top_four, start=1):
            weight = abs(row["value"]) / active_total * 100 if active_total else 0
            html_parts.append(f"<b>{index}. {row['name']}</b> — {euro(row['value'])} ({weight:.1f} % des actifs)")
        self.top_assets_content.setText("<br>".join(html_parts))

        if hasattr(self, "top_assets_table"):
            self.populate_table(self.top_assets_table, positives, total=active_total)

    def populate_table(self, table: QTableWidget, rows, total: float) -> None:
        table.setRowCount(0)
        for row_index, row in enumerate(rows):
            table.insertRow(row_index)
            weight = abs(row["value"]) / total * 100 if total else 0
            values = [
                row["name"],
                row["category"],
                row["asset_type"],
                euro(row["value"]),
                f"{weight:.1f} %",
                "+ 2,1 %" if row["value"] > 0 else "-",
                row["status"],
            ]
            table.setRowHeight(row_index, 42)
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if col in {3, 4, 5}:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if col == 3:
                    item.setForeground(Qt.red if row["value"] < 0 else Qt.darkGreen)
                table.setItem(row_index, col, item)

    def open_add_dialog(self) -> None:
        dialog = AssetDialog(self)
        if dialog.exec() == QDialog.Accepted:
            self.db.add_asset(dialog.data())
            self.refresh()

    def clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class AssetDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ajouter un élément patrimonial")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.category = QComboBox()
        self.category.addItems([
            "Immobilier",
            "Comptes bancaires",
            "Assurance-vie",
            "PEA",
            "CTO",
            "SCPI",
            "Crypto",
            "Métaux précieux",
            "Objets de valeur",
            "Crédit immobilier",
            "Crédit consommation",
            "Dette fiscale",
            "Autres actifs",
        ])
        self.asset_type = QLineEdit()
        self.value = QDoubleSpinBox()
        self.value.setRange(-100000000, 100000000)
        self.value.setDecimals(2)
        self.value.setSuffix(" €")
        self.valuation_date = QDateEdit(QDate.currentDate())
        self.valuation_date.setCalendarPopup(True)
        self.valuation_mode = QComboBox()
        self.valuation_mode.addItems(["Manuelle", "Importée", "Calculée", "Historique"])
        self.status = QComboBox()
        self.status.addItems(["Actif", "Archivé", "Vendu / Clos"])
        self.comment = QPlainTextEdit()
        self.comment.setFixedHeight(80)
        for label, widget in [
            ("Nom", self.name),
            ("Catégorie", self.category),
            ("Type", self.asset_type),
            ("Valeur estimée", self.value),
            ("Date de valorisation", self.valuation_date),
            ("Mode", self.valuation_mode),
            ("Statut", self.status),
            ("Commentaire", self.comment),
        ]:
            form.addRow(label, widget)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def data(self) -> dict:
        return {
            "name": self.name.text().strip() or "Nouvel élément",
            "category": self.category.currentText(),
            "asset_type": self.asset_type.text().strip() or "Actif",
            "value": float(self.value.value()),
            "valuation_date": self.valuation_date.date().toString("yyyy-MM-dd"),
            "valuation_mode": self.valuation_mode.currentText(),
            "comment": self.comment.toPlainText().strip(),
            "status": self.status.currentText(),
        }
