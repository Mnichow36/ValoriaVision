from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioHypothesis:
    name: str
    income_pct: float
    expense_pct: float

    @staticmethod
    def _signed(value: float) -> str:
        if abs(value) < 0.005:
            return "0 %"
        sign = "+" if value > 0 else ""
        return f"{sign}{value:g} %"

    @property
    def description(self) -> str:
        if abs(self.income_pct) < 0.005 and abs(self.expense_pct) < 0.005:
            return "Montants prévisionnels inchangés."
        return (
            f"Revenus {self._signed(self.income_pct)} · "
            f"Dépenses {self._signed(self.expense_pct)}"
        )


class ScenarioHypothesisService:
    """Hypothèses chiffrées des scénarios standards du prévisionnel.

    Les pourcentages sont stockés dans la table générique `settings`, ce qui
    permet de les rendre modifiables par l'interface sans migration de schéma.
    Ils ne s'appliquent qu'aux récurrences prévisionnelles : une transaction
    réelle ou une transaction future déjà enregistrée n'est jamais réécrite.
    """

    BUILT_INS = ("Prudent", "Réaliste", "Optimiste")

    DEFAULTS = {
        "Prudent": {"income_pct": -5.0, "expense_pct": 10.0},
        "Réaliste": {"income_pct": 0.0, "expense_pct": 0.0},
        "Optimiste": {"income_pct": 5.0, "expense_pct": -5.0},
    }

    SETTING_KEYS = {
        "Prudent": {
            "income_pct": "scenario.prudent.income_pct",
            "expense_pct": "scenario.prudent.expense_pct",
        },
        "Réaliste": {
            "income_pct": "scenario.realiste.income_pct",
            "expense_pct": "scenario.realiste.expense_pct",
        },
        "Optimiste": {
            "income_pct": "scenario.optimiste.income_pct",
            "expense_pct": "scenario.optimiste.expense_pct",
        },
    }

    def __init__(self, db) -> None:
        self.db = db

    def _read_float(self, key: str, default: float) -> float:
        try:
            return float(self.db.get_setting(key, str(default)))
        except (TypeError, ValueError):
            return float(default)

    def get(self, scenario_name: str) -> ScenarioHypothesis | None:
        name = str(scenario_name or "").strip()
        defaults = self.DEFAULTS.get(name)
        keys = self.SETTING_KEYS.get(name)
        if defaults is None or keys is None:
            return None
        return ScenarioHypothesis(
            name=name,
            income_pct=self._read_float(keys["income_pct"], defaults["income_pct"]),
            expense_pct=self._read_float(keys["expense_pct"], defaults["expense_pct"]),
        )

    def set_percentages(self, scenario_name: str, income_pct: float, expense_pct: float) -> None:
        name = str(scenario_name or "").strip()
        if name not in self.BUILT_INS:
            raise ValueError("Seuls les scénarios standards peuvent recevoir ces hypothèses.")
        keys = self.SETTING_KEYS[name]
        self.db.set_setting(keys["income_pct"], str(float(income_pct)))
        self.db.set_setting(keys["expense_pct"], str(float(expense_pct)))

    def describe(self, scenario_name: str) -> str:
        hypothesis = self.get(scenario_name)
        if hypothesis is None:
            return "Événements propres au scénario personnalisé appliqués à la projection."
        return hypothesis.description

    def apply_amount(self, scenario_name: str, amount: float) -> float:
        hypothesis = self.get(scenario_name)
        value = float(amount or 0)
        if hypothesis is None or value == 0:
            return round(value, 2)
        percentage = hypothesis.income_pct if value > 0 else hypothesis.expense_pct
        adjusted = abs(value) * (1.0 + percentage / 100.0)
        return round(adjusted if value > 0 else -adjusted, 2)

    def apply_event(self, scenario_name: str, event: dict) -> dict:
        result = dict(event)
        # Les hypothèses standards modifient les prévisions, jamais les
        # transactions déjà inscrites dans le registre des transactions.
        if str(result.get("source", "")).casefold() != "récurrence".casefold():
            return result
        original = float(result.get("amount", 0) or 0)
        adjusted = self.apply_amount(scenario_name, original)
        result["amount"] = adjusted
        if adjusted != original:
            hypothesis = self.get(scenario_name)
            percentage = hypothesis.income_pct if original > 0 else hypothesis.expense_pct
            result["scenario_original_amount"] = round(original, 2)
            result["scenario_adjustment_pct"] = percentage
            result["scenario_rule"] = hypothesis.description
        return result
