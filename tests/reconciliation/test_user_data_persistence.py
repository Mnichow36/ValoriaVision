import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.database import Database, default_data_dir
from app.security.auth_service import AuthService


class TestUserDataPersistence(unittest.TestCase):
    def test_windows_data_directory_is_stable_and_outside_bundle(self):
        env = {
            "LOCALAPPDATA": r"C:\Users\Test\AppData\Local",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(sys, "platform", "win32"):
                self.assertEqual(
                    default_data_dir(),
                    Path(env["LOCALAPPDATA"]) / "ValoriaVision",
                )

    def test_environment_override_has_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            with mock.patch.dict(
                os.environ,
                {"VALORIA_DATA_DIR": directory, "LOCALAPPDATA": "ignored"},
                clear=True,
            ):
                self.assertEqual(default_data_dir(), Path(directory))

    def test_database_and_master_password_survive_new_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "valoria_vision.db"

            with mock.patch.object(
                Database, "seal_database_to_encrypted_vault", return_value=None
            ):
                first = Database(database_path)
                first.initialize()
                first.set_setting("test.restart_marker", "preserved")
                AuthService(first).set_master_password("TEST12-secure")

                reopened = Database(database_path)
                reopened.initialize()

            self.assertEqual(reopened.get_setting("test.restart_marker"), "preserved")
            self.assertTrue(AuthService(reopened).is_configured())
            self.assertTrue(
                AuthService(reopened).verify_master_password("TEST12-secure")
            )
            self.assertEqual(reopened.encrypted_db_path.parent, Path(directory) / "secure")
            self.assertEqual(reopened.backup_dir, Path(directory) / "backups")


if __name__ == "__main__":
    unittest.main()
