from __future__ import annotations

import atexit
import base64
import binascii
import re
import shutil
import sqlite3
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from app.database import SCHEMA_VERSION, Database

ROLE_ADMIN = "admin"
ROLE_CONTRIBUTOR = "contributor"
ROLE_READER = "reader"
ROLES = (ROLE_ADMIN, ROLE_CONTRIBUTOR, ROLE_READER)
ROLE_LABELS = {
    ROLE_ADMIN: "Administrateur",
    ROLE_CONTRIBUTOR: "Contributeur",
    ROLE_READER: "Lecteur",
}

MAX_NAME_LENGTH = 40
MAX_AVATAR_BYTES = 256 * 1024
DEFAULT_COLORS = ("#2563eb", "#0f766e", "#7c3aed", "#b45309", "#be123c")
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_AVATAR = re.compile(r"^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=\s]+)$")
_MAGIC = {"png": b"\x89PNG\r\n\x1a\n", "jpeg": b"\xff\xd8\xff", "webp": b"RIFF"}

USER_TABLES = ("app_users", "user_settings", "access_grants")


class UserError(ValueError):
    """Erreur de validation (nom, rôle, avatar, dernier administrateur…)."""


class UserNotFound(LookupError):
    pass


# ----------------------------------------------------------------------
# Périmètre d'un profil
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Scope:
    """Ce qu'un profil peut voir et faire.

    ``accounts`` / ``assets`` valent ``None`` quand tout est visible
    (administrateur, profil Démo). Sinon ce sont les identifiants autorisés.
    """

    user_id: int | None
    role: str
    accounts: frozenset[int] | None = None
    assets: frozenset[int] | None = None

    @property
    def restricted(self) -> bool:
        return self.accounts is not None or self.assets is not None

    @property
    def can_write(self) -> bool:
        return self.role in (ROLE_ADMIN, ROLE_CONTRIBUTOR)

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    def sees_account(self, account_id: int | None) -> bool:
        if account_id is None or self.accounts is None:
            return True
        return int(account_id) in self.accounts

    def sees_asset(self, asset_id: int | None) -> bool:
        if asset_id is None or self.assets is None:
            return True
        return int(asset_id) in self.assets


UNRESTRICTED = Scope(user_id=None, role=ROLE_ADMIN)


def _now_sql() -> str:
    return "CURRENT_TIMESTAMP"


