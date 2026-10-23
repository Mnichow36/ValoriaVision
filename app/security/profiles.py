from __future__ import annotations

import base64
import binascii
import json
import re
import secrets
import shutil
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.database import Database

LEGACY_PROFILE_ID = "principal"
MAX_NAME_LENGTH = 40
MAX_AVATAR_BYTES = 256 * 1024
DEFAULT_COLORS = ("#2563eb", "#0f766e", "#7c3aed", "#b45309", "#be123c")
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_AVATAR = re.compile(r"^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=\s]+)$")
_MAGIC = {"png": b"\x89PNG\r\n\x1a\n", "jpeg": b"\xff\xd8\xff", "webp": b"RIFF"}


class ProfileError(ValueError):
    """Erreur de validation (nom, couleur, avatar…)."""


class ProfileNotFound(LookupError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _peek_setting(db_path: Path, key: str) -> str:
    """Lit un réglage en lecture seule, sans créer ni réparer la base."""
    if not db_path.exists():
        return ""
    try:
        conn = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return ""
    return str(row[0]) if row else ""


class ProfileManager:
    """Registre des profils locaux.

    Chaque profil possède sa propre base SQLite, son coffre et sa clé : rien n'est
    partagé. Le profil d'origine (la base existante) est enregistré **en place**
    sous l'identifiant « principal » : aucun fichier n'est déplacé.
    Le registre (profiles.json) ne contient que des informations d'affichage
    (nom, couleur, type, avatar) ; il ne contient aucun secret.
    """

    def __init__(self, base_dir: Path, legacy_database: Database | None = None) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.base_dir / "profiles.json"
        self.profiles_dir = self.base_dir / "profiles"
        self.avatars_dir = self.base_dir / "avatars"
        self._lock = threading.RLock()
        self._legacy = legacy_database
        self._instances: dict[str, Database] = {}
        if legacy_database is not None:
            self._instances[LEGACY_PROFILE_ID] = legacy_database

    # ------------------------------------------------------------------
    # Registre
    # ------------------------------------------------------------------
    def _read(self) -> dict:
        if self.registry_path.exists():
            try:
                data = json.loads(self.registry_path.read_text(encoding="utf-8"))
                if isinstance(data.get("profiles"), list):
                    return data
            except (OSError, ValueError):
                pass
        return {"version": 1, "profiles": []}

    def _write(self, data: dict) -> None:
        tmp = self.registry_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.registry_path)

    def _legacy_db_path(self) -> Path:
        if self._legacy is not None:
            return Path(self._legacy.path)
        return self.base_dir / "valoria_vision.db"

    def _legacy_exists(self) -> bool:
        path = self._legacy_db_path()
        vault = path.parent / "secure" / "valoria_vision.vvdb"
        return path.exists() or vault.exists()

    def _load(self) -> dict:
        data = self._read()
        known = {p["id"] for p in data["profiles"]}
        if LEGACY_PROFILE_ID not in known and self._legacy_exists():
            legacy_path = self._legacy_db_path()
            data["profiles"].insert(
                0,
                {
                    "id": LEGACY_PROFILE_ID,
                    "name": "Profil principal",
                    "color": DEFAULT_COLORS[0],
                    "kind": "personal",
                    "dir": str(legacy_path.parent.relative_to(self.base_dir))
                    if legacy_path.parent.is_relative_to(self.base_dir)
                    else str(legacy_path.parent),
                    "db": legacy_path.name,
                    "avatar": None,
                    "created_at": _now(),
                    "last_login_at": None,
                },
            )
            self._write(data)
        return data

    # ------------------------------------------------------------------
    # Accès
    # ------------------------------------------------------------------
    def _entry(self, profile_id: str) -> dict:
        for entry in self._load()["profiles"]:
            if entry["id"] == profile_id:
                return entry
        raise ProfileNotFound(profile_id)

    def _db_path(self, entry: dict) -> Path:
        return (self.base_dir / entry["dir"] / entry["db"]).resolve()

    def database_for(self, profile_id: str) -> Database:
        with self._lock:
            entry = self._entry(profile_id)
            if profile_id not in self._instances:
                key_id = None if profile_id == LEGACY_PROFILE_ID else profile_id
                self._instances[profile_id] = Database(self._db_path(entry), key_id=key_id)
            return self._instances[profile_id]

    def peek_setting(self, profile_id: str, key: str) -> str:
        return _peek_setting(self._db_path(self._entry(profile_id)), key)

    def exists(self, profile_id: str) -> bool:
        try:
            self._entry(profile_id)
            return True
        except ProfileNotFound:
            return False

    def get(self, profile_id: str) -> dict:
        return self._public(self._entry(profile_id))

    def list_profiles(self) -> list[dict]:
        with self._lock:
            return [self._public(entry) for entry in self._load()["profiles"]]

    def only_profile_id(self) -> str | None:
        profiles = self._load()["profiles"]
        return profiles[0]["id"] if len(profiles) == 1 else None

    def _public(self, entry: dict) -> dict:
        db_path = self._db_path(entry)
        return {
            "id": entry["id"],
            "name": entry["name"],
            "color": entry.get("color") or DEFAULT_COLORS[0],
            "kind": entry.get("kind", "personal"),
            "avatar": self._avatar_data_url(entry),
            "lastLoginAt": entry.get("last_login_at"),
            "configured": _peek_setting(db_path, "security.master_password_enabled") == "true",
            "recoveryKeyConfigured": bool(_peek_setting(db_path, "security.recovery_hash")),
            "removable": entry["id"] != LEGACY_PROFILE_ID,
        }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @staticmethod
    def _clean_name(name: str) -> str:
        name = " ".join((name or "").split())
        if not name:
            raise ProfileError("Le nom du profil est obligatoire.")
        if len(name) > MAX_NAME_LENGTH:
            raise ProfileError(f"Le nom du profil ne doit pas dépasser {MAX_NAME_LENGTH} caractères.")
        return name

    def _check_unique(self, data: dict, name: str, ignore_id: str | None = None) -> None:
        for entry in data["profiles"]:
            if entry["id"] != ignore_id and entry["name"].casefold() == name.casefold():
                raise ProfileError("Un profil porte déjà ce nom.")

    @staticmethod
    def _clean_color(color: str | None, index: int) -> str:
        if color and _COLOR.match(color):
            return color.lower()
        if color:
            raise ProfileError("Couleur invalide.")
        return DEFAULT_COLORS[index % len(DEFAULT_COLORS)]

    # ------------------------------------------------------------------
    # Création, modification, suppression
    # ------------------------------------------------------------------
    def create(self, name: str, color: str | None = None, kind: str = "personal") -> dict:
        if kind not in ("personal", "demo"):
            raise ProfileError("Type de profil inconnu.")
        name = self._clean_name(name)
        with self._lock:
            data = self._load()
            self._check_unique(data, name)
            if kind == "demo" and any(p.get("kind") == "demo" for p in data["profiles"]):
                raise ProfileError("Un profil Démo existe déjà.")
            profile_id = secrets.token_hex(4)
            while any(p["id"] == profile_id for p in data["profiles"]):
                profile_id = secrets.token_hex(4)
            directory = Path("profiles") / profile_id
            entry = {
                "id": profile_id,
                "name": name,
                "color": self._clean_color(color, len(data["profiles"])),
                "kind": kind,
                "dir": str(directory),
                "db": "valoria_vision.db",
                "avatar": None,
                "created_at": _now(),
                "last_login_at": None,
            }
            db = Database(self._db_path(entry), key_id=profile_id)
            try:
                with db.connect() as conn:
                    db.create_schema(conn)
                    db.apply_migrations(conn)
                    if kind == "demo":
                        db.seed_if_empty(conn)
                        db.seed_recurring_items(conn)
                    db.set_schema_version(conn, _schema_version())
            except Exception:
                shutil.rmtree(self.base_dir / directory, ignore_errors=True)
                raise
            self._instances[profile_id] = db
            data["profiles"].append(entry)
            self._write(data)
            return self._public(entry)

    def update(self, profile_id: str, name: str | None = None, color: str | None = None) -> dict:
        with self._lock:
            data = self._load()
            entry = next((p for p in data["profiles"] if p["id"] == profile_id), None)
            if entry is None:
                raise ProfileNotFound(profile_id)
            if name is not None:
                clean = self._clean_name(name)
                self._check_unique(data, clean, ignore_id=profile_id)
                entry["name"] = clean
            if color is not None:
                entry["color"] = self._clean_color(color, 0)
            self._write(data)
            return self._public(entry)

    def touch_login(self, profile_id: str) -> None:
        with self._lock:
            data = self._load()
            for entry in data["profiles"]:
                if entry["id"] == profile_id:
                    entry["last_login_at"] = _now()
            self._write(data)

    def delete(self, profile_id: str) -> None:
        with self._lock:
            if profile_id == LEGACY_PROFILE_ID:
                raise ProfileError("Le profil d'origine ne peut pas être supprimé dans cette version.")
            data = self._load()
            entry = next((p for p in data["profiles"] if p["id"] == profile_id), None)
            if entry is None:
                raise ProfileNotFound(profile_id)
            self.set_avatar(profile_id, None)
            data = self._load()
            data["profiles"] = [p for p in data["profiles"] if p["id"] != profile_id]
            self._write(data)
            self._instances.pop(profile_id, None)
            shutil.rmtree(self.base_dir / entry["dir"], ignore_errors=True)

    # ------------------------------------------------------------------
    # Avatar (image réduite côté interface, stockée hors coffre pour être
    # affichable avant la connexion)
    # ------------------------------------------------------------------
    def _avatar_path(self, entry: dict) -> Path | None:
        name = entry.get("avatar")
        return self.avatars_dir / name if name else None

    def _avatar_data_url(self, entry: dict) -> str | None:
        path = self._avatar_path(entry)
        if path is None or not path.exists():
            return None
        ext = path.suffix.lstrip(".")
        mime = "jpeg" if ext in ("jpg", "jpeg") else ext
        return f"data:image/{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")

    def set_avatar(self, profile_id: str, data_url: str | None) -> dict:
        with self._lock:
            data = self._load()
            entry = next((p for p in data["profiles"] if p["id"] == profile_id), None)
            if entry is None:
                raise ProfileNotFound(profile_id)
            old = self._avatar_path(entry)
            if data_url:
                match = _AVATAR.match(data_url.strip())
                if not match:
                    raise ProfileError("Image non prise en charge (JPG, PNG ou WebP).")
                kind = match.group(1)
                try:
                    raw = base64.b64decode(re.sub(r"\s", "", match.group(2)), validate=True)
                except (binascii.Error, ValueError) as exc:
                    raise ProfileError("Image illisible.") from exc
                if len(raw) > MAX_AVATAR_BYTES:
                    raise ProfileError("Image trop lourde (256 Ko maximum après réduction).")
                if not raw.startswith(_MAGIC[kind]) or (kind == "webp" and raw[8:12] != b"WEBP"):
                    raise ProfileError("Le contenu ne correspond pas au format annoncé.")
                self.avatars_dir.mkdir(parents=True, exist_ok=True)
                name = f"{profile_id}-{secrets.token_hex(3)}.{'jpg' if kind == 'jpeg' else kind}"
                (self.avatars_dir / name).write_bytes(raw)
                entry["avatar"] = name
            else:
                entry["avatar"] = None
            self._write(data)
            if old is not None and old.exists() and old.name != entry["avatar"]:
                old.unlink(missing_ok=True)
            return self._public(entry)


def _schema_version() -> int:
    from app.database import SCHEMA_VERSION

    return SCHEMA_VERSION
