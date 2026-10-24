"""Protection des données par mot de passe (chiffrement 2/3).

Cycle de vie de la base familiale quand la protection est active :

    verrouillée  : seul le coffre chiffré (.vvdb) existe sur le disque, la clé n'est nulle part ;
    ouverte      : un mot de passe (ou une clé de secours) a ouvert une serrure ; la clé est en
                   mémoire, la base de travail (.db) est recréée depuis le coffre ;
    verrouillage : le coffre est mis à jour, la base de travail est effacée, la clé est oubliée.

Ce module ne connaît ni FastAPI ni les profils : il ne manipule que les fichiers et les clés.
"""
from __future__ import annotations

import gc
import json
import re
import time
from pathlib import Path

from app.security.crypto_service import (
    CryptoService,
    SecurityIntegrityError,
    VaultLockedError,
)
from app.security.keyslots import KIND_PASSWORD, KIND_RECOVERY, KeySlotError

DIRECTORY_FILE = "directory.json"
# Champs conservés pour afficher le choix de profil quand tout est verrouillé (jamais d'avatar).
DIRECTORY_FIELDS = (
    "id", "name", "color", "kind", "role", "roleLabel", "configured",
    "recoveryKeyConfigured", "removable", "lastLoginAt", "premiumLocked",
)
# (nombre d'échecs, secondes d'attente) ; compteur en mémoire car la base est verrouillée.
LOCKED_THROTTLE_STEPS = ((5, 30), (8, 120), (10, 600))


class ProtectionError(RuntimeError):
    pass


def normalize_recovery_key(key: str) -> str:
    return re.sub(r"[\s-]", "", key or "").upper()


