from pathlib import Path
from datetime import date, datetime
from typing import Any

ASSET_DIR = Path(__file__).resolve().parent / "assets"
COMBO_ARROW = (ASSET_DIR / "chevron_down.svg").as_posix()

COLORS = {
    "navy": "#071A3D",
    "navy_hover": "#0B2554",
    "blue": "#2563EB",
    "blue_soft": "#EAF1FF",
    "background": "#F7F9FC",
    "card": "#FFFFFF",
    "text": "#0F172A",
    "muted": "#64748B",
    "border": "#E5E7EB",
    "green": "#16A34A",
    "red": "#DC2626",
    "amber": "#F59E0B",
    "info": "#0EA5E9",
    "purple": "#7C3AED",
}

APP_STYLESHEET = f"""
QMainWindow {{
    background: {COLORS['background']};
}}
QWidget {{
    font-family: 'Segoe UI', 'Inter', Arial, sans-serif;
    color: {COLORS['text']};
    font-size: 13px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #CBD5E1;
    border-radius: 5px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: #CBD5E1;
    border-radius: 5px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
QFrame#Sidebar {{
    background: {COLORS['navy']};
}}
QLabel#AppTitle {{
    color: white;
    font-size: 22px;
    font-weight: bold;
}}
QLabel#AppSubtitle {{
    color: #BFD2FF;
    font-size: 11px;
}}
QPushButton#NavButton {{
    background: transparent;
    color: #DDE7FF;
    border: none;
    text-align: left;
    padding: 12px 16px;
    border-radius: 12px;
    font-weight: bold;
}}
QPushButton#NavButton:hover {{
    background: {COLORS['navy_hover']};
}}
QPushButton#NavButton:checked {{
    background: {COLORS['blue']};
    color: white;
}}
QPushButton#PrimaryButton {{
    background: {COLORS['blue']};
    color: white;
    border: none;
    border-radius: 12px;
    padding: 10px 16px;
    font-weight: bold;
}}
QPushButton#PrimaryButton:hover {{
    background: #1D4ED8;
}}
QPushButton#SecondaryButton {{
    background: white;
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
    padding: 10px 16px;
    font-weight: bold;
}}
QPushButton#SecondaryButton:hover {{
    border: 1px solid {COLORS['blue']};
    color: {COLORS['blue']};
}}
QFrame#Card {{
    background: {COLORS['card']};
    border: 1px solid {COLORS['border']};
    border-radius: 18px;
}}
QLabel#PageTitle {{
    font-size: 26px;
    font-weight: bold;
    color: {COLORS['text']};
}}
QLabel#PageSubtitle {{
    font-size: 13px;
    color: {COLORS['muted']};
}}
QLabel#CardTitle {{
    font-size: 12px;
    font-weight: bold;
    color: {COLORS['muted']};
}}
QLabel#CardValue {{
    font-size: 26px;
    font-weight: bold;
    color: {COLORS['text']};
}}
QLabel#CardHint {{
    font-size: 12px;
    color: {COLORS['muted']};
}}
QTableWidget {{
    background: white;
    border: 1px solid {COLORS['border']};
    border-radius: 14px;
    gridline-color: {COLORS['border']};
    selection-background-color: {COLORS['blue_soft']};
    selection-color: {COLORS['text']};
}}
QHeaderView::section {{
    background: #F8FAFC;
    color: {COLORS['muted']};
    border: none;
    border-bottom: 1px solid {COLORS['border']};
    padding: 11px;
    font-weight: bold;
}}
QLineEdit, QDoubleSpinBox {{
    background: white;
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    padding: 9px 12px;
    min-height: 24px;
}}
QComboBox, QDateEdit {{
    background: white;
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    padding: 9px 44px 9px 14px;
    min-height: 24px;
}}
QComboBox:focus, QDateEdit:focus, QLineEdit:focus, QDoubleSpinBox:focus {{
    border: 1px solid {COLORS['blue']};
}}
QComboBox::drop-down, QDateEdit::drop-down {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 34px;
    border-left: 1px solid {COLORS['border']};
    border-top-right-radius: 10px;
    border-bottom-right-radius: 10px;
    background: #F8FAFC;
}}
QComboBox::drop-down:hover, QDateEdit::drop-down:hover {{
    background: #EEF2FF;
}}
QComboBox::down-arrow, QDateEdit::down-arrow {{
    image: url({COMBO_ARROW});
    width: 14px;
    height: 14px;
}}
QComboBox QAbstractItemView {{
    background: white;
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['blue_soft']};
    selection-color: {COLORS['text']};
    padding: 4px;
}}
QTabWidget::pane {{
    border: none;
}}
QTabBar::tab {{
    background: transparent;
    color: {COLORS['muted']};
    padding: 10px 16px;
    font-weight: bold;
}}
QTabBar::tab:selected {{
    color: {COLORS['blue']};
    border-bottom: 3px solid {COLORS['blue']};
}}
"""


def euro(value: float) -> str:
    """Format money for user-facing screens using French cents."""
    return f"{float(value or 0):,.2f} €".replace(",", " ").replace(".", ",")


def euro_precise(value: float) -> str:
    """Display an exact amount with cents for audit/diagnostic screens."""
    return euro(value)


def format_date_fr(value: Any) -> str:
    """Return a French date label while keeping ISO dates internally."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    text = str(value or "").strip()
    if not text:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19] if "%H" in fmt else text[:10], fmt).strftime("%d/%m/%Y")
        except ValueError:
            pass
    return text


def qdate_to_iso(qdate: Any) -> str:
    return qdate.toString("yyyy-MM-dd") if hasattr(qdate, "toString") else str(qdate or "")
