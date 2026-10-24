from __future__ import annotations

import base64
import sqlite3
import unittest

from app.security.backup_service import BackupError, BackupService, WrongPassphrase, passphrase_problem
from tests.api.test_access_control import ADMIN_PASSWORD, LEA_PASSWORD, AccessControlBase

PHRASE = "le vieux phare sous la pluie"


class BackupApiTests(AccessControlBase):
    def create(self, phrase=PHRASE, confirm=None):
        return self.admin.post("/api/v1/backups", {"passphrase": phrase, "confirm": phrase if confirm is None else confirm})

    def account_count(self) -> int:
        with sqlite3.connect(self.database.path) as conn:
            return conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]

    def test_create_download_and_list(self):
        response = self.create()
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        blob = base64.b64decode(body["data"])
        self.assertTrue(blob.startswith(b"VALORIA-VVB-v2"))
        self.assertGreater(body["info"]["accounts"], 0)
        listing = self.admin.get("/api/v1/backups").json()
        self.assertEqual(listing["backups"][0]["name"], body["name"])
        self.assertIsNotNone(listing["lastBackupAt"])
        again = self.admin.post("/api/v1/backups/download", {"name": body["name"]}).json()
        self.assertEqual(again["data"], body["data"])

    def test_passphrase_rules(self):
        self.assertEqual(self.create("court").status_code, 422)
        self.assertEqual(self.create(PHRASE, "autre phrase secrete").status_code, 422)
        self.assertIsNotNone(passphrase_problem("aaaaaaaaaaaaaaa"))

    def test_file_is_not_plain_sqlite_and_wrong_phrase_fails(self):
        body = self.create().json()
        blob = base64.b64decode(body["data"])
        self.assertNotIn(b"SQLite format 3", blob)
        self.assertNotIn(b"Compte courant", blob)
        bad = self.admin.post(
            "/api/v1/backups/inspect", {"data": body["data"], "passphrase": "ce n'est pas la bonne phrase"}
        )
        self.assertEqual(bad.status_code, 403)
        good = self.admin.post("/api/v1/backups/inspect", {"data": body["data"], "passphrase": PHRASE})
        self.assertEqual(good.status_code, 200, good.text)
        self.assertTrue(good.json()["backup"]["verified"])
        self.assertEqual(good.json()["backup"]["accounts"], good.json()["current"]["accounts"])

    def test_tampered_file_is_refused(self):
        body = self.create().json()
        blob = bytearray(base64.b64decode(body["data"]))
        blob[-20] ^= 0xFF
        response = self.admin.post(
            "/api/v1/backups/inspect", {"data": base64.b64encode(bytes(blob)).decode(), "passphrase": PHRASE}
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self.admin.post("/api/v1/backups/inspect", {"data": base64.b64encode(b"n'importe quoi").decode(), "passphrase": PHRASE}).status_code,
            422,
        )

    def test_restore_replaces_data_and_closes_sessions(self):
        body = self.create().json()
        before = self.account_count()
        self.as_admin()
        extra = self.admin.post("/api/v1/accounts", {
            "name": "Compte test", "bank": "Banque", "account_type": "Compte courant", "initial_balance": 10,
            "initial_date": "2026-01-01",
        })
        self.assertIn(extra.status_code, (200, 201), extra.text)
        self.assertEqual(self.account_count(), before + 1)
        wrong = self.admin.post("/api/v1/backups/restore", {"name": body["name"], "passphrase": PHRASE, "password": "mauvais"})
        self.assertEqual(wrong.status_code, 403)
        self.assertEqual(self.account_count(), before + 1)
        done = self.admin.post(
            "/api/v1/backups/restore", {"name": body["name"], "passphrase": PHRASE, "password": ADMIN_PASSWORD}
        )
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual(self.account_count(), before)
        self.assertEqual(self.admin.get("/api/v1/accounts").status_code, 401)
        # la copie d'avant restauration existe et contient le compte ajouté
        safety = done.json()["safetyCopy"]
        service = BackupService(self.database.path, self.database.backup_dir)
        self.assertEqual(service.inspect(service.resolve(safety).read_bytes(), PHRASE)["accounts"], before + 1)
        # on peut se reconnecter avec les profils de la sauvegarde
        self.login("u1", ADMIN_PASSWORD)

    def test_restore_wrong_backup_phrase_changes_nothing(self):
        body = self.create().json()
        before = self.account_count()
        response = self.admin.post(
            "/api/v1/backups/restore",
            {"name": body["name"], "passphrase": "une autre phrase secrete", "password": ADMIN_PASSWORD},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.account_count(), before)

    def test_only_admin_can_use_backups(self):
        body = self.create().json()
        lea = self.as_user(self.lea, LEA_PASSWORD)
        self.assertEqual(lea.get("/api/v1/backups").status_code, 403)
        self.assertEqual(lea.post("/api/v1/backups", {"passphrase": PHRASE, "confirm": PHRASE}).status_code, 403)
        self.assertEqual(lea.post("/api/v1/backups/download", {"name": body["name"]}).status_code, 403)

    def test_names_cannot_escape_the_backup_folder(self):
        for name in ("../valoria.db", "..\\valoria.db", "/etc/passwd", "a/b.vvb", "x.db"):
            r = self.admin.post("/api/v1/backups/download", {"name": name})
            self.assertEqual(r.status_code, 422, name)
        self.assertEqual(self.admin.post("/api/v1/backups/delete", {"name": "../valoria.db"}).status_code, 422)

    def test_delete_local_copy(self):
        body = self.create().json()
        self.assertEqual(self.admin.post("/api/v1/backups/delete", {"name": body["name"]}).status_code, 200)
        self.assertEqual(self.admin.get("/api/v1/backups").json()["backups"], [])


