from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ReconciliationRules:
    auto_threshold: int = 90
    review_threshold: int = 60
    ambiguity_min_delta: int = 10
    date_tolerance_days: int = 5
    amount_tolerance_absolute: float = 1.00
    amount_tolerance_relative: float = 0.01
    label_similarity_minimum: float = 0.0
    same_account_required: bool = True
    same_direction_required: bool = True
    date_weight: int = 25
    amount_weight: int = 35
    label_weight: int = 30
    category_weight: int = 10
    counterparty_match_bonus: int = 5
    external_reference_match_bonus: int = 10

    def __post_init__(self) -> None:
        if not 0 <= self.review_threshold <= self.auto_threshold <= 100:
            raise ValueError("Les seuils doivent vérifier 0 <= review <= auto <= 100")
        if self.ambiguity_min_delta < 0:
            raise ValueError("L'écart minimal d'ambiguïté doit être positif")
        if self.date_tolerance_days < 0:
            raise ValueError("La tolérance de date doit être positive")
        if self.amount_tolerance_absolute < 0 or self.amount_tolerance_relative < 0:
            raise ValueError("Les tolérances de montant doivent être positives")
        if not 0 <= self.label_similarity_minimum <= 1:
            raise ValueError("La similarité minimale du libellé doit être comprise entre 0 et 1")
        if self.counterparty_match_bonus < 0 or self.external_reference_match_bonus < 0:
            raise ValueError("Les bonus de rapprochement doivent être positifs")
        if sum(self.weights.values()) != 100:
            raise ValueError("La somme des poids doit être égale à 100")

    @property
    def weights(self) -> dict[str, int]:
        return {
            "date": self.date_weight,
            "amount": self.amount_weight,
            "label": self.label_weight,
            "category": self.category_weight,
        }

    def snapshot(self) -> dict[str, object]:
        return asdict(self)

