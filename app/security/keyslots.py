"""Serrures de clé : le mot de passe ouvre le coffre.

Principe (comme un coffre à plusieurs serrures) :
- le coffre est chiffré par UNE clé de données (32 octets, format Fernet) ;
- cette clé n'est jamais écrite telle quelle sur le disque ;
- chaque profil a une « serrure » : la clé de données chiffrée par une clé dérivée de son
  mot de passe (PBKDF2), plus une serrure pour sa clé de secours ;
- un mauvais mot de passe ne déchiffre rien : on ne compare jamais de mot de passe, on essaie
  d'ouvrir la serrure (le chiffrement authentifié échoue si le secret est faux).

Le fichier ``secure/keyslots.json`` ne contient donc ni mot de passe ni clé en clair.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from datetime import datetime
from pathlib import Path

try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception:  # pragma: no cover
    Fernet = None
    InvalidToken = Exception

KEYSLOTS_FILE = "keyslots.json"
KEYSLOTS_VERSION = 1
SLOT_ITERATIONS = 390_000
KIND_PASSWORD = "password"
KIND_RECOVERY = "recovery"


class KeySlotError(RuntimeError):
    pass


def _wrapping_key(secret: str, salt: bytes, iterations: int) -> bytes:
    derived = hashlib.pbkdf2_hmac("sha256", secret.encode("utf-8"), salt, iterations, dklen=32)
    return base64.urlsafe_b64encode(derived)


class KeySlotStore:
    """Lit et écrit les serrures d'un coffre (un fichier JSON à côté du coffre)."""

    def __init__(self, secure_dir: Path, iterations: int = SLOT_ITERATIONS) -> None:
        self.path = Path(secure_dir) / KEYSLOTS_FILE
        self.iterations = iterations

    # -- lecture / écriture du fichier ------------------------------------------------
    def _load(self) -> dict:
        if not self.path.exists():
            return {"version": KEYSLOTS_VERSION, "slots": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise KeySlotError("Le fichier des serrures de clé est illisible.") from exc
        if not isinstance(data, dict) or not isinstance(data.get("slots"), list):
            raise KeySlotError("Le fichier des serrures de clé est invalide.")
        return data

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.path)  # écriture atomique : jamais de fichier à moitié écrit

    # -- état -------------------------------------------------------------------------
    @property
    def exists(self) -> bool:
        """Vrai dès qu'au moins une serrure existe : le coffre est alors « protégé »."""
        try:
            return bool(self._load()["slots"])
        except KeySlotError:
            # Un fichier abîmé ne doit surtout pas faire repasser le coffre en mode ouvert.
            return self.path.exists()

    def owners(self, kind: str = KIND_PASSWORD) -> list[str]:
        return [slot["owner"] for slot in self._load()["slots"] if slot["kind"] == kind]

    def has_slot(self, owner: str, kind: str = KIND_PASSWORD) -> bool:
        return any(slot["owner"] == owner and slot["kind"] == kind for slot in self._load()["slots"])

    # -- serrures ---------------------------------------------------------------------
    def add(self, data_key: bytes, owner: str, secret: str, kind: str = KIND_PASSWORD) -> None:
        """Crée (ou remplace) la serrure de ``owner`` : ``data_key`` chiffrée par ``secret``."""
        if Fernet is None:
            raise KeySlotError("Le module cryptography est introuvable.")
        if not secret:
            raise KeySlotError("Un secret vide ne peut pas fermer une serrure.")
        salt = secrets.token_bytes(16)
        wrapped = Fernet(_wrapping_key(secret, salt, self.iterations)).encrypt(data_key)
        data = self._load()
        data["slots"] = [s for s in data["slots"] if not (s["owner"] == owner and s["kind"] == kind)]
        data["slots"].append({
            "owner": str(owner),
            "kind": kind,
            "salt": base64.b64encode(salt).decode("ascii"),
            "iterations": self.iterations,
            "wrapped": wrapped.decode("ascii"),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        })
        self._save(data)

    def open(self, owner: str, secret: str, kind: str = KIND_PASSWORD) -> bytes | None:
        """Ouvre la serrure : retourne la clé de données, ou ``None`` si le secret est faux."""
        if Fernet is None or not secret:
            return None
        for slot in self._load()["slots"]:
            if slot["owner"] == owner and slot["kind"] == kind:
                try:
                    key = _wrapping_key(secret, base64.b64decode(slot["salt"]), int(slot["iterations"]))
                    return Fernet(key).decrypt(slot["wrapped"].encode("ascii"))
                except (InvalidToken, ValueError, KeyError):
                    return None
        return None

    def open_any(self, secret: str, kind: str = KIND_PASSWORD) -> tuple[str, bytes] | None:
        """Essaie toutes les serrures du type donné (utile pour une clé de secours)."""
        for owner in self.owners(kind):
            key = self.open(owner, secret, kind)
            if key is not None:
                return owner, key
        return None

    def remove(self, owner: str, kind: str | None = None) -> None:
        data = self._load()
        data["slots"] = [
            s for s in data["slots"]
            if not (s["owner"] == owner and (kind is None or s["kind"] == kind))
        ]
        self._save(data)

    def created_at(self, owner: str, kind: str = KIND_PASSWORD) -> str | None:
        for slot in self._load()["slots"]:
            if slot["owner"] == owner and slot["kind"] == kind:
                return slot.get("created_at")
        return None