class UserStore:
    """Profils d'accès stockés dans la base familiale commune."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Schéma
    # ------------------------------------------------------------------
    def db_exists(self) -> bool:
        return Path(self.db.path).exists()

    def ensure_schema(self) -> None:
        if not self.db_exists():
            return
        if getattr(self, "_schema_for", None) == str(self.db.path):
            return
        with self.db.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS app_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    color TEXT NOT NULL DEFAULT '#2563eb',
                    role TEXT NOT NULL DEFAULT 'reader',
                    avatar TEXT,
                    last_login_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (user_id, key),
                    FOREIGN KEY(user_id) REFERENCES app_users(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS access_grants (
                    user_id INTEGER NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id INTEGER NOT NULL,
                    PRIMARY KEY (user_id, resource_type, resource_id),
                    FOREIGN KEY(user_id) REFERENCES app_users(id) ON DELETE CASCADE
                );
                """
            )
        self._schema_for = str(self.db.path)

    def initialize_family_database(self) -> None:
        """Crée la base familiale vide (première installation uniquement)."""
        with self.db.connect() as conn:
            self.db.create_schema(conn)
            self.db.apply_migrations(conn)
            self.db.set_schema_version(conn, SCHEMA_VERSION)
        self.ensure_schema()

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------
    def _rows(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        if not self.db_exists():
            return []
        self.ensure_schema()
        with self.db.connect() as conn:
            return conn.execute(sql, params).fetchall()

    def count(self) -> int:
        rows = self._rows("SELECT COUNT(*) AS n FROM app_users")
        return int(rows[0]["n"]) if rows else 0

    def _public(self, row: sqlite3.Row, totals: dict[str, int]) -> dict:
        grants = self.grants(int(row["id"]))
        is_admin = row["role"] == ROLE_ADMIN
        configured = self.get_setting(int(row["id"]), "security.master_password_enabled") == "true"
        return {
            "id": f"u{row['id']}",
            "name": row["name"],
            "color": row["color"],
            "kind": "personal",
            "role": row["role"],
            "roleLabel": ROLE_LABELS.get(row["role"], row["role"]),
            "avatar": row["avatar"],
            "lastLoginAt": row["last_login_at"],
            "configured": configured,
            "recoveryKeyConfigured": bool(self.get_setting(int(row["id"]), "security.recovery_hash")),
            "removable": True,
            "scopeAccounts": totals["accounts"] if is_admin else len(grants["accounts"]),
            "scopeAssets": totals["assets"] if is_admin else len(grants["assets"]),
            "totalAccounts": totals["accounts"],
            "totalAssets": totals["assets"],
        }

    def totals(self) -> dict[str, int]:
        if not self.db_exists():
            return {"accounts": 0, "assets": 0}
        with self.db.connect() as conn:
            accounts = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
            assets = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
        return {"accounts": int(accounts), "assets": int(assets)}

    def list_users(self) -> list[dict]:
        rows = self._rows("SELECT * FROM app_users ORDER BY id")
        totals = self.totals()
        return [self._public(r, totals) for r in rows]

    def get_row(self, user_id: int) -> sqlite3.Row:
        rows = self._rows("SELECT * FROM app_users WHERE id = ?", (int(user_id),))
        if not rows:
            raise UserNotFound(str(user_id))
        return rows[0]

    def get(self, user_id: int) -> dict:
        return self._public(self.get_row(user_id), self.totals())

    def exists(self, user_id: int) -> bool:
        try:
            self.get_row(user_id)
            return True
        except UserNotFound:
            return False

    @staticmethod
    def parse_public_id(public_id: str | None) -> int | None:
        match = re.fullmatch(r"u(\d+)", public_id or "")
        return int(match.group(1)) if match else None

    def only_user_id(self) -> int | None:
        rows = self._rows("SELECT id FROM app_users")
        return int(rows[0]["id"]) if len(rows) == 1 else None

    # ------------------------------------------------------------------
    # Réglages d'un profil (mot de passe, clé de secours, essais…)
    # ------------------------------------------------------------------
    def get_setting(self, user_id: int, key: str, default: str = "") -> str:
        rows = self._rows("SELECT value FROM user_settings WHERE user_id = ? AND key = ?", (int(user_id), key))
        return str(rows[0]["value"]) if rows else default

    def set_setting(self, user_id: int, key: str, value: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO user_settings(user_id, key, value) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
                (int(user_id), key, value),
            )
        self.db.seal_database_to_encrypted_vault()

    def settings_for(self, user_id: int) -> "UserSettings":
        return UserSettings(self, int(user_id))

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @staticmethod
    def _clean_name(name: str) -> str:
        name = " ".join((name or "").split())
        if not name:
            raise UserError("Le nom du profil est obligatoire.")
        if len(name) > MAX_NAME_LENGTH:
            raise UserError(f"Le nom du profil ne doit pas dépasser {MAX_NAME_LENGTH} caractères.")
        return name

    @staticmethod
    def _clean_color(color: str | None, index: int) -> str:
        if color and _COLOR.match(color):
            return color.lower()
        if color:
            raise UserError("Couleur invalide.")
        return DEFAULT_COLORS[index % len(DEFAULT_COLORS)]

    @staticmethod
    def _clean_role(role: str) -> str:
        if role not in ROLES:
            raise UserError("Rôle inconnu.")
        return role

    @staticmethod
    def _clean_avatar(data_url: str) -> str:
        match = _AVATAR.match((data_url or "").strip())
        if not match:
            raise UserError("Image non prise en charge (JPG, PNG ou WebP).")
        kind = match.group(1)
        try:
            raw = base64.b64decode(re.sub(r"\s", "", match.group(2)), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise UserError("Image illisible.") from exc
        if len(raw) > MAX_AVATAR_BYTES:
            raise UserError("Image trop lourde (256 Ko maximum après réduction).")
        if not raw.startswith(_MAGIC[kind]) or (kind == "webp" and raw[8:12] != b"WEBP"):
            raise UserError("Le contenu ne correspond pas au format annoncé.")
        return data_url.strip()

    def _admin_count(self) -> int:
        rows = self._rows("SELECT COUNT(*) AS n FROM app_users WHERE role = ?", (ROLE_ADMIN,))
        return int(rows[0]["n"])

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------
    def create(
        self,
        name: str,
        role: str = ROLE_CONTRIBUTOR,
        color: str | None = None,
        avatar: str | None = None,
        accounts: list[int] | None = None,
        assets: list[int] | None = None,
    ) -> dict:
        clean_name = self._clean_name(name)
        clean_role = self._clean_role(role)
        clean_avatar = self._clean_avatar(avatar) if avatar else None
        self.ensure_schema()
        with self.db.connect() as conn:
            if conn.execute("SELECT 1 FROM app_users WHERE name = ?", (clean_name,)).fetchone():
                raise UserError("Un profil porte déjà ce nom.")
            index = conn.execute("SELECT COUNT(*) FROM app_users").fetchone()[0]
            cursor = conn.execute(
                "INSERT INTO app_users(name, color, role, avatar) VALUES (?, ?, ?, ?)",
                (clean_name, self._clean_color(color, int(index)), clean_role, clean_avatar),
            )
            user_id = int(cursor.lastrowid)
        if clean_role != ROLE_ADMIN:
            self.set_grants(user_id, accounts or [], assets or [])
        self.db.seal_database_to_encrypted_vault()
        return self.get(user_id)

    def update(
        self,
        user_id: int,
        name: str | None = None,
        color: str | None = None,
        role: str | None = None,
        avatar: str | None = None,
        clear_avatar: bool = False,
    ) -> dict:
        row = self.get_row(user_id)
        fields: dict[str, object] = {}
        if name is not None:
            clean = self._clean_name(name)
            with self.db.connect() as conn:
                other = conn.execute(
                    "SELECT 1 FROM app_users WHERE name = ? AND id <> ?", (clean, int(user_id))
                ).fetchone()
            if other:
                raise UserError("Un profil porte déjà ce nom.")
            fields["name"] = clean
        if color is not None:
            fields["color"] = self._clean_color(color, 0)
        if role is not None and role != row["role"]:
            clean_role = self._clean_role(role)
            if row["role"] == ROLE_ADMIN and self._admin_count() <= 1:
                raise UserError("Il doit rester au moins un administrateur.")
            fields["role"] = clean_role
        if clear_avatar:
            fields["avatar"] = None
        elif avatar:
            fields["avatar"] = self._clean_avatar(avatar)
        if fields:
            assignments = ", ".join(f"{column} = ?" for column in fields)
            with self.db.connect() as conn:
                conn.execute(
                    f"UPDATE app_users SET {assignments} WHERE id = ?", (*fields.values(), int(user_id))
                )
            self.db.seal_database_to_encrypted_vault()
        return self.get(user_id)

    def delete(self, user_id: int) -> None:
        row = self.get_row(user_id)
        if row["role"] == ROLE_ADMIN and self._admin_count() <= 1:
            raise UserError("Le dernier administrateur ne peut pas être supprimé.")
        with self.db.connect() as conn:
            conn.execute("DELETE FROM user_settings WHERE user_id = ?", (int(user_id),))
            conn.execute("DELETE FROM access_grants WHERE user_id = ?", (int(user_id),))
            conn.execute("DELETE FROM app_users WHERE id = ?", (int(user_id),))
        self.db.seal_database_to_encrypted_vault()

    def touch_login(self, user_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute("UPDATE app_users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?", (int(user_id),))

    # ------------------------------------------------------------------
    # Droits d'accès
    # ------------------------------------------------------------------
    def grants(self, user_id: int) -> dict[str, list[int]]:
        rows = self._rows(
            "SELECT resource_type, resource_id FROM access_grants WHERE user_id = ? ORDER BY resource_id",
            (int(user_id),),
        )
        result: dict[str, list[int]] = {"accounts": [], "assets": []}
        for row in rows:
            key = "accounts" if row["resource_type"] == "account" else "assets"
            result[key].append(int(row["resource_id"]))
        return result

    def set_grants(self, user_id: int, accounts: list[int], assets: list[int]) -> None:
        self.get_row(user_id)
        with self.db.connect() as conn:
            valid_accounts = {int(r[0]) for r in conn.execute("SELECT id FROM accounts")}
            valid_assets = {int(r[0]) for r in conn.execute("SELECT id FROM assets")}
            conn.execute("DELETE FROM access_grants WHERE user_id = ?", (int(user_id),))
            conn.executemany(
                "INSERT OR IGNORE INTO access_grants(user_id, resource_type, resource_id) VALUES (?, 'account', ?)",
                [(int(user_id), int(a)) for a in accounts if int(a) in valid_accounts],
            )
            conn.executemany(
                "INSERT OR IGNORE INTO access_grants(user_id, resource_type, resource_id) VALUES (?, 'asset', ?)",
                [(int(user_id), int(a)) for a in assets if int(a) in valid_assets],
            )
        self.db.seal_database_to_encrypted_vault()

    def grant(self, user_id: int, resource_type: str, resource_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO access_grants(user_id, resource_type, resource_id) VALUES (?, ?, ?)",
                (int(user_id), resource_type, int(resource_id)),
            )

    def access_matrix(self) -> dict:
        """Tableau « qui voit quoi » pour l'écran d'administration."""
        if not self.db_exists():
            return {"users": [], "resources": []}
        users = self.list_users()
        grants = {u["id"]: self.grants(int(u["id"][1:])) for u in users}
        with self.db.connect() as conn:
            accounts = conn.execute(
                "SELECT id, name FROM accounts ORDER BY name COLLATE NOCASE"
            ).fetchall()
            assets = conn.execute("SELECT id, name FROM assets ORDER BY name COLLATE NOCASE").fetchall()
        resources = []
        for kind, rows, key in (("account", accounts, "accounts"), ("asset", assets, "assets")):
            for row in rows:
                resources.append(
                    {
                        "type": kind,
                        "id": int(row["id"]),
                        "name": row["name"],
                        "visibleTo": [
                            u["id"]
                            for u in users
                            if u["role"] == ROLE_ADMIN or int(row["id"]) in grants[u["id"]][key]
                        ],
                    }
                )
        return {"users": users, "resources": resources}

    def scope_for(self, user_id: int) -> Scope:
        row = self.get_row(user_id)
        if row["role"] == ROLE_ADMIN:
            return Scope(user_id=int(user_id), role=ROLE_ADMIN)
        grants = self.grants(int(user_id))
        return Scope(
            user_id=int(user_id),
            role=row["role"],
            accounts=frozenset(grants["accounts"]),
            assets=frozenset(grants["assets"]),
        )

    # ------------------------------------------------------------------
    # Reprise d'une installation existante (mot de passe unique → 1er admin)
    # ------------------------------------------------------------------
    def migrate_legacy_password(self, display_name: str, avatar: str | None = None) -> dict | None:
        if not self.db_exists():
            return None
        self.ensure_schema()
        if self.count() > 0:
            return None
        if self.db.get_setting("security.master_password_enabled", "false") != "true":
            return None
        try:
            user = self.create(display_name or "Administrateur", ROLE_ADMIN, avatar=None)
        except UserError:
            user = self.create("Administrateur", ROLE_ADMIN)
        user_id = int(user["id"][1:])
        with self.db.connect() as conn:
            rows = conn.execute("SELECT key, value FROM settings WHERE key LIKE 'security.%'").fetchall()
            for row in rows:
                if row["key"].startswith("security.database_vault"):
                    continue
                conn.execute(
                    "INSERT OR REPLACE INTO user_settings(user_id, key, value) VALUES (?, ?, ?)",
                    (user_id, row["key"], row["value"]),
                )
        if avatar:
            try:
                self.update(user_id, avatar=avatar)
            except UserError:
                pass
        self.db.seal_database_to_encrypted_vault()
        return self.get(user_id)


class UserSettings:
    """Adaptateur qui laisse ``AuthService`` travailler sur les réglages d'un profil."""

    def __init__(self, store: UserStore, user_id: int) -> None:
        self.store = store
        self.user_id = user_id

    def get_setting(self, key: str, default: str = "") -> str:
        return self.store.get_setting(self.user_id, key, default)

    def set_setting(self, key: str, value: str) -> None:
        self.store.set_setting(self.user_id, key, value)

    def connect(self):
        return self.store.db.connect()

    def audit_event(self, conn, event_type, entity, entity_id, message, metadata=None):
        try:
            name = self.store.get_row(self.user_id)["name"]
        except UserNotFound:
            name = "?"
        meta = dict(metadata or {})
        meta["user_id"] = self.user_id
        self.store.db.audit_event(conn, event_type, entity, entity_id, f"[{name}] {message}", meta)


# ----------------------------------------------------------------------
# Copie filtrée de la base pour un profil à périmètre limité
# ----------------------------------------------------------------------
class ScopedDatabase(Database):
    """Copie jetable de la base familiale, réduite au périmètre d'un profil.

    Tous les calculs (tableau de bord, budgets, prévisions, rapprochement…) y
    travaillent comme sur une vraie base : les chiffres sont donc naturellement
    ceux du périmètre visible. Aucune écriture ne revient vers la base d'origine.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.data_dir = self.path.parent
        self.backup_dir = self.data_dir / "backups"
        self.secure_dir = self.data_dir / "secure"
        self.encrypted_db_path = self.secure_dir / "valoria_vision.vvdb"
        self.crypto = None  # type: ignore[assignment]

    def seal_database_to_encrypted_vault(self):  # pas de coffre pour une copie
        return None


class ScopedSnapshots:
    def __init__(self, source: Database) -> None:
        self.source = source
        self._root: Path | None = None
        self._lock = threading.Lock()
        self._cache: dict[int, list[tuple[tuple, ScopedDatabase]]] = {}
        self._counter = 0
        atexit.register(self.clear)

    def _fingerprint(self) -> tuple[int, int]:
        stat = Path(self.source.path).stat()
        return stat.st_mtime_ns, stat.st_size

    def view(self, scope: Scope) -> ScopedDatabase:
        if scope.user_id is None:
            raise ValueError("Un périmètre limité suppose un profil identifié.")
        key = (self._fingerprint(), scope.accounts, scope.assets)
        with self._lock:
            entries = self._cache.setdefault(scope.user_id, [])
            for cached_key, database in entries:
                if cached_key == key:
                    return database
            self._counter += 1
            if self._root is None:
                self._root = Path(tempfile.mkdtemp(prefix="valoria-scope-"))
            target = self._root / f"scope-{scope.user_id}-{self._counter}.db"
            self._build(target, scope)
            database = ScopedDatabase(target)
            entries.append((key, database))
            while len(entries) > 2:
                _, stale = entries.pop(0)
                stale.path.unlink(missing_ok=True)
            return database

    def _build(self, target: Path, scope: Scope) -> None:
        source = sqlite3.connect(Path(self.source.path).resolve().as_uri() + "?mode=ro", uri=True)
        copy = sqlite3.connect(target)
        try:
            source.backup(copy)
        finally:
            source.close()
        try:
            copy.row_factory = sqlite3.Row
            copy.execute("PRAGMA foreign_keys = ON")
            all_accounts = {int(r[0]) for r in copy.execute("SELECT id FROM accounts")}
            all_assets = {int(r[0]) for r in copy.execute("SELECT id FROM assets")}
            hidden_accounts = sorted(all_accounts - set(scope.accounts)) if scope.accounts is not None else []
            hidden_assets = sorted(all_assets - set(scope.assets)) if scope.assets is not None else []
            tables = [
                r[0]
                for r in copy.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
            ]
            for table in tables:
                if table in ("accounts", "assets"):
                    continue
                columns = {r[1] for r in copy.execute(f'PRAGMA table_info("{table}")')}
                if "account_id" in columns and hidden_accounts:
                    copy.execute(
                        f'DELETE FROM "{table}" WHERE account_id IN ({",".join("?" * len(hidden_accounts))})',
                        hidden_accounts,
                    )
                if "asset_id" in columns and hidden_assets:
                    copy.execute(
                        f'DELETE FROM "{table}" WHERE asset_id IN ({",".join("?" * len(hidden_assets))})',
                        hidden_assets,
                    )
            if hidden_accounts:
                copy.execute(
                    f"DELETE FROM accounts WHERE id IN ({','.join('?' * len(hidden_accounts))})", hidden_accounts
                )
            if hidden_assets:
                copy.execute(
                    f"DELETE FROM assets WHERE id IN ({','.join('?' * len(hidden_assets))})", hidden_assets
                )
            for orphan_sql in (
                "DELETE FROM reconciliation_proposals WHERE id NOT IN "
                "(SELECT proposal_id FROM reconciliation_proposal_members)",
                "DELETE FROM reconciliations WHERE id NOT IN "
                "(SELECT reconciliation_id FROM reconciliation_members)",
            ):
                try:
                    copy.execute(orphan_sql)
                except sqlite3.OperationalError:
                    pass  # schéma de rapprochement absent ou différent
            for table in USER_TABLES:
                copy.execute(f'DROP TABLE IF EXISTS "{table}"')
            copy.execute("DELETE FROM settings WHERE key LIKE 'security.%'")
            # Les budgets restent ceux de la famille : l'écart avec le réalisé d'un
            # périmètre partiel n'aurait pas de sens (voir DashboardReadService).
            copy.execute(
                "INSERT INTO settings(key, value) VALUES ('scope.restricted', '1') "
                "ON CONFLICT(key) DO UPDATE SET value = '1'"
            )
            copy.execute("DELETE FROM audit_log")
            copy.commit()
        finally:
            copy.close()

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            if self._root is not None:
                shutil.rmtree(self._root, ignore_errors=True)
            self._root = None
