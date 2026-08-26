from __future__ import annotations

from app.services.scenario_hypothesis_service import ScenarioHypothesisService


class FakeDatabase:
    def __init__(self) -> None:
        self.settings: dict[str, str] = {}

    def get_setting(self, key: str, default: str = "") -> str:
        return self.settings.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self.settings[key] = value


def main() -> None:
    db = FakeDatabase()
    service = ScenarioHypothesisService(db)

    assert service.apply_amount("Réaliste", 1000) == 1000
    assert service.apply_amount("Réaliste", -1000) == -1000

    assert service.apply_amount("Prudent", 1000) == 950
    assert service.apply_amount("Prudent", -1000) == -1100

    assert service.apply_amount("Optimiste", 1000) == 1050
    assert service.apply_amount("Optimiste", -1000) == -950

    recurrence = {
        "source": "Récurrence",
        "amount": -1000.0,
        "name": "Loyer",
    }
    adjusted = service.apply_event("Prudent", recurrence)
    assert adjusted["amount"] == -1100
    assert adjusted["scenario_original_amount"] == -1000
    assert adjusted["scenario_adjustment_pct"] == 10
    assert "Dépenses +10 %" in adjusted["scenario_rule"]

    future_transaction = {
        "source": "Transaction future",
        "amount": -1000.0,
        "name": "Transaction déjà enregistrée",
    }
    untouched = service.apply_event("Prudent", future_transaction)
    assert untouched["amount"] == -1000
    assert "scenario_adjustment_pct" not in untouched

    service.set_percentages("Prudent", income_pct=-12.0, expense_pct=18.0)
    assert service.apply_amount("Prudent", 1000) == 880
    assert service.apply_amount("Prudent", -1000) == -1180

    print("OK - Lot 6.1 scénarios standards : hypothèses et ajustements validés")


if __name__ == "__main__":
    main()
