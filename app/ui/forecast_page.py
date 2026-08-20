from __future__ import annotations

from datetime import datetime, timedelta
from PySide6.QtCore import QDate, QObject, QPoint, QRectF, Qt, Slot, QTimer
from PySide6.QtGui import QBrush, QColor, QCursor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFrame,
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QSizePolicy,
    QMenu, QMessageBox, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
    QToolTip, QVBoxLayout, QWidget,
)

from app.database import Database
from app.services.forecast_chart_service import ForecastChartService
from app.theme import COLORS, euro
from app.widgets import Card, KpiCard, PageHeader, primary_button
from app.ui.plotly_runtime import build_plotly_html

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except Exception:
    QWebEngineView = None
    WEBENGINE_AVAILABLE = False

try:
    from PySide6.QtWebChannel import QWebChannel
    WEBCHANNEL_AVAILABLE = True
except Exception:
    QWebChannel = None
    WEBCHANNEL_AVAILABLE = False

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except Exception:
    go = None
    PLOTLY_AVAILABLE = False


class ForecastDailyChart(Card):
    """Daily cash curve with contextual day actions."""

    def __init__(self, parent_page: "ForecastPage") -> None:
        super().__init__()
        self.parent_page = parent_page
        self.data: dict | None = None
        self.setMinimumHeight(430)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.open_context_menu)

    def set_forecast(self, data: dict) -> None:
        self.data = data
        self.update()

    def chart_rect(self) -> QRectF:
        rect = self.rect().adjusted(24, 20, -24, -18)
        return rect.adjusted(0, 70, 0, -34)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(24, 20, -24, -18)
        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(QFont("Segoe UI", 16, QFont.Bold))
        painter.drawText(rect.left(), rect.top() + 20, "Courbe de trésorerie prévisionnelle")
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor(COLORS["muted"]))
        painter.drawText(rect.left(), rect.top() + 42, "Un point par jour sur la période sélectionnée. Survolez ou cliquez un jour pour voir ses opérations.")

        chart = self.chart_rect()
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        for i in range(5):
            y = chart.top() + chart.height() * i / 4
            painter.drawLine(chart.left(), y, chart.right(), y)

        if not self.data or not self.data.get("balances"):
            painter.setPen(QColor(COLORS["muted"]))
            painter.drawText(chart, Qt.AlignCenter, "Aucune donnée prévisionnelle.")
            return

        balances = [float(value) for value in self.data["balances"]]
        labels = self.data["labels"]
        minimum = min(balances)
        maximum = max(balances)
        if minimum == maximum:
            maximum += 1
        padding = (maximum - minimum) * 0.18
        minimum -= padding
        maximum += padding

        def point(index: int, value: float) -> tuple[float, float]:
            x = chart.left() + chart.width() * index / max(1, len(balances) - 1)
            y = chart.bottom() - chart.height() * (value - minimum) / (maximum - minimum)
            return x, y

        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(QFont("Segoe UI", 8))
        for i in range(5):
            value = maximum - (maximum - minimum) * i / 4
            y = chart.top() + chart.height() * i / 4
            painter.drawText(QRectF(chart.left() - 4, y - 9, 70, 18), Qt.AlignLeft, f"{value/1000:.0f} k€")

        path = QPainterPath()
        first_x, first_y = point(0, balances[0])
        path.moveTo(first_x, first_y)
        for index, value in enumerate(balances[1:], start=1):
            x, y = point(index, value)
            path.lineTo(x, y)

        pen = QPen(QColor(COLORS["green"]), 3)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)

        for index, value in enumerate(balances):
            x, y = point(index, value)
            day = self.data["daily_points"][index]
            has_events = bool(day["events"])
            painter.setBrush(QBrush(QColor(COLORS["green"] if has_events else "#94A3B8")))
            painter.setPen(Qt.NoPen)
            radius = 4 if has_events else 2.2
            painter.drawEllipse(QRectF(x - radius, y - radius, radius * 2, radius * 2))

        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(QFont("Segoe UI", 8))
        label_step = max(1, len(labels) // 6)
        for index, label in enumerate(labels):
            if index % label_step == 0 or index == len(labels) - 1:
                x, _ = point(index, minimum)
                painter.drawText(QRectF(x - 32, chart.bottom() + 12, 64, 18), Qt.AlignCenter, label)

    def nearest_day_index(self, pos: QPoint) -> int | None:
        if not self.data or not self.data.get("balances"):
            return None
        chart = self.chart_rect()
        if pos.x() < chart.left() or pos.x() > chart.right():
            return None
        count = len(self.data["balances"])
        relative = (pos.x() - chart.left()) / max(1, chart.width())
        index = round(relative * max(0, count - 1))
        return max(0, min(count - 1, index))

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        index = self.nearest_day_index(event.pos())
        if index is None or not self.data:
            return
        day = self.data["daily_points"][index]
        QToolTip.showText(event.globalPos(), self.parent_page.tooltip_for_day(day), self)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.open_day_popup(event.pos())

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.open_day_popup(event.pos())

    def open_day_popup(self, pos: QPoint) -> None:
        index = self.nearest_day_index(pos)
        if index is None or not self.data:
            return
        self.parent_page.open_day_popup(self.data["daily_points"][index])

    def open_context_menu(self, pos: QPoint) -> None:
        index = self.nearest_day_index(pos)
        if index is None or not self.data:
            return
        day = self.data["daily_points"][index]
        menu = QMenu(self)
        action_day = menu.addAction("Voir les opérations de cette journée")
        menu.addSeparator()
        recurring_events = [event for event in day["events"] if event.get("recurring_id")]
        recurring_actions = {}
        if recurring_events:
            manage_menu = menu.addMenu("Gérer les récurrences du jour")
            for event in recurring_events:
                label = f"{event['name']} — {event['account']}"
                sub = manage_menu.addMenu(label)
                recurring_actions[sub.addAction("Modifier la récurrence")] = ("edit", event["recurring_id"])
                recurring_actions[sub.addAction("Supprimer la récurrence")] = ("delete", event["recurring_id"])
        selected = menu.exec(self.mapToGlobal(pos))
        if selected == action_day:
            self.parent_page.open_day_popup(day)
        elif selected in recurring_actions:
            action_type, recurring_id = recurring_actions[selected]
            if action_type == "edit":
                self.parent_page.edit_recurring_item(recurring_id)
            elif action_type == "delete":
                self.parent_page.delete_recurring_item(recurring_id)


class ForecastPlotlyBridge(QObject):
    """Bridge between Plotly JS events and the ForecastPage."""

    def __init__(self, parent_page: "ForecastPage") -> None:
        super().__init__(parent_page)
        self.parent_page = parent_page
        self.active_period = ""

    @Slot(str)
    def activePeriodChanged(self, period: str) -> None:
        self.active_period = period or ""

    @Slot(str)
    def periodClicked(self, period: str) -> None:
        self.active_period = period or self.active_period
        self.parent_page.open_period_by_key(self.active_period)

    @Slot(str)
    def periodContextMenu(self, period: str) -> None:
        self.active_period = period or self.active_period
        self.parent_page.open_period_context_menu_by_key(self.active_period)


class ForecastPlotlyWebView(QWebEngineView if QWebEngineView is not None else QWidget):
    """QWebEngineView with the browser context menu disabled."""

    def __init__(self, chart_card: "InteractiveForecastPlotlyChart") -> None:
        super().__init__(chart_card)
        self.chart_card = chart_card

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        event.accept()
        self.chart_card.open_context_menu_from_view_position(event.pos())


class InteractiveForecastPlotlyChart(Card):
    """Premium combined forecast chart.

    Crédits and débits are displayed as columns. Closing cash balance is
    superimposed as a line on a secondary axis. Interactions are kept through
    Qt WebChannel: hover details, click period detail, right-click recurrence
    context menu.
    """

    def __init__(self, parent_page: "ForecastPage") -> None:
        super().__init__()
        self.parent_page = parent_page
        self.data: dict | None = None
        self.pending_render = False
        self.setMinimumHeight(450)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        title = QLabel("Flux prévisionnels & solde de trésorerie")
        title.setStyleSheet("font-size:18px; font-weight: bold; color:#0F172A;")
        subtitle = QLabel("Crédits et débits en colonnes, solde cumulé en courbe. Survol : détail, clic : opérations, clic droit : récurrences.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#64748B;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.loading_label = QLabel("Chargement du graphique combiné…")
        self.loading_label.setWordWrap(True)
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet(
            "background:#F8FAFC; border:1px dashed #CBD5E1; border-radius:14px; "
            "padding:22px; color:#64748B; font-weight: bold;"
        )

        self.fallback_message = QLabel("")
        self.fallback_message.setWordWrap(True)
        self.fallback_message.setAlignment(Qt.AlignCenter)
        self.fallback_message.setStyleSheet(
            "background:#F8FAFC; border:1px dashed #CBD5E1; border-radius:14px; "
            "padding:22px; color:#64748B; font-weight: bold;"
        )

        self.web = None
        self.channel = None
        self.bridge = None
        if PLOTLY_AVAILABLE and WEBENGINE_AVAILABLE and WEBCHANNEL_AVAILABLE:
            self.web = ForecastPlotlyWebView(self)
            self.web.setMinimumHeight(360)
            self.web.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.channel = QWebChannel(self.web.page())
            self.bridge = ForecastPlotlyBridge(parent_page)
            self.channel.registerObject("forecastBridge", self.bridge)
            self.web.page().setWebChannel(self.channel)
            layout.addWidget(self.loading_label, stretch=1)
            layout.addWidget(self.web, stretch=1)
            self.web.setVisible(False)
        else:
            self.fallback_message.setText(
                "Plotly, QWebEngineView ou QWebChannel n’est pas disponible. "
                "Le graphique combiné interactif ne peut pas être affiché."
            )
            layout.addWidget(self.fallback_message, stretch=1)

    def set_chart_data(self, data: dict) -> None:
        self.data = data
        if self.web is None:
            return
        if self.pending_render:
            return
        self.pending_render = True
        QTimer.singleShot(40, self.render)

    def set_forecast(self, data: dict) -> None:
        """Compatibility shim for old calls."""
        self.set_chart_data(data)

    def period_from_view_position(self, pos: QPoint) -> str:
        points = self.data.get("points", []) if self.data else []
        if not points or self.web is None:
            return ""
        width = max(1, self.web.width())
        relative = max(0.0, min(1.0, float(pos.x()) / float(width)))
        index = round(relative * max(0, len(points) - 1))
        return str(points[index]["period"])

    def open_context_menu_from_view_position(self, pos: QPoint) -> None:
        period = ""
        if self.bridge is not None and self.bridge.active_period:
            period = self.bridge.active_period
        if not period:
            period = self.period_from_view_position(pos)
        self.parent_page.open_period_context_menu_by_key(period)

    def render(self) -> None:
        self.pending_render = False
        if not self.data or not self.web or go is None:
            return

        points = self.data.get("points", [])
        if not points:
            fig = go.Figure()
            fig.add_annotation(text="Aucune donnée prévisionnelle.", x=0.5, y=0.5, showarrow=False, xref="paper", yref="paper")
        else:
            labels = [point["label"] for point in points]
            periods = [point["period"] for point in points]
            credits = [float(point.get("credits", 0) or 0) for point in points]
            debits = [float(point.get("debits", 0) or 0) for point in points]
            balances = [float(point.get("closing_balance", 0) or 0) for point in points]
            hover_text = []
            for point in points:
                events = point.get("events", [])
                lines = [
                    f"<b>{point.get('label')}</b>",
                    f"Période : {point.get('period_start')} → {point.get('period_end')}",
                    f"Crédits : {euro(point.get('credits', 0))}",
                    f"Débits : {euro(point.get('debits', 0))}",
                    f"Solde début : {euro(point.get('opening_balance', 0))}",
                    f"Solde fin : {euro(point.get('closing_balance', 0))}",
                    f"Opérations : {point.get('flow_count', 0)}",
                ]
                for event in events[:4]:
                    lines.append(f"• {event.get('name', '')} — {euro(event.get('amount', 0))}")
                if len(events) > 4:
                    lines.append(f"+ {len(events) - 4} autre(s)")
                hover_text.append("<br>".join(lines))

            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    x=labels,
                    y=credits,
                    name="Crédits",
                    marker=dict(color="#22C55E"),
                    customdata=periods,
                    hovertext=hover_text,
                    hovertemplate="%{hovertext}<extra></extra>",
                )
            )
            fig.add_trace(
                go.Bar(
                    x=labels,
                    y=debits,
                    name="Débits",
                    marker=dict(color="#EF4444"),
                    customdata=periods,
                    hovertext=hover_text,
                    hovertemplate="%{hovertext}<extra></extra>",
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=labels,
                    y=balances,
                    name="Solde",
                    mode="lines+markers",
                    line=dict(color="#2563EB", width=4, shape="spline"),
                    marker=dict(size=7),
                    yaxis="y2",
                    customdata=periods,
                    hovertext=hover_text,
                    hovertemplate="%{hovertext}<extra></extra>",
                )
            )
            fig.update_layout(
                barmode="group",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                yaxis=dict(title="Flux", ticksuffix=" €", showgrid=True),
                yaxis2=dict(title="Solde", ticksuffix=" €", overlaying="y", side="right", showgrid=False),
            )

        fig.update_layout(
            template="plotly_white",
            margin=dict(l=40, r=62, t=30, b=44),
            paper_bgcolor="white",
            plot_bgcolor="white",
            font=dict(family="Segoe UI, Inter, Arial", size=11, color="#0F172A"),
            hoverlabel=dict(bgcolor="white", font_size=12, font_family="Segoe UI"),
            height=360,
        )
        plot_body = fig
        bridge_js = """
        <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
        <script>
        (function() {
            function setupBridge() {
                if (typeof qt === "undefined" || !qt.webChannelTransport) { return; }
                new QWebChannel(qt.webChannelTransport, function(channel) {
                    var bridge = channel.objects.forecastBridge;
                    var gd = document.getElementById("forecast_combined_plot");
                    var activePeriod = "";
                    if (!gd || !bridge) { return; }

                    function pointPeriod(evt) {
                        if (!evt || !evt.points || !evt.points.length) { return ""; }
                        return String(evt.points[0].customdata || "");
                    }

                    gd.on("plotly_hover", function(evt) {
                        activePeriod = pointPeriod(evt);
                        if (activePeriod) { bridge.activePeriodChanged(activePeriod); }
                    });

                    gd.on("plotly_click", function(evt) {
                        var p = pointPeriod(evt) || activePeriod;
                        if (p) { bridge.periodClicked(p); }
                    });

                    gd.addEventListener("contextmenu", function(ev) {
                        ev.preventDefault();
                        if (activePeriod) { bridge.periodContextMenu(activePeriod); }
                        return false;
                    });
                });
            }
            if (document.readyState === "complete") { setupBridge(); }
            else { window.addEventListener("load", setupBridge); }
        })();
        </script>
        """
        full_html, base_url = build_plotly_html(
            fig,
            "forecast_combined_plot",
            360,
            extra_js=bridge_js,
            config={"displayModeBar": False, "responsive": True, "locale": "fr", "scrollZoom": False},
        )
        if self.loading_label is not None:
            self.loading_label.setVisible(False)
        self.web.setVisible(True)
        if base_url is not None:
            self.web.setHtml(full_html, base_url)
        else:
            self.web.setHtml(full_html)



