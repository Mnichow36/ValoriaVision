"""Protection des données par mot de passe (chiffrement 2/3) : activation, verrouillage, reprise."""
from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.database import Database
from app.security.crypto_service import VaultLockedError
from tests.api.test_access_control import (
    ADMIN_PASSWORD,
    LEA_PASSWORD,
    MARIE_PASSWORD,
    AccessControlBase,
    Session,
)


class ProtectionBase(AccessControlBase):
    def restart(self) -> None:
        """Simule l'arrêt puis le relancement de l'application (nouvelle clé en mémoire : aucune)."""
        self.database = Database(Path(self.database.path))
        self.client = TestClient(create_app(self.database))

    def enable(self, password: str = ADMIN_PASSWORD):
        return self.as_admin().post("/api/v1/security/protection/enable", {"password": password})

    def unlock(self, profile_id: str, password: str):
        return self.client.post("/api/v1/auth/unlock", json={"profile_id": profile_id, "password": password})

    def lock_everything(self, session: Session):
        response = session.post("/api/v1/security/protection/lock")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["plaintextRemoved"])

    @property
    def db_path(self) -> Path:
        return Path(self.database.path)


class EnableTest(ProtectionBase):
    def test_wrong_password_changes_nothing(self):
        response = self.enable("pas-le-bon")
        self.assertEqual(response.status_code, 403, response.text)
        self.assertFalse(self.database.crypto.protected)

    def test_enable_creates_safety_copy_recovery_key_and_removes_legacy_key(self):
        response = self.enable()
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["enabled"])
        self.assertRegex(body["recoveryKey"], r"^[A-Z0-9]{4}(-[A-Z0-9]{4})+$")
        self.assertTrue((self.database.backup_dir / body["safetyCopy"]).exists())
        self.assertTrue(self.database.crypto.protected)
        self.assertIsNone(self.database.crypto.legacy_key())
        self.assertFalse(self.database.crypto.local_key_path.exists())

    def test_files_on_disk_hold_neither_password_nor_key(self):
        body = self.enable().json()
        secure = self.database.secure_dir
        for name in ("keyslots.json", "directory.json"):
            text = (secure / name).read_text(encoding="utf-8")
            self.assertNotIn(ADMIN_PASSWORD, text)
            self.assertNotIn(body["recoveryKey"].replace("-", ""), text)
        directory = json.loads((secure / "directory.json").read_text(encoding="utf-8"))
        self.assertEqual({item["name"] for item in directory}, {"Administrateur", "Marie", "Léa"})
        self.assertTrue(all("avatar" not in item for item in directory))

    def test_cannot_enable_twice_and_only_admin_can_enable(self):
        self.assertEqual(self.enable().status_code, 200)
        self.assertEqual(self.enable().status_code, 409)
        marie = self.as_user(self.marie, MARIE_PASSWORD)
        self.assertEqual(marie.post("/api/v1/security/protection/enable", {"password": MARIE_PASSWORD}).status_code, 403)

    def test_status_reports_protection(self):
        admin = self.as_admin()
        self.assertFalse(admin.get("/api/v1/security/status").json()["protectionEnabled"])
        self.enable()
        status = self.as_admin().get("/api/v1/security/status").json()
        self.assertTrue(status["protectionEnabled"])
        self.assertEqual(status["protectionProfilesWithAccess"], 1)


class StartupTest(ProtectionBase):
    def test_launcher_startup_does_not_crash_on_locked_vault_with_leftover_database(self):
        """Fermeture brutale : un .db en clair traîne, mais le coffre est verrouillé au relancement."""
        self.enable()
        self.restart()
        self.db_path.write_bytes(b"reste d'une fermeture brutale")
        self.assertFalse(self.database.crypto.protected is False)
        self.assertTrue(self.database.crypto.locked)
        self.assertFalse(self.database.prepare_existing_database())  # appelé par app/api/run.py


