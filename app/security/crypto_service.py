from __future__ import annotations

import base64
import json
import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception:  # pragma: no cover - handled at runtime in app
    Fernet = None
    InvalidToken = Exception

try:
    import keyring
except Exception:  # pragma: no cover - keyring optional fallback
    keyring = None


MAGIC = b"VALORIA-VVB-v1\n"
KEYRING_SERVICE = "ValoriaVision"
KEYRING_USER = "local_database_key"


class SecurityConfigurationError(RuntimeError):
    pass


class SecurityIntegrityError(RuntimeError):
    pass


@dataclass
class EncryptionResult:
    output_path: Path
    size_bytes: int
    encrypted: bool
    algorithm: str
    created_at: str


class CryptoService:
    """Local envelope encryption for Valoria Vision.

    V0.6.0 goal:
    - encrypted database vault (.vvdb);
    - encrypted backups (.vvb);
    - integrity verification through Fernet authenticated encryption.

    The master password screen arrives in V0.6.0. Until then the key is stored
    in the OS keyring when available, with a local-file fallback for development.
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.security_dir = data_dir / "security"
        self.security_dir.mkdir(parents=True, exist_ok=True)
        self.local_key_path = self.security_dir / "valoria_local_dev.key"

    @property
    def available(self) -> bool:
        return Fernet is not None

    def _ensure_available(self) -> None:
        if Fernet is None:
            raise SecurityConfigurationError(
                "Le module cryptography est introuvable. Relancez install.bat pour installer les dépendances."
            )

    def _read_key_from_keyring(self) -> bytes | None:
        if keyring is None:
            return None
        try:
            stored = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
        except Exception:
            return None
        if not stored:
            return None
        return stored.encode("utf-8")

    def _write_key_to_keyring(self, key: bytes) -> bool:
        if keyring is None:
            return False
        try:
            keyring.set_password(KEYRING_SERVICE, KEYRING_USER, key.decode("utf-8"))
            return True
        except Exception:
            return False

    def _read_key_from_local_file(self) -> bytes | None:
        if not self.local_key_path.exists():
            return None
        return self.local_key_path.read_bytes().strip()

    def _write_key_to_local_file(self, key: bytes) -> None:
        self.local_key_path.write_bytes(key)
        try:
            os.chmod(self.local_key_path, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass

    def get_or_create_key(self) -> bytes:
        self._ensure_available()
        key = self._read_key_from_keyring()
        if key:
            return key
        key = self._read_key_from_local_file()
        if key:
            # Best effort: migrate local fallback to OS keyring.
            self._write_key_to_keyring(key)
            return key

        key = Fernet.generate_key()
        if not self._write_key_to_keyring(key):
            self._write_key_to_local_file(key)
        return key

    def key_storage_label(self) -> str:
        if self._read_key_from_keyring():
            return "coffre OS / keyring"
        if self._read_key_from_local_file():
            return "fichier local de secours"
        return "non initialisé"

    def encrypt_bytes(self, payload: bytes, metadata: dict[str, Any] | None = None) -> bytes:
        self._ensure_available()
        fernet = Fernet(self.get_or_create_key())
        encrypted = fernet.encrypt(payload)
        envelope = {
            "format": "ValoriaVisionEncryptedBackup",
            "version": 1,
            "algorithm": "Fernet-AES128-CBC-HMAC-SHA256",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "metadata": metadata or {},
            "payload": encrypted.decode("ascii"),
        }
        return MAGIC + json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8")

    def decrypt_bytes(self, envelope_bytes: bytes) -> bytes:
        self._ensure_available()
        if not envelope_bytes.startswith(MAGIC):
            raise SecurityIntegrityError("Format de sauvegarde chiffrée Valoria non reconnu.")
        raw = envelope_bytes[len(MAGIC):]
        try:
            envelope = json.loads(raw.decode("utf-8"))
            token = envelope["payload"].encode("ascii")
            fernet = Fernet(self.get_or_create_key())
            return fernet.decrypt(token)
        except InvalidToken as exc:
            raise SecurityIntegrityError("Clé invalide ou sauvegarde altérée.") from exc
        except Exception as exc:
            raise SecurityIntegrityError(f"Sauvegarde chiffrée illisible : {exc}") from exc

    def encrypt_file(self, source: Path, target: Path, metadata: dict[str, Any] | None = None) -> EncryptionResult:
        payload = source.read_bytes()
        encrypted = self.encrypt_bytes(payload, metadata)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(encrypted)
        return EncryptionResult(
            output_path=target,
            size_bytes=target.stat().st_size,
            encrypted=True,
            algorithm="Fernet",
            created_at=datetime.now().isoformat(timespec="seconds"),
        )

    def decrypt_file(self, source: Path, target: Path) -> Path:
        decrypted = self.decrypt_bytes(source.read_bytes())
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(decrypted)
        return target

    @staticmethod
    def is_encrypted_file(path: Path) -> bool:
        if not path.exists() or path.stat().st_size < len(MAGIC):
            return False
        with path.open("rb") as handle:
            return handle.read(len(MAGIC)) == MAGIC
