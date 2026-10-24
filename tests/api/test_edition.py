"""Éditions Standard / Premium : limite de comptes, profils verrouillés, devises, scénarios."""
from __future__ import annotations

from tests.api.test_access_control import (
    ADMIN_PASSWORD,
    MARIE_PASSWORD,
    AccessControlBase,
)

ACCOUNT = {
    "name": "Compte test", "bank": "Banque", "account_type": "Compte courant",
    "initial_balance": 10, "initial_date": "2026-01-01",
}


class EditionBase(AccessControlBase):
    def set_edition(self, edition: str):
        return self.as_admin().post("/api/v1/edition", {"edition": edition})

    def edition(self, session=None) -> dict:
        return (session or self.as_admin()).get("/api/v1/me").json()["me"]["edition"]

    def active_count(self) -> int:
        """Compte via l'objet admin courant (un seul profil ouvert à la fois)."""
        return sum(1 for a in self.admin.get("/api/v1/accounts").json()["accounts"] if a["status"] == "Actif")


class SwitchTest(EditionBase):
    def test_switch_between_editions_and_describe(self):
        self.assertEqual(self.edition()["code"], "premium")
        response = self.set_edition("standard")
        self.assertEqual(response.status_code, 200, response.text)
        info = response.json()["edition"]
        self.assertEqual(info["code"], "standard")
        self.assertEqual(info["accountLimit"], 3)
        self.assertFalse(info["multiProfile"])
        self.assertEqual(len(info["catalogue"]), 6)
        self.assertEqual(self.set_edition("premium").json()["edition"]["code"], "premium")

    def test_unknown_edition_refused_and_only_admin_switches(self):
        self.assertEqual(self.set_edition("gold").status_code, 422)
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        self.assertEqual(marie.post("/api/v1/edition", {"edition": "standard"}).status_code, 403)

    def test_edition_survives_restart(self):
        self.set_edition("standard")
        from fastapi.testclient import TestClient
        from app.api.main import create_app
        self.client = TestClient(create_app(self.database))
        # le seul profil utilisable en Standard est l'administrateur
        self.assertEqual(self.edition(self.login("u1", ADMIN_PASSWORD))["code"], "standard")


class AccountLimitTest(EditionBase):
    def setUp(self):
        super().setUp()
        self.set_edition("standard")

    def test_creation_blocked_at_three_active_accounts_without_deleting_anything(self):
        admin = self.as_admin()
        before = self.active_count()
        self.assertGreaterEqual(before, 3)
        response = admin.post("/api/v1/accounts", ACCOUNT)
        self.assertEqual(response.status_code, 403, response.text)
        self.assertIn("Premium", response.json()["detail"])
        self.assertEqual(response.headers.get("x-valoria-premium"), "accounts")
        self.assertEqual(self.active_count(), before)
        info = self.edition(admin)
        self.assertFalse(info["canCreateAccount"])
        self.assertEqual(info["activeAccounts"], before)

    def test_archiving_frees_a_place_and_reactivating_is_limited(self):
        admin = self.as_admin()
        accounts = admin.get("/api/v1/accounts").json()["accounts"]
        active = [a for a in accounts if a["status"] == "Actif"]
        for account in active[: len(active) - 2]:
            self.assertEqual(admin.post(f"/api/v1/accounts/{account['id']}/status", {"status": "Archivé"}).status_code, 200)
        self.assertEqual(self.active_count(), 2)
        self.assertEqual(admin.post("/api/v1/accounts", ACCOUNT).status_code, 200)
        self.assertEqual(self.active_count(), 3)
        archived = active[0]
        blocked = admin.post(f"/api/v1/accounts/{archived['id']}/status", {"status": "Actif"})
        self.assertEqual(blocked.status_code, 403, blocked.text)

    def test_premium_lifts_the_limit(self):
        self.set_edition("premium")
        self.assertEqual(self.as_admin().post("/api/v1/accounts", ACCOUNT).status_code, 200)

    def test_foreign_currency_needs_premium(self):
        admin = self.as_admin()
        accounts = admin.get("/api/v1/accounts").json()["accounts"]
        for account in accounts:
            admin.post(f"/api/v1/accounts/{account['id']}/status", {"status": "Archivé"})
        response = admin.post("/api/v1/accounts", {**ACCOUNT, "currency": "USD"})
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(response.headers.get("x-valoria-premium"), "multi_currency")
        self.assertEqual(admin.post("/api/v1/accounts", {**ACCOUNT, "currency": "EUR"}).status_code, 200)


