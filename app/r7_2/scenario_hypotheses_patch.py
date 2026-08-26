from __future__ import annotations

from app.database import Database
from app.services.scenario_hypothesis_service import ScenarioHypothesisService


_PATCH_MARKER = "_r7_2_lot6_scenario_hypotheses_applied"


def apply_r7_2_scenario_hypotheses_patch() -> None:
    """Raccorde les hypothèses de scénarios standards au moteur prévisionnel.

    Lot 6.1 :
    - Prudent / Réaliste / Optimiste produisent enfin des projections distinctes ;
    - les coefficients sont lus depuis `settings` et restent donc paramétrables ;
    - seules les récurrences prévisionnelles sont ajustées ;
    - l'hypothèse active est expliquée dans le panneau d'information du
      Prévisionnel ;
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

    # Rendre l'hypothèse visible et explicable directement dans Prévisionnel.
    try:
        from app.ui.forecast_page import ForecastPage

        if not getattr(ForecastPage, _PATCH_MARKER, False):
            original_refresh_info_card = ForecastPage.refresh_info_card

            def refresh_info_card_with_scenario(self, data: dict) -> None:
                original_refresh_info_card(self, data)
                if not hasattr(self, "scenario") or not hasattr(self, "info_layout"):
                    return
                scenario_name = self.scenario.currentText()
                description = ScenarioHypothesisService(self.db).describe(scenario_name)
                self.add_info_block("Hypothèse appliquée", description)

            ForecastPage.refresh_info_card = refresh_info_card_with_scenario
            setattr(ForecastPage, _PATCH_MARKER, True)
    except Exception:
        # Le moteur métier reste actif même si l'écran n'est pas disponible.
        pass

    # Un ancien copier/coller dans ScenarioDialog appelle une méthode de durée
    # qui appartient en réalité au dialogue d'événement et référence des champs
    # inexistants. Le neutraliser rend Création / Modification de scénario
    # utilisable en attendant le nettoyage structurel du fichier UI.
    try:
        from app.ui.scenarios_page import ScenarioDialog

        def _safe_update_duration_state(self) -> None:
            return None

        ScenarioDialog.update_duration_state = _safe_update_duration_state
    except Exception:
        pass
