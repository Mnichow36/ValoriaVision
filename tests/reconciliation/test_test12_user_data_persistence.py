from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class PersistentDataDirectoryTests(unittest.TestCase):
    def test_explicit_data_directory_override_is_stable(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "ValoriaUserData"
            with patch.dict(os.environ, {"VALORIA_VISION_DATA_DIR": str(target)}, clear=False):
                from app import database
                self.assertEqual(database._persistent_data_dir(), target.resolve())

    def test_windows_data_directory_uses_localappdata(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("app.database.sys.platform", "win32"), patch.dict(
                os.environ, {"LOCALAPPDATA": tmp}, clear=False
            ):
                from app import database
                expected = Path(tmp) / "ValoriaVision" / "data"
                self.assertEqual(database._persistent_data_dir(), expected)

    def test_database_survives_two_instances_on_same_user_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            from app.database import Database

            path = Path(tmp) / "data" / "valoria_vision.db"
            first = Database(path)
            first.initialize()
            first.set_setting("test12.persistence_probe", "kept")

            second = Database(path)
            second.initialize()
            self.assertEqual(second.get_setting("test12.persistence_probe", ""), "kept")


if __name__ == "__main__":
    unittest.main()
