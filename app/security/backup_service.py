"""Sauvegardes chiffrées portables (.vvb v2).

Le fichier est protégé par une phrase secrète choisie par l'utilisateur
(scrypt -> AES-256-GCM) et non par une clé liée à l'ordinateur : il peut être
restauré sur n'importe quelle machine. Les anciens .vvb (clé locale) restent
lisibles sur l'ordinateur qui les a créés.

Disposition du fichier :
    MAGIC | longueur de l'en-tête (4 octets) | en-tête JSON | contenu chiffré
L'en-tête (paramètres scrypt, nonce, résumé du contenu) est authentifié : toute
modification fait échouer le déchiffrement.
"""

from __future__ import annotations

import base64
import json
import os
import re
import sqlite3
import struct
import tempfile
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC_V2 = b"VALORIA-VVB-v2\n"
MAGIC_V1 = b"VALORIA-VVB-v1\n"
FORMAT_NAME = "ValoriaVisionBackup"
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**15, 8, 1
MAX_N, MAX_R, MAX_P = 2**17, 8, 2
MIN_PASSPHRASE = 10
NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,120}\.vvb$")
REQUIRED_TABLES = ("accounts", "transactions")
COUNTED_TABLES = {
    "accounts": "accounts",
    "assets": "assets",
    "transactions": "transactions",
    "users": "app_users",
    "budgets": "budgets",
}


class BackupError(Exception):
    """Erreur affichable telle quelle à l'utilisateur."""


class WrongPassphrase(BackupError):
    pass


@dataclass
class OpenedBackup:
    info: dict[str, Any]
    database: bytes
    legacy: bool = False


def passphrase_problem(passphrase: str) -> str | None:
    if len(passphrase) < MIN_PASSPHRASE:
        return f"La phrase secrète doit contenir au moins {MIN_PASSPHRASE} caractères."
    if len(set(passphrase)) < 4:
        return "La phrase secrète est trop répétitive."
    return None


def passphrase_strength(passphrase: str) -> int:
    """0 à 4, utilisé seulement pour l'indication visuelle côté interface."""
    score = 0
    if len(passphrase) >= MIN_PASSPHRASE:
        score += 1
    if len(passphrase) >= 16:
        score += 1
    if len(passphrase.split()) >= 3 or len(passphrase) >= 24:
        score += 1
    classes = sum(
        bool(re.search(pattern, passphrase)) for pattern in (r"[a-z]", r"[A-Z]", r"\d", r"[^\w\s]")
    )
    if classes >= 3:
        score += 1
    return min(score, 4)