class ForecastPage(QWidget):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.chart_service = ForecastChartService(db)
        self.current_forecast: dict | None = None
        self.current_chart_data: dict | None = None
        self.analysis_visible = False
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(14)
        self.build()

    def build(self) -> None:
        add_btn = primary_button("+ Ajouter événement / récurrence")
        add_btn.clicked.connect(self.open_add_recurring_dialog)

        self.analysis_btn = QPushButton("Analyse de la période")
        self.analysis_btn.setCursor(Qt.PointingHandCursor)
        self.analysis_btn.clicked.connect(self.toggle_analysis_drawer)
        self.analysis_btn.setStyleSheet(
            "QPushButton {background:#FFFFFF; color:#0F172A; border:1px solid #CBD5E1; border-radius:14px; padding:12px 18px; font-size:15px; font-weight: bold;} "
            "QPushButton:hover {background:#F8FAFC; border-color:#2563EB; color:#2563EB;}"
        )

        manage_btn = QPushButton("Gérer les récurrences")
        manage_btn.setCursor(Qt.PointingHandCursor)
        manage_btn.clicked.connect(self.open_recurring_list_dialog)
        manage_btn.setStyleSheet(
            "QPushButton {background:#FFFFFF; color:#0F172A; border:1px solid #CBD5E1; border-radius:14px; padding:12px 18px; font-size:15px; font-weight: bold;} "
            "QPushButton:hover {background:#F8FAFC;}"
        )
        self.layout.addWidget(PageHeader("Prévisionnel de trésorerie", "Solde quotidien, opérations réelles et prévisionnelles", [self.analysis_btn, manage_btn, add_btn]))

        filters = Card()
        filter_layout = QGridLayout(filters)
        filter_layout.setContentsMargins(16, 12, 16, 12)
        filter_layout.setHorizontalSpacing(12)
        filter_layout.setVerticalSpacing(10)

        self.start_date = QDateEdit(QDate(2026, 6, 23))
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("dd/MM/yyyy")
        self.start_date.setMinimumWidth(170)
        self.start_date.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.start_date.dateChanged.connect(self.refresh)

        self.horizon = QComboBox()
        self.horizon.addItems(["30 jours", "60 jours", "90 jours"])
        self.horizon.setMinimumWidth(140)
        self.horizon.setMinimumContentsLength(8)
        self.horizon.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.horizon.setCurrentText("30 jours")
        self.horizon.currentIndexChanged.connect(self.refresh)

        self.scenario = QComboBox()
        self.scenario.setMinimumWidth(180)
        self.scenario.setMinimumContentsLength(14)
        self.scenario.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.scenario.addItems(["Prudent", "Réaliste", "Optimiste"])
        self.scenario.setCurrentText("Réaliste")
        self.scenario.currentIndexChanged.connect(self.refresh)

        self.granularity = QComboBox()
        self.granularity.addItems(["Vue quotidienne", "Vue mensuelle"])
        self.granularity.setMinimumWidth(160)
        self.granularity.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.granularity.currentIndexChanged.connect(self.refresh)

        self.account_filter = QComboBox()
        self.account_filter.setMinimumWidth(520)
        self.account_filter.setMinimumContentsLength(36)
        self.account_filter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.refresh_account_filter_options()
        self.account_filter.currentIndexChanged.connect(self.refresh)

        fields = [
            (0, 0, "Date de départ", self.start_date, 1),
            (0, 2, "Période", self.horizon, 1),
            (0, 4, "Scénario", self.scenario, 1),
            (1, 0, "Compte bancaire", self.account_filter, 3),
            (1, 4, "Vue", self.granularity, 1),
        ]
        for row, col, label, widget, span in fields:
            caption = QLabel(label)
            caption.setStyleSheet("font-weight: bold; color:#0F172A;")
            filter_layout.addWidget(caption, row, col)
            filter_layout.addWidget(widget, row, col + 1, 1, span)

        filter_layout.setColumnStretch(1, 2)
        filter_layout.setColumnStretch(3, 1)
        filter_layout.setColumnStretch(5, 1)
        filter_layout.setColumnStretch(6, 1)
        self.layout.addWidget(filters)

        self.kpi_grid = QGridLayout()
        self.kpi_grid.setSpacing(12)
        self.layout.addLayout(self.kpi_grid)

        main_area = QWidget()
        main_layout = QHBoxLayout(main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(16)

        self.chart = InteractiveForecastPlotlyChart(self)
        main_layout.addWidget(self.chart, stretch=1)

        self.analysis_drawer = self.build_analysis_drawer()
        self.analysis_drawer.setVisible(False)
        main_layout.addWidget(self.analysis_drawer)

        self.layout.addWidget(main_area, stretch=1)

        info = QLabel("Survol : solde et opérations du jour. Clic : popup du jour. Clic droit : menu de gestion des récurrences.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#64748B; padding-left:4px;")
        self.layout.addWidget(info)
        self.refresh()


    def build_analysis_drawer(self) -> QFrame:
        drawer = QFrame()
        drawer.setObjectName("AnalysisDrawer")
        drawer.setFixedWidth(460)
        drawer.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        drawer.setStyleSheet(
            "QFrame#AnalysisDrawer {"
            "background:#FFFFFF;"
            "border:1px solid #E5E7EB;"
            "border-radius:18px;"
            "}"
        )

        layout = QVBoxLayout(drawer)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Analyse de la période")
        title.setWordWrap(True)
        title.setStyleSheet("font-size:18px; font-weight: bold; color:#0F172A; background:transparent; border:none;")
        close_btn = QPushButton("×")
        close_btn.setFixedSize(34, 34)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton {background:#F8FAFC; border:1px solid #E5E7EB; border-radius:17px; font-size:20px; font-weight: bold; color:#334155;} "
            "QPushButton:hover {background:#EAF1FF; color:#2563EB;}"
        )
        close_btn.clicked.connect(self.close_analysis_drawer)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(close_btn)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        content = QWidget()
        content.setStyleSheet("background:transparent;")
        self.info_layout = QVBoxLayout(content)
        self.info_layout.setContentsMargins(0, 0, 4, 0)
        self.info_layout.setSpacing(14)

        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)
        return drawer

    def toggle_analysis_drawer(self) -> None:
        if not hasattr(self, "analysis_drawer"):
            return
        self.analysis_visible = not self.analysis_drawer.isVisible()
        self.analysis_drawer.setVisible(self.analysis_visible)
        self.analysis_btn.setText("Masquer l’analyse" if self.analysis_visible else "Analyse de la période")

    def close_analysis_drawer(self) -> None:
        if hasattr(self, "analysis_drawer"):
            self.analysis_visible = False
            self.analysis_drawer.setVisible(False)
        if hasattr(self, "analysis_btn"):
            self.analysis_btn.setText("Analyse de la période")


    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.refresh()


    def refresh_scenario_options(self) -> None:
        if not hasattr(self, "scenario"):
            return
        previous = self.scenario.currentText()
        self.scenario.blockSignals(True)
        self.scenario.clear()
        for name in ["Prudent", "Réaliste", "Optimiste"]:
            self.scenario.addItem(name)
        try:
            with self.db.connect() as conn:
                rows = list(
                    conn.execute(
                        """
                        SELECT name
                        FROM scenarios
                        WHERE deleted_at IS NULL
                          AND is_active = 1
                          AND is_reference = 0
                        ORDER BY updated_at DESC, name
                        """
                    )
                )
            for row in rows:
                name = row["name"]
                if self.scenario.findText(name) < 0:
                    self.scenario.addItem(name)
        except Exception:
            pass
        idx = self.scenario.findText(previous)
        self.scenario.setCurrentIndex(idx if idx >= 0 else self.scenario.findText("Réaliste"))
        self.scenario.blockSignals(False)



    def refresh_account_filter_options(self) -> None:
        """Refresh account selector from SQLite without recreating the page.

        The forecast page is instantiated once when the application starts.
        Accounts created later must still appear when the user comes back to
        the forecast screen.
        """
        if not hasattr(self, "account_filter"):
            return

        previous_id = self.account_filter.currentData()
        self.account_filter.blockSignals(True)
        self.account_filter.clear()
        self.account_filter.addItem("Tous les comptes bancaires", None)

        for acc in self.db.list_accounts():
            if acc["status"] != "Actif":
                continue
            identifier = (acc["identifier"] or "").strip()
            if identifier:
                label = f"{acc['bank']} — {acc['name']} — {identifier}"
            else:
                label = f"{acc['bank']} — {acc['name']}"
            self.account_filter.addItem(label, acc["id"])

        index = self.account_filter.findData(previous_id)
        self.account_filter.setCurrentIndex(index if index >= 0 else 0)
        self.account_filter.blockSignals(False)


    def refresh(self) -> None:
        if not hasattr(self, "kpi_grid"):
            return
        if hasattr(self, "account_filter"):
            self.refresh_account_filter_options()
        if hasattr(self, "scenario"):
            self.refresh_scenario_options()
        start = self.start_date.date().toString("yyyy-MM-dd")
        days = int(self.horizon.currentText().split()[0])
        scenario = self.scenario.currentText()
        account_id = self.account_filter.currentData() if hasattr(self, "account_filter") else None
        data = self.db.cash_forecast(start, days, scenario, account_id=account_id)
        self.current_forecast = data
        start_dt = datetime.strptime(start, "%Y-%m-%d").date()
        end_dt = start_dt + timedelta(days=days)
        granularity = "day" if self.granularity.currentText().startswith("Vue quotidienne") else "month"
        chart_data = self.chart_service.build_cashflow_chart_series(
            start_dt,
            end_dt,
            account_id=account_id,
            scenario=scenario,
            granularity=granularity,
        )
        self.current_chart_data = chart_data

        self.clear_layout(self.kpi_grid)
        cards = [
            KpiCard("Cash de départ", euro(data["starting_cash"]), "Liquidités actuelles", "blue"),
            KpiCard(f"Cash à J+{days}", euro(data["end_balance"]), f"Scénario {scenario.lower()}", "green" if data["end_balance"] >= 0 else "red"),
            KpiCard("Point bas", euro(data["min_balance"]), "Minimum projeté", "red" if data["min_balance"] < 5000 else "purple"),
            KpiCard("Entrées période", euro(data["total_in"]), "Opérations réelles + prévisionnelles", "green"),
            KpiCard("Sorties période", euro(data["total_out"]), "Opérations réelles + prévisionnelles", "red"),
        ]
        for col, card in enumerate(cards):
            self.kpi_grid.addWidget(card, 0, col)
        self.chart.set_chart_data(chart_data)
        self.refresh_info_card(data)

    def refresh_info_card(self, data: dict) -> None:
        if not hasattr(self, "info_layout"):
            return
        self.clear_layout(self.info_layout)

        alert_color = "#FEE2E2" if data.get("alert_level") == "critical" else "#FEF3C7" if data.get("alert_level") == "warning" else "#DCFCE7"
        alert_frame = QFrame()
        alert_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        alert_frame.setStyleSheet(f"background:{alert_color}; border:1px solid #E5E7EB; border-radius:14px;")
        alert_layout = QVBoxLayout(alert_frame)
        alert_layout.setContentsMargins(14, 12, 14, 12)
        alert_layout.setSpacing(4)

        alert_title = QLabel(str(data["alert"]))
        alert_title.setWordWrap(True)
        alert_title.setStyleSheet("font-weight: bold; color:#0F172A; background:transparent; border:none;")
        alert_detail = QLabel(f"Point bas : {euro(data['min_balance'])}\n{data.get('alert_detail', '')}")
        alert_detail.setWordWrap(True)
        alert_detail.setStyleSheet("color:#64748B; background:transparent; border:none;")
        alert_detail.setTextInteractionFlags(Qt.TextSelectableByMouse)

        alert_layout.addWidget(alert_title)
        alert_layout.addWidget(alert_detail)
        self.info_layout.addWidget(alert_frame)

        rules_frame = QFrame()
        rules_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        rules_frame.setStyleSheet("background:#F8FAFC; border:none; border-radius:12px;")
        rules_layout = QVBoxLayout(rules_frame)
        rules_layout.setContentsMargins(12, 10, 12, 10)
        rules_layout.setSpacing(4)

        rules_title = QLabel("Règle d’alerte point bas")
        rules_title.setWordWrap(True)
        rules_title.setStyleSheet("font-weight: bold; color:#334155; background:transparent; border:none;")
        rules_body = QLabel(
            "• Point bas < 0 € : alerte critique\n"
            "• Point bas < 5 000 € : vigilance\n"
            "• Point bas ≥ 5 000 € : aucune alerte critique"
        )
        rules_body.setWordWrap(True)
        rules_body.setStyleSheet("color:#475569; background:transparent; border:none;")
        rules_body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        rules_layout.addWidget(rules_title)
        rules_layout.addWidget(rules_body)
        self.info_layout.addWidget(rules_frame)

        selected_account_id = data.get("account_id")
        if selected_account_id is None:
            recurring_models = len(self.db.list_recurring_items())
        else:
            recurring_models = len([row for row in self.db.list_recurring_items(active_only=False) if row["account_id"] == selected_account_id and row["status"] == "Actif"])
        generated_events = len(data["events"])
        self.add_info_block("Compte sélectionné", data.get("account_label", "Tous les comptes"))
        self.add_info_block("Opérations sur la période", str(generated_events))
        self.add_info_block("Modèles récurrents actifs", str(recurring_models))
        self.add_info_block("Scénario", self.scenario.currentText())

        explanation = QLabel("<b>Différence :</b><br>Un modèle récurrent est une règle, par exemple “Loyer mensuel”.<br>Une opération prévisionnelle est une échéance générée par cette règle sur la période.")
        explanation.setWordWrap(True)
        explanation.setStyleSheet("color:#64748B; background:#F8FAFC; border-radius:12px; padding:10px;")
        self.info_layout.addWidget(explanation)
        self.info_layout.addStretch(1)

    def add_info_block(self, label: str, value: str, background: str = "transparent") -> None:
        block = QFrame()
        block.setStyleSheet(f"background:{background}; border:none; border-radius:12px;")
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(4)

        title = QLabel(label)
        title.setStyleSheet("font-weight: bold; color:#0F172A;")
        title.setWordWrap(True)
        value_label = QLabel(value)
        value_label.setWordWrap(True)
        value_label.setStyleSheet("color:#64748B;")
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        block_layout.addWidget(title)
        block_layout.addWidget(value_label)
        self.info_layout.addWidget(block)

    def tooltip_for_day(self, day: dict) -> str:
        header = f"<b>{format_date_fr(day['date'])}</b><br>Solde : {euro(day['balance'])}<br>"
        if not day["events"]:
            return header + "<span style='color:#64748B'>Aucune opération ce jour.</span>"
        lines = []
        for event in day["events"][:6]:
            lines.append(f"{event['name']} : {euro(event['amount'])}")
        more = "" if len(day["events"]) <= 6 else f"<br>+ {len(day['events']) - 6} autre(s)"
        return header + "<br>".join(lines) + more

    def open_day_popup(self, day: dict) -> None:
        dialog = DayOperationsDialog(self, day)
        if dialog.exec():
            self.refresh()

    def period_by_key(self, period: str) -> dict | None:
        if not self.current_chart_data:
            return None
        for point in self.current_chart_data.get("points", []):
            if str(point.get("period")) == str(period):
                return point
        return None

    def period_to_day_dialog_payload(self, point: dict) -> dict:
        return {
            "date": point.get("label", point.get("period", "")),
            "balance": point.get("closing_balance", 0),
            "in": point.get("credits", 0),
            "out": point.get("debits", 0),
            "net": point.get("net", 0),
            "events": point.get("events", []),
        }

    def open_period_by_key(self, period: str) -> None:
        point = self.period_by_key(period)
        if point:
            self.open_period_popup(point)

    def open_period_popup(self, point: dict) -> None:
        dialog = DayOperationsDialog(self, self.period_to_day_dialog_payload(point))
        if dialog.exec():
            self.refresh()

    def open_period_context_menu_by_key(self, period: str) -> None:
        point = self.period_by_key(period)
        if point:
            self.open_period_context_menu(point)

    # Compatibility aliases for existing daily interactions.
    def day_by_date(self, date: str) -> dict | None:
        return self.period_by_key(date)

    def open_day_by_date(self, date: str) -> None:
        self.open_period_by_key(date)

    def open_day_context_menu_by_date(self, date: str) -> None:
        self.open_period_context_menu_by_key(date)

    def open_day_context_menu(self, day: dict) -> None:
        # Accept both legacy day dicts and new chart period dicts.
        if "period" in day:
            self.open_period_context_menu(day)
        else:
            self.open_period_context_menu({
                "label": day.get("date", ""),
                "events": day.get("events", []),
            })

    def open_period_context_menu(self, point: dict) -> None:
        menu = QMenu(self)
        action_day = menu.addAction("Voir les opérations de cette période")
        menu.addSeparator()
        recurring_events = [event for event in point.get("events", []) if event.get("recurring_id")]
        recurring_actions = {}
        if recurring_events:
            manage_menu = menu.addMenu("Gérer les récurrences de la période")
            for event in recurring_events:
                label = f"{event['name']} — {event['account']}"
                sub = manage_menu.addMenu(label)
                recurring_actions[sub.addAction("Modifier la récurrence")] = ("edit", event["recurring_id"])
                recurring_actions[sub.addAction("Supprimer la récurrence")] = ("delete", event["recurring_id"])
        else:
            menu.addAction("Aucune récurrence sur cette période").setEnabled(False)
        selected = menu.exec(QCursor.pos())
        if selected == action_day:
            if "period" in point:
                self.open_period_popup(point)
            else:
                self.open_day_popup(point)
        elif selected in recurring_actions:
            action_type, recurring_id = recurring_actions[selected]
            if action_type == "edit":
                self.edit_recurring_item(recurring_id)
            elif action_type == "delete":
                self.delete_recurring_item(recurring_id)

    def open_add_recurring_dialog(self) -> None:
        accounts = self.db.list_accounts()
        dialog = RecurringDialog(accounts, parent=self, categories=self.db.category_names())
        if dialog.exec() == QDialog.Accepted:
            self.db.add_recurring_item(dialog.data())
            self.refresh()

    def open_recurring_list_dialog(self) -> None:
        dialog = RecurringListDialog(self.db, self)
        if dialog.exec():
            self.refresh()

    def edit_recurring_item(self, recurring_id: int) -> None:
        row = self.db.get_recurring_item(recurring_id)
        if not row:
            QMessageBox.warning(self, "Récurrence introuvable", "La récurrence sélectionnée est introuvable.")
            return
        dialog = RecurringDialog(self.db.list_accounts(), parent=self, row=row, categories=self.db.category_names())
        if dialog.exec() == QDialog.Accepted:
            self.db.update_recurring_item(recurring_id, dialog.data())
            self.refresh()

    def delete_recurring_item(self, recurring_id: int) -> None:
        row = self.db.get_recurring_item(recurring_id)
        if not row:
            return
        answer = QMessageBox.question(self, "Supprimer la récurrence", f"Supprimer la récurrence « {row['name']} » ?")
        if answer == QMessageBox.Yes:
            self.db.delete_recurring_item(recurring_id)
            self.refresh()

    def clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class DayOperationsDialog(QDialog):
    def __init__(self, parent: ForecastPage, day: dict) -> None:
        super().__init__(parent)
        self.page = parent
        self.day = day
        self.setWindowTitle(f"Opérations du {format_date_fr(day['date'])}")
        self.resize(980, 540)
        self.setMinimumSize(820, 460)
        self.build()

    def build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)

        title = QLabel(f"Opérations du {format_date_fr(self.day['date'])}")
        title.setStyleSheet("font-size:22px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel(f"Solde du jour : {euro(self.day['balance'])} — Entrées : {euro(self.day['in'])} — Sorties : {euro(self.day['out'])} — Net : {euro(self.day['net'])}")
        subtitle.setStyleSheet("color:#64748B;")
        layout.addWidget(subtitle)

        if not self.day["events"]:
            empty = QLabel("Aucune opération réelle ou prévisionnelle n’est prévue sur cette journée.")
            empty.setWordWrap(True)
            empty.setStyleSheet("background:#F8FAFC; border:1px dashed #CBD5E1; border-radius:14px; padding:18px; color:#64748B;")
            layout.addWidget(empty)
        else:
            self.table = QTableWidget(0, 6)
            self.table.setHorizontalHeaderLabels(["Libellé", "Catégorie", "Compte", "Montant", "Origine", "Scénario"])
            self.table.verticalHeader().setVisible(False)
            self.table.setEditTriggers(QTableWidget.NoEditTriggers)
            self.table.setSelectionBehavior(QTableWidget.SelectRows)
            self.table.setAlternatingRowColors(True)
            self.table.setFocusPolicy(Qt.NoFocus)
            self.table.setShowGrid(False)
            self.table.setStyleSheet(
                "QTableWidget { background:#FFFFFF; alternate-background-color:#F8FAFC; border:1px solid #E5E7EB; border-radius:12px; }"
                "QTableWidget::item:selected { background:#EAF1FF; color:#0F172A; border:none; }"
                "QTableWidget::item:hover { background:#F8FAFC; border:none; }"
                "QHeaderView::section { background:#F8FAFC; color:#64748B; font-weight: bold; border:none; border-bottom:1px solid #E5E7EB; padding:8px; }"
            )
            self.table.horizontalHeader().setStretchLastSection(True)
            self.table.setColumnWidth(0, 240)
            self.table.setColumnWidth(1, 140)
            self.table.setColumnWidth(2, 150)
            self.table.setColumnWidth(3, 110)
            self.table.setColumnWidth(4, 140)
            self.table.setContextMenuPolicy(Qt.CustomContextMenu)
            self.table.customContextMenuRequested.connect(self.open_context_menu)

            for idx, event in enumerate(self.day["events"]):
                self.table.insertRow(idx)
                values = [event["name"], event["category"], event["account"], euro(event["amount"]), event["source"], event["scenario"]]
                for col, value in enumerate(values):
                    clean_value = str(value).replace("\n", " ").replace("\r", " ").replace("�", "")
                    item = QTableWidgetItem(clean_value)
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    if col == 3:
                        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                        item.setForeground(Qt.red if event["amount"] < 0 else Qt.darkGreen)
                    if col == 0:
                        item.setData(Qt.UserRole, event.get("recurring_id"))
                    self.table.setItem(idx, col, item)
            layout.addWidget(self.table)
            hint = QLabel("Clic droit sur une ligne de récurrence pour la modifier ou la supprimer.")
            hint.setStyleSheet("color:#64748B;")
            layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def open_context_menu(self, pos: QPoint) -> None:
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        recurring_id = self.table.item(row, 0).data(Qt.UserRole)
        if not recurring_id:
            return
        menu = QMenu(self.table)
        edit_action = menu.addAction("Modifier la récurrence")
        delete_action = menu.addAction("Supprimer la récurrence")
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == edit_action:
            self.page.edit_recurring_item(recurring_id)
            self.accept()
        elif chosen == delete_action:
            self.page.delete_recurring_item(recurring_id)
            self.accept()


class RecurringDialog(QDialog):
    def __init__(self, accounts, parent=None, row=None, categories: list[str] | None = None) -> None:
        super().__init__(parent)
        self.row = row
        self.setWindowTitle("Modifier un événement prévisionnel" if row else "Ajouter un événement prévisionnel")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.account = QComboBox()
        self.account.addItem("Aucun compte spécifique", None)
        for acc in accounts:
            label = f"{acc['name']} — {acc['bank']}"
            self.account.addItem(label, acc["id"])

        self.name = QLineEdit()
        self.name.setPlaceholderText("Ex. Loyer, Retraite, Assurance")
        self.category = QComboBox()
        self.category.addItems(list(categories or ["Revenus", "Logement", "Alimentation", "Transport", "Loisirs", "Santé", "Énergie", "Impôts", "Assurances", "Épargne", "Investissement", "Autre"]))
        self.amount = QDoubleSpinBox()
        self.amount.setRange(0, 100000000)
        self.amount.setDecimals(2)
        self.amount.setSuffix(" €")
        self.frequency = QComboBox()
        self.frequency.addItems(["Ponctuel", "Mensuel", "Hebdomadaire", "Trimestriel", "Annuel"])
        self.next_date = QDateEdit(QDate.currentDate())
        self.next_date.setCalendarPopup(True)
        self.scenario = QComboBox()
        self.scenario.addItems(["Prudent", "Réaliste", "Optimiste"])
        self.scenario.setCurrentText("Réaliste")
        self.status = QComboBox()
        self.status.addItems(["Actif", "Inactif"])

        for label, widget in [
            ("Compte", self.account), ("Nom", self.name), ("Catégorie", self.category),
            ("Montant", self.amount), ("Fréquence", self.frequency),
            ("Prochaine date", self.next_date), ("Scénario", self.scenario), ("Statut", self.status),
        ]:
            form.addRow(label, widget)
        layout.addLayout(form)

        help_label = QLabel("Choisissez Ponctuel pour une opération unique, ou une fréquence pour une récurrence. Le sens de la catégorie applique le signe.")
        help_label.setStyleSheet("color:#64748B;")
        layout.addWidget(help_label)

        if row:
            self.populate_from_row(row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def populate_from_row(self, row) -> None:
        self.account.setCurrentIndex(max(0, self.account.findData(row["account_id"])))
        self.name.setText(row["name"] or "")
        self.category.setCurrentText(row["category"] or "Autre")
        self.amount.setValue(abs(float(row["amount"] or 0)))
        self.frequency.setCurrentText(row["frequency"] or "Mensuel")
        y, m, d = [int(v) for v in (row["next_date"] or QDate.currentDate().toString("yyyy-MM-dd")).split('-')]
        self.next_date.setDate(QDate(y, m, d))
        self.scenario.setCurrentText(row["scenario"] or "Réaliste")
        self.status.setCurrentText(row["status"] or "Actif")

    def data(self) -> dict:
        return {
            "account_id": self.account.currentData(),
            "name": self.name.text().strip() or "Nouvelle récurrence",
            "category": self.category.currentText(),
            "amount": float(self.amount.value()),
            "frequency": self.frequency.currentText(),
            "next_date": self.next_date.date().toString("yyyy-MM-dd"),
            "end_date": None,
            "scenario": self.scenario.currentText(),
            "status": self.status.currentText(),
        }


class RecurringListDialog(QDialog):
    def __init__(self, db: Database, parent=None) -> None:
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Liste des récurrences")
        self.resize(980, 560)
        self.setMinimumSize(860, 480)
        self.build()
        self.refresh_table()

    def build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)

        title = QLabel("Récurrences par compte bancaire")
        title.setStyleSheet("font-size:22px; font-weight: bold;")
        layout.addWidget(title)

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Compte"))
        self.account_filter = QComboBox()
        self.account_filter.addItem("Tous les comptes", None)
        for acc in self.db.list_accounts():
            self.account_filter.addItem(f"{acc['name']} — {acc['bank']}", acc['id'])
        self.account_filter.currentIndexChanged.connect(self.refresh_table)
        filters.addWidget(self.account_filter)
        filters.addStretch(1)
        layout.addLayout(filters)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Nom", "Compte", "Catégorie", "Montant", "Fréquence", "Prochaine date", "Scénario", "Statut"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setShowGrid(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.setStyleSheet(
            "QTableWidget { background:#FFFFFF; alternate-background-color:#F8FAFC; border:1px solid #E5E7EB; border-radius:12px; }"
            "QTableWidget::item { border:none; padding:8px 6px; }"
            "QTableWidget::item:selected { background:#EAF1FF; color:#0F172A; border:none; }"
            "QTableWidget::item:hover { background:#F8FAFC; border:none; }"
            "QHeaderView::section { background:#F8FAFC; color:#64748B; font-weight: bold; border:none; border-bottom:1px solid #E5E7EB; padding:8px; }"
        )
        self.table.customContextMenuRequested.connect(self.open_context_menu)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        actions = QHBoxLayout()
        self.edit_btn = QPushButton("Modifier")
        self.delete_btn = QPushButton("Supprimer")
        self.close_btn = QPushButton("Fermer")
        self.edit_btn.clicked.connect(self.edit_selected)
        self.delete_btn.clicked.connect(self.delete_selected)
        self.close_btn.clicked.connect(self.accept)
        actions.addWidget(self.edit_btn)
        actions.addWidget(self.delete_btn)
        actions.addStretch(1)
        actions.addWidget(self.close_btn)
        layout.addLayout(actions)

    def rows(self):
        rows = self.db.list_recurring_items(active_only=False)
        acc_id = self.account_filter.currentData()
        if acc_id is None:
            return rows
        return [r for r in rows if r["account_id"] == acc_id]

    def refresh_table(self) -> None:
        rows = self.rows()
        self.table.setRowCount(0)
        for r, row in enumerate(rows):
            self.table.insertRow(r)
            values = [
                row["name"],
                row["account_name"] or "Tous comptes",
                row["category"] or "Autre",
                euro(float(row["amount"] or 0)),
                row["frequency"],
                format_date_fr(row["next_date"]),
                row["scenario"],
                row["status"],
            ]
            for c, value in enumerate(values):
                clean_value = str(value).replace("\n", " ").replace("\r", " ").replace("�", "")
                item = QTableWidgetItem(clean_value)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if c == 0:
                    item.setData(Qt.UserRole, row["id"])
                if c == 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(r, c, item)
        if rows:
            self.table.selectRow(0)

    def selected_id(self):
        item = self.table.item(self.table.currentRow(), 0)
        return item.data(Qt.UserRole) if item else None

    def open_context_menu(self, pos: QPoint) -> None:
        item = self.table.itemAt(pos)
        if not item:
            return
        self.table.selectRow(item.row())
        menu = QMenu(self.table)
        edit_action = menu.addAction("Modifier")
        delete_action = menu.addAction("Supprimer")
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == edit_action:
            self.edit_selected()
        elif chosen == delete_action:
            self.delete_selected()

    def edit_selected(self) -> None:
        recurring_id = self.selected_id()
        if not recurring_id:
            return
        row = self.db.get_recurring_item(recurring_id)
        dialog = RecurringDialog(self.db.list_accounts(), parent=self, row=row, categories=self.db.category_names())
        if dialog.exec() == QDialog.Accepted:
            self.db.update_recurring_item(recurring_id, dialog.data())
            self.refresh_table()

    def delete_selected(self) -> None:
        recurring_id = self.selected_id()
        if not recurring_id:
            return
        row = self.db.get_recurring_item(recurring_id)
        if QMessageBox.question(self, "Supprimer la récurrence", f"Supprimer la récurrence « {row['name']} » ?") == QMessageBox.Yes:
            self.db.delete_recurring_item(recurring_id)
            self.refresh_table()