class ProfilesTest(EditionBase):
    def test_extra_profiles_kept_but_locked_in_standard(self):
        self.set_edition("standard")
        profiles = {p["name"]: p for p in self.client.get("/api/v1/profiles").json()["profiles"]}
        self.assertFalse(profiles["Administrateur"]["premiumLocked"])
        self.assertTrue(profiles["Marie"]["premiumLocked"])
        self.assertTrue(profiles["Léa"]["premiumLocked"])
        refused = self.client.post("/api/v1/auth/unlock", json={"profile_id": self.marie, "password": MARIE_PASSWORD})
        self.assertEqual(refused.status_code, 403, refused.text)
        self.assertEqual(refused.headers.get("x-valoria-premium"), "profiles")
        self.assertEqual(self.as_admin().get("/api/v1/profiles").status_code, 200)

    def test_new_profile_blocked_then_everything_returns_with_premium(self):
        self.set_edition("standard")
        blocked = self.as_admin().post(
            "/api/v1/profiles", {"name": "Paul", "role": "reader", "password": "PaulSecret321!!"}
        )
        self.assertEqual(blocked.status_code, 403, blocked.text)
        self.set_edition("premium")
        self.assertEqual(self.login(self.marie, MARIE_PASSWORD).get("/api/v1/me").json()["me"]["name"], "Marie")

    def test_password_pin_and_security_stay_free(self):
        self.set_edition("standard")
        status = self.as_admin().get("/api/v1/security/status")
        self.assertEqual(status.status_code, 200)


class ScenarioTest(EditionBase):
    PAYLOAD = {"name": "Mon scénario", "description": "", "scenario_type": "custom", "start_date": "2026-11-01", "horizon_months": 12}

    def test_custom_scenarios_locked_in_standard_but_readable(self):
        self.set_edition("standard")
        admin = self.as_admin()
        self.assertEqual(admin.get("/api/v1/scenarios").status_code, 200)
        blocked = admin.post("/api/v1/scenarios", self.PAYLOAD)
        self.assertEqual(blocked.status_code, 403, blocked.text)
        self.assertEqual(blocked.headers.get("x-valoria-premium"), "scenario_builder")
        # les coefficients des scénarios standard de la courbe restent libres
        preset = admin.post("/api/v1/scenario-presets/Prudent", {"income_percent": 90, "expense_percent": 110})
        self.assertEqual(preset.status_code, 200, preset.text)


class LockedVaultTest(EditionBase):
    def test_locked_profile_refused_before_the_vault_opens(self):
        self.set_edition("standard")
        admin = self.as_admin()
        self.assertEqual(admin.post("/api/v1/security/protection/enable", {"password": ADMIN_PASSWORD}).status_code, 200)
        self.assertEqual(admin.post("/api/v1/security/protection/lock").status_code, 200)
        listing = {p["name"]: p for p in self.client.get("/api/v1/profiles").json()["profiles"]}
        self.assertTrue(listing["Marie"]["premiumLocked"])
        self.assertFalse(listing["Administrateur"]["premiumLocked"])
        refused = self.client.post("/api/v1/auth/unlock", json={"profile_id": self.marie, "password": MARIE_PASSWORD})
        self.assertEqual(refused.status_code, 403, refused.text)
        self.assertTrue(self.database.crypto.locked)
        self.assertEqual(self.login("u1", ADMIN_PASSWORD).get("/api/v1/me").status_code, 200)
