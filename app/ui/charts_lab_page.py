from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.theme import COLORS
from app.widgets import Card
from app.ui.plotly_runtime import build_plotly_html

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except Exception:
    QWebEngineView = None
    WEBENGINE_AVAILABLE = False

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except Exception:
    go = None
    PLOTLY_AVAILABLE = False


PLOTLY_TEMPLATE = "plotly_white"


class PlotlyChartCard(Card):
    """Card displaying one Plotly chart inside PySide6 via QWebEngineView."""

    def __init__(self, title: str, subtitle: str, figure_factory, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(390)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-size:17px; font-weight: bold; color:#0F172A;")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet("color:#64748B;")

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

        if not PLOTLY_AVAILABLE:
            layout.addWidget(self.message("Plotly n’est pas installé. Relancez install.bat pour installer les nouvelles dépendances."))
            return
        if not WEBENGINE_AVAILABLE:
            layout.addWidget(self.message("QWebEngineView n’est pas disponible dans cette installation PySide6. Le laboratoire reste sécurisé et n’empêche pas l’application de démarrer."))
            return

        try:
            fig = figure_factory()
            fig.update_layout(
                template=PLOTLY_TEMPLATE,
                margin=dict(l=24, r=24, t=28, b=28),
                paper_bgcolor="white",
                plot_bgcolor="white",
                font=dict(family="Segoe UI, Inter, Arial", size=12, color="#0F172A"),
                hoverlabel=dict(bgcolor="white", font_size=12, font_family="Segoe UI"),
                height=300,
            )
            html, base_url = build_plotly_html(
                fig,
                "charts_lab_plotly",
                300,
                config={
                    "displayModeBar": False,
                    "responsive": True,
                    "locale": "fr",
                    "scrollZoom": False,
                },
            )
            view = QWebEngineView()
            view.setMinimumHeight(300)
            if base_url is not None:
                view.setHtml(html, base_url)
            else:
                view.setHtml(html)
            layout.addWidget(view, stretch=1)
        except Exception as exc:
            layout.addWidget(self.message(f"Impossible d’afficher ce graphique Plotly : {exc}"))

    def message(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(
            "background:#F8FAFC; border:1px dashed #CBD5E1; border-radius:14px; "
            "padding:22px; color:#64748B; font-weight: bold;"
        )
        label.setMinimumHeight(250)
        return label


class PlotlyChartsLab(QWidget):
    """Plotly laboratory connected to real Valoria Vision data in V0.6.6."""

    def __init__(self, db: Database, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.build()

    def build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 16, 8, 8)
        root.setSpacing(14)

        intro = Card()
        intro_layout = QVBoxLayout(intro)
        intro_layout.setContentsMargins(18, 16, 18, 16)
        intro_layout.setSpacing(8)

        title = QLabel("Laboratoire charts Plotly — données réelles")
        title.setStyleSheet("font-size:20px; font-weight: bold;")
        subtitle = QLabel(
            "Phase 2 : les graphiques Plotly sont maintenant raccordés aux données réelles de Valoria Vision. Aucun graphique existant n’est encore remplacé."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#64748B;")
        badge = QLabel("V0.6.6 — raccord transactions, budgets, patrimoine et prévisionnel")
        badge.setStyleSheet(
            f"background:{COLORS['blue_soft']}; color:{COLORS['blue']}; "
            "border-radius:12px; padding:10px 12px; font-weight: bold;"
        )

        intro_layout.addWidget(title)
        intro_layout.addWidget(subtitle)
        intro_layout.addWidget(badge)
        root.addWidget(intro)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        page = QWidget()
        page.setStyleSheet("background:transparent;")
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)

        month = self.db.get_setting("current_month", "2026-06")
        start_date = self.db.default_forecast_start_date()

        cards = [
            PlotlyChartCard(
                "Donut — dépenses réelles",
                f"Transactions réelles du mois {month}, par catégorie.",
                self.donut_expenses,
            ),
            PlotlyChartCard(
                "Treemap — patrimoine réel",
                "Actifs et passifs réels saisis dans le module Patrimoine.",
                self.treemap_assets,
            ),
            PlotlyChartCard(
                "Courbe — trésorerie prévisionnelle réelle",
                f"Projection réelle à partir du {start_date}, transactions et récurrences incluses.",
                self.cash_line,
            ),
            PlotlyChartCard(
                "Budget — prévu / réalisé réel",
                f"Budgets et transactions réelles du mois {month}.",
                self.budget_grouped_bar,
            ),
        ]

        for i, card in enumerate(cards):
            grid.addWidget(card, i // 2, i % 2)

        scroll.setWidget(page)
        root.addWidget(scroll, stretch=1)

    def empty_figure(self, message: str):
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=15, color="#64748B"),
            xref="paper",
            yref="paper",
        )
        fig.update_xaxes(visible=False)
        fig.update_yaxes(visible=False)
        return fig

    @staticmethod
    def euro_hover() -> str:
        return "%{label}<br>%{value:,.2f} €<extra></extra>"

    def donut_expenses(self):
        data = self.db.expenses_by_category()
        if not data:
            return self.empty_figure("Aucune dépense réelle à afficher sur le mois.")
        labels = list(data.keys())
        values = [float(value or 0) for value in data.values()]
        fig = go.Figure(
            data=[
                go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.58,
                    sort=False,
                    textinfo="label+percent",
                    hovertemplate=self.euro_hover(),
                )
            ]
        )
        fig.update_layout(showlegend=False)
        return fig

    def treemap_assets(self):
        """Real assets treemap with robust Plotly ids.

        V0.6.6 fix:
        Real data can contain duplicate labels or labels identical to parent
        categories. Plotly treemap can then render a blank area if only labels
        and parents are provided. We now provide stable unique ids and parent
        ids, and we keep all values positive.
        """
        assets = [row for row in self.db.list_assets() if row["status"] == "Actif"]
        if not assets:
            return self.empty_figure("Aucun actif réel à afficher.")

        ids = ["root"]
        labels = ["Patrimoine"]
        parents = [""]
        values = []
        category_totals: dict[str, float] = {}
        children_by_category: dict[str, list[tuple[str, float, int]]] = {}

        for asset in assets:
            raw_value = float(asset["value"] or 0)
            value = abs(raw_value)
            if value <= 0:
                continue

            base_category = asset["category"] or "Autres"
            category = "Passifs" if raw_value < 0 else base_category
            category_totals[category] = category_totals.get(category, 0.0) + value
            children_by_category.setdefault(category, []).append((asset["name"] or "Élément", value, int(asset["id"])))

        total = round(sum(category_totals.values()), 2)
        if total <= 0:
            return self.empty_figure("Aucun montant patrimonial exploitable.")

        values.append(total)

        for index, (category, total_category) in enumerate(sorted(category_totals.items(), key=lambda item: item[1], reverse=True), start=1):
            category_id = f"cat-{index}"
            ids.append(category_id)
            labels.append(category)
            parents.append("root")
            values.append(round(float(total_category or 0), 2))

            for child_index, (name, value, asset_id) in enumerate(sorted(children_by_category.get(category, []), key=lambda item: item[1], reverse=True), start=1):
                ids.append(f"asset-{asset_id}-{child_index}")
                labels.append(name)
                parents.append(category_id)
                values.append(round(float(value or 0), 2))

        fig = go.Figure(
            go.Treemap(
                ids=ids,
                labels=labels,
                parents=parents,
                values=values,
                branchvalues="total",
                textinfo="label+value+percent parent",
                hovertemplate="<b>%{label}</b><br>%{value:,.2f} €<extra></extra>",
                maxdepth=3,
            )
        )
        fig.update_layout(uniformtext=dict(minsize=10, mode="hide"))
        return fig

    def cash_line(self):
        start_date = self.db.default_forecast_start_date()
        forecast = self.db.cash_forecast(start_date, 30, "Réaliste")
        points = forecast.get("daily_points", [])
        if not points:
            return self.empty_figure("Aucune donnée prévisionnelle à afficher.")

        labels = [point.get("label", point.get("date", "")) for point in points]
        balances = [float(point.get("balance", 0) or 0) for point in points]
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=balances,
                mode="lines+markers",
                name="Trésorerie",
                line=dict(width=4, shape="spline"),
                fill="tozeroy",
                hovertemplate="%{x}<br>%{y:,.2f} €<extra></extra>",
            )
        )
        fig.update_yaxes(ticksuffix=" €")
        fig.update_xaxes(tickangle=0)
        return fig

    def budget_grouped_bar(self):
        month = self.db.get_setting("current_month", "2026-06")
        report = self.db.budget_report(month)
        rows = [row for row in report.get("rows", []) if float(row.get("planned", 0) or 0) > 0 or float(row.get("actual", 0) or 0) > 0]
        if not rows:
            return self.empty_figure("Aucun budget ou réalisé à afficher.")

        rows = sorted(rows, key=lambda row: max(float(row.get("planned", 0) or 0), float(row.get("actual", 0) or 0)), reverse=True)[:8]
        categories = [row["category"] for row in rows]
        planned = [float(row.get("planned", 0) or 0) for row in rows]
        actual = [float(row.get("actual", 0) or 0) for row in rows]

        fig = go.Figure()
        fig.add_trace(go.Bar(x=categories, y=planned, name="Prévu", hovertemplate="%{x}<br>Prévu : %{y:,.2f} €<extra></extra>"))
        fig.add_trace(go.Bar(x=categories, y=actual, name="Réalisé", hovertemplate="%{x}<br>Réalisé : %{y:,.2f} €<extra></extra>"))
        fig.update_layout(barmode="group", legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
        fig.update_yaxes(ticksuffix=" €")
        return fig
