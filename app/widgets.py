from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QBrush
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QToolTip,
)
from app.theme import COLORS


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)


class KpiCard(Card):
    def __init__(self, title: str, value: str, hint: str = "", accent: str = "blue") -> None:
        super().__init__()
        self.accent = COLORS.get(accent, COLORS["blue"])
        self.setMinimumHeight(104)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(7)

        top = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {self.accent}; font-size: 14px;")
        top.addWidget(title_label)
        top.addStretch(1)
        top.addWidget(dot)

        value_label = QLabel(value)
        value_label.setObjectName("CardValue")
        hint_label = QLabel(hint)
        hint_label.setObjectName("CardHint")

        layout.addLayout(top)
        layout.addWidget(value_label)
        layout.addWidget(hint_label)


class PageHeader(QWidget):
    def __init__(self, title: str, subtitle: str, actions: list[QPushButton] | None = None) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(12)

        texts = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("PageSubtitle")
        texts.addWidget(title_label)
        texts.addWidget(subtitle_label)
        layout.addLayout(texts)
        layout.addStretch(1)

        for button in actions or []:
            layout.addWidget(button)


def primary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("PrimaryButton")
    button.setCursor(Qt.PointingHandCursor)
    return button


def secondary_button(text: str) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("SecondaryButton")
    button.setCursor(Qt.PointingHandCursor)
    return button


class StepLabel(QLabel):
    def __init__(self, number: int, text: str, active: bool = False) -> None:
        super().__init__(f"{number}. {text}")
        color = COLORS["blue"] if active else COLORS["muted"]
        bg = COLORS["blue_soft"] if active else "#F8FAFC"
        self.setStyleSheet(
            f"background:{bg}; color:{color}; border:1px solid {COLORS['border']}; "
            "border-radius:10px; padding:8px 10px; font-weight: bold;"
        )


