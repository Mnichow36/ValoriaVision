"""Éditions Standard et Premium : ce que chacune comprend, et les règles qui en découlent.

Un seul endroit décide des droits (ce fichier). L'interface ne fait que montrer ; le serveur
applique toujours la règle, même si l'écran se trompe.

Principes :
- l'édition se choisit pour toute l'installation (réglage ``premium.mode``) ; pour l'instant
  c'est un interrupteur local d'essai, sans paiement ;
- repasser en Standard ne supprime jamais rien : ce qui dépasse la limite reste visible et
  conservé, mais verrouillé tant que Premium n'est pas actif.
"""
from __future__ import annotations

from pathlib import Path

EDITION_STANDARD = "standard"
EDITION_PREMIUM = "premium"
EDITIONS = (EDITION_STANDARD, EDITION_PREMIUM)
PREFERENCE_KEY = "premium.mode"  # valeurs stockées : "free" (Standard, défaut) ou "premium"

STANDARD_ACCOUNT_LIMIT = 3
STANDARD_CURRENCIES = ("EUR",)

# (clé, libellé, Standard, Premium)
CATALOGUE = (
    ("accounts", "Comptes", "3 maximum", "Illimités"),
    ("multi_currency", "Multi-devises", "Euro seul", "Inclus"),
    ("password_pin", "Mot de passe, code PIN", "Inclus", "Inclus"),
    ("data_protection", "Protection des données", "Inclus", "Inclus"),
    ("profiles", "Profils et accès famille", "1 profil", "Illimités"),
    ("scenario_builder", "Scénarios personnalisés", "Verrouillé", "Inclus"),
)

PREMIUM_MESSAGES = {
    "accounts": (
        f"L’édition Standard comprend {STANDARD_ACCOUNT_LIMIT} comptes actifs. "
        "La création ou la réactivation d’un compte supplémentaire est réservée à l’édition Premium."
    ),
    "multi_currency": "Les comptes dans une autre devise que l’euro sont réservés à l’édition Premium.",
    "profiles": "Les profils supplémentaires et leurs accès sont réservés à l’édition Premium.",
    "scenario_builder": "Les scénarios personnalisés sont réservés à l’édition Premium.",
}


class PremiumRequired(Exception):
    def __init__(self, feature: str) -> None:
        self.feature = feature
        super().__init__(PREMIUM_MESSAGES.get(feature, "Cette fonction est réservée à l’édition Premium."))


class EditionService:
    def __init__(self, database) -> None:
        self.database = database

    # -- état -----------------------------------------------------------------------------
    def _ready(self) -> bool:
        """Évite de créer une base vide : avant la première installation, il n'y a rien à lire."""
        return Path(self.database.path).exists() and Path(self.database.path).stat().st_size > 0

    def current(self) -> str:
        if not self._ready():
            return EDITION_STANDARD
        value = str(self.database.get_user_preference(PREFERENCE_KEY, "free") or "free").strip().lower()
        return EDITION_PREMIUM if value == "premium" else EDITION_STANDARD

    def is_premium(self) -> bool:
        return self.current() == EDITION_PREMIUM

    def set(self, edition: str) -> str:
        edition = str(edition or "").strip().lower()
        if edition not in EDITIONS:
            raise ValueError("Cette édition n’existe pas.")
        self.database.set_user_preference(PREFERENCE_KEY, "premium" if edition == EDITION_PREMIUM else "free")
        return edition

    def active_accounts(self) -> int:
        if not self._ready():
            return 0
        with self.database.connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM accounts WHERE status = 'Actif'").fetchone()[0])

    def primary_user_id(self, users: list[dict]) -> int | None:
        """Seul profil utilisable en Standard : le plus ancien administrateur."""
        personal = [u for u in users if u.get("kind") == "personal"]
        admins = [u for u in personal if u.get("role") == "admin"]
        pool = admins or personal
        if not pool:
            return None
        return min(int(str(u["id"]).lstrip("u")) for u in pool)

    # -- règles ---------------------------------------------------------------------------
    def check_new_active_account(self) -> None:
        if not self.is_premium() and self.active_accounts() >= STANDARD_ACCOUNT_LIMIT:
            raise PremiumRequired("accounts")

    def check_currency(self, currency: str, previous: str | None = None) -> None:
        code = str(currency or "EUR").strip().upper()
        if self.is_premium() or code in STANDARD_CURRENCIES:
            return
        if previous is not None and str(previous).strip().upper() == code:
            return  # compte déjà dans cette devise : on ne bloque pas sa modification
        raise PremiumRequired("multi_currency")

    def check_profiles(self) -> None:
        if not self.is_premium():
            raise PremiumRequired("profiles")

    def check_scenario_builder(self) -> None:
        if not self.is_premium():
            raise PremiumRequired("scenario_builder")

    # -- description pour l'interface -------------------------------------------------------
    def describe(self, users: list[dict] | None = None, user_id: int | None = None) -> dict:
        edition = self.current()
        premium = edition == EDITION_PREMIUM
        active = self.active_accounts()
        primary = self.primary_user_id(users or [])
        return {
            "code": edition,
            "label": "Premium" if premium else "Standard",
            "accountLimit": None if premium else STANDARD_ACCOUNT_LIMIT,
            "activeAccounts": active,
            "canCreateAccount": premium or active < STANDARD_ACCOUNT_LIMIT,
            "currencies": None if premium else list(STANDARD_CURRENCIES),
            "multiCurrency": premium,
            "multiProfile": premium,
            "scenarioBuilder": premium,
            "lockedProfiles": [] if premium else [
                u["id"] for u in (users or []) if u.get("kind") == "personal" and primary is not None
                and int(str(u["id"]).lstrip("u")) != primary
            ],
            "catalogue": [
                {"key": key, "label": label, "standard": std, "premium": prem}
                for key, label, std, prem in CATALOGUE
            ],
            "testSwitch": True,
        }


__all__ = ["EditionService", "PremiumRequired", "EDITION_STANDARD", "EDITION_PREMIUM", "STANDARD_ACCOUNT_LIMIT"]
