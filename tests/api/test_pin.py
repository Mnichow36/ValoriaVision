from __future__ import annotations

import unittest

from tests.api.test_access_control import (
    ADMIN_PASSWORD,
    LEA_PASSWORD,
    MARIE_PASSWORD,
    AccessControlBase,
)
from app.security.auth_service import AuthService

PIN = "482915"


class PinPolicyTest(unittest.TestCase):
    def test_policy_rejects_weak_or_malformed_pins(self):
        service = AuthService(db=None)
        for bad in ("", "12345", "1234567", "abcdef", "12 456", "111111", "000000", "123456", "654321", "234567", "012345"):
            self.assertFalse(service.pin_policy(bad).ok, bad)
        for good in ("482915", "135790", "121212", "100000"):
            self.assertTrue(service.pin_policy(good).ok, good)

    def test_policy_rejects_non_ascii_digits(self):
        self.assertFalse(AuthService(db=None).pin_policy("٤٨٢٩١٥").ok)


class PinFlowTest(AccessControlBase):
    def unlock_pin(self, profile_id: str, pin: str):
        return self.client.post("/api/v1/auth/unlock-pin", json={"profile_id": profile_id, "pin": pin})

    def create_pin(self, session, pin: str = PIN, password: str = MARIE_PASSWORD):
        return session.post("/api/v1/security/pin", {"password": password, "pin": pin})

    def profile(self, profile_id: str) -> dict:
        profiles = self.client.get("/api/v1/auth/status").json()["profiles"]
        return next(p for p in profiles if p["id"] == profile_id)

    def test_create_then_unlock_after_lock(self):
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        self.assertFalse(marie.get("/api/v1/security/status").json()["pinConfigured"])
        self.assertEqual(self.create_pin(marie).status_code, 200)
        status = marie.get("/api/v1/security/status").json()
        self.assertTrue(status["pinConfigured"])
        self.assertTrue(status["pinCreatedAt"])
        self.assertTrue(self.profile(self.marie)["pinAvailable"])

        marie.post("/api/v1/auth/lock")
        response = self.unlock_pin(self.marie, PIN)
        self.assertEqual(response.status_code, 200, response.text)
        session = Session(self.client, response.json()["token"])
        self.assertEqual(session.get("/api/v1/accounts").status_code, 200)
        self.assertTrue(session.get("/api/v1/security/status").json()["pinLastUsedAt"])

    def test_pin_is_never_stored_in_clear(self):
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        self.create_pin(marie)
        with self.database.connect() as conn:
            rows = conn.execute("SELECT key, value FROM user_settings WHERE key LIKE 'security.pin%'").fetchall()
        self.assertTrue(rows)
        self.assertFalse(any(PIN in str(row["value"]) for row in rows))

    def test_create_needs_the_right_password_and_a_valid_pin(self):
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        self.assertEqual(self.create_pin(marie, password="mauvais").status_code, 403)
        self.assertEqual(self.create_pin(marie, pin="123456").status_code, 422)
        self.assertEqual(self.create_pin(marie, pin="12ab56").status_code, 422)
        self.assertFalse(marie.get("/api/v1/security/status").json()["pinConfigured"])

    def test_readers_can_have_a_pin_too(self):
        lea = self.as_user(self.lea, LEA_PASSWORD)
        self.assertEqual(self.create_pin(lea, password=LEA_PASSWORD).status_code, 200)

    def test_pin_refused_when_none_is_set_or_before_any_password_login(self):
        self.assertEqual(self.unlock_pin(self.marie, PIN).status_code, 409)
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        self.create_pin(marie)
        # Nouveau « lancement » : l'API repart de zéro, le PIN n'est pas proposé.
        from fastapi.testclient import TestClient
        from app.api.main import create_app

        fresh = TestClient(create_app(self.database))
        profile = next(p for p in fresh.get("/api/v1/auth/status").json()["profiles"] if p["id"] == self.marie)
        self.assertTrue(profile["pinConfigured"])
        self.assertFalse(profile["pinAvailable"])
        response = fresh.post("/api/v1/auth/unlock-pin", json={"profile_id": self.marie, "pin": PIN})
        self.assertEqual(response.status_code, 409)

    def test_five_wrong_pins_disable_it_and_password_still_works(self):
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        self.create_pin(marie)
        marie.post("/api/v1/auth/lock")
        for expected in (4, 3, 2, 1):
            response = self.unlock_pin(self.marie, "999000")
            self.assertEqual(response.status_code, 403)
            self.assertIn(f"{expected} essai", response.json()["detail"])
        last = self.unlock_pin(self.marie, "999000")
        self.assertEqual(last.status_code, 403)
        self.assertIn("désactivé", last.json()["detail"])
        self.assertFalse(self.profile(self.marie)["pinConfigured"])
        # Même le bon PIN ne rouvre plus rien ; le mot de passe, si.
        self.assertEqual(self.unlock_pin(self.marie, PIN).status_code, 409)
        self.login(self.marie, MARIE_PASSWORD)

    def test_a_good_pin_resets_the_error_counter(self):
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        self.create_pin(marie)
        marie.post("/api/v1/auth/lock")
        for _ in range(3):
            self.unlock_pin(self.marie, "999000")
        opened = self.unlock_pin(self.marie, PIN)
        self.assertEqual(opened.status_code, 200)
        Session(self.client, opened.json()["token"]).post("/api/v1/auth/lock")
        response = self.unlock_pin(self.marie, "999000")
        self.assertIn("4 essai", response.json()["detail"])

    def test_pin_is_per_profile(self):
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        self.create_pin(marie)
        lea = self.as_user(self.lea, LEA_PASSWORD)
        lea.post("/api/v1/auth/lock")
        self.assertEqual(self.unlock_pin(self.lea, PIN).status_code, 409)

    def test_user_can_delete_its_pin_with_the_password(self):
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        self.create_pin(marie)
        self.assertEqual(marie.post("/api/v1/security/pin/delete", {"password": "mauvais"}).status_code, 403)
        self.assertEqual(marie.post("/api/v1/security/pin/delete", {"password": MARIE_PASSWORD}).status_code, 200)
        self.assertFalse(marie.get("/api/v1/security/status").json()["pinConfigured"])

    def test_administrator_can_remove_another_profile_pin_but_not_others(self):
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        self.create_pin(marie)
        denied = marie.post(f"/api/v1/profiles/{self.lea}/pin/delete", {"password": MARIE_PASSWORD})
        self.assertEqual(denied.status_code, 403)
        admin = self.as_admin()
        self.assertEqual(
            admin.post(f"/api/v1/profiles/{self.marie}/pin/delete", {"password": "mauvais"}).status_code, 403
        )
        ok = admin.post(f"/api/v1/profiles/{self.marie}/pin/delete", {"password": ADMIN_PASSWORD})
        self.assertEqual(ok.status_code, 200, ok.text)
        self.assertFalse(self.profile(self.marie)["pinConfigured"])
        # Le mot de passe de Marie n'a pas bougé.
        self.login(self.marie, MARIE_PASSWORD)

    def test_recovery_key_reset_removes_the_pin(self):
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        key = marie.post("/api/v1/security/recovery-key", {"password": MARIE_PASSWORD}).json()["recoveryKey"]
        self.create_pin(marie)
        response = self.client.post(
            "/api/v1/auth/recover",
            json={"profile_id": self.marie, "recovery_key": key, "new_password": "NouveauSecret789!"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(self.profile(self.marie)["pinConfigured"])

    def test_events_are_journaled_without_the_pin(self):
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        self.create_pin(marie)
        marie.post("/api/v1/auth/lock")
        self.unlock_pin(self.marie, "999000")
        admin = self.as_admin()
        events = admin.get("/api/v1/security/journal").json()["events"]
        text = " ".join(str(e) for e in events)
        self.assertIn("auth.pin_created", text)
        self.assertIn("auth.pin_failure", text)
        self.assertNotIn(PIN, text)
        self.assertNotIn("999000", text)


class Session:
    def __init__(self, client, token: str):
        self.client = client
        self.headers = {"X-Valoria-Session": token}

    def get(self, path):
        return self.client.get(path, headers=self.headers)

    def post(self, path, json=None):
        return self.client.post(path, headers=self.headers, json=json)


if __name__ == "__main__":
    unittest.main()