class LineChart(Card):
    def __init__(
        self,
        title: str,
        series: dict[str, list[float]],
        labels: list[str],
        parent: QWidget | None = None,
        subtitle: str = "",
        area_fill: bool = True,
    ) -> None:
        super().__init__(parent)
        self.title = title
        self.subtitle = subtitle
        self.series = series
        self.labels = labels
        self.area_fill = area_fill
        self.setMinimumHeight(350)
        self.setMouseTracking(True)
        self.palette = [COLORS["green"], COLORS["blue"], COLORS["red"], COLORS["purple"]]
        self._tooltip_points: list[dict] = []

    def _format_x_label(self, label: str) -> str:
        if isinstance(label, str) and len(label) == 10 and label[4] == "-" and label[7] == "-":
            return f"{label[8:10]}/{label[5:7]}"
        return str(label)

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(24, 20, -24, -18)

        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(QFont("Segoe UI", 13, QFont.Bold))
        painter.drawText(rect.left(), rect.top() + 4, self.title)
        if self.subtitle:
            painter.setPen(QColor(COLORS["muted"]))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(rect.left(), rect.top() + 24, self.subtitle)

        chart = rect.adjusted(6, 56, -6, -74)
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        for i in range(5):
            y = chart.top() + chart.height() * i / 4
            painter.drawLine(chart.left(), y, chart.right(), y)
        painter.drawLine(chart.left(), chart.bottom(), chart.right(), chart.bottom())

        self._tooltip_points = []
        all_values = [v for values in self.series.values() for v in values]
        if not all_values:
            return
        minimum = min(all_values)
        maximum = max(all_values)
        if minimum == maximum:
            maximum += 1
        padding = (maximum - minimum) * 0.18
        minimum -= padding
        maximum += padding

        def point(index: int, value: float) -> tuple[float, float]:
            x = chart.left() + chart.width() * index / max(1, len(self.labels) - 1)
            y = chart.bottom() - chart.height() * (value - minimum) / (maximum - minimum)
            return x, y

        # Y-axis reference labels
        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(QFont("Segoe UI", 8))
        for i in range(5):
            value = maximum - (maximum - minimum) * i / 4
            y = chart.top() + chart.height() * i / 4
            painter.drawText(QRectF(chart.left() - 8, y - 8, 62, 18), Qt.AlignLeft, f"{value/1000:.0f} k€")

        for color_index, (name, values) in enumerate(self.series.items()):
            color = QColor(self.palette[color_index % len(self.palette)])
            path = QPainterPath()
            first_x, first_y = point(0, values[0])
            path.moveTo(first_x, first_y)
            for i, value in enumerate(values[1:], start=1):
                x, y = point(i, value)
                path.lineTo(x, y)

            if self.area_fill and color_index == 1:
                fill_path = QPainterPath(path)
                last_x, _ = point(len(values) - 1, values[-1])
                fill_path.lineTo(last_x, chart.bottom())
                fill_path.lineTo(first_x, chart.bottom())
                fill_path.closeSubpath()
                fill = QColor(color)
                fill.setAlpha(24)
                painter.fillPath(fill_path, fill)

            pen = QPen(color, 3)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)

            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            for i, value in enumerate(values):
                x, y = point(i, value)
                painter.drawEllipse(QRectF(x - 4, y - 4, 8, 8))
                if i < len(self.labels):
                    previous = values[i - 1] if i > 0 and i - 1 < len(values) else None
                    self._tooltip_points.append({
                        "x": x,
                        "y": y,
                        "index": i,
                        "series": name,
                        "label": self.labels[i],
                        "value": float(value or 0),
                        "previous": None if previous is None else float(previous or 0),
                    })

            legend_x = chart.left() + color_index * 140
            legend_y = rect.bottom() - 8
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(QRectF(legend_x, legend_y - 10, 10, 10), 5, 5)
            painter.setPen(QColor(COLORS["muted"]))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(legend_x + 16, legend_y, name)

        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(QFont("Segoe UI", 8))
        label_count = len(self.labels)
        if label_count:
            max_ticks = 8
            step = max(1, (label_count - 1) // max(1, max_ticks - 1))
            tick_indexes = list(range(0, label_count, step))
            if tick_indexes[-1] != label_count - 1:
                tick_indexes.append(label_count - 1)
            tick_indexes = sorted(set(tick_indexes))
            for i in tick_indexes:
                x, _ = point(i, minimum)
                painter.setPen(QPen(QColor(COLORS["border"]), 1))
                painter.drawLine(x, chart.bottom(), x, chart.bottom() + 4)
                painter.setPen(QColor(COLORS["muted"]))
                painter.drawText(QRectF(x - 34, chart.bottom() + 8, 68, 18), Qt.AlignCenter, self._format_x_label(self.labels[i]))

    @staticmethod
    def _format_money(value: float) -> str:
        return f"{float(value or 0):,.2f} €".replace(",", " ").replace(".", ",")

    def nearest_tooltip_point(self, pos: QPoint) -> dict | None:
        if not self._tooltip_points:
            return None
        best = None
        best_distance = 999999.0
        for item in self._tooltip_points:
            dx = float(pos.x()) - float(item["x"])
            dy = float(pos.y()) - float(item["y"])
            distance = (dx * dx + dy * dy) ** 0.5
            if distance < best_distance:
                best = item
                best_distance = distance
        return best if best is not None and best_distance <= 22 else None

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        point = self.nearest_tooltip_point(event.pos())
        if point is None:
            QToolTip.hideText()
            return
        previous = point.get("previous")
        variation = ""
        if previous is not None:
            delta = point["value"] - previous
            sign = "+" if delta >= 0 else ""
            variation = f"<br>Variation : {sign}{self._format_money(delta)}"
        QToolTip.showText(
            event.globalPos(),
            (
                f"<b>{self._format_x_label(point['label'])}</b><br>"
                f"{point['series']} : {self._format_money(point['value'])}"
                f"{variation}"
            ),
            self,
        )


class DonutChart(Card):
    def __init__(self, title: str, data: dict[str, float], parent: QWidget | None = None, center_label: str = "total") -> None:
        super().__init__(parent)
        self.title = title
        self.data = data
        self.center_label = center_label
        self.setMinimumHeight(300)
        self.palette = [COLORS["blue"], COLORS["green"], COLORS["amber"], COLORS["purple"], COLORS["info"], COLORS["red"], "#94A3B8"]

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(22, 20, -22, -18)

        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(QFont("Segoe UI", 13, QFont.Bold))
        painter.drawText(rect.left(), rect.top() + 5, self.title)

        total = sum(abs(value) for value in self.data.values())
        if total <= 0:
            return

        size = min(rect.width() * 0.40, rect.height() - 64)
        pie_rect = QRectF(rect.left() + 2, rect.top() + 60, size, size)
        start_angle = 90 * 16

        for index, (_label, value) in enumerate(self.data.items()):
            span = int(-360 * 16 * abs(value) / total)
            color = QColor(self.palette[index % len(self.palette)])
            painter.setPen(QPen(color, 22))
            painter.drawArc(pie_rect, start_angle, span)
            start_angle += span

        center = pie_rect.center()
        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(QFont("Segoe UI", 16, QFont.Bold))
        painter.drawText(QRectF(center.x() - 70, center.y() - 20, 140, 28), Qt.AlignCenter, f"{total/1000:.0f} k€")
        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRectF(center.x() - 70, center.y() + 8, 140, 20), Qt.AlignCenter, self.center_label)

        legend_x = pie_rect.right() + 28
        legend_y = pie_rect.top() + 6
        painter.setFont(QFont("Segoe UI", 9))
        for index, (label, value) in enumerate(self.data.items()):
            y = legend_y + index * 27
            color = QColor(self.palette[index % len(self.palette)])
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(QRectF(legend_x, y, 10, 10), 5, 5)
            painter.setPen(QColor(COLORS["text"]))
            percent = abs(value) / total * 100
            amount = f"{abs(value)/1000:.0f} k€" if abs(value) >= 1000 else f"{abs(value):.0f} €"
            painter.drawText(legend_x + 18, y + 10, f"{label}  {percent:.0f}%  ({amount})")
