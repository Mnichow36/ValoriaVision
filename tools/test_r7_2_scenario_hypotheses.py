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

    prudent = service.get("Prudent")
    realistic = service.get("Réaliste")
    optimistic = service.get("Optimiste")

    assert prudent.income_pct == -5.0
    assert prudent.expense_pct == 10.0
    assert realistic.income_pct == 0.0
    assert realistic.expense_pct == 0.0
    assert optimistic.income_pct == 5.0
    assert optimistic.expense_pct == -5.0

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
    assert "Revenus -12 %" in service.describe("Prudent")
    assert "Dépenses +18 %" in service.describe("Prudent")

    # Le scénario Réaliste reste techniquement configurable au niveau service,
    # mais l'interface Lot 6.1 le verrouille à 0 / 0 et le réécrit ainsi à
    # chaque sauvegarde des hypothèses standards.
    service.set_percentages("Réaliste", income_pct=0.0, expense_pct=0.0)
    assert service.describe("Réaliste") == "Montants prévisionnels inchangés."

    print("OK - Lot 6.1 scénarios standards : hypothèses, paramétrage et ajustements validés")


if __name__ == "__main__":
    main()
