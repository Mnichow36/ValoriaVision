from __future__ import annotations

from app.database import Database
from app.services.scenario_hypothesis_service import ScenarioHypothesisService


_PATCH_MARKER = "_r7_2_lot6_scenario_hypotheses_applied"


def apply_r7_2_scenario_hypotheses_patch() -> None:
    """Raccorde les hypothèses de scénarios standards au moteur prévisionnel.

    Lot 6.1 :
    - Prudent / Réaliste / Optimiste produisent des projections distinctes ;
    - les coefficients sont persistés dans `settings` ;
    - seules les récurrences prévisionnelles sont ajustées ;
    - l'hypothèse active est expliquée dans le Prévisionnel ;
    - un bouton Paramétrer ouvre l'édition des coefficients ;
    - le dialogue de scénario est sécurisé contre un ancien appel UX erroné.
    """
    if getattr(Database, _PATCH_MARKER, False):
        return

    original_forecast_events = Database.forecast_events

    def forecast_events_with_hypotheses(
        self,
        start_date: str = "2026-06-23",
        horizon_days: int = 90,
        scenario: str = "Réaliste",
        account_id: int | None = None,
    ) -> list[dict]:
        events = original_forecast_events(
            self,
            start_date=start_date,
            horizon_days=horizon_days,
            scenario=scenario,
            account_id=account_id,
        )
        service = ScenarioHypothesisService(self)
        if str(scenario or "").strip() not in service.BUILT_INS:
            return events
        return [service.apply_event(scenario, event) for event in events]

    def scenario_hypothesis(self, scenario_name: str) -> dict:
        service = ScenarioHypothesisService(self)
        hypothesis = service.get(scenario_name)
        if hypothesis is None:
            return {
                "name": str(scenario_name or ""),
                "custom": True,
                "description": service.describe(scenario_name),
            }
        return {
            "name": hypothesis.name,
            "custom": False,
            "income_pct": hypothesis.income_pct,
            "expense_pct": hypothesis.expense_pct,
            "description": hypothesis.description,
        }

    Database.forecast_events = forecast_events_with_hypotheses
    Database.scenario_hypothesis = scenario_hypothesis
    setattr(Database, _PATCH_MARKER, True)

    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QDialog,
            QDialogButtonBox,
            QDoubleSpinBox,
            QFormLayout,
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QMessageBox,
            QPushButton,
            QVBoxLayout,
        )
        from app.ui.forecast_page import ForecastPage

        class ScenarioHypothesesDialog(QDialog):
            """Edition des hypothèses des scénarios standards."""

            def __init__(self, db, parent=None) -> None:
                super().__init__(parent)
                self.db = db
                self.service = ScenarioHypothesisService(db)
                self.setWindowTitle("Paramétrer les scénarios standards")
                self.setMinimumWidth(620)

                root = QVBoxLayout(self)
                root.setContentsMargins(22, 20, 22, 20)
                root.setSpacing(14)

                title = QLabel("Hypothèses de projection")
                title.setStyleSheet("font-size:20px; font-weight:bold; color:#0F172A;")
                root.addWidget(title)

                intro = QLabel(
                    "Ces coefficients s'appliquent uniquement aux récurrences prévisionnelles. "
                    "Ils ne modifient jamais les transactions réelles ni le montant enregistré des récurrences."
                )
                intro.setWordWrap(True)
                intro.setStyleSheet("color:#64748B;")
                root.addWidget(intro)

                self.fields: dict[str, tuple[QDoubleSpinBox, QDoubleSpinBox]] = {}
                for name in self.service.BUILT_INS:
                    group = QGroupBox(name)
                    group.setStyleSheet(
                        "QGroupBox {font-weight:bold; color:#0F172A; border:1px solid #E5E7EB; "
                        "border-radius:12px; margin-top:10px; padding-top:8px;} "
                        "QGroupBox::title {subcontrol-origin: margin; left:12px; padding:0 6px;}"
                    )
                    form = QFormLayout(group)
                    income = self._percent_spin()
                    expense = self._percent_spin()
                    form.addRow("Variation des revenus", income)
                    form.addRow("Variation des dépenses", expense)
                    self.fields[name] = (income, expense)
                    root.addWidget(group)

                reference_note = QLabel(
                    "Réaliste constitue la référence et reste fixé à 0 % / 0 %. "
                    "Prudent et Optimiste sont personnalisables."
                )
                reference_note.setWordWrap(True)
                reference_note.setStyleSheet(
                    "background:#F8FAFC; border-radius:10px; padding:10px; color:#475569;"
                )
                root.addWidget(reference_note)

                buttons_row = QHBoxLayout()
                reset_btn = QPushButton("Réinitialiser les valeurs")
                reset_btn.clicked.connect(self.reset_defaults)
                buttons_row.addWidget(reset_btn)
                buttons_row.addStretch(1)

                buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
                buttons.button(QDialogButtonBox.Save).setText("Enregistrer")
                buttons.accepted.connect(self.save_and_accept)
                buttons.rejected.connect(self.reject)
                buttons_row.addWidget(buttons)
                root.addLayout(buttons_row)

                self.load_values()

            @staticmethod
            def _percent_spin() -> QDoubleSpinBox:
                spin = QDoubleSpinBox()
                spin.setRange(-100.0, 200.0)
                spin.setDecimals(1)
                spin.setSingleStep(1.0)
                spin.setSuffix(" %")
                spin.setAlignment(Qt.AlignRight)
                spin.setMinimumWidth(150)
                return spin

            def load_values(self) -> None:
                for name, (income, expense) in self.fields.items():
                    hypothesis = self.service.get(name)
                    income.setValue(float(hypothesis.income_pct))
                    expense.setValue(float(hypothesis.expense_pct))
                # Le scénario de référence doit toujours représenter les données telles quelles.
                realistic_income, realistic_expense = self.fields["Réaliste"]
                realistic_income.setValue(0.0)
                realistic_expense.setValue(0.0)
                realistic_income.setEnabled(False)
                realistic_expense.setEnabled(False)

            def reset_defaults(self) -> None:
                for name, defaults in self.service.DEFAULTS.items():
                    income, expense = self.fields[name]
                    income.setValue(float(defaults["income_pct"]))
                    expense.setValue(float(defaults["expense_pct"]))

            def save_and_accept(self) -> None:
                try:
                    for name in ("Prudent", "Optimiste"):
                        income, expense = self.fields[name]
                        self.service.set_percentages(name, income.value(), expense.value())
                    self.service.set_percentages("Réaliste", 0.0, 0.0)
                    try:
                        self.db.seal_database_to_encrypted_vault()
                    except Exception:
                        pass
                    self.accept()
                except Exception as exc:
                    QMessageBox.critical(self, "Scénarios", f"Impossible d'enregistrer les hypothèses :\n{exc}")

        if not getattr(ForecastPage, _PATCH_MARKER, False):
            original_build = ForecastPage.build
            original_refresh_info_card = ForecastPage.refresh_info_card

            def open_scenario_hypotheses_dialog(self) -> None:
                dialog = ScenarioHypothesesDialog(self.db, self)
                if dialog.exec() == QDialog.Accepted:
                    self.refresh()

            def build_with_scenario_settings(self) -> None:
                original_build(self)
                try:
                    filters = self.layout.itemAt(1).widget()
                    filter_layout = filters.layout()
                    button = QPushButton("Paramétrer")
                    button.setCursor(Qt.PointingHandCursor)
                    button.setToolTip("Modifier les hypothèses Prudent et Optimiste")
                    button.setStyleSheet(
                        "QPushButton {background:#FFFFFF; color:#2563EB; border:1px solid #BFDBFE; "
                        "border-radius:10px; padding:8px 12px; font-weight:bold;} "
                        "QPushButton:hover {background:#EFF6FF; border-color:#2563EB;}"
                    )
                    button.clicked.connect(self.open_scenario_hypotheses_dialog)
                    self.scenario_settings_btn = button
                    filter_layout.addWidget(button, 0, 6)
                except Exception:
                    pass

            def refresh_info_card_with_scenario(self, data: dict) -> None:
                original_refresh_info_card(self, data)
                if not hasattr(self, "scenario") or not hasattr(self, "info_layout"):
                    return
                scenario_name = self.scenario.currentText()
                description = ScenarioHypothesisService(self.db).describe(scenario_name)
                self.add_info_block("Hypothèse appliquée", description)

            ForecastPage.open_scenario_hypotheses_dialog = open_scenario_hypotheses_dialog
            ForecastPage.build = build_with_scenario_settings
            ForecastPage.refresh_info_card = refresh_info_card_with_scenario
            setattr(ForecastPage, _PATCH_MARKER, True)
    except Exception:
        # Le moteur métier reste actif même si l'écran n'est pas disponible.
        pass

    # Un ancien copier/coller dans ScenarioDialog appelle une méthode de durée
    # qui appartient au dialogue d'événement et référence des champs inexistants.
    try:
        from app.ui.scenarios_page import ScenarioDialog

        def _safe_update_duration_state(self) -> None:
            return None

        ScenarioDialog.update_duration_state = _safe_update_duration_state
    except Exception:
        pass