class LockedLifecycleTest(ProtectionBase):
    def setUp(self):
        super().setUp()
        self.recovery_key = self.enable().json()["recoveryKey"]

    def test_lock_removes_plaintext_and_revokes_sessions(self):
        admin = self.as_admin()
        self.assertTrue(self.db_path.exists())
        self.lock_everything(admin)
        self.assertFalse(self.db_path.exists())
        self.assertTrue(self.database.encrypted_db_path.exists())
        self.assertEqual(admin.get("/api/v1/accounts").status_code, 401)

    def test_restart_shows_profiles_without_touching_data(self):
        self.lock_everything(self.as_admin())
        self.restart()
        status = self.client.get("/api/v1/auth/status").json()
        self.assertTrue(status["dataLocked"])
        self.assertEqual({p["name"] for p in status["profiles"]}, {"Administrateur", "Marie", "Léa"})
        self.assertFalse(self.db_path.exists(), "aucune base vide ne doit être créée")
        access = {p["name"]: p["vaultAccess"] for p in status["profiles"]}
        self.assertEqual(access, {"Administrateur": True, "Marie": False, "Léa": False})

    def test_wrong_password_never_creates_a_database(self):
        self.lock_everything(self.as_admin())
        self.restart()
        response = self.unlock("u1", "pas-le-bon")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(self.db_path.exists())

    def test_admin_password_reopens_all_data(self):
        before = len(self.as_admin().get("/api/v1/accounts").json()["accounts"])
        self.lock_everything(self.admin)
        self.restart()
        admin = self.login("u1", ADMIN_PASSWORD)
        self.assertEqual(len(admin.get("/api/v1/accounts").json()["accounts"]), before)
        self.assertEqual(admin.get("/api/v1/auth/status").json()["dataLocked"], False)

    def test_other_profiles_open_after_the_administrator(self):
        self.lock_everything(self.as_admin())
        self.restart()
        refused = self.unlock(self.marie, MARIE_PASSWORD)
        self.assertEqual(refused.status_code, 409)
        self.assertEqual(refused.headers.get("X-Valoria-Vault"), "admin-first")
        self.assertFalse(self.db_path.exists())
        self.login("u1", ADMIN_PASSWORD)
        self.login(self.marie, MARIE_PASSWORD)  # crée sa serrure
        self.lock_everything(self.as_admin())
        self.restart()
        self.login(self.marie, MARIE_PASSWORD)  # désormais Marie ouvre seule

    def test_wrong_attempts_are_throttled_while_locked(self):
        self.lock_everything(self.as_admin())
        self.restart()
        codes = [self.unlock("u1", f"faux-{i}").status_code for i in range(5)]
        self.assertEqual(codes[:4], [401] * 4)
        self.assertEqual(codes[4], 429)
        self.assertEqual(self.unlock("u1", ADMIN_PASSWORD).status_code, 429)
        self.assertTrue(self.client.get("/api/v1/auth/status").json()["retryAfterSeconds"] >= 0)

    def test_changed_password_replaces_the_lock(self):
        admin = self.as_admin()
        new = "NouveauSecret987!"
        response = admin.post("/api/v1/security/change-password", {"current_password": ADMIN_PASSWORD, "new_password": new})
        self.assertEqual(response.status_code, 200, response.text)
        self.lock_everything(admin)
        self.restart()
        self.assertEqual(self.unlock("u1", ADMIN_PASSWORD).status_code, 401)
        self.assertEqual(self.unlock("u1", new).status_code, 200)

    def test_recovery_key_opens_locked_data_and_sets_a_new_password(self):
        self.lock_everything(self.as_admin())
        self.restart()
        new = "ApresSecours654!"
        response = self.client.post(
            "/api/v1/auth/recover",
            json={"profile_id": "u1", "recovery_key": self.recovery_key, "new_password": new},
        )
        self.assertEqual(response.status_code, 200, response.text)
        fresh_key = response.json()["recoveryKey"]
        self.assertNotEqual(fresh_key, self.recovery_key)
        self.lock_everything(Session(self.client, response.json()["token"], "u1"))
        self.restart()
        self.assertEqual(self.unlock("u1", new).status_code, 200)

    def test_wrong_recovery_key_is_refused_without_opening(self):
        self.lock_everything(self.as_admin())
        self.restart()
        response = self.client.post(
            "/api/v1/auth/recover",
            json={"profile_id": "u1", "recovery_key": "AAAA-BBBB-CCCC-DDDD-EEEE-FFFF", "new_password": "ApresSecours654!"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(self.database.crypto.locked)
        self.assertFalse(self.db_path.exists())

    def test_abrupt_stop_is_recovered_at_next_unlock(self):
        admin = self.as_admin()
        created = admin.post("/api/v1/accounts", {"name": "Compte ajouté avant l'arrêt", "bank": "Banque", "account_type": "Compte courant", "initial_balance": 10, "initial_date": "2026-01-01"})
        self.assertIn(created.status_code, (200, 201), created.text)
        # Aucun verrouillage : la base en clair reste sur le disque, comme après un plantage.
        self.assertTrue(self.db_path.exists())
        self.restart()
        self.assertTrue(self.client.get("/api/v1/auth/status").json()["dataLocked"])
        admin = self.login("u1", ADMIN_PASSWORD)
        names = [a["name"] for a in admin.get("/api/v1/accounts").json()["accounts"]]
        self.assertIn("Compte ajouté avant l'arrêt", names)

    def test_empty_file_left_behind_is_never_taken_for_the_database(self):
        self.lock_everything(self.as_admin())
        self.db_path.write_bytes(b"")
        self.restart()
        admin = self.login("u1", ADMIN_PASSWORD)
        self.assertTrue(len(admin.get("/api/v1/accounts").json()["accounts"]) > 0)

    def test_locked_database_refuses_to_open_or_create_a_file(self):
        self.lock_everything(self.as_admin())
        self.restart()
        with self.assertRaises(VaultLockedError):
            self.database.connect()
        self.assertFalse(self.db_path.exists())

    def test_deleting_a_profile_removes_its_lock(self):
        self.login(self.marie, MARIE_PASSWORD)
        admin = self.as_admin()
        self.assertIn("2", self.database.crypto.slots.owners())
        response = admin.post(f"/api/v1/profiles/{self.marie}/delete", {"password": ADMIN_PASSWORD})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("2", self.database.crypto.slots.owners())

    def test_clean_shutdown_closes_the_vault(self):
        self.as_admin()
        with TestClient(create_app(self.database)):
            pass
        self.assertFalse(self.db_path.exists())
        self.assertTrue(self.database.crypto.locked)

    def test_backup_made_before_activation_is_still_readable(self):
        copies = sorted(self.database.backup_dir.glob("valoria_vision_backup_*.vvb"))
        self.assertTrue(copies)
        self.as_admin()
        restored = self.database.crypto.decrypt_bytes(copies[-1].read_bytes())
        self.assertTrue(restored.startswith(b"SQLite format 3"))


class UnprotectedStaysUnchangedTest(AccessControlBase):
    def test_default_mode_has_no_lock_and_no_extra_files(self):
        self.assertFalse(self.database.crypto.protected)
        self.assertFalse((self.database.secure_dir / "keyslots.json").exists())
        status = self.client.get("/api/v1/auth/status").json()
        self.assertFalse(status["dataLocked"])
