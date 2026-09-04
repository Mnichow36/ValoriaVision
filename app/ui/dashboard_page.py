from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.database import Database
from app.services.business_rules import is_current_expense, is_true_income
from app.theme import euro, format_date_fr
from app.widgets import Card, KpiCard, PageHeader
from app.ui.plotly_components import PlotlyFigureCard, empty_figure, go


class DashboardPage(QWidget):
    """Dashboard V0.6.8.1 — current month budget plus annual income/expense bars."""

    GREETING_TITLE = "Bonjour"

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(16)
        self.build()

    def build(self) -> None:
        self.layout.addWidget(
            PageHeader(
                self.GREETING_TITLE,
                "Voici votre situation financière — budget, patrimoine et alertes clés",
            )
        )

        self.kpi_grid = QGridLayout()
        self.kpi_grid.setSpacing(12)
        self.layout.addLayout(self.kpi_grid)

        self.main_grid = QGridLayout()
        self.main_grid.setSpacing(16)
        self.layout.addLayout(self.main_grid, stretch=2)

        self.bottom_grid = QGridLayout()
        self.bottom_grid.setSpacing(16)
        self.layout.addLayout(self.bottom_grid, stretch=1)

        self.refresh()

    def refresh(self) -> None:
        self.clear_layout(self.kpi_grid)
        self.clear_layout(self.main_grid)
        self.clear_layout(self.bottom_grid)

        metrics = self.db.dashboard_metrics()
        current_month = date.today().strftime("%Y-%m")
        current_year = date.today().year
        cards = [
            KpiCard("Liquidités disponibles", euro(metrics["cash"]), "Comptes courants + épargne", "blue"),
            KpiCard("Liquidités prévisionnelles J+30", euro(metrics["forecast_30"]), f"Depuis le {metrics['forecast_start_date']} — scénario réaliste", "green"),
            KpiCard("Patrimoine net", euro(metrics["patrimoine_net"]), "+ 6,3 % vs mois dernier", "purple"),
            KpiCard("Revenus du mois", euro(metrics["revenus"]), "Hors transferts internes", "green"),
            KpiCard("Dépenses du mois", euro(metrics["depenses"]), "Hors transferts et investissements", "red"),
        ]
        for col, card in enumerate(cards):
            self.kpi_grid.addWidget(card, 0, col)

        forecast_chart = self.db.dashboard_forecast_chart(60)
        budget_report = self.db.budget_report(current_month)

        self.main_grid.addWidget(
            PlotlyFigureCard(
                "Analyse budgétaire — treemap des consommations",
                (
                    f"Mois {budget_report['month']} : taille = réalisé, regroupement par statut budget. "
                    f"Réalisé {euro(budget_report['total_realized'])} / prévu {euro(budget_report['total_planned'])}."
                ),
                lambda: self.plotly_budget_treemap(budget_report),
                min_height=305,
                chart_height=220,
            ),
            0,
            0,
            1,
            2,
        )

        self.main_grid.addWidget(
            PlotlyFigureCard(
                "Répartition du patrimoine",
                "Actifs réels par famille patrimoniale.",
                self.plotly_assets_donut,
                min_height=305,
                chart_height=220,
            ),
            0,
            2,
        )
        self.main_grid.setColumnStretch(0, 2)
        self.main_grid.setColumnStretch(1, 2)
        self.main_grid.setColumnStretch(2, 2)

        self.bottom_grid.addWidget(
            PlotlyFigureCard(
                "Revenus / dépenses mensuels — année en cours",
                f"Comparatif mensuel de janvier à décembre {current_year}.",
                lambda year=current_year: self.plotly_yearly_income_expense_bars(year),
                min_height=285,
                chart_height=205,
            ),
            0,
            0,
        )
        self.bottom_grid.addWidget(self.alerts_card(forecast_chart), 0, 1)
        self.bottom_grid.addWidget(self.summary_card(), 0, 2)
        self.bottom_grid.setColumnStretch(0, 2)
        self.bottom_grid.setColumnStretch(1, 1)
        self.bottom_grid.setColumnStretch(2, 1)

    def plotly_budget_treemap(self, report: dict):
        if go is None:
            return None
        rows = [
            row for row in report.get("rows", [])
            if float(row.get("actual", 0) or 0) > 0 or float(row.get("planned", 0) or 0) > 0
        ]
        if not rows:
            return empty_figure("Aucune donnée budgétaire à afficher.")

        status_order = ["Dépassement", "Vigilance", "Non budgété", "OK"]
        status_labels = {
            "Dépassement": "Dépassements",
            "Vigilance": "Vigilances",
            "Non budgété": "Non budgété",
            "OK": "OK",
        }
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            status = row.get("status") or "OK"
            grouped.setdefault(status, []).append(row)

        ids = ["root"]
        labels = ["Budget"]
        parents = [""]
        values = []
        customdata = [["", "", "", "", ""]]

        total = 0.0
        for row in rows:
            total += max(float(row.get("actual", 0) or 0), float(row.get("planned", 0) or 0), 1.0)
        values.append(round(total, 2))

        for status in status_order:
            status_rows = grouped.get(status, [])
            if not status_rows:
                continue
            status_id = f"status-{status}"
            status_value = sum(max(float(row.get("actual", 0) or 0), float(row.get("planned", 0) or 0), 1.0) for row in status_rows)
            ids.append(status_id)
            labels.append(status_labels.get(status, status))
            parents.append("root")
            values.append(round(status_value, 2))
            customdata.append(["", "", "", "", status])

            for index, row in enumerate(sorted(status_rows, key=lambda r: float(r.get("usage", 0) or 0), reverse=True), start=1):
                category = row["category"]
                planned = float(row.get("planned", 0) or 0)
                actual = float(row.get("actual", 0) or 0)
                remaining = float(row.get("remaining", 0) or 0)
                usage = float(row.get("usage", 0) or 0)
                value = max(actual, planned, 1.0)
                ids.append(f"{status_id}-{index}-{category}")
                labels.append(category)
                parents.append(status_id)
                values.append(round(value, 2))
                customdata.append([
                    f"{planned:,.2f} €",
                    f"{actual:,.2f} €",
                    f"{remaining:,.2f} €",
                    f"{usage:.1f} %",
                    status,
                ])

        fig = go.Figure(
            go.Treemap(
                ids=ids,
                labels=labels,
                parents=parents,
                values=values,
                branchvalues="total",
                customdata=customdata,
                textinfo="label+percent parent",
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    "Statut : %{customdata[4]}<br>"
                    "Prévu : %{customdata[0]}<br>"
                    "Réalisé : %{customdata[1]}<br>"
                    "Reste : %{customdata[2]}<br>"
                    "Utilisation : %{customdata[3]}<extra></extra>"
                ),
                maxdepth=3,
            )
        )
        fig.update_layout(uniformtext=dict(minsize=10, mode="hide"), margin=dict(l=10, r=10, t=10, b=10))
        return fig

    def plotly_assets_donut(self):
        if go is None:
            return None
        patrimoine = self.db.asset_summary()
        data = {k: abs(float(v or 0)) for k, v in patrimoine.items() if float(v or 0) > 0}
        if not data:
            return empty_figure("Aucun actif positif à afficher.")
        fig = go.Figure(
            go.Pie(
                labels=list(data.keys()),
                values=list(data.values()),
                hole=0.58,
                sort=False,
                textinfo="percent",
                hovertemplate="%{label}<br>%{value:,.2f} €<extra></extra>",
            )
        )
        fig.update_layout(showlegend=True, legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02), margin=dict(l=10, r=130, t=10, b=10))
        return fig

    def yearly_income_expense_points(self, year: int) -> list[dict]:
        """Income and expenses by month for the current calendar year.

        This replaces the previous daily cumulative month chart to avoid
        Dashboard redundancy and give a year-to-date / full-year reading.
        """
        month_labels = ["Jan.", "Fév.", "Mars", "Avr.", "Mai", "Juin", "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."]
        points = [
            {
                "month": month,
                "label": month_labels[month - 1],
                "income": 0.0,
                "expense": 0.0,
            }
            for month in range(1, 13)
        ]

        with self.db.connect() as conn:
            rows = list(
                conn.execute(
                    """
                    SELECT tx_date, category, amount
                    FROM transactions
                    WHERE tx_date >= ? AND tx_date <= ?
                    ORDER BY tx_date
                    """,
                    (f"{year:04d}-01-01", f"{year:04d}-12-31"),
                )
            )

        for row in rows:
            try:
                month = datetime.strptime(str(row["tx_date"]), "%Y-%m-%d").month
            except Exception:
                continue
            amount = float(row["amount"] or 0)
            category = row["category"]
            if is_true_income(category, amount):
                points[month - 1]["income"] += amount
            elif is_current_expense(category, amount):
                points[month - 1]["expense"] += abs(amount)

        for point in points:
            point["income"] = round(point["income"], 2)
            point["expense"] = round(point["expense"], 2)
            point["net"] = round(point["income"] - point["expense"], 2)
        return points

    def plotly_yearly_income_expense_bars(self, year: int):
        if go is None:
            return None
        points = self.yearly_income_expense_points(year)
        labels = [point["label"] for point in points]
        income = [point["income"] for point in points]
        expense = [point["expense"] for point in points]

        if not any(income) and not any(expense):
            return empty_figure(f"Aucun revenu ou dépense réelle à afficher pour {year}.")

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=labels,
                y=income,
                name="Revenus",
                hovertemplate="%{x}<br>Revenus : %{y:,.2f} €<extra></extra>",
            )
        )
        fig.add_trace(
            go.Bar(
                x=labels,
                y=expense,
                name="Dépenses",
                hovertemplate="%{x}<br>Dépenses : %{y:,.2f} €<extra></extra>",
            )
        )
        fig.update_layout(
            barmode="group",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            yaxis=dict(title="Montant", ticksuffix=" €", showgrid=True),
            margin=dict(l=46, r=18, t=10, b=34),
        )
        return fig

    def alerts_card(self, forecast_chart: dict) -> Card:
        card = Card()
        card.setMinimumHeight(285)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        title = QLabel("Alertes")
        title.setStyleSheet("font-weight: bold; font-size: 17px;")
        layout.addWidget(title)

        alerts = [
            (
                "🔴" if forecast_chart.get("alert_level") == "critical" else "🟡" if forecast_chart.get("alert_level") == "warning" else "🟢",
                forecast_chart["alert"],
                f"Point bas : {euro(forecast_chart['min_balance'])} — {forecast_chart.get('alert_detail', '')}",
            ),
            (
                "🔵",
                "Comparaison des scénarios à 60 jours",
                (
                    f"Prudent : {euro(forecast_chart.get('end_balance_by_scenario', {}).get('Prudent', forecast_chart['end_balance']))} — "
                    f"Réaliste : {euro(forecast_chart.get('end_balance_by_scenario', {}).get('Réaliste', forecast_chart['end_balance']))} — "
                    f"Optimiste : {euro(forecast_chart.get('end_balance_by_scenario', {}).get('Optimiste', forecast_chart['end_balance']))}"
                ),
            ),
            (
                "🔵",
                "Flux pris en compte",
                f"Entrées : {euro(forecast_chart['total_in'])} — Sorties : {euro(forecast_chart['total_out'])}",
            ),
        ]
        for icon, label, detail in alerts:
            row = QLabel(f"{icon}  <b>{label}</b><br><span style='color:#64748B'>{detail}</span>")
            row.setWordWrap(True)
            row.setStyleSheet("padding: 4px 0;")
            layout.addWidget(row)
        layout.addStretch(1)
        link = QLabel("<span style='color:#2563EB; font-weight: bold;'>Dashboard mois courant, budget & synthèse annuelle</span>")
        layout.addWidget(link)
        return card

    def summary_card(self) -> Card:
        card = Card()
        card.setMinimumHeight(285)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        title = QLabel("Synthèse rapide")
        title.setStyleSheet("font-weight: bold; font-size: 17px;")
        layout.addWidget(title)
        rows = [
            ("Comptes bancaires", "7"),
            ("Investissements", "3"),
            ("Biens immobiliers", "1"),
            ("Dettes en cours", "1"),
        ]
        for label, value in rows:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 7, 0, 7)
            row_layout.setSpacing(12)
            label_widget = QLabel(label)
            label_widget.setStyleSheet("color:#0F172A; font-weight: bold;")
            value_widget = QLabel(value)
            value_widget.setStyleSheet("color:#2563EB; font-weight: bold; padding-left:16px;")
            row_layout.addWidget(label_widget)
            row_layout.addStretch(1)
            row_layout.addWidget(value_widget)
            row_widget.setStyleSheet("border-bottom: 1px solid #EEF2F7;")
            layout.addWidget(row_widget)
        layout.addStretch(1)
        link = QLabel("<span style='color:#2563EB; font-weight: bold;'>Voir le détail</span>")
        layout.addWidget(link)
        return card

    def clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
