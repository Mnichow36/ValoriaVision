"""Serrures de clé : le mot de passe ouvre le coffre (chiffrement 1/3, mode dormant)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet

from app.security.crypto_service import CryptoService, SecurityIntegrityError, VaultLockedError
from app.security.keyslots import KIND_RECOVERY, KeySlotError, KeySlotStore


class KeySlotStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = KeySlotStore(Path(self.tmp.name) / "secure", iterations=1000)
        self.key = Fernet.generate_key()

    def test_correct_password_opens_and_wrong_one_does_not(self):
        self.store.add(self.key, "1", "Secret-correct-1")
        self.assertEqual(self.store.open("1", "Secret-correct-1"), self.key)
        self.assertIsNone(self.store.open("1", "mauvais"))
        self.assertIsNone(self.store.open("2", "Secret-correct-1"))

    def test_file_contains_neither_password_nor_key(self):
        self.store.add(self.key, "1", "Secret-correct-1")
        raw = self.store.path.read_text(encoding="utf-8")
        self.assertNotIn("Secret-correct-1", raw)
        self.assertNotIn(self.key.decode(), raw)

    def test_each_profile_has_its_own_lock_for_the_same_key(self):
        self.store.add(self.key, "1", "Admin-pass-123")
        self.store.add(self.key, "2", "Marie-pass-456")
        self.assertEqual(self.store.open("1", "Admin-pass-123"), self.key)
        self.assertEqual(self.store.open("2", "Marie-pass-456"), self.key)
        self.assertIsNone(self.store.open("2", "Admin-pass-123"))

    def test_changing_password_replaces_the_lock(self):
        self.store.add(self.key, "1", "Ancien-pass-1")
        self.store.add(self.key, "1", "Nouveau-pass-2")
        self.assertIsNone(self.store.open("1", "Ancien-pass-1"))
        self.assertEqual(self.store.open("1", "Nouveau-pass-2"), self.key)
        self.assertEqual(len(self.store.owners()), 1)

    def test_recovery_key_is_an_independent_lock(self):
        self.store.add(self.key, "1", "Admin-pass-123")
        self.store.add(self.key, "1", "CLE-DE-SECOURS-XYZ", KIND_RECOVERY)
        self.assertEqual(self.store.open_any("CLE-DE-SECOURS-XYZ", KIND_RECOVERY), ("1", self.key))
        self.assertIsNone(self.store.open_any("autre", KIND_RECOVERY))
        self.store.remove("1", KIND_RECOVERY)
        self.assertEqual(self.store.open("1", "Admin-pass-123"), self.key)

    def test_empty_secret_is_refused(self):
        with self.assertRaises(KeySlotError):
            self.store.add(self.key, "1", "")
        self.assertIsNone(self.store.open("1", ""))

    def test_corrupted_file_keeps_the_vault_protected(self):
        self.store.add(self.key, "1", "Admin-pass-123")
        self.store.path.write_text("{ pas du json", encoding="utf-8")
        self.assertTrue(self.store.exists)
        with self.assertRaises(KeySlotError):
            self.store.owners()


class ProtectedCryptoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.crypto = CryptoService(self.dir)
        self.crypto.slots.iterations = 1000

    def _protect(self):
        legacy = self.crypto.get_or_create_key()
        self.crypto.slots.add(legacy, "1", "Admin-pass-123")
        return legacy

    def test_without_slots_nothing_changes(self):
        self.assertFalse(self.crypto.protected)
        blob = self.crypto.encrypt_bytes(b"donnees")
        self.assertEqual(self.crypto.decrypt_bytes(blob), b"donnees")

    def test_protected_vault_refuses_to_work_until_unlocked(self):
        legacy = self._protect()
        self.assertTrue(self.crypto.protected and self.crypto.locked)
        with self.assertRaises(VaultLockedError):
            self.crypto.encrypt_bytes(b"x")
        self.crypto.unlock(self.crypto.slots.open("1", "Admin-pass-123"))
        self.assertFalse(self.crypto.locked)
        blob = self.crypto.encrypt_bytes(b"donnees")
        self.assertEqual(self.crypto.decrypt_bytes(blob), b"donnees")
        # Même clé qu'avant : les sauvegardes et le coffre existants restent lisibles.
        self.assertEqual(Fernet(legacy).decrypt(__import__("json").loads(blob[len(b"VALORIA-VVB-v1\n"):])["payload"].encode()), b"donnees")

    def test_lock_forgets_the_key(self):
        self._protect()
        self.crypto.unlock(self.crypto.slots.open("1", "Admin-pass-123"))
        self.crypto_blob = self.crypto.encrypt_bytes(b"x")
        self.crypto.lock()
        with self.assertRaises(VaultLockedError):
            self.crypto.decrypt_bytes(self.crypto_blob)

    def test_protected_mode_never_generates_a_new_key(self):
        self._protect()
        self.crypto.purge_legacy_key()
        self.assertIsNone(self.crypto.legacy_key())
        with self.assertRaises(VaultLockedError):
            self.crypto.get_or_create_key()
        self.assertIsNone(self.crypto.legacy_key())

    def test_purge_removes_the_old_key_file(self):
        self.crypto.get_or_create_key()
        self.crypto.purge_legacy_key()
        self.assertIsNone(self.crypto.legacy_key())

    def test_locked_vault_is_not_mistaken_for_a_corrupted_one(self):
        self._protect()
        self.crypto.unlock(self.crypto.slots.open("1", "Admin-pass-123"))
        blob = self.crypto.encrypt_bytes(b"x")
        self.crypto.lock()
        with self.assertRaises(VaultLockedError):
            self.crypto.decrypt_bytes(blob)

    def test_wrong_key_is_still_reported_as_integrity_error(self):
        self._protect()
        self.crypto.unlock(Fernet.generate_key())
        blob = CryptoService(self.dir / "autre").encrypt_bytes(b"x")
        with self.assertRaises(SecurityIntegrityError):
            self.crypto.decrypt_bytes(blob)

    def test_label_reflects_the_mode(self):
        self.assertNotIn("mot de passe", self.crypto.key_storage_label())
        self._protect()
        self.assertEqual(self.crypto.key_storage_label(), "mot de passe (verrouillé)")


if __name__ == "__main__":
    unittest.main()
