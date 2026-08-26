from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from app.widgets import Card, PageHeader


class PremiumLockedPage(QWidget):
    """Page d'information affichée lorsqu'un module Premium est verrouillé."""

    def __init__(
        self,
        title: str,
        description: str,
        premium_benefits: list[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        layout.addWidget(
            PageHeader(
                f"{title} — Premium",
                "Fonctionnalité réservée aux éditions Premium de Valoria Vision",
            )
        )

        card = Card()
        body = QVBoxLayout(card)
        body.setContentsMargins(24, 22, 24, 22)
        body.setSpacing(14)

        badge = QLabel("PREMIUM")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedWidth(110)
        badge.setStyleSheet(
            "background:#EEF2FF; color:#4338CA; border:1px solid #C7D2FE; "
            "border-radius:12px; padding:7px 10px; font-weight:bold;"
        )
        body.addWidget(badge)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size:24px; font-weight:bold; color:#0F172A;")
        body.addWidget(title_label)

        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setStyleSheet("font-size:15px; color:#475569;")
        body.addWidget(description_label)

        benefits = list(premium_benefits or [])
        if benefits:
            benefits_label = QLabel(
                "<b>Ce module permet notamment :</b><br><br>"
                + "<br>".join(f"• {item}" for item in benefits)
            )
            benefits_label.setWordWrap(True)
            benefits_label.setStyleSheet("color:#334155; line-height:1.5;")
            body.addWidget(benefits_label)

        note = QLabel(
            "Les fonctions Prudent, Réaliste et Optimiste du Prévisionnel restent disponibles "
            "dans le socle standard. Le module Scénarios concerne les simulations avancées et personnalisées."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "background:#F8FAFC; border-radius:12px; padding:12px; color:#64748B;"
        )
        body.addWidget(note)

        layout.addWidget(card)
        layout.addStretch(1)
