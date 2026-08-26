from __future__ import annotations


class FeatureAccessService:
    """Centralise les droits fonctionnels selon l'édition Valoria Vision.

    Le dépôt ne possède pas encore de moteur de licence commercial. Cette
    couche fournit donc un point d'entrée unique et remplaçable pour les
    contrôles d'accès, sans disperser des conditions dans l'UI.
    """

    EDITION_SETTING_KEY = "product.edition"

    FREE = "free"
    PREMIUM = "premium"
    PREMIUM_PERSONNEL = "premium_personnel"
    PATRIMOINE_EXPERT = "patrimoine_expert"
    PRO = "pro"

    PREMIUM_EDITIONS = {
        PREMIUM,
        PREMIUM_PERSONNEL,
        PATRIMOINE_EXPERT,
        PRO,
    }

    FEATURE_SCENARIOS = "scenarios"

    def __init__(self, db) -> None:
        self.db = db

    def edition(self) -> str:
        raw = str(self.db.get_setting(self.EDITION_SETTING_KEY, self.FREE) or self.FREE)
        return raw.strip().lower().replace(" ", "_")

    def has_feature(self, feature: str) -> bool:
        if feature == self.FEATURE_SCENARIOS:
            return self.edition() in self.PREMIUM_EDITIONS
        return True

    def is_premium(self) -> bool:
        return self.edition() in self.PREMIUM_EDITIONS

    def set_edition(self, edition: str) -> None:
        value = str(edition or self.FREE).strip().lower().replace(" ", "_")
        self.db.set_setting(self.EDITION_SETTING_KEY, value)
