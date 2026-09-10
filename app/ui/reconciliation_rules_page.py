from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.widgets import Card, primary_button, secondary_button


class ReconciliationRulesPage(QWidget):
    """Understandable and atomic editor for R8 automatic matching rules."""

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.fields: dict[str, QWidget] = {}
        self.build()
        self.load_rules()

    def build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 8, 8)
        layout.setSpacing(12)

        intro = Card()
        intro_layout = QVBoxLayout(intro)
        title = QLabel("Règles de rapprochement automatique")
        title.setStyleSheet("font-size:18px; font-weight:bold;")
        description = QLabel(
            "Ces règles comparent chaque transaction réelle aux occurrences "
            "prévisionnelles. Toute modification réévalue automatiquement les "
            "décisions existantes et conserve leur historique."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color:#64748B;")
        intro_layout.addWidget(title)
        intro_layout.addWidget(description)
        layout.addWidget(intro)

        layout.addWidget(self.required_card())
        layout.addWidget(self.tolerances_card())
        layout.addWidget(self.score_card())
        layout.addWidget(self.thresholds_card())

        actions = QHBoxLayout()
        reset = secondary_button("Valeurs recommandées")
        reset.clicked.connect(self.load_defaults)
        save = primary_button("Enregistrer et réévaluer")
        save.clicked.connect(self.save_rules)
        actions.addStretch(1)
        actions.addWidget(reset)
        actions.addWidget(save)
        layout.addLayout(actions)
        layout.addStretch(1)

        scroll.setWidget(page)
        root.addWidget(scroll)

    def card(self, title_text: str, help_text: str) -> tuple[Card, QFormLayout]:
        card = Card()
        layout = QVBoxLayout(card)
        title = QLabel(title_text)
        title.setStyleSheet("font-size:16px; font-weight:bold;")
        help_label = QLabel(help_text)
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color:#64748B;")
        form = QFormLayout()
        form.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(help_label)
        layout.addLayout(form)
        return card, form

    def spin(self, minimum: int, maximum: int, suffix: str = "") -> QSpinBox:
        field = QSpinBox()
        field.setRange(minimum, maximum)
        field.setSuffix(suffix)
        field.setMinimumWidth(170)
        return field

    def decimal(
        self,
        minimum: float,
        maximum: float,
        decimals: int,
        suffix: str = "",
    ) -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setRange(minimum, maximum)
        field.setDecimals(decimals)
        field.setSuffix(suffix)
        field.setMinimumWidth(170)
        return field

    def required_card(self) -> Card:
        card, form = self.card(
            "Critères obligatoires",
            "Si un critère obligatoire diffère, le candidat est immédiatement écarté.",
        )
        account = QCheckBox("Exiger le même compte bancaire")
        direction = QCheckBox("Exiger le même sens Débit / Crédit")
        self.fields["same_account_required"] = account
        self.fields["same_direction_required"] = direction
        form.addRow("Compte", account)
        form.addRow("Sens", direction)
        return card

    def tolerances_card(self) -> Card:
        card, form = self.card(
            "Tolérances",
            "Un candidat hors tolérance de date ou de montant n’entre pas dans le score.",
        )
        date_days = self.spin(0, 365, " jour(s)")
        amount_absolute = self.decimal(0, 1_000_000, 2, " €")
        amount_relative = self.decimal(0, 100, 2, " %")
        label_minimum = self.decimal(0, 100, 0, " %")
        self.fields.update(
            {
                "date_tolerance_days": date_days,
                "amount_tolerance_absolute": amount_absolute,
                "amount_tolerance_relative": amount_relative,
                "label_similarity_minimum": label_minimum,
            }
        )
        form.addRow("Écart maximal de date", date_days)
        form.addRow("Écart maximal en euros", amount_absolute)
        form.addRow("Écart maximal en pourcentage", amount_relative)
        form.addRow("Similarité minimale du libellé", label_minimum)
        return card

    def score_card(self) -> Card:
        card, form = self.card(
            "Composition du score",
            "Les quatre pondérations principales doivent totaliser exactement 100. "
            "Les références disponibles peuvent ajouter un bonus, sans dépasser 100.",
        )
        for field_name, label in (
            ("date_weight", "Date"),
            ("amount_weight", "Montant"),
            ("label_weight", "Libellé"),
            ("category_weight", "Catégorie"),
            ("counterparty_match_bonus", "Bonus bénéficiaire / émetteur"),
            ("external_reference_match_bonus", "Bonus référence bancaire"),
        ):
            field = self.spin(0, 100, " pt")
            self.fields[field_name] = field
            form.addRow(label, field)
        return card

    def thresholds_card(self) -> Card:
        card, form = self.card(
            "Décision",
            "Au-dessus du seuil Auto, le rapprochement est créé. Entre les deux "
            "seuils, il est proposé À vérifier. En dessous, il reste À traiter.",
        )
        review = self.spin(0, 100, " / 100")
        automatic = self.spin(0, 100, " / 100")
        ambiguity = self.spin(0, 100, " pt")
        self.fields.update(
            {
                "review_threshold": review,
                "auto_threshold": automatic,
                "ambiguity_min_delta": ambiguity,
            }
        )
        form.addRow("Seuil À vérifier", review)
        form.addRow("Seuil Rapprochée auto", automatic)
        form.addRow("Écart minimal entre candidats", ambiguity)
        return card

    def set_values(self, rules) -> None:
        for name, field in self.fields.items():
            value = getattr(rules, name)
            if isinstance(field, QCheckBox):
                field.setChecked(bool(value))
            elif name in {"amount_tolerance_relative", "label_similarity_minimum"}:
                field.setValue(float(value) * 100)
            else:
                field.setValue(value)

    def load_rules(self) -> None:
        self.set_values(self.db.reconciliation_rules())

    def load_defaults(self) -> None:
        from app.services.reconciliation import ReconciliationRules

        self.set_values(ReconciliationRules())

    def values(self) -> dict[str, object]:
        values: dict[str, object] = {}
        for name, field in self.fields.items():
            key = f"reconciliation.{name}"
            if isinstance(field, QCheckBox):
                values[key] = field.isChecked()
            elif name in {"amount_tolerance_relative", "label_similarity_minimum"}:
                values[key] = field.value() / 100
            else:
                values[key] = field.value()
        return values

    def save_rules(self) -> None:
        try:
            rules = self.db.set_reconciliation_settings(self.values())
        except Exception as exc:
            QMessageBox.critical(self, "Règles de rapprochement", str(exc))
            return
        QMessageBox.information(
            self,
            "Règles de rapprochement",
            "Règles enregistrées. Les transactions concernées ont été réévaluées.\n\n"
            f"Seuil Auto : {rules.auto_threshold}/100 — "
            f"À vérifier : {rules.review_threshold}/100.",
        )