class BackupServiceTests(unittest.TestCase):
    def test_kdf_parameters_are_bounded(self):
        import json, struct, tempfile
        from pathlib import Path
        from app.security import backup_service as bs

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "v.db"
            conn = sqlite3.connect(db)
            conn.execute("create table accounts(id)")
            conn.execute("create table transactions(id)")
            conn.commit(); conn.close()
            service = BackupService(db, Path(tmp) / "b")
            blob, _ = service.build(PHRASE)
            offset = len(bs.MAGIC_V2)
            length = struct.unpack(">I", blob[offset : offset + 4])[0]
            header = json.loads(blob[offset + 4 : offset + 4 + length])
            header["kdf"]["n"] = 2**24
            raw = json.dumps(header).encode()
            forged = bs.MAGIC_V2 + struct.pack(">I", len(raw)) + raw + blob[offset + 4 + length :]
            with self.assertRaises(BackupError):
                service.open(forged, PHRASE)
            with self.assertRaises(WrongPassphrase):
                service.open(blob, "pas la bonne phrase du tout")


if __name__ == "__main__":
    unittest.main()


class ResetApiTests(AccessControlBase):
    PHRASE_OK = "REMETTRE À ZÉRO"

    def reset(self, password=ADMIN_PASSWORD, confirmation=PHRASE_OK, passphrase=PHRASE):
        return self.admin.post(
            "/api/v1/system/reset", {"password": password, "confirmation": confirmation, "passphrase": passphrase}
        )

    def test_wrong_password_or_confirmation_changes_nothing(self):
        self.assertEqual(self.reset(password="mauvais").status_code, 403)
        self.as_admin()
        self.assertEqual(self.reset(confirmation="oui").status_code, 422)
        self.assertEqual(self.reset(passphrase="court").status_code, 422)
        self.assertTrue(self.database.path.exists())
        self.assertEqual(self.admin.get("/api/v1/backups").json()["backups"], [])

    def test_only_admin_can_reset(self):
        lea = self.as_user(self.lea, LEA_PASSWORD)
        response = lea.post(
            "/api/v1/system/reset", {"password": LEA_PASSWORD, "confirmation": self.PHRASE_OK, "passphrase": PHRASE}
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(self.database.path.exists())

    def test_reset_keeps_a_safety_copy_and_restarts_from_first_installation(self):
        done = self.reset()
        self.assertEqual(done.status_code, 200, done.text)
        self.assertFalse(self.database.path.exists())
        status = self.client.get("/api/v1/auth/status").json()
        self.assertFalse(status["configured"])
        self.assertEqual(self.admin.get("/api/v1/accounts").status_code, 401)
        # la copie de sécurité contient toujours les données d'avant
        service = BackupService(self.database.path, self.database.backup_dir)
        safety = service.resolve(done.json()["safetyCopy"])
        self.assertIn("avant_remise_a_zero", safety.name)
        self.assertGreater(service.inspect(safety.read_bytes(), PHRASE)["accounts"], 0)
        # nouvelle installation : base vide, nouvel administrateur
        setup = self.client.post("/api/v1/auth/setup", json={"password": ADMIN_PASSWORD, "name": "Nouveau"})
        self.assertEqual(setup.status_code, 200, setup.text)
        token = setup.json()["token"]
        accounts = self.client.get("/api/v1/accounts", headers={"X-Valoria-Session": token}).json()["accounts"]
        self.assertEqual(accounts, [])

    def test_locked_database_file_is_wiped_in_place(self):
        """Sous Windows le fichier peut rester verrouillé : la base est alors vidée par SQLite."""
        from pathlib import Path
        from unittest import mock

        real_unlink = Path.unlink
        locked = Path(self.database.path)

        def fake_unlink(path, *args, **kwargs):
            if Path(path) == locked:
                raise PermissionError("verrouillé")
            return real_unlink(path, *args, **kwargs)

        with mock.patch.object(Path, "unlink", fake_unlink), mock.patch("time.sleep"):
            done = self.reset()
        self.assertEqual(done.status_code, 200, done.text)
        self.assertFalse(self.client.get("/api/v1/auth/status").json()["configured"])
        setup = self.client.post("/api/v1/auth/setup", json={"password": ADMIN_PASSWORD, "name": "Nouveau"})
        self.assertEqual(setup.status_code, 200, setup.text)
        accounts = self.client.get("/api/v1/accounts", headers={"X-Valoria-Session": setup.json()["token"]}).json()["accounts"]
        self.assertEqual(accounts, [])


class BackupLocationTests(AccessControlBase):
    def test_default_then_custom_directory_used_for_create_list_and_restore_source(self):
        import tempfile
        from pathlib import Path

        info = self.admin.get("/api/v1/backups/location").json()
        self.assertTrue(info["isDefault"])
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "Famille" / "Sauvegardes"
            probe = self.admin.post("/api/v1/backups/location/test", {"directory": str(target)})
            self.assertEqual(probe.status_code, 200, probe.text)
            self.assertFalse(probe.json()["exists"])
            saved = self.admin.put("/api/v1/backups/location", {"directory": str(target)})
            self.assertEqual(saved.status_code, 200, saved.text)
            self.assertFalse(saved.json()["isDefault"])
            self.assertTrue(target.is_dir())
            created = self.admin.post("/api/v1/backups", {"passphrase": PHRASE, "confirm": PHRASE}).json()
            self.assertTrue((target / created["name"]).is_file())
            listing = self.admin.get("/api/v1/backups").json()
            self.assertEqual(listing["directory"], str(target))
            self.assertEqual([row["name"] for row in listing["backups"]], [created["name"]])
            inspected = self.admin.post("/api/v1/backups/inspect", {"name": created["name"], "passphrase": PHRASE})
            self.assertEqual(inspected.status_code, 200, inspected.text)
            back = self.admin.put("/api/v1/backups/location", {"directory": ""})
            self.assertTrue(back.json()["isDefault"])
            self.assertEqual(self.admin.get("/api/v1/backups").json()["backups"], [])

    def test_invalid_directories_are_refused_with_a_message(self):
        import tempfile
        from pathlib import Path

        self.assertEqual(self.admin.put("/api/v1/backups/location", {"directory": "dossier/relatif"}).status_code, 422)
        with tempfile.TemporaryDirectory() as tmp:
            a_file = Path(tmp) / "fichier.txt"
            a_file.write_text("x")
            self.assertEqual(self.admin.put("/api/v1/backups/location", {"directory": str(a_file)}).status_code, 422)
        self.assertTrue(self.admin.get("/api/v1/backups/location").json()["isDefault"])

    def test_only_the_administrator_can_change_the_directory(self):
        lea = self.as_user(self.lea, LEA_PASSWORD)
        self.assertEqual(lea.get("/api/v1/backups/location").status_code, 403)
        self.assertEqual(lea.put("/api/v1/backups/location", {"directory": "C:\\\\Temp"}).status_code, 403)
        self.assertEqual(lea.post("/api/v1/backups/location/test", {"directory": "C:\\\\Temp"}).status_code, 403)


class RestoreLockedFileTests(AccessControlBase):
    def test_restore_falls_back_to_in_place_copy_when_file_cannot_be_replaced(self):
        from unittest import mock

        body = self.admin.post("/api/v1/backups", {"passphrase": PHRASE, "confirm": PHRASE}).json()
        with sqlite3.connect(self.database.path) as conn:
            before = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
        extra = self.admin.post("/api/v1/accounts", {
            "name": "Compte verrou", "bank": "Banque", "account_type": "Compte courant", "initial_balance": 10,
            "initial_date": "2026-01-01",
        })
        self.assertIn(extra.status_code, (200, 201), extra.text)
        with mock.patch.object(BackupService, "_replace_file", side_effect=PermissionError("fichier verrouillé")), \
                mock.patch("app.security.backup_service.time.sleep"):
            done = self.admin.post(
                "/api/v1/backups/restore", {"name": body["name"], "passphrase": PHRASE, "password": ADMIN_PASSWORD}
            )
        self.assertEqual(done.status_code, 200, done.text)
        with sqlite3.connect(self.database.path) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0], before)
