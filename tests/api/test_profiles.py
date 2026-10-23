from __future__ import annotations

import base64
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import HTTPException

from app.api.main import (
    PasswordPayload,
    ProfileCreatePayload,
    ProfileDeletePayload,
    ProfileUpdatePayload,
    create_app,
)
from app.database import Database
from app.security.auth_service import AuthService
from app.security.profiles import LEGACY_PROFILE_ID, ProfileError, ProfileManager

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
PNG_URL = "data:image/png;base64," + base64.b64encode(PNG).decode()


def _legacy(root: str) -> Database:
    database = Database(Path(root) / "valoria.db")
    with database.connect() as conn:
        database.create_schema(conn)
        database.apply_migrations(conn)
        database.seed_if_empty(conn)
    AuthService(database).set_master_password("MotDePasse123!")
    return database


def _route(app, path: str, method: str):
    return next(r.endpoint for r in app.routes if r.path == path and method in r.methods)


class Api:
    def __init__(self, app):
        self.app = app

    def __getattr__(self, name):
        table = {
            "status": ("/api/v1/auth/status", "GET"),
            "unlock": ("/api/v1/auth/unlock", "POST"),
            "setup": ("/api/v1/auth/setup", "POST"),
            "list": ("/api/v1/profiles", "GET"),
            "create": ("/api/v1/profiles", "POST"),
            "update": ("/api/v1/profiles/{profile_id}", "PUT"),
            "delete": ("/api/v1/profiles/{profile_id}/delete", "POST"),
            "accounts": ("/api/v1/accounts", "GET"),
        }
        path, method = table[name]
        return _route(self.app, path, method)


class ProfileManagerTest(unittest.TestCase):
    def test_existing_database_becomes_first_profile_in_place(self):
        with TemporaryDirectory() as root:
            database = _legacy(root)
            before = database.path.read_bytes()
            manager = ProfileManager(Path(root), legacy_database=database)
            listing = manager.list_profiles()
            self.assertEqual([p["id"] for p in listing], [LEGACY_PROFILE_ID])
            self.assertTrue(listing[0]["configured"])
            self.assertFalse(listing[0]["removable"])
            self.assertEqual(database.path.read_bytes(), before)  # rien n'a été déplacé ni modifié
            self.assertTrue((Path(root) / "profiles.json").exists())

    def test_create_isolated_databases_and_unique_names(self):
        with TemporaryDirectory() as root:
            manager = ProfileManager(Path(root), legacy_database=_legacy(root))
            marie = manager.create("Marie", "#0f766e")
            self.assertNotEqual(manager.database_for(marie["id"]).path, manager.database_for(LEGACY_PROFILE_ID).path)
            self.assertTrue(manager.database_for(marie["id"]).path.exists())
            with self.assertRaises(ProfileError):
                manager.create("marie")
            with self.assertRaises(ProfileError):
                manager.create("   ")
            with self.assertRaises(ProfileError):
                manager.create("X", "rouge")
            demo = manager.create("Démo", kind="demo")
            with self.assertRaises(ProfileError):
                manager.create("Autre démo", kind="demo")
            with manager.database_for(demo["id"]).connect() as conn:
                self.assertGreater(conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0], 0)
            with manager.database_for(marie["id"]).connect() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0], 0)

    def test_avatar_validation(self):
        with TemporaryDirectory() as root:
            manager = ProfileManager(Path(root), legacy_database=_legacy(root))
            pid = manager.create("Marie")["id"]
            self.assertTrue(manager.set_avatar(pid, PNG_URL)["avatar"].startswith("data:image/png;base64,"))
            for bad in (
                "data:image/gif;base64,AAAA",
                "data:image/png;base64,@@@@",
                "data:image/jpeg;base64," + base64.b64encode(PNG).decode(),  # contenu ≠ format annoncé
                "data:image/png;base64," + base64.b64encode(PNG + b"\x00" * 300_000).decode(),
            ):
                with self.assertRaises(ProfileError, msg=bad[:30]):
                    manager.set_avatar(pid, bad)
            self.assertIsNone(manager.set_avatar(pid, None)["avatar"])
            self.assertEqual(list((Path(root) / "avatars").glob("*")), [])


class ProfilesApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = self.tmp.name
        self.api = Api(create_app(_legacy(self.root)))

    def tearDown(self):
        self.tmp.cleanup()

    def _create(self, name="Marie", password="Marie-Secret-2026!", **extra):
        return self.api.create(ProfileCreatePayload(name=name, password=password, **extra), None)

    def test_create_returns_recovery_key_and_profile_opens_with_its_own_password(self):
        result = self._create()
        pid = result["profile"]["id"]
        self.assertRegex(result["recoveryKey"], r"^([A-Z2-9]{4}-){5}[A-Z2-9]{4}$")
        with self.assertRaises(HTTPException) as ctx:  # plusieurs profils : il faut choisir
            self.api.unlock(PasswordPayload(password="Marie-Secret-2026!"), None)
        self.assertEqual(ctx.exception.status_code, 409)
        with self.assertRaises(HTTPException) as ctx:  # le mot de passe d'un autre profil ne marche pas
            self.api.unlock(PasswordPayload(password="MotDePasse123!", profile_id=pid), None)
        self.assertEqual(ctx.exception.status_code, 401)
        token = self.api.unlock(PasswordPayload(password="Marie-Secret-2026!", profile_id=pid), None)["token"]
        self.assertEqual(self.api.accounts(token, None)["accounts"], [])  # coffre vierge de Marie

    def test_create_applies_password_policy_and_leaves_no_orphan(self):
        with self.assertRaises(HTTPException) as ctx:
            self._create(password="faible")
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(len(self.api.list(None)["profiles"]), 1)
        with self.assertRaises(HTTPException):
            self._create(avatar="data:image/gif;base64,AAAA")
        self.assertEqual(len(self.api.list(None)["profiles"]), 1)

    def test_switching_profile_revokes_previous_session_and_isolates_data(self):
        pid = self._create()["profile"]["id"]
        first = self.api.unlock(PasswordPayload(password="MotDePasse123!", profile_id=LEGACY_PROFILE_ID), None)["token"]
        self.assertTrue(self.api.accounts(first, None)["accounts"])  # données du profil d'origine
        second = self.api.unlock(PasswordPayload(password="Marie-Secret-2026!", profile_id=pid), None)["token"]
        with self.assertRaises(HTTPException) as ctx:
            self.api.accounts(first, None)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(self.api.accounts(second, None)["accounts"], [])

    def test_failed_attempt_on_another_profile_does_not_switch_the_active_one(self):
        pid = self._create()["profile"]["id"]
        token = self.api.unlock(PasswordPayload(password="MotDePasse123!", profile_id=LEGACY_PROFILE_ID), None)["token"]
        with self.assertRaises(HTTPException):
            self.api.unlock(PasswordPayload(password="mauvais", profile_id=pid), None)
        self.assertTrue(self.api.accounts(token, None)["accounts"])  # toujours le profil d'origine

    def test_lockout_is_per_profile(self):
        pid = self._create()["profile"]["id"]
        for _ in range(3):
            with self.assertRaises(HTTPException):
                self.api.unlock(PasswordPayload(password="mauvais", profile_id=pid), None)
        with self.assertRaises(HTTPException) as ctx:
            self.api.unlock(PasswordPayload(password="Marie-Secret-2026!", profile_id=pid), None)
        self.assertEqual(ctx.exception.status_code, 429)
        ok = self.api.unlock(PasswordPayload(password="MotDePasse123!", profile_id=LEGACY_PROFILE_ID), None)
        self.assertIn("token", ok)  # l'autre profil n'est pas bloqué

    def test_demo_profile_opens_without_password_and_has_sample_data(self):
        pid = self.api.create(ProfileCreatePayload(name="Démo", kind="demo"), None)["profile"]["id"]
        token = self.api.unlock(PasswordPayload(profile_id=pid), None)["token"]
        self.assertTrue(self.api.accounts(token, None)["accounts"])

    def test_status_lists_profiles_without_secrets(self):
        self._create()
        status = self.api.status(None, None)
        self.assertEqual(len(status["profiles"]), 2)
        self.assertTrue(status["profileRequired"])
        self.assertNotIn("hash", str(status).lower())

    def test_update_needs_the_profile_to_be_open(self):
        pid = self._create()["profile"]["id"]
        token = self.api.unlock(PasswordPayload(password="MotDePasse123!", profile_id=LEGACY_PROFILE_ID), None)["token"]
        with self.assertRaises(HTTPException) as ctx:
            self.api.update(pid, ProfileUpdatePayload(name="Autre"), token, None)
        self.assertEqual(ctx.exception.status_code, 403)
        renamed = self.api.update(LEGACY_PROFILE_ID, ProfileUpdatePayload(name="François", avatar=PNG_URL), token, None)
        self.assertEqual(renamed["profile"]["name"], "François")
        self.assertIsNotNone(renamed["profile"]["avatar"])
        cleared = self.api.update(LEGACY_PROFILE_ID, ProfileUpdatePayload(clear_avatar=True), token, None)
        self.assertIsNone(cleared["profile"]["avatar"])

    def test_delete_requires_password_and_protects_the_original_profile(self):
        pid = self._create()["profile"]["id"]
        directory = Path(self.root) / "profiles" / pid
        self.assertTrue(directory.exists())
        with self.assertRaises(HTTPException) as ctx:
            self.api.delete(pid, ProfileDeletePayload(password="faux"), None)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertTrue(directory.exists())
        self.assertEqual(self.api.delete(pid, ProfileDeletePayload(password="Marie-Secret-2026!"), None), {"deleted": True})
        self.assertFalse(directory.exists())
        with self.assertRaises(HTTPException) as ctx:
            self.api.delete(LEGACY_PROFILE_ID, ProfileDeletePayload(password="MotDePasse123!"), None)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_first_installation_creates_the_first_profile_on_setup(self):
        with TemporaryDirectory() as root:
            api = Api(create_app(Database(Path(root) / "valoria.db")))
            self.assertEqual(api.status(None, None)["profiles"], [])
            with self.assertRaises(HTTPException) as ctx:
                api.setup(PasswordPayload(password="faible"), None)
            self.assertEqual(ctx.exception.status_code, 422)
            token = api.setup(PasswordPayload(password="Premier-Mdp-2026!"), None)["token"]
            self.assertEqual(api.accounts(token, None)["accounts"], [])
            self.assertEqual(len(api.status(token, None)["profiles"]), 1)
            api2 = Api(create_app(Database(Path(root) / "valoria.db")))  # redémarrage
            self.assertTrue(api2.status(None, None)["configured"])


if __name__ == "__main__":
    unittest.main()