class ProtectionService:
    def __init__(self, database) -> None:
        self.database = database
        self.crypto: CryptoService = database.crypto
        self.directory_path = Path(database.secure_dir) / DIRECTORY_FILE
        self._failures: dict[str, tuple[int, float]] = {}

    # -- état ---------------------------------------------------------------------------
    @property
    def protected(self) -> bool:
        return self.crypto.protected

    @property
    def locked(self) -> bool:
        return self.crypto.locked

    def owners(self) -> list[str]:
        return self.crypto.slots.owners(KIND_PASSWORD) if self.protected else []

    def has_password_slot(self, user_id: int) -> bool:
        return self.protected and self.crypto.slots.has_slot(str(user_id), KIND_PASSWORD)

    # -- annuaire des profils (visible même verrouillé) -----------------------------------
    def write_directory(self, listing: list[dict]) -> None:
        entries = [{key: item.get(key) for key in DIRECTORY_FIELDS if key in item} for item in listing if item.get("kind") == "personal"]
        self.directory_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.directory_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.directory_path)

    def read_directory(self) -> list[dict]:
        try:
            raw = json.loads(self.directory_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        profiles = []
        for item in raw if isinstance(raw, list) else []:
            profiles.append({
                "avatar": None, "lastLoginAt": None, "configured": True,
                "recoveryKeyConfigured": False, "removable": True, "roleLabel": "",
                "scopeAccounts": 0, "scopeAssets": 0, "totalAccounts": 0, "totalAssets": 0,
                "pinConfigured": False, "pinAvailable": False,
                **item,
            })
        return profiles

    # -- activation -----------------------------------------------------------------------
    def enable(self, owner_id: int, password: str, recovery_key: str, listing: list[dict]) -> Path:
        """Active la protection. Retourne la copie de sécurité créée juste avant.

        Rien n'est supprimé tant que la nouvelle serrure n'a pas prouvé qu'elle rouvre le coffre ;
        à la moindre erreur, tout est remis comme avant.
        """
        if self.protected:
            raise ProtectionError("La protection par mot de passe est déjà active.")
        safety = self.database.create_backup()  # copie complète + coffre à jour
        legacy = self.crypto.legacy_key()
        if legacy is None:
            raise ProtectionError("La clé actuelle du coffre est introuvable : activation annulée.")
        try:
            self.crypto.slots.add(legacy, str(owner_id), password, KIND_PASSWORD)
            self.crypto.slots.add(legacy, str(owner_id), normalize_recovery_key(recovery_key), KIND_RECOVERY)
            opened = self.crypto.slots.open(str(owner_id), password)
            if opened != legacy:
                raise ProtectionError("La serrure ne rouvre pas le coffre : activation annulée.")
            self.crypto.unlock(opened)
            # Preuve par l'usage : le coffre actuel doit se relire avec la clé issue de la serrure.
            if self.database.encrypted_db_path.exists():
                self.crypto.decrypt_bytes(self.database.encrypted_db_path.read_bytes())
            self.write_directory(listing)
        except Exception:
            self.crypto.lock()
            self.crypto.slots.path.unlink(missing_ok=True)
            self.directory_path.unlink(missing_ok=True)
            raise
        self.crypto.purge_legacy_key()
        return safety

    # -- ouverture ------------------------------------------------------------------------
    def throttle_seconds(self, user_id: int | str) -> int:
        count, until = self._failures.get(str(user_id), (0, 0.0))
        return max(0, int(until - time.time()))

    def register_failure(self, user_id: int | str) -> int:
        count, _ = self._failures.get(str(user_id), (0, 0.0))
        count += 1
        delay = 0
        for threshold, seconds in LOCKED_THROTTLE_STEPS:
            if count >= threshold:
                delay = seconds
        self._failures[str(user_id)] = (count, time.time() + delay if delay else 0.0)
        return delay

    def unlock_with_password(self, user_id: int, password: str) -> bool:
        key = self.crypto.slots.open(str(user_id), password, KIND_PASSWORD)
        if key is None:
            return False
        self._open(key)
        self._failures.pop(str(user_id), None)
        return True

    def unlock_with_recovery(self, recovery_key: str) -> int | None:
        found = self.crypto.slots.open_any(normalize_recovery_key(recovery_key), KIND_RECOVERY)
        if found is None:
            return None
        owner, key = found
        self._open(key)
        return int(owner)

    def _open(self, key: bytes) -> None:
        """Garde la clé en mémoire puis remet la base de travail à disposition."""
        self.crypto.unlock(key)
        try:
            self.restore_working_copy()
        except Exception:
            self.crypto.lock()
            raise

    def restore_working_copy(self) -> None:
        database = self.database
        path = Path(database.path)
        vault = Path(database.encrypted_db_path)
        if path.exists() and path.stat().st_size == 0:
            path.unlink()  # fichier vide laissé par un accès accidentel : jamais une vraie base
        if path.exists():
            # Reste d'une fermeture brutale : c'est la version la plus récente, on la remet au coffre.
            database.seal_database_to_encrypted_vault()
        elif vault.exists():
            try:
                self.crypto.decrypt_file(vault, path)
            except SecurityIntegrityError as exc:
                raise ProtectionError("Le coffre ne s'ouvre pas avec cette clé.") from exc

    # -- serrures des profils -------------------------------------------------------------
    def _data_key(self) -> bytes:
        if self.crypto.locked:
            raise VaultLockedError("Les données sont verrouillées.")
        return self.crypto.get_or_create_key()

    def set_password(self, user_id: int, password: str) -> None:
        """Crée ou remplace la serrure « mot de passe » d'un profil (coffre ouvert requis)."""
        if self.protected:
            self.crypto.slots.add(self._data_key(), str(user_id), password, KIND_PASSWORD)

    def set_recovery(self, user_id: int, recovery_key: str) -> None:
        if self.protected:
            self.crypto.slots.add(self._data_key(), str(user_id), normalize_recovery_key(recovery_key), KIND_RECOVERY)

    def remove_profile(self, user_id: int) -> None:
        if self.protected:
            self.crypto.slots.remove(str(user_id))

    # -- verrouillage ---------------------------------------------------------------------
    def lock(self) -> bool:
        """Remet le coffre à jour, efface la base de travail et oublie la clé.

        Retourne vrai si la base en clair a bien été effacée. Sinon (fichier occupé sous Windows),
        la clé est tout de même oubliée et la base sera reprise au prochain déverrouillage.
        """
        if not self.protected or self.locked:
            return True
        path = Path(self.database.path)
        if path.exists():
            self.database.seal_database_to_encrypted_vault()
        removed = self._remove_working_files(path)
        self.crypto.lock()
        return removed

    @staticmethod
    def _remove_working_files(path: Path) -> bool:
        targets = [path.with_name(path.name + suffix) for suffix in ("-wal", "-shm")] + [path]
        for target in targets:
            for attempt in range(8):
                gc.collect()
                try:
                    target.unlink(missing_ok=True)
                    break
                except PermissionError:
                    if attempt == 7:
                        return False
                    time.sleep(0.25)
        return True

    # -- remise à zéro --------------------------------------------------------------------
    def reset(self) -> None:
        """Retire la protection (utilisé quand toutes les données sont effacées)."""
        self.crypto.lock()
        for target in (self.crypto.slots.path, self.directory_path):
            target.unlink(missing_ok=True)
        self._failures.clear()


__all__ = ["ProtectionService", "ProtectionError", "normalize_recovery_key", "KeySlotError"]
