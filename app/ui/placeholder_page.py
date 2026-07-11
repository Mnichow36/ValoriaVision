from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget
from app.widgets import Card, PageHeader


class PlaceholderPage(QWidget):
    def __init__(self, title: str, subtitle: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)
        layout.addWidget(PageHeader(title, subtitle))
        card = Card()
        card_layout = QVBoxLayout(card)
        message = QLabel("Cet écran est prévu dans la roadmap. Les écrans primaires validés sont déjà structurés dans cette V0.1.")
        message.setWordWrap(True)
        message.setStyleSheet("font-size: 15px; color: #64748B;")
        card_layout.addWidget(message)
        layout.addWidget(card)
        layout.addStretch(1)
