from __future__ import annotations

import base64
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

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


if __name__ == "__main__":
    unittest.main()