def _derive(passphrase: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return Scrypt(salt=salt, length=32, n=n, r=r, p=p).derive(passphrase.encode("utf-8"))


def count_content(database_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    conn = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)
    try:
        for key, table in COUNTED_TABLES.items():
            try:
                counts[key] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            except sqlite3.DatabaseError:
                counts[key] = 0
    finally:
        conn.close()
    return counts


def verify_database_file(path: Path) -> dict[str, int]:
    """Contrôle qu'un fichier est une base Valoria saine ; renvoie son contenu."""
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            verdict = conn.execute("PRAGMA integrity_check").fetchone()
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise BackupError("Le contenu de la sauvegarde n'est pas une base de données lisible.") from exc
    if not verdict or verdict[0] != "ok":
        raise BackupError("La base contenue dans la sauvegarde est endommagée.")
    missing = [name for name in REQUIRED_TABLES if name not in tables]
    if missing:
        raise BackupError("Ce fichier n'est pas une sauvegarde Valoria Vision (tables manquantes).")
    return count_content(path)


class BackupService:
    def __init__(
        self,
        database_path: Path,
        backup_dir: Path,
        legacy_decrypt: Callable[[bytes], bytes] | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.backup_dir = Path(backup_dir)
        self.legacy_decrypt = legacy_decrypt

    # ------------------------------------------------------------------
    # Création
    # ------------------------------------------------------------------
    def snapshot_bytes(self) -> bytes:
        """Copie cohérente de la base en cours d'utilisation (API de sauvegarde SQLite)."""
        if not self.database_path.exists():
            raise BackupError("Base de données introuvable.")
        with tempfile.TemporaryDirectory(prefix="valoria-backup-") as tmp:
            target = Path(tmp) / "snapshot.db"
            source = sqlite3.connect(f"file:{self.database_path.as_posix()}?mode=ro", uri=True)
            copy = sqlite3.connect(target)
            try:
                source.backup(copy)
            finally:
                copy.close()
                source.close()
            verify_database_file(target)
            return target.read_bytes()

    def build(self, passphrase: str, kind: str = "manual", database: bytes | None = None) -> tuple[bytes, dict]:
        problem = passphrase_problem(passphrase)
        if problem:
            raise BackupError(problem)
        data = database if database is not None else self.snapshot_bytes()
        with tempfile.TemporaryDirectory(prefix="valoria-backup-") as tmp:
            probe = Path(tmp) / "probe.db"
            probe.write_bytes(data)
            counts = verify_database_file(probe)
        info = {"createdAt": datetime.now().isoformat(timespec="seconds"), "kind": kind, **counts}
        salt, nonce = os.urandom(16), os.urandom(12)
        header = {
            "format": FORMAT_NAME,
            "version": 2,
            "cipher": "AES-256-GCM",
            "kdf": {"name": "scrypt", "n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P, "salt": base64.b64encode(salt).decode()},
            "nonce": base64.b64encode(nonce).decode(),
            "info": info,
        }
        header_bytes = json.dumps(header, ensure_ascii=False, sort_keys=True).encode("utf-8")
        key = _derive(passphrase, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
        ciphertext = AESGCM(key).encrypt(nonce, zlib.compress(data, 6), header_bytes)
        blob = MAGIC_V2 + struct.pack(">I", len(header_bytes)) + header_bytes + ciphertext
        # Contrôle de bout en bout : on relit et déchiffre ce qu'on vient de produire.
        reopened = self.open(blob, passphrase)
        if reopened.database != data:
            raise BackupError("Le contrôle de la sauvegarde a échoué ; elle n'a pas été conservée.")
        return blob, info

    def save_local(self, blob: bytes, kind: str = "manual") -> Path:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = "valoria_vision_backup" if kind == "manual" else "valoria_vision_avant_restauration"
        target = self.backup_dir / f"{prefix}_{stamp}.vvb"
        counter = 1
        while target.exists():
            target = self.backup_dir / f"{prefix}_{stamp}_{counter}.vvb"
            counter += 1
        temporary = target.with_suffix(".vvb.tmp")
        temporary.write_bytes(blob)
        os.replace(temporary, target)
        return target

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------
    @staticmethod
    def is_v2(blob: bytes) -> bool:
        return blob.startswith(MAGIC_V2)

    @staticmethod
    def is_legacy(blob: bytes) -> bool:
        return blob.startswith(MAGIC_V1)

    def read_header(self, blob: bytes) -> dict[str, Any]:
        """Résumé lisible sans phrase secrète (date, nombre d'éléments)."""
        if self.is_legacy(blob):
            return {"legacy": True, "kind": "legacy"}
        header, _ = self._split(blob)
        return {**header.get("info", {}), "legacy": False}

    def _split(self, blob: bytes) -> tuple[dict[str, Any], bytes]:
        if not self.is_v2(blob):
            raise BackupError("Ce fichier n'est pas une sauvegarde Valoria Vision.")
        try:
            offset = len(MAGIC_V2)
            (length,) = struct.unpack(">I", blob[offset : offset + 4])
            header_bytes = blob[offset + 4 : offset + 4 + length]
            if len(header_bytes) != length or length > 65536:
                raise ValueError("en-tête tronqué")
            header = json.loads(header_bytes.decode("utf-8"))
        except (struct.error, ValueError, UnicodeDecodeError) as exc:
            raise BackupError("Le fichier de sauvegarde est incomplet ou endommagé.") from exc
        if header.get("format") != FORMAT_NAME or header.get("version") != 2:
            raise BackupError("Version de sauvegarde non reconnue.")
        return header, blob[offset + 4 + length :]

    def open(self, blob: bytes, passphrase: str) -> OpenedBackup:
        if self.is_legacy(blob):
            if self.legacy_decrypt is None:
                raise BackupError("Ancienne sauvegarde non lisible ici.")
            try:
                data = self.legacy_decrypt(blob)
            except Exception as exc:
                raise BackupError(
                    "Cette ancienne sauvegarde est liée à l'ordinateur qui l'a créée et ne peut pas être lue ici."
                ) from exc
            return OpenedBackup({"kind": "legacy"}, data, legacy=True)
        header, ciphertext = self._split(blob)
        try:
            kdf = header["kdf"]
            n, r, p = int(kdf["n"]), int(kdf["r"]), int(kdf["p"])
            if kdf.get("name") != "scrypt" or n > MAX_N or r > MAX_R or p > MAX_P or n < 2**10:
                raise ValueError("paramètres refusés")
            salt = base64.b64decode(kdf["salt"])
            nonce = base64.b64decode(header["nonce"])
        except (KeyError, ValueError, TypeError) as exc:
            raise BackupError("Le fichier de sauvegarde est incomplet ou endommagé.") from exc
        offset = len(MAGIC_V2)
        header_bytes = blob[offset + 4 : offset + 4 + struct.unpack(">I", blob[offset : offset + 4])[0]]
        try:
            plain = AESGCM(_derive(passphrase, salt, n, r, p)).decrypt(nonce, ciphertext, header_bytes)
            data = zlib.decompress(plain)
        except InvalidTag as exc:
            raise WrongPassphrase("Phrase secrète incorrecte, ou fichier modifié.") from exc
        except zlib.error as exc:
            raise BackupError("Le contenu de la sauvegarde est endommagé.") from exc
        return OpenedBackup({**header.get("info", {})}, data)

    def inspect(self, blob: bytes, passphrase: str) -> dict[str, Any]:
        opened = self.open(blob, passphrase)
        with tempfile.TemporaryDirectory(prefix="valoria-backup-") as tmp:
            probe = Path(tmp) / "probe.db"
            probe.write_bytes(opened.database)
            counts = verify_database_file(probe)
        return {**opened.info, **counts, "legacy": opened.legacy, "verified": True}

    # ------------------------------------------------------------------
    # Copies locales
    # ------------------------------------------------------------------
    def resolve(self, name: str) -> Path:
        if not NAME_PATTERN.match(name or ""):
            raise BackupError("Nom de sauvegarde invalide.")
        path = self.backup_dir / name
        if not path.is_file():
            raise BackupError("Sauvegarde introuvable.")
        return path

    def list_local(self) -> list[dict[str, Any]]:
        if not self.backup_dir.exists():
            return []
        rows = []
        for path in self.backup_dir.glob("*.vvb"):
            if not NAME_PATTERN.match(path.name):
                continue
            try:
                with path.open("rb") as handle:
                    head = handle.read(70000)
                info = self.read_header(head) if not self.is_legacy(head) else {"legacy": True, "kind": "legacy"}
            except Exception:
                info = {"damaged": True, "kind": "unknown"}
            stat = path.stat()
            rows.append(
                {
                    "name": path.name,
                    "size": stat.st_size,
                    "modifiedAt": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    **info,
                }
            )
        rows.sort(key=lambda row: row["modifiedAt"], reverse=True)
        return rows

    def delete_local(self, name: str) -> None:
        self.resolve(name).unlink()

    # ------------------------------------------------------------------
    # Restauration
    # ------------------------------------------------------------------
    def restore(self, blob: bytes, passphrase: str) -> Path:
        """Remplace la base par celle de la sauvegarde ; renvoie la copie d'avant restauration.

        Pour une ancienne sauvegarde (clé de l'ordinateur), la phrase fournie sert à
        protéger la copie d'avant restauration.

        Ordre : lecture + contrôle complet de la sauvegarde, copie de l'état
        actuel, puis échange atomique du fichier. Rien n'est touché si une
        étape échoue avant l'échange.
        """
        opened = self.open(blob, passphrase)
        with tempfile.TemporaryDirectory(prefix="valoria-restore-") as tmp:
            probe = Path(tmp) / "probe.db"
            probe.write_bytes(opened.database)
            verify_database_file(probe)
        safety_path: Path | None = None
        if self.database_path.exists():
            safety_blob, _ = self.build(passphrase, kind="pre-restore")
            safety_path = self.save_local(safety_blob, kind="pre-restore")
        staging = self.database_path.with_name(self.database_path.name + ".restore")
        staging.write_bytes(opened.database)
        try:
            for suffix in ("-wal", "-shm"):
                self.database_path.with_name(self.database_path.name + suffix).unlink(missing_ok=True)
            try:
                os.replace(staging, self.database_path)
            except OSError as exc:
                raise BackupError(
                    "Impossible de remplacer la base (fichier utilisé par un autre programme). "
                    "Fermez les autres fenêtres Valoria puis réessayez ; vos données n'ont pas été modifiées."
                ) from exc
        finally:
            staging.unlink(missing_ok=True)
        return safety_path or self.database_path

