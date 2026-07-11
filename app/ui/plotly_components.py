from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout

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


def empty_figure(message: str):
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


class PlotlyFigureCard(Card):
    """Reusable premium Plotly chart card for Valoria Vision.

    V0.6.6:
    - uses local Plotly.js instead of CDN;
    - defers chart rendering shortly after the card is displayed;
    - shows an immediate lightweight placeholder to reduce perceived latency.
    """

    def __init__(
        self,
        title: str,
        subtitle: str,
        figure_factory,
        parent=None,
        min_height: int = 320,
        chart_height: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.figure_factory = figure_factory
        self.chart_height = chart_height or max(220, min_height - 88)
        self.view = None
        self.loading_label = None

        self.setMinimumHeight(min_height)
        self.setMaximumHeight(min_height + 24)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 14, 18, 14)
        self.layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-size:16px; font-weight: bold; color:#0F172A;")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet("color:#64748B;")

        self.layout.addWidget(title_label)
        if subtitle:
            self.layout.addWidget(subtitle_label)

        if not PLOTLY_AVAILABLE:
            self.layout.addWidget(self.message("Plotly n’est pas installé. Relancez install.bat pour installer les nouvelles dépendances."))
            return
        if not WEBENGINE_AVAILABLE:
            self.layout.addWidget(self.message("QWebEngineView n’est pas disponible dans cette installation PySide6."))
            return

        self.loading_label = self.message("Chargement du graphique…")
        self.layout.addWidget(self.loading_label)

        # Let the page and KPI cards appear first, then render the heavier web chart.
        QTimer.singleShot(40, self.render_chart)

    def render_chart(self) -> None:
        try:
            fig = self.figure_factory()
            fig.update_layout(
                template=PLOTLY_TEMPLATE,
                margin=dict(l=18, r=18, t=18, b=18),
                paper_bgcolor="white",
                plot_bgcolor="white",
                font=dict(family="Segoe UI, Inter, Arial", size=11, color="#0F172A"),
                hoverlabel=dict(bgcolor="white", font_size=11, font_family="Segoe UI"),
                height=self.chart_height,
            )

            html, base_url = build_plotly_html(fig, "valoria_plotly_chart", self.chart_height)
            self.view = QWebEngineView()
            self.view.setMinimumHeight(self.chart_height)
            self.view.setMaximumHeight(self.chart_height)
            self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            if self.loading_label is not None:
                self.layout.removeWidget(self.loading_label)
                self.loading_label.deleteLater()
                self.loading_label = None

            self.layout.addWidget(self.view)
            if base_url is not None:
                self.view.setHtml(html, base_url)
            else:
                self.view.setHtml(html)
        except Exception as exc:
            if self.loading_label is not None:
                self.loading_label.setText(f"Impossible d’afficher ce graphique Plotly : {exc}")
            else:
                self.layout.addWidget(self.message(f"Impossible d’afficher ce graphique Plotly : {exc}"))

    def message(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(
            "background:#F8FAFC; border:1px dashed #CBD5E1; border-radius:14px; "
            "padding:20px; color:#64748B; font-weight: bold;"
        )
        label.setMinimumHeight(min(240, self.chart_height))
        return label
