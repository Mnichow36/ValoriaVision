from __future__ import annotations

import shutil
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.services.counterparty_parser import extract_counterparty
from app.services.business_rules import balance_at_date, is_current_expense, is_patrimonial_asset, is_true_income, summarize_accounts_at_date
from app.services.forecast_reconciliation_service import ForecastReconciliationService
from app.services.reconciliation import (
    ReconciliationRules,
    affected_transactions_for_occurrences,
    qualify_and_persist_transaction,
    reevaluate_all_transactions,
    reevaluate_for_occurrences,
    reevaluate_transaction,
)
from app.security.crypto_service import CryptoService, SecurityIntegrityError
from app.migrations.r8_reconciliation import apply_r8_reconciliation_foundation

ROOT_DIR = Path(__file__).resolve().parent.parent

FORECAST_SCENARIO_PRESETS = {
    "Réaliste": {
        "description": "Montants prévisionnels conservés tels qu’ils ont été saisis.",
        "income_percent": 100.0,
        "expense_percent": 100.0,
        "color": "#2563eb",
    },
    "Prudent": {
        "description": "Recettes minorées et dépenses majorées pour anticiper une situation tendue.",
        "income_percent": 90.0,
        "expense_percent": 110.0,
        "color": "#e11d48",
    },
    "Optimiste": {
        "description": "Recettes majorées et dépenses minorées pour visualiser un contexte favorable.",
        "income_percent": 110.0,
        "expense_percent": 95.0,
        "color": "#7c3aed",
    },
}


def default_data_dir() -> Path:
    """Return a stable, per-user directory for Valoria data.

    PyInstaller one-file applications are extracted to a temporary directory at
    every launch. Storing the database relative to __file__ therefore loses the
    apparent database on restart. VALORIA_DATA_DIR remains available for tests,
    support and portable development setups.
    """
    override = os.environ.get("VALORIA_DATA_DIR")
    if override:
        return Path(override).expanduser()

    if sys.platform == "win32":
        windows_root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if windows_root:
            return Path(windows_root) / "ValoriaVision"

    xdg_root = os.environ.get("XDG_DATA_HOME")
    if xdg_root:
        return Path(xdg_root) / "ValoriaVision"
    return Path.home() / ".local" / "share" / "ValoriaVision"


DATA_DIR = default_data_dir()
BACKUP_DIR = DATA_DIR / "backups"
SECURE_DIR = DATA_DIR / "secure"
ENCRYPTED_DB_PATH = SECURE_DIR / "valoria_vision.vvdb"
DB_PATH = DATA_DIR / "valoria_vision.db"
SCHEMA_VERSION = 16


@dataclass
class Account:
    id: int
    name: str
    bank: str
    account_type: str
    identifier: str
    reference_balance: float
    reference_date: str
    initial_balance: float
    initial_date: str
    currency: str
    status: str


class Database:
    """SQLite data layer for Valoria Vision.

    V0.3.0 consolidates:
    - schema metadata and migrations;
    - account balance calculations;
    - import batches;
    - settings/categories;
    - backup and restore helpers.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else DB_PATH
        self.data_dir = self.path.parent
        self.backup_dir = self.data_dir / "backups"
        self.secure_dir = self.data_dir / "secure"
        self.encrypted_db_path = self.secure_dir / "valoria_vision.vvdb"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.crypto = CryptoService(self.data_dir)

    def restore_plain_database_from_encrypted_vault(self) -> bool:
        """Restore the working SQLite file from the encrypted local vault.

        If a packaged or stale vault was encrypted with another local key,
        Fernet raises InvalidToken. In that case the app must not crash: the
        unreadable vault is quarantined and the normal initialization flow
        creates/uses a valid local database.
        """
        if self.path.exists() or not self.encrypted_db_path.exists():
            return False
        try:
            self.crypto.decrypt_file(self.encrypted_db_path, self.path)
            return True
        except SecurityIntegrityError as exc:
            self.quarantine_invalid_encrypted_vault(str(exc))
            return False

    def quarantine_invalid_encrypted_vault(self, reason: str = "invalid_encrypted_vault") -> Path | None:
        """Move an unreadable encrypted vault aside.

        This protects the app from startup crashes when a .vvdb file was copied
        from another installation or generated with another key.
        """
        if not self.encrypted_db_path.exists():
            return None
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = self.backup_dir / f"valoria_vision_invalid_vault_{stamp}.vvdb"
        counter = 1
        while target.exists():
            target = self.backup_dir / f"valoria_vision_invalid_vault_{stamp}_{counter}.vvdb"
            counter += 1
        shutil.move(str(self.encrypted_db_path), str(target))
        try:
            self.path.unlink(missing_ok=True)
        except Exception:
            pass
        return target

    def seal_database_to_encrypted_vault(self) -> Path | None:
        """Create/update the encrypted local vault from the current SQLite DB."""
        if not self.path.exists():
            return None
        self.secure_dir.mkdir(parents=True, exist_ok=True)
        self.crypto.encrypt_file(
            self.path,
            self.encrypted_db_path,
            metadata={
                "kind": "database_vault",
                "source": self.path.name,
                "schema_version": SCHEMA_VERSION,
            },
        )
        return self.encrypted_db_path

    def encrypted_backup_path(self, target_dir: Path, stamp: str) -> Path:
        return target_dir / f"valoria_vision_backup_{stamp}.vvb"

    def database_encryption_status(self) -> dict:
        return {
            "encrypted_vault_exists": self.encrypted_db_path.exists(),
            "encrypted_vault_path": str(self.encrypted_db_path),
            "active_sqlite_exists": self.path.exists(),
            "active_sqlite_path": str(self.path),
            "crypto_available": self.crypto.available,
            "key_storage": self.crypto.key_storage_label(),
        }


    def quarantine_invalid_database(self, reason: str = "invalid_sqlite") -> Path | None:
        """Move a non-SQLite/corrupt database aside instead of crashing.

        This protects the app from the SQLite error:
        "sqlite3.DatabaseError: file is not a database".

        The file is not deleted. It is moved into data/backups so the user can
        keep it for inspection or recovery.
        """
        if not self.path.exists() or self.path.stat().st_size == 0:
            return None
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = self.backup_dir / f"valoria_vision_{reason}_{stamp}.db"
        counter = 1
        while target.exists():
            target = self.backup_dir / f"valoria_vision_{reason}_{stamp}_{counter}.db"
            counter += 1
        shutil.move(str(self.path), str(target))
        return target

    def ensure_valid_database_file(self) -> Path | None:
        """Validate the SQLite file and quarantine it if it is not a database."""
        if not self.path.exists() or self.path.stat().st_size == 0:
            return None
        try:
            probe = sqlite3.connect(self.path)
            try:
                probe.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
            finally:
                probe.close()
            return None
        except sqlite3.DatabaseError:
            return self.quarantine_invalid_database("invalid_sqlite")

    def connect(self) -> sqlite3.Connection:
        recovered = self.ensure_valid_database_file()
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        if recovered is not None:
            # We just created a new empty DB after quarantining a bad file.
            # Make it immediately usable for the current screen/action.
            self.create_schema(conn)
            self.apply_migrations(conn)
            self.seed_if_empty(conn)
            self.seed_recurring_items(conn)
            self.set_schema_version(conn, SCHEMA_VERSION)
            self.set_setting("last_invalid_database_quarantine", str(recovered))
        return conn

    def initialize(self) -> None:
        self.restore_plain_database_from_encrypted_vault()
        self.ensure_valid_database_file()
        with self.connect() as conn:
            self.create_schema(conn)
            self.apply_migrations(conn)
            self.seed_if_empty(conn)
            self.seed_recurring_items(conn)
            self.set_schema_version(conn, SCHEMA_VERSION)
        self.seal_database_to_encrypted_vault()
        self.set_setting("security.database_vault_path", str(self.encrypted_db_path))

    def prepare_existing_database(self) -> bool:
        """Apply schema migrations to an existing local database for API use.

        The React API must never create a new user database implicitly. It does,
        however, need the same schema upgrades as the desktop application before
        invoking business methods that rely on newer transaction columns.
        """
        if not self.path.exists():
            return False
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                self.create_schema(conn)
                self.apply_migrations(conn)
                self.set_schema_version(conn, SCHEMA_VERSION)
        finally:
            conn.close()
        return True

    def create_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL DEFAULT 'Dépense',
                direction TEXT NOT NULL DEFAULT 'Dépense',
                color TEXT,
                is_system INTEGER NOT NULL DEFAULT 0,
                budget_enabled INTEGER NOT NULL DEFAULT 1,
                uuid TEXT,
                deleted_at TEXT,
                sync_status TEXT NOT NULL DEFAULT 'local',
                external_id TEXT,
                external_source TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                bank TEXT NOT NULL,
                account_type TEXT NOT NULL,
                identifier TEXT,
                reference_balance REAL NOT NULL DEFAULT 0,
                reference_date TEXT NOT NULL,
                initial_balance REAL NOT NULL DEFAULT 0,
                initial_date TEXT,
                currency TEXT NOT NULL DEFAULT 'EUR',
                status TEXT NOT NULL DEFAULT 'Actif',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                tx_date TEXT NOT NULL,
                label TEXT NOT NULL,
                beneficiary TEXT,
                category TEXT,
                amount REAL NOT NULL,
                tx_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Validée',
                source TEXT NOT NULL DEFAULT 'Manuel',
                import_batch_id INTEGER,
                signature TEXT,
                categorization_status TEXT NOT NULL DEFAULT 'to_categorize',
                categorized_by TEXT,
                categorization_rule_id INTEGER,
                categorized_at TEXT,
                currency TEXT NOT NULL DEFAULT 'EUR',
                source_line INTEGER,
                source_profile TEXT,
                raw_payload TEXT,
                source_identifier TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT,
                FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE,
                FOREIGN KEY(import_batch_id) REFERENCES import_batches(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS import_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                account_id INTEGER NOT NULL,
                imported_count INTEGER NOT NULL DEFAULT 0,
                duplicate_count INTEGER NOT NULL DEFAULT 0,
                error_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Importé',
                canceled_at TEXT,
                parser_profile TEXT,
                source_fingerprint TEXT,
                diagnostic_summary TEXT,
                header_line INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS categorization_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                priority INTEGER NOT NULL DEFAULT 100,
                match_field TEXT NOT NULL,
                match_operator TEXT NOT NULL,
                match_value TEXT NOT NULL,
                transaction_type TEXT,
                account_id INTEGER,
                min_amount REAL,
                max_amount REAL,
                target_category_id INTEGER NOT NULL,
                confidence INTEGER NOT NULL DEFAULT 100,
                last_used_at TEXT,
                usage_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                deleted_at TEXT,
                FOREIGN KEY(target_category_id) REFERENCES categories(id),
                FOREIGN KEY(account_id) REFERENCES accounts(id)
            );

            CREATE TABLE IF NOT EXISTS categorization_rule_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                rule_id INTEGER NOT NULL,
                transaction_id INTEGER NOT NULL,
                import_batch_id INTEGER,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                result_status TEXT NOT NULL,
                match_reason TEXT,
                FOREIGN KEY(rule_id) REFERENCES categorization_rules(id),
                FOREIGN KEY(transaction_id) REFERENCES transactions(id)
            );


            CREATE TABLE IF NOT EXISTS forecast_occurrences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                source_type TEXT NOT NULL,
                source_id INTEGER,
                account_id INTEGER,
                expected_date TEXT NOT NULL,
                original_expected_date TEXT,
                rescheduled_at TEXT,
                expected_amount REAL NOT NULL,
                expected_label TEXT,
                expected_category TEXT,
                expected_category_id INTEGER,
                direction TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'planned',
                actual_transaction_id INTEGER,
                actual_date TEXT,
                actual_amount REAL,
                amount_delta REAL,
                match_confidence INTEGER,
                match_reason TEXT,
                ignored_reason TEXT,
                cancelled_reason TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                deleted_at TEXT,
                FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE SET NULL,
                FOREIGN KEY(actual_transaction_id) REFERENCES transactions(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS recurring_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER,
                name TEXT NOT NULL,
                category TEXT,
                amount REAL NOT NULL,
                frequency TEXT NOT NULL DEFAULT 'Mensuel',
                next_date TEXT NOT NULL,
                end_date TEXT,
                scenario TEXT NOT NULL DEFAULT 'Réaliste',
                status TEXT NOT NULL DEFAULT 'Actif',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT,
                FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                value REAL NOT NULL,
                valuation_date TEXT NOT NULL,
                valuation_mode TEXT NOT NULL DEFAULT 'Manuelle',
                comment TEXT,
                details_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'Actif',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS asset_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                valuation_date TEXT NOT NULL,
                value REAL NOT NULL,
                source TEXT NOT NULL DEFAULT 'Manuelle',
                comment TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month TEXT NOT NULL,
                category TEXT NOT NULL,
                planned_amount REAL NOT NULL DEFAULT 0,
                alert_threshold REAL NOT NULL DEFAULT 100,
                notes TEXT,
                status TEXT NOT NULL DEFAULT 'Actif',
                uuid TEXT,
                deleted_at TEXT,
                sync_status TEXT NOT NULL DEFAULT 'local',
                external_id TEXT,
                external_source TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT,
                UNIQUE(month, category)
            );

            CREATE INDEX IF NOT EXISTS idx_categorization_rules_priority ON categorization_rules(is_active, priority, deleted_at);
            CREATE INDEX IF NOT EXISTS idx_categorization_rule_logs_tx ON categorization_rule_logs(transaction_id, rule_id);

            CREATE INDEX IF NOT EXISTS idx_budgets_month_category ON budgets(month, category);


            CREATE TABLE IF NOT EXISTS scenarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                scenario_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                horizon_months INTEGER,
                currency_code TEXT NOT NULL DEFAULT 'EUR',
                is_reference INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_premium INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                deleted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS scenario_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                scenario_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                label TEXT NOT NULL,
                description TEXT,
                event_date TEXT NOT NULL,
                end_date TEXT,
                amount REAL NOT NULL,
                currency_code TEXT NOT NULL DEFAULT 'EUR',
                frequency TEXT NOT NULL DEFAULT 'once',
                duration_months INTEGER,
                account_id INTEGER,
                asset_id INTEGER,
                liability_id INTEGER,
                metadata_json TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                deleted_at TEXT,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id)
            );

            CREATE TABLE IF NOT EXISTS feature_flags (
                key TEXT PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 0,
                tier TEXT NOT NULL DEFAULT 'Free',
                description TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS currencies (
                code TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                label TEXT NOT NULL,
                decimal_places INTEGER NOT NULL DEFAULT 2,
                is_default INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS translations (
                locale TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT,
                PRIMARY KEY(locale, key)
            );

            CREATE TABLE IF NOT EXISTS user_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT 'global',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                entity TEXT,
                entity_id TEXT,
                message TEXT,
                metadata_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_scenarios_active ON scenarios(is_reference, is_active, deleted_at);
            CREATE INDEX IF NOT EXISTS idx_scenario_events_scenario ON scenario_events(scenario_id, deleted_at);
            CREATE INDEX IF NOT EXISTS idx_scenario_events_date ON scenario_events(event_date, end_date, frequency);

            CREATE INDEX IF NOT EXISTS idx_transactions_account_date ON transactions(account_id, tx_date);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_signature ON transactions(signature) WHERE signature IS NOT NULL;
            CREATE INDEX IF NOT EXISTS idx_import_batches_account ON import_batches(account_id);
            CREATE INDEX IF NOT EXISTS idx_recurring_items_date ON recurring_items(next_date, status);
            CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at);
            """
        )

    def apply_migrations(self, conn: sqlite3.Connection) -> None:
        self.ensure_columns(conn, "accounts", {
            "updated_at": "TEXT",
            "initial_balance": "REAL NOT NULL DEFAULT 0",
            "initial_date": "TEXT",
        })
        conn.execute("""
            UPDATE accounts
            SET initial_balance = reference_balance,
                initial_date = reference_date
            WHERE initial_date IS NULL OR initial_date = ''
        """)
        self.ensure_columns(conn, "transactions", {"updated_at": "TEXT"})
        self.ensure_columns(conn, "import_batches", {"status": "TEXT NOT NULL DEFAULT 'Importé'", "canceled_at": "TEXT"})
        self.ensure_columns(conn, "assets", {"updated_at": "TEXT", "details_json": "TEXT NOT NULL DEFAULT '{}'"})
        conn.execute("UPDATE import_batches SET status = 'Importé' WHERE status IS NULL OR status = ''")
        self.apply_category_foundation(conn)
        self.seed_categories(conn)
        self.apply_categorization_rules_foundation(conn)
        self.seed_settings(conn)
        self.apply_budgets_foundation(conn)
        self.apply_scenarios_foundation(conn)
        self.apply_forecast_reconciliation_foundation(conn)
        self.apply_premium_foundation(conn)
        self.apply_r7_2_foundation(conn)
        self.apply_reconciliation_multi_link_foundation(conn)
        apply_r8_reconciliation_foundation(conn)

    def ensure_columns(self, conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    def apply_category_foundation(self, conn: sqlite3.Connection) -> None:
        """V0.6.8.1 — user-managed categories foundation."""
        self.ensure_columns(conn, "categories", {
            "direction": "TEXT NOT NULL DEFAULT 'Dépense'",
            "budget_enabled": "INTEGER NOT NULL DEFAULT 1",
            "uuid": "TEXT",
            "deleted_at": "TEXT",
            "sync_status": "TEXT NOT NULL DEFAULT 'local'",
            "external_id": "TEXT",
            "external_source": "TEXT",
            "updated_at": "TEXT",
        })
        self.populate_uuid(conn, "categories")
        conn.execute("""
            UPDATE categories
            SET direction = CASE
                WHEN kind = 'Revenu' THEN 'Recette'
                WHEN kind = 'Neutre' THEN 'Neutre'
                ELSE 'Dépense'
            END
            WHERE direction IS NULL OR direction = ''
        """)
        conn.execute("UPDATE categories SET budget_enabled = 0 WHERE direction <> 'Dépense'")
        conn.execute("UPDATE categories SET budget_enabled = 1 WHERE direction = 'Dépense' AND budget_enabled IS NULL")

    def apply_categorization_rules_foundation(self, conn: sqlite3.Connection) -> None:
        """V0.6.8.1 — automatic categorization rules foundation."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS categorization_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                priority INTEGER NOT NULL DEFAULT 100,
                match_field TEXT NOT NULL,
                match_operator TEXT NOT NULL,
                match_value TEXT NOT NULL,
                transaction_type TEXT,
                account_id INTEGER,
                min_amount REAL,
                max_amount REAL,
                target_category_id INTEGER NOT NULL,
                confidence INTEGER NOT NULL DEFAULT 100,
                last_used_at TEXT,
                usage_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                deleted_at TEXT,
                FOREIGN KEY(target_category_id) REFERENCES categories(id),
                FOREIGN KEY(account_id) REFERENCES accounts(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS categorization_rule_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                rule_id INTEGER NOT NULL,
                transaction_id INTEGER NOT NULL,
                import_batch_id INTEGER,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                result_status TEXT NOT NULL,
                match_reason TEXT,
                FOREIGN KEY(rule_id) REFERENCES categorization_rules(id),
                FOREIGN KEY(transaction_id) REFERENCES transactions(id)
            )
        """)
        self.ensure_columns(conn, "transactions", {
            "categorization_status": "TEXT NOT NULL DEFAULT 'to_categorize'",
            "categorized_by": "TEXT",
            "categorization_rule_id": "INTEGER",
            "categorized_at": "TEXT",
        })
        self.ensure_columns(conn, "categorization_rules", {
            "uuid": "TEXT",
            "description": "TEXT",
            "is_active": "INTEGER NOT NULL DEFAULT 1",
            "priority": "INTEGER NOT NULL DEFAULT 100",
            "transaction_type": "TEXT",
            "account_id": "INTEGER",
            "min_amount": "REAL",
            "max_amount": "REAL",
            "confidence": "INTEGER NOT NULL DEFAULT 100",
            "last_used_at": "TEXT",
            "usage_count": "INTEGER NOT NULL DEFAULT 0",
            "created_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "deleted_at": "TEXT",
        })
        self.ensure_columns(conn, "categorization_rule_logs", {
            "uuid": "TEXT",
            "import_batch_id": "INTEGER",
            "applied_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "match_reason": "TEXT",
        })
        self.populate_uuid(conn, "categorization_rules")
        self.populate_uuid(conn, "categorization_rule_logs")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_categorization_rules_priority ON categorization_rules(is_active, priority, deleted_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_categorization_rule_logs_tx ON categorization_rule_logs(transaction_id, rule_id)")
        conn.execute("""
            UPDATE transactions
            SET categorization_status = CASE
                WHEN status = 'À catégoriser' OR category IS NULL OR category = '' OR category = 'À catégoriser' THEN 'to_categorize'
                WHEN source = 'Manuel' THEN 'manual'
                ELSE COALESCE(categorization_status, 'manual')
            END
            WHERE categorization_status IS NULL OR categorization_status = ''
        """)

    def apply_budgets_foundation(self, conn: sqlite3.Connection) -> None:
        """V0.6.0 Budgets V1 foundation."""
        self.ensure_columns(conn, "budgets", {
            "uuid": "TEXT",
            "deleted_at": "TEXT",
            "sync_status": "TEXT NOT NULL DEFAULT 'local'",
            "external_id": "TEXT",
            "external_source": "TEXT",
            "created_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TEXT",
        })
        self.populate_uuid(conn, "budgets")
        self.seed_default_budgets(conn)

    def seed_default_budgets(self, conn: sqlite3.Connection) -> None:
        """Seed demo/default budgets for the current month if none exist."""
        current_month = self.get_setting("current_month", "2026-06")
        count = conn.execute("SELECT COUNT(*) AS c FROM budgets WHERE month = ?", (current_month,)).fetchone()["c"]
        if count:
            return

        defaults = [
            ("Logement", 1300.00, 95.0, "Loyer, charges et logement"),
            ("Alimentation", 450.00, 90.0, "Courses et alimentation"),
            ("Transport", 250.00, 90.0, "Carburant, énergie, transports"),
            ("Loisirs", 180.00, 90.0, "Streaming, sorties, loisirs"),
            ("Santé", 120.00, 90.0, "Santé et remboursements"),
            ("Assurances", 160.00, 90.0, "Assurances"),
            ("Impôts", 350.00, 95.0, "Fiscalité et prélèvements"),
            ("Énergie", 180.00, 90.0, "Énergie, électricité, gaz"),
            ("Shopping", 200.00, 90.0, "Achats divers"),
        ]
        conn.executemany(
            """
            INSERT OR IGNORE INTO budgets(month, category, planned_amount, alert_threshold, notes, uuid)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [(current_month, category, amount, threshold, notes, str(uuid4())) for category, amount, threshold, notes in defaults],
        )

    def apply_scenarios_foundation(self, conn: sqlite3.Connection) -> None:
        """V0.6.8.1 — personalized scenario builder foundation."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                scenario_type TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                horizon_months INTEGER,
                currency_code TEXT NOT NULL DEFAULT 'EUR',
                is_reference INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_premium INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                deleted_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenario_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                scenario_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                label TEXT NOT NULL,
                description TEXT,
                event_date TEXT NOT NULL,
                end_date TEXT,
                amount REAL NOT NULL,
                currency_code TEXT NOT NULL DEFAULT 'EUR',
                frequency TEXT NOT NULL DEFAULT 'once',
                duration_months INTEGER,
                account_id INTEGER,
                asset_id INTEGER,
                liability_id INTEGER,
                metadata_json TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                deleted_at TEXT,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id)
            )
        """)
        self.ensure_columns(conn, "scenarios", {
            "uuid": "TEXT",
            "description": "TEXT",
            "scenario_type": "TEXT NOT NULL DEFAULT 'Projet libre'",
            "start_date": "TEXT NOT NULL DEFAULT CURRENT_DATE",
            "end_date": "TEXT",
            "horizon_months": "INTEGER",
            "currency_code": "TEXT NOT NULL DEFAULT 'EUR'",
            "is_reference": "INTEGER NOT NULL DEFAULT 0",
            "is_active": "INTEGER NOT NULL DEFAULT 1",
            "is_premium": "INTEGER NOT NULL DEFAULT 0",
            "created_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "deleted_at": "TEXT",
        })
        self.ensure_columns(conn, "scenario_events", {
            "uuid": "TEXT",
            "description": "TEXT",
            "end_date": "TEXT",
            "currency_code": "TEXT NOT NULL DEFAULT 'EUR'",
            "frequency": "TEXT NOT NULL DEFAULT 'once'",
            "duration_months": "INTEGER",
            "account_id": "INTEGER",
            "asset_id": "INTEGER",
            "liability_id": "INTEGER",
            "metadata_json": "TEXT",
            "is_active": "INTEGER NOT NULL DEFAULT 1",
            "created_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "deleted_at": "TEXT",
        })
        self.populate_uuid(conn, "scenarios")
        self.populate_uuid(conn, "scenario_events")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scenarios_active ON scenarios(is_reference, is_active, deleted_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scenario_events_scenario ON scenario_events(scenario_id, deleted_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_scenario_events_date ON scenario_events(event_date, end_date, frequency)")
        reference = conn.execute("SELECT id FROM scenarios WHERE is_reference = 1 AND deleted_at IS NULL LIMIT 1").fetchone()
        if reference is None:
            conn.execute(
                """
                INSERT INTO scenarios(uuid, name, description, scenario_type, start_date, horizon_months, currency_code, is_reference, is_active, is_premium)
                VALUES (?, 'Référence', 'Situation réelle actuelle sans hypothèse supplémentaire.', 'Référence', DATE('now'), 12, 'EUR', 1, 1, 0)
                """,
                (str(uuid4()),),
            )


    def apply_forecast_reconciliation_foundation(self, conn: sqlite3.Connection) -> None:
        """V0.6.6-R6 — forecast/reality reconciliation foundation."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS forecast_occurrences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                source_type TEXT NOT NULL,
                source_id INTEGER,
                account_id INTEGER,
                expected_date TEXT NOT NULL,
                original_expected_date TEXT,
                rescheduled_at TEXT,
                expected_amount REAL NOT NULL,
                expected_label TEXT,
                expected_category TEXT,
                expected_category_id INTEGER,
                direction TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'planned',
                actual_transaction_id INTEGER,
                actual_date TEXT,
                actual_amount REAL,
                amount_delta REAL,
                match_confidence INTEGER,
                match_reason TEXT,
                ignored_reason TEXT,
                cancelled_reason TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                deleted_at TEXT,
                FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE SET NULL,
                FOREIGN KEY(actual_transaction_id) REFERENCES transactions(id) ON DELETE SET NULL
            )
        """)
        self.ensure_columns(conn, "forecast_occurrences", {
            "uuid": "TEXT",
            "source_type": "TEXT NOT NULL DEFAULT 'recurring'",
            "source_id": "INTEGER",
            "account_id": "INTEGER",
            "expected_date": "TEXT",
            "original_expected_date": "TEXT",
            "rescheduled_at": "TEXT",
            "expected_amount": "REAL NOT NULL DEFAULT 0",
            "expected_label": "TEXT",
            "expected_category": "TEXT",
            "expected_category_id": "INTEGER",
            "direction": "TEXT NOT NULL DEFAULT 'debit'",
            "status": "TEXT NOT NULL DEFAULT 'planned'",
            "actual_transaction_id": "INTEGER",
            "actual_date": "TEXT",
            "actual_amount": "REAL",
            "amount_delta": "REAL",
            "match_confidence": "INTEGER",
            "match_reason": "TEXT",
            "ignored_reason": "TEXT",
            "cancelled_reason": "TEXT",
            "created_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "updated_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "deleted_at": "TEXT",
        })
        self.populate_uuid(conn, "forecast_occurrences")
        conn.execute("""
            UPDATE forecast_occurrences
            SET original_expected_date = expected_date
            WHERE original_expected_date IS NULL OR original_expected_date = ''
        """)
        # The identity of a generated occurrence is its original due date.
        # Several overdue occurrences from one recurrence may therefore be
        # rescheduled to the same target date without being merged.
        conn.execute("DROP INDEX IF EXISTS idx_forecast_occurrences_source_date")
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_forecast_occurrences_source_origin
            ON forecast_occurrences(source_type, source_id, original_expected_date)
            WHERE deleted_at IS NULL
              AND source_id IS NOT NULL
              AND original_expected_date IS NOT NULL
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_forecast_occurrences_status ON forecast_occurrences(status, expected_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_forecast_occurrences_actual_tx ON forecast_occurrences(actual_transaction_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_forecast_occurrences_account_date ON forecast_occurrences(account_id, expected_date)")


    def apply_r7_2_foundation(self, conn: sqlite3.Connection) -> None:
        """V0.6.6-R7.2 — import traceability and reconciliation status cleanup."""
        self.ensure_columns(conn, "transactions", {
            "beneficiary": "TEXT",
            "source_line": "INTEGER",
            "source_profile": "TEXT",
            "raw_payload": "TEXT",
            "source_identifier": "TEXT",
            "currency": "TEXT NOT NULL DEFAULT 'EUR'",
        })
        missing_beneficiaries = conn.execute(
            """
            SELECT id, label
            FROM transactions
            WHERE beneficiary IS NULL OR TRIM(beneficiary) = ''
            """
        ).fetchall()
        conn.executemany(
            "UPDATE transactions SET beneficiary = ? WHERE id = ?",
            [
                (extract_counterparty(row["label"]), int(row["id"]))
                for row in missing_beneficiaries
            ],
        )
        self.ensure_columns(conn, "import_batches", {
            "parser_profile": "TEXT",
            "source_fingerprint": "TEXT",
            "diagnostic_summary": "TEXT",
            "header_line": "INTEGER",
        })
        self.ensure_columns(conn, "forecast_occurrences", {
            "match_type": "TEXT",
            # 1 = occurrence modifiée à la main : la régénération ne l'écrase plus.
            "manually_edited": "INTEGER NOT NULL DEFAULT 0",
        })
        # R7.2: the ambiguous status planned_confirmed is not accepted.
        # If an occurrence has no real transaction, it returns to planned/overdue.
        # If it already has a linked transaction, it is a genuine manual reconciliation.
        conn.execute("""
            UPDATE forecast_occurrences
            SET status = CASE
                    WHEN actual_transaction_id IS NOT NULL THEN 'confirmed'
                    WHEN expected_date < DATE('now') THEN 'overdue'
                    ELSE 'planned'
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE status = 'planned_confirmed'
        """)
        conn.execute("UPDATE forecast_occurrences SET match_type = 'automatic' WHERE status = 'auto_matched' AND (match_type IS NULL OR match_type = '')")
        conn.execute("UPDATE forecast_occurrences SET match_type = 'manual' WHERE status = 'confirmed' AND (match_type IS NULL OR match_type = '')")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_reconciliation_source ON transactions(source, account_id, tx_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_forecast_occurrences_match_type ON forecast_occurrences(match_type, status)")


    def apply_reconciliation_multi_link_foundation(self, conn: sqlite3.Connection) -> None:
        """V0.6.6-R7.2.4 - multi-element and partial reconciliation links."""
        self.ensure_columns(conn, "forecast_occurrences", {
            "matched_amount": "REAL NOT NULL DEFAULT 0",
            "remaining_amount": "REAL",
            "overage_amount": "REAL NOT NULL DEFAULT 0",
        })
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS forecast_reconciliation_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                occurrence_id INTEGER NOT NULL,
                transaction_id INTEGER NOT NULL,
                applied_amount REAL NOT NULL,
                match_type TEXT NOT NULL DEFAULT 'manual',
                confidence INTEGER,
                reason TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                deleted_at TEXT,
                FOREIGN KEY(occurrence_id) REFERENCES forecast_occurrences(id) ON DELETE CASCADE,
                FOREIGN KEY(transaction_id) REFERENCES transactions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            UPDATE forecast_occurrences
            SET matched_amount = ABS(COALESCE(actual_amount, 0)),
                remaining_amount = MAX(ABS(expected_amount) - ABS(COALESCE(actual_amount, 0)), 0),
                overage_amount = MAX(ABS(COALESCE(actual_amount, 0)) - ABS(expected_amount), 0)
            WHERE actual_transaction_id IS NOT NULL
              AND (matched_amount = 0 OR remaining_amount IS NULL)
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_reconciliation_links_active_pair
            ON forecast_reconciliation_links(occurrence_id, transaction_id)
            WHERE deleted_at IS NULL
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reconciliation_links_occurrence ON forecast_reconciliation_links(occurrence_id, deleted_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reconciliation_links_transaction ON forecast_reconciliation_links(transaction_id, deleted_at)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS forecast_reconciliation_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE NOT NULL,
                occurrence_id INTEGER NOT NULL,
                transaction_id INTEGER NOT NULL,
                score INTEGER NOT NULL,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'to_review',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                deleted_at TEXT,
                FOREIGN KEY(occurrence_id) REFERENCES forecast_occurrences(id) ON DELETE CASCADE,
                FOREIGN KEY(transaction_id) REFERENCES transactions(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_reconciliation_proposals_active_pair
            ON forecast_reconciliation_proposals(occurrence_id, transaction_id)
            WHERE deleted_at IS NULL AND status = 'to_review'
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reconciliation_proposals_transaction ON forecast_reconciliation_proposals(transaction_id, status, deleted_at)")
        # Preserve links created by versions that stored one transaction directly
        # on the occurrence. INSERT OR IGNORE keeps the migration idempotent.
        conn.execute(
            """
            INSERT OR IGNORE INTO forecast_reconciliation_links(
                uuid, occurrence_id, transaction_id, applied_amount,
                match_type, confidence, reason, created_at, updated_at
            )
            SELECT lower(hex(randomblob(16))), o.id, o.actual_transaction_id,
                   ABS(COALESCE(o.actual_amount, t.amount, 0)),
                   COALESCE(o.match_type, 'legacy'), o.match_confidence,
                   COALESCE(o.match_reason, 'Migration du rapprochement historique.'),
                   o.created_at, o.updated_at
            FROM forecast_occurrences o
            JOIN transactions t ON t.id = o.actual_transaction_id
            WHERE o.deleted_at IS NULL
              AND o.actual_transaction_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM forecast_reconciliation_links l
                  WHERE l.occurrence_id = o.id
                    AND l.transaction_id = o.actual_transaction_id
                    AND l.deleted_at IS NULL
              )
            """
        )


    def apply_premium_foundation(self, conn: sqlite3.Connection) -> None:
        """V0.6.0 long-term foundation: Premium flags, currencies, languages, sync metadata."""
        technical_columns = {
            "uuid": "TEXT",
            "deleted_at": "TEXT",
            "sync_status": "TEXT NOT NULL DEFAULT 'local'",
            "external_id": "TEXT",
            "external_source": "TEXT",
        }

        for table in ["accounts", "transactions", "import_batches", "recurring_items", "assets", "asset_values", "budgets", "categories", "scenarios", "scenario_events"]:
            self.ensure_columns(conn, table, technical_columns)
            self.populate_uuid(conn, table)

        self.ensure_columns(conn, "transactions", {"currency": "TEXT NOT NULL DEFAULT 'EUR'"})
        self.ensure_columns(conn, "recurring_items", {"currency": "TEXT NOT NULL DEFAULT 'EUR'"})
        self.ensure_columns(conn, "assets", {"currency": "TEXT NOT NULL DEFAULT 'EUR'"})
        self.ensure_columns(conn, "asset_values", {"currency": "TEXT NOT NULL DEFAULT 'EUR'"})

        self.seed_feature_flags(conn)
        self.seed_currencies(conn)
        self.seed_translations(conn)
        self.seed_user_preferences(conn)
        already_logged = conn.execute(
            "SELECT 1 FROM audit_log WHERE event_type = ? AND entity_id = ? LIMIT 1",
            ("migration", "V0.6.0"),
        ).fetchone()
        if already_logged is None:
            self.audit_event(conn, "migration", "system", "V0.6.0", "Socle Premium & évolutivité long terme appliqué.")

    def populate_uuid(self, conn: sqlite3.Connection, table: str) -> None:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if "uuid" not in existing:
            return
        rows = conn.execute(f"SELECT id FROM {table} WHERE uuid IS NULL OR uuid = ''").fetchall()
        for row in rows:
            conn.execute(f"UPDATE {table} SET uuid = ? WHERE id = ?", (str(uuid4()), row["id"]))

    def seed_feature_flags(self, conn: sqlite3.Connection) -> None:
        flags = [
            ("premium.enabled", 0, "Premium", "Activation générale du socle Premium."),
            ("premium.multi_currency", 0, "Premium", "Préparation multi-devises, désactivée par défaut."),
            ("premium.multi_language", 0, "Premium", "Préparation multi-langues, désactivée par défaut."),
            ("premium.open_banking", 0, "Premium", "Préparation future Open Banking, non activée."),
            ("premium.cloud_sync", 0, "Premium", "Préparation synchronisation cloud future."),
            ("premium.multi_profile", 0, "Premium", "Préparation multi-profils / foyer."),
            ("premium.scenario_builder", 0, "Premium", "Créateur de scénarios personnalisés."),
            ("premium.advanced_scenarios", 0, "Premium", "Scénarios avancés : emprunts détaillés, immobilier, fiscalité."),
            ("premium.scenario_comparison", 0, "Premium", "Comparaison avancée de scénarios."),
            ("premium.scenario_reports", 0, "Premium", "Rapports PDF de simulation de scénarios."),
            ("premium.advanced_categorization_rules", 0, "Premium", "Règles de catégorisation avancées."),
            ("premium.regex_categorization", 0, "Premium", "Règles de catégorisation par expressions régulières."),
            ("premium.ai_categorization_suggestions", 0, "Premium", "Suggestions IA de catégorisation."),
            ("premium.bulk_rule_simulation", 0, "Premium", "Simulation massive des règles de catégorisation."),
            ("premium.loan_simulation", 0, "Premium", "Simulation détaillée d’emprunts."),
            ("premium.real_estate_simulation", 0, "Premium", "Simulation immobilière avancée."),
            ("module.scenarios_v1", 1, "Roadmap", "Socle créateur de scénarios V1 actif."),
            ("module.budgets_v1", 1, "Roadmap", "Module Budgets V1 actif."),
            ("module.investments_v1", 0, "Roadmap", "Module Investissements V1 à venir."),
            ("module.reports_v1", 0, "Roadmap", "Module Rapports & exports V1 à venir."),
        ]
        conn.executemany(
            """
            INSERT OR IGNORE INTO feature_flags(key, enabled, tier, description)
            VALUES (?, ?, ?, ?)
            """,
            flags,
        )

    def seed_currencies(self, conn: sqlite3.Connection) -> None:
        currencies = [
            ("EUR", "€", "Euro", 2, 1, 1),
            ("USD", "$", "Dollar américain", 2, 0, 0),
            ("GBP", "£", "Livre sterling", 2, 0, 0),
            ("CHF", "CHF", "Franc suisse", 2, 0, 0),
            ("PLN", "zł", "Zloty", 2, 0, 0),
        ]
        conn.executemany(
            """
            INSERT OR IGNORE INTO currencies(code, symbol, label, decimal_places, is_default, enabled)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            currencies,
        )

    def seed_translations(self, conn: sqlite3.Connection) -> None:
        translations = [
            ("fr", "app.title", "Valoria Vision"),
            ("fr", "nav.dashboard", "Dashboard"),
            ("fr", "nav.accounts", "Comptes"),
            ("fr", "nav.transactions", "Transactions"),
            ("fr", "nav.forecast", "Prévisionnel"),
            ("fr", "nav.assets", "Patrimoine"),
            ("fr", "settings.premium_foundation", "Socle Premium & évolutivité"),
            ("en", "app.title", "Valoria Vision"),
            ("en", "nav.dashboard", "Dashboard"),
            ("en", "nav.accounts", "Accounts"),
            ("en", "nav.transactions", "Transactions"),
            ("en", "nav.forecast", "Forecast"),
            ("en", "nav.assets", "Net worth"),
            ("en", "settings.premium_foundation", "Premium & scalability foundation"),
        ]
        conn.executemany(
            """
            INSERT OR IGNORE INTO translations(locale, key, value)
            VALUES (?, ?, ?)
            """,
            translations,
        )

    def seed_user_preferences(self, conn: sqlite3.Connection) -> None:
        preferences = [
            ("locale.default", "fr", "global"),
            ("currency.default", "EUR", "global"),
            ("premium.mode", "free", "global"),
            ("sync.device_id", str(uuid4()), "device"),
            ("open_banking.prepared", "false", "global"),
        ]
        for key, value, scope in preferences:
            conn.execute(
                "INSERT OR IGNORE INTO user_preferences(key, value, scope) VALUES (?, ?, ?)",
                (key, value, scope),
            )

    def audit_event(
        self,
        conn: sqlite3.Connection,
        event_type: str,
        entity: str | None,
        entity_id: str | None,
        message: str,
        metadata: dict | None = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO audit_log(event_type, entity, entity_id, message, metadata_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (event_type, entity, entity_id, message, json.dumps(metadata or {}, ensure_ascii=False)),
        )

    def schema_version(self, conn: sqlite3.Connection | None = None) -> int:
        own_conn = conn is None
        conn = conn or self.connect()
        try:
            row = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
            return int(row["value"]) if row else 0
        finally:
            if own_conn:
                conn.close()

    def set_schema_version(self, conn: sqlite3.Connection, version: int) -> None:
        conn.execute(
            """
            INSERT INTO schema_meta(key, value, updated_at) VALUES('schema_version', ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
            """,
            (str(version),),
        )

    def seed_settings(self, conn: sqlite3.Connection) -> None:
        defaults = {
            "product_name": "Valoria Vision",
            "currency": "EUR",
            "current_month": "2026-06",
            "last_backup_path": "",
        }
        for key, value in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)",
                (key, value),
            )

    def seed_categories(self, conn: sqlite3.Connection) -> None:
        defaults = [
            ("Logement", "Dépense", "Dépense", "#2563EB"),
            ("Alimentation", "Dépense", "Dépense", "#16A34A"),
            ("Transport", "Dépense", "Dépense", "#F59E0B"),
            ("Loisirs", "Dépense", "Dépense", "#8B5CF6"),
            ("Santé", "Dépense", "Dépense", "#06B6D4"),
            ("Revenus", "Revenu", "Recette", "#10B981"),
            ("Transferts", "Neutre", "Neutre", "#64748B"),
            ("Investissement", "Investissement", "Dépense", "#1D4ED8"),
            ("Épargne", "Épargne", "Dépense", "#0F766E"),
            ("Assurances", "Dépense", "Dépense", "#EF4444"),
            ("Impôts", "Dépense", "Dépense", "#F97316"),
            ("Énergie", "Dépense", "Dépense", "#0EA5E9"),
            ("À catégoriser", "Neutre", "Neutre", "#A16207"),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO categories(name, kind, direction, color, is_system, budget_enabled) VALUES (?, ?, ?, ?, 1, CASE WHEN ? = 'Dépense' THEN 1 ELSE 0 END)",
            [(name, kind, direction, color, direction) for name, kind, direction, color in defaults],
        )


    def seed_recurring_items(self, conn: sqlite3.Connection) -> None:
        """Seed a few recurring cash-flow items for the forecast module."""
        count = conn.execute("SELECT COUNT(*) AS c FROM recurring_items").fetchone()["c"]
        if count:
            return

        def account_id_by_type(account_type: str) -> int | None:
            row = conn.execute("SELECT id FROM accounts WHERE account_type = ? ORDER BY id LIMIT 1", (account_type,)).fetchone()
            return int(row["id"]) if row else None

        current_account = account_id_by_type("Compte courant")
        savings_account = account_id_by_type("Compte épargne")
        investment_account = account_id_by_type("Compte investissement")

        items = [
            (current_account, "Salaire", "Revenus", 2800.00, "Mensuel", "2026-07-01", None, "Réaliste", "Actif"),
            (current_account, "Loyer", "Logement", -1200.00, "Mensuel", "2026-07-05", None, "Réaliste", "Actif"),
            (current_account, "EDF", "Énergie", -98.40, "Mensuel", "2026-07-12", None, "Réaliste", "Actif"),
            (current_account, "Netflix", "Loisirs", -15.99, "Mensuel", "2026-07-21", None, "Réaliste", "Actif"),
            (current_account, "Impôts", "Impôts", -320.00, "Mensuel", "2026-07-11", None, "Réaliste", "Actif"),
            (investment_account, "Versement PEA", "Investissement", -650.00, "Mensuel", "2026-07-15", None, "Prudent", "Actif"),
            (savings_account, "Épargne programmée", "Épargne", -200.00, "Mensuel", "2026-07-21", None, "Prudent", "Actif"),
        ]
        conn.executemany(
            """
            INSERT INTO recurring_items(account_id, name, category, amount, frequency, next_date, end_date, scenario, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            items,
        )


    def seed_if_empty(self, conn: sqlite3.Connection) -> None:
        count = conn.execute("SELECT COUNT(*) AS c FROM accounts").fetchone()["c"]
        if count:
            return

        accounts = [
            ("Compte courant", "Crédit Agricole", "Compte courant", "**** 8425", 12450.00, "2026-06-23", "EUR", "Actif"),
            ("Livret A", "Crédit Agricole", "Compte épargne", "**** 1022", 18000.00, "2026-06-23", "EUR", "Actif"),
            ("Boursorama", "Boursobank", "Compte courant", "**** 5541", 25300.00, "2026-06-23", "EUR", "Actif"),
            ("PEA", "Boursobank", "Compte investissement", "**** 8712", 28700.00, "2026-06-23", "EUR", "Actif"),
            ("Assurance Vie", "Linxea", "Compte investissement", "**** 3490", 45000.00, "2026-06-22", "EUR", "Actif"),
            ("Livret Jeune", "CIC", "Compte épargne", "**** 2114", 1250.00, "2026-06-23", "EUR", "Actif"),
            ("Crédit immobilier", "Crédit Agricole", "Compte crédit", "**** 7780", -125000.00, "2026-06-23", "EUR", "Actif"),
        ]
        conn.executemany(
            """
            INSERT INTO accounts(name, bank, account_type, identifier, reference_balance, reference_date, initial_balance, initial_date, currency, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [(name, bank, account_type, identifier, balance, ref_date, balance, ref_date, currency, status)
             for name, bank, account_type, identifier, balance, ref_date, currency, status in accounts],
        )

        transactions = [
            (1, "2026-06-23", "Carrefour Market", "Alimentation", -65.40, "Débit", "Validée", "Démo"),
            (1, "2026-06-22", "Salaire", "Revenus", 2800.00, "Crédit", "Validée", "Démo"),
            (2, "2026-06-21", "Virement interne", "Transferts", -200.00, "Débit", "Validée", "Démo"),
            (1, "2026-06-21", "Netflix", "Loisirs", -15.99, "Débit", "Validée", "Démo"),
            (1, "2026-06-20", "Total Energies", "Transport", -85.60, "Débit", "Validée", "Démo"),
            (1, "2026-06-20", "Abonnement Spotify", "Loisirs", -9.99, "Débit", "Validée", "Démo"),
            (2, "2026-06-19", "Virement depuis CC", "Transferts", 200.00, "Crédit", "Validée", "Démo"),
            (1, "2026-06-18", "Loyer", "Logement", -1200.00, "Débit", "Validée", "Démo"),
            (1, "2026-06-18", "Ameli", "Santé", -28.50, "Débit", "Validée", "Démo"),
            (1, "2026-06-17", "Amazon EU", "Shopping", -42.90, "Débit", "À catégoriser", "Démo"),
            (3, "2026-06-16", "Virement compte courant", "Transferts", 500.00, "Crédit", "Validée", "Démo"),
            (4, "2026-06-15", "ETF Monde", "Investissement", -650.00, "Débit", "Validée", "Démo"),
            (1, "2026-06-14", "Opération inconnue", None, -37.20, "Débit", "À catégoriser", "Démo"),
            (1, "2026-06-13", "Prime assurance", "Assurances", -156.00, "Débit", "Validée", "Démo"),
            (1, "2026-06-12", "EDF", "Énergie", -98.40, "Débit", "Validée", "Démo"),
            (1, "2026-06-11", "Impôts", "Impôts", -320.00, "Débit", "Validée", "Démo"),
        ]
        for row in transactions:
            signature = self.make_signature(row[0], row[1], row[2], row[4])
            conn.execute(
                """
                INSERT INTO transactions(account_id, tx_date, label, category, amount, tx_type, status, source, signature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*row, signature),
            )

        assets = [
            ("Résidence principale", "Immobilier", "Appartement", 220000, "2026-06-23", "Manuelle", "Estimation prudente", "Actif"),
            ("PEA — Boursorama", "Placements financiers", "PEA", 65000, "2026-06-23", "Importée", "Compte investissement", "Actif"),
            ("Assurance-vie — Linxea", "Assurance-vie", "Fonds euros + unités", 45000, "2026-06-23", "Manuelle", "Contrat principal", "Actif"),
            ("Liquidités", "Liquidités", "Comptes bancaires + épargne", 73750, "2026-06-23", "Calculée", "Somme comptes liquides", "Actif"),
            ("Objets de valeur", "Autres actifs", "Objets personnels", 25070, "2026-06-23", "Manuelle", "Estimation utilisateur", "Actif"),
            ("Crédit immobilier", "Crédit immobilier", "Capital restant dû", -125000, "2026-06-23", "Calculée", "Dette principale", "Actif"),
        ]
        conn.executemany(
            """
            INSERT INTO assets(name, category, asset_type, value, valuation_date, valuation_mode, comment, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            assets,
        )
        for asset_id, asset in enumerate(assets, start=1):
            for month_index, multiplier in enumerate([0.94, 0.96, 0.97, 0.98, 0.99, 1.00], start=1):
                conn.execute(
                    "INSERT INTO asset_values(asset_id, valuation_date, value, source, comment) VALUES (?, ?, ?, ?, ?)",
                    (asset_id, f"2026-{month_index:02d}-23", asset[3] * multiplier, asset[5], asset[6]),
                )

    @staticmethod
    def make_signature(account_id: int, tx_date: str, label: str, amount: float) -> str:
        clean = " ".join((label or "").lower().strip().split())[:80]
        return f"{account_id}|{tx_date}|{round(float(amount or 0), 2)}|{clean}"

    def list_accounts(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT
                        a.*,
                        COALESCE(a.initial_balance, a.reference_balance) AS effective_initial_balance,
                        COALESCE(a.initial_date, a.reference_date) AS effective_initial_date,
                        COALESCE(
                            SUM(
                                CASE
                                    WHEN t.tx_date > COALESCE(a.initial_date, a.reference_date)
                                    THEN t.amount
                                    ELSE 0
                                END
                            ),
                            0
                        ) AS post_reference_movements,
                        COALESCE(a.initial_balance, a.reference_balance)
                        + COALESCE(
                            SUM(
                                CASE
                                    WHEN t.tx_date > COALESCE(a.initial_date, a.reference_date)
                                    THEN t.amount
                                    ELSE 0
                                END
                            ),
                            0
                        ) AS calculated_balance,
                        COALESCE(
                            MAX(
                                CASE
                                    WHEN t.tx_date > COALESCE(a.initial_date, a.reference_date)
                                    THEN t.tx_date
                                    ELSE NULL
                                END
                            ),
                            COALESCE(a.initial_date, a.reference_date)
                        ) AS calculated_date
                    FROM accounts a
                    LEFT JOIN transactions t ON t.account_id = a.id
                    GROUP BY a.id
                    ORDER BY a.status, a.bank, a.name
                    """
                )
            )

    def add_account(self, data: dict) -> None:
        payload = dict(data)
        initial_balance = float(payload.get("initial_balance", payload.get("reference_balance", 0)) or 0)
        initial_date = payload.get("initial_date", payload.get("reference_date"))
        payload["initial_balance"] = initial_balance
        payload["initial_date"] = initial_date
        # Backward-compatible aliases kept for existing screens and migrations.
        payload["reference_balance"] = initial_balance
        payload["reference_date"] = initial_date
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO accounts(name, bank, account_type, identifier, reference_balance, reference_date, initial_balance, initial_date, currency, status)
                VALUES (:name, :bank, :account_type, :identifier, :reference_balance, :reference_date, :initial_balance, :initial_date, :currency, :status)
                """,
                payload,
            )

    def update_account_reference(self, account_id: int, reference_balance: float, reference_date: str) -> None:
        """Update the account's initial balance/date.

        Method name kept for compatibility, but V0.4.7 business meaning is now
        "initial balance".
        """
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE accounts
                SET reference_balance = ?,
                    reference_date = ?,
                    initial_balance = ?,
                    initial_date = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (reference_balance, reference_date, reference_balance, reference_date, account_id),
            )

    def update_account(self, account_id: int, data: dict) -> None:
        data = dict(data)
        data["id"] = account_id
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE accounts
                SET name = :name,
                    bank = :bank,
                    account_type = :account_type,
                    identifier = :identifier,
                    currency = :currency,
                    status = :status,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """,
                data,
            )

    def update_account_status(self, account_id: int, status: str) -> bool:
        """Update only the lifecycle status of an account."""
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE accounts
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, account_id),
            )
        return cursor.rowcount > 0

    def account_dependencies(self, account_id: int) -> dict[str, int]:
        """Count business records that would be affected by deleting an account."""
        queries = {
            "transactions": "SELECT COUNT(*) FROM transactions WHERE account_id = ?",
            "imports": "SELECT COUNT(*) FROM import_batches WHERE account_id = ?",
            "recurrences": "SELECT COUNT(*) FROM recurring_items WHERE account_id = ?",
            "forecasts": "SELECT COUNT(*) FROM forecast_occurrences WHERE account_id = ?",
            "rules": "SELECT COUNT(*) FROM categorization_rules WHERE account_id = ?",
            "scenario_events": "SELECT COUNT(*) FROM scenario_events WHERE account_id = ?",
        }
        with self.connect() as conn:
            return {
                key: int(conn.execute(query, (account_id,)).fetchone()[0] or 0)
                for key, query in queries.items()
            }

    def delete_account(self, account_id: int) -> bool:
        """Delete an empty account after the service has checked its dependencies."""
        with self.connect() as conn:
            cursor = conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        deleted = cursor.rowcount > 0
        if deleted:
            self.seal_database_to_encrypted_vault()
        return deleted

    def account_balance_at_date(self, account_id: int, target_date: str):
        with self.connect() as conn:
            account = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
            if not account:
                return None
            tx_rows = list(
                conn.execute(
                    """
                    SELECT tx_date, amount
                    FROM transactions
                    WHERE account_id = ? AND tx_date <= ?
                    ORDER BY tx_date, id
                    """,
                    (account_id, target_date),
                )
            )
        initial_balance = account["initial_balance"] if "initial_balance" in account.keys() else account["reference_balance"]
        initial_date = account["initial_date"] if "initial_date" in account.keys() and account["initial_date"] else account["reference_date"]
        return balance_at_date(initial_balance, initial_date, tx_rows, target_date)

    def account_summary_at_date(self, target_date: str) -> dict[str, float]:
        with self.connect() as conn:
            accounts = list(conn.execute("SELECT * FROM accounts WHERE status = 'Actif'"))
            account_ids = [int(account["id"]) for account in accounts]
            transactions_by_account: dict[int, list] = {account_id: [] for account_id in account_ids}
            if account_ids:
                placeholders = ",".join("?" for _ in account_ids)
                rows = list(
                    conn.execute(
                        f"""
                        SELECT account_id, tx_date, amount
                        FROM transactions
                        WHERE account_id IN ({placeholders}) AND tx_date <= ?
                        ORDER BY tx_date, id
                        """,
                        [*account_ids, target_date],
                    )
                )
                for row in rows:
                    transactions_by_account[int(row["account_id"])].append(row)
        return summarize_accounts_at_date(accounts, transactions_by_account, target_date)

    _LINK_SELECT = """
        SELECT l.id AS link_id, l.transaction_id, l.occurrence_id, l.applied_amount,
               l.match_type, l.confidence, l.reason, l.created_at, l.deleted_at,
               o.expected_label, o.expected_date, o.expected_amount,
               o.source_type, o.source_id, r.name AS recurrence_name,
               t.tx_date, t.label AS tx_label, t.amount AS tx_amount
        FROM forecast_reconciliation_links l
        JOIN forecast_occurrences o ON o.id = l.occurrence_id
        JOIN transactions t ON t.id = l.transaction_id
        LEFT JOIN recurring_items r ON o.source_type = 'recurring' AND r.id = o.source_id
    """

    @staticmethod
    def _link_dict(row) -> dict:
        return {
            "link_id": int(row["link_id"]),
            "transaction_id": int(row["transaction_id"]),
            "occurrence_id": int(row["occurrence_id"]),
            "applied_amount": float(row["applied_amount"] or 0),
            "match_type": str(row["match_type"] or ""),
            "confidence": row["confidence"],
            "reason": str(row["reason"] or ""),
            "created_at": str(row["created_at"] or ""),
            "cancelled_at": str(row["deleted_at"] or ""),
            "active": row["deleted_at"] is None,
            "occurrence_label": str(row["expected_label"] or ""),
            "occurrence_date": str(row["expected_date"] or ""),
            "occurrence_amount": float(row["expected_amount"] or 0),
            "source_type": str(row["source_type"] or ""),
            "source_id": row["source_id"],
            "recurrence_name": str(row["recurrence_name"] or ""),
            "transaction_date": str(row["tx_date"] or ""),
            "transaction_label": str(row["tx_label"] or ""),
            "transaction_amount": float(row["tx_amount"] or 0),
        }

    def reconciliation_links(
        self,
        *,
        include_cancelled: bool = False,
        transaction_id: int | None = None,
        occurrence_id: int | None = None,
    ) -> list[dict]:
        """Links between realized transactions and forecast occurrences.

        A cancelled link is never erased: it keeps its dates, so that the
        history between a transaction and a recurrence/forecast stays readable.
        """
        conditions = []
        params: list = []
        if not include_cancelled:
            conditions.append("l.deleted_at IS NULL")
        if transaction_id is not None:
            conditions.append("l.transaction_id = ?")
            params.append(int(transaction_id))
        if occurrence_id is not None:
            conditions.append("l.occurrence_id = ?")
            params.append(int(occurrence_id))
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        with self.connect() as conn:
            rows = list(conn.execute(self._LINK_SELECT + where + " ORDER BY l.id DESC", params))
        return [self._link_dict(row) for row in rows]

    def active_reconciliation_by_transaction(self) -> dict[int, list[dict]]:
        grouped: dict[int, list[dict]] = {}
        for link in reversed(self.reconciliation_links()):
            grouped.setdefault(link["transaction_id"], []).append(link)
        return grouped

    def budget_months(self) -> list[str]:
        with self.connect() as conn:
            rows = list(conn.execute(
                """
                SELECT month FROM budgets
                UNION
                SELECT SUBSTR(tx_date, 1, 7) AS month FROM transactions
                WHERE tx_date IS NOT NULL AND LENGTH(tx_date) >= 7
                ORDER BY month DESC
                """
            ))
        months = [row["month"] for row in rows if row["month"]]
        current = self.get_setting("current_month", "2026-06")
        if current not in months:
            months.insert(0, current)
        return months

    def list_budgets(self, month: str | None = None) -> list[sqlite3.Row]:
        month = month or self.get_setting("current_month", "2026-06")
        with self.connect() as conn:
            self.ensure_budget_month(conn, month)
            return list(conn.execute(
                "SELECT * FROM budgets WHERE month = ? AND deleted_at IS NULL ORDER BY category",
                (month,),
            ))

    def ensure_budget_month(self, conn: sqlite3.Connection, month: str) -> None:
        count = conn.execute("SELECT COUNT(*) AS c FROM budgets WHERE month = ?", (month,)).fetchone()["c"]
        if count:
            return
        previous = conn.execute("SELECT month FROM budgets WHERE month < ? GROUP BY month ORDER BY month DESC LIMIT 1", (month,)).fetchone()
        if previous:
            rows = list(conn.execute(
                "SELECT category, planned_amount, alert_threshold, notes FROM budgets WHERE month = ? AND deleted_at IS NULL",
                (previous["month"],),
            ))
            conn.executemany(
                """
                INSERT OR IGNORE INTO budgets(month, category, planned_amount, alert_threshold, notes, uuid)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [(month, row["category"], row["planned_amount"], row["alert_threshold"], row["notes"], str(uuid4())) for row in rows],
            )
        else:
            self.seed_default_budgets(conn)

    def upsert_budget(self, month: str, category: str, planned_amount: float, alert_threshold: float = 100.0, notes: str = "") -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO budgets(month, category, planned_amount, alert_threshold, notes, uuid, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(month, category) DO UPDATE SET
                    planned_amount = excluded.planned_amount,
                    alert_threshold = excluded.alert_threshold,
                    notes = excluded.notes,
                    status = 'Actif',
                    deleted_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (month, category, float(planned_amount or 0), float(alert_threshold or 100), notes or "", str(uuid4())),
            )
        self.seal_database_to_encrypted_vault()

    def delete_budget(self, budget_id: int) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE budgets SET deleted_at = CURRENT_TIMESTAMP, status = 'Supprimé', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (budget_id,))
        self.seal_database_to_encrypted_vault()

    def budget_realized_by_category(self, month: str) -> dict[str, float]:
        with self.connect() as conn:
            rows = list(conn.execute(
                """
                SELECT COALESCE(category, 'À catégoriser') AS category, amount
                FROM transactions
                WHERE tx_date LIKE ?
                """,
                (month + "%",),
            ))
        totals: dict[str, float] = {}
        for row in rows:
            category = row["category"] or "À catégoriser"
            amount = float(row["amount"] or 0)
            if is_current_expense(category, amount):
                totals[category] = totals.get(category, 0.0) + abs(amount)
        return totals

    def budget_report(self, month: str | None = None) -> dict:
        month = month or self.get_setting("current_month", "2026-06")
        with self.connect() as conn:
            self.ensure_budget_month(conn, month)
            budgets = list(conn.execute(
                "SELECT * FROM budgets WHERE month = ? AND deleted_at IS NULL ORDER BY category",
                (month,),
            ))
        realized = self.budget_realized_by_category(month)
        categories = sorted(set([row["category"] for row in budgets]) | set(realized.keys()))

        rows = []
        total_planned = 0.0
        total_realized = 0.0
        over_count = 0
        warning_count = 0

        budget_by_category = {row["category"]: row for row in budgets}
        for category in categories:
            budget = budget_by_category.get(category)
            planned = float(budget["planned_amount"] or 0) if budget else 0.0
            alert_threshold = float(budget["alert_threshold"] or 100) if budget else 100.0
            actual = float(realized.get(category, 0.0))
            remaining = planned - actual
            usage = (actual / planned * 100) if planned else (100.0 if actual else 0.0)
            if planned and actual > planned:
                status = "Dépassement"
                over_count += 1
            elif planned and usage >= alert_threshold:
                status = "Vigilance"
                warning_count += 1
            elif not planned and actual:
                status = "Non budgété"
                warning_count += 1
            else:
                status = "OK"

            rows.append({
                "id": int(budget["id"]) if budget else None,
                "month": month,
                "category": category,
                "planned": planned,
                "actual": actual,
                "remaining": remaining,
                "usage": usage,
                "alert_threshold": alert_threshold,
                "status": status,
                "notes": budget["notes"] if budget else "",
            })
            total_planned += planned
            total_realized += actual

        total_remaining = total_planned - total_realized
        usage_total = (total_realized / total_planned * 100) if total_planned else 0.0
        return {
            "month": month,
            "rows": rows,
            "total_planned": round(total_planned, 2),
            "total_realized": round(total_realized, 2),
            "total_remaining": round(total_remaining, 2),
            "usage_total": round(usage_total, 1),
            "over_count": over_count,
            "warning_count": warning_count,
            "status": "Dépassement" if over_count else "Vigilance" if warning_count else "OK",
        }

    def budget_categories_available(self) -> list[str]:
        """Categories that can be used in the Budgets module.

        The Settings > Catégories screen is now the source of truth. We keep a
        fallback on historical transaction categories so existing data remains
        visible even if an old category was not formally registered yet.
        """
        with self.connect() as conn:
            rows = list(conn.execute(
                """
                SELECT name FROM categories
                WHERE deleted_at IS NULL
                  AND budget_enabled = 1
                  AND direction = 'Dépense'
                UNION
                SELECT DISTINCT category AS name FROM transactions
                WHERE amount < 0 AND category IS NOT NULL AND category <> ''
                ORDER BY name
                """
            ))
        excluded = {"Transferts", "Investissement", "À catégoriser", "Revenus"}
        return [row["name"] for row in rows if row["name"] and row["name"] not in excluded]

    def list_categories(self, include_deleted: bool = False, kind: str | None = None) -> list[sqlite3.Row]:
        where = []
        params: list = []
        if not include_deleted:
            where.append("deleted_at IS NULL")
        if kind:
            where.append("kind = ?")
            params.append(kind)
        sql_where = "WHERE " + " AND ".join(where) if where else ""
        with self.connect() as conn:
            return list(conn.execute(f"SELECT * FROM categories {sql_where} ORDER BY kind, name", params))

    def category_names(self, include_blank: bool = False, include_deleted: bool = False, kind: str | None = None) -> list[str]:
        names = [row["name"] for row in self.list_categories(include_deleted=include_deleted, kind=kind)]
        return ([""] if include_blank else []) + names

    def category_usage_summary(self) -> list[dict]:
        with self.connect() as conn:
            categories = list(conn.execute("SELECT * FROM categories WHERE deleted_at IS NULL ORDER BY kind, name"))
            output = []
            for row in categories:
                name = row["name"]
                tx_count = conn.execute("SELECT COUNT(*) AS c FROM transactions WHERE category = ?", (name,)).fetchone()["c"]
                recurring_count = conn.execute("SELECT COUNT(*) AS c FROM recurring_items WHERE category = ? AND status = 'Actif'", (name,)).fetchone()["c"]
                budget_count = conn.execute("SELECT COUNT(*) AS c FROM budgets WHERE category = ? AND deleted_at IS NULL", (name,)).fetchone()["c"]
                output.append({
                    "id": row["id"],
                    "name": row["name"],
                    "kind": row["kind"],
                    "direction": row["direction"] or self.default_direction_for_kind(row["kind"]),
                    "color": row["color"] or "",
                    "budget_enabled": int(row["budget_enabled"] or 0),
                    "is_system": int(row["is_system"] or 0),
                    "deleted_at": row["deleted_at"],
                    "tx_count": int(tx_count or 0),
                    "recurring_count": int(recurring_count or 0),
                    "budget_count": int(budget_count or 0),
                })
            return output

    @staticmethod
    def default_direction_for_kind(kind: str | None) -> str:
        if kind == "Revenu":
            return "Recette"
        if kind == "Neutre":
            return "Neutre"
        return "Dépense"

    @staticmethod
    def normalize_category_direction(direction: str | None) -> str:
        value = (direction or "Dépense").strip()
        return value if value in {"Recette", "Dépense", "Neutre"} else "Dépense"

    def category_direction(self, category: str | None) -> str:
        if not category:
            return "Neutre"
        with self.connect() as conn:
            row = conn.execute(
                "SELECT direction, kind FROM categories WHERE name = ? AND deleted_at IS NULL",
                (category,),
            ).fetchone()
        if not row:
            return "Neutre"
        return self.normalize_category_direction(row["direction"] or self.default_direction_for_kind(row["kind"]))

    def normalize_amount_for_category(self, category: str | None, amount: float) -> float:
        """Apply category direction to manual amounts.

        Recette -> positive amount
        Dépense -> negative amount
        Neutre -> keep the entered sign, useful for transfers/corrections.
        """
        value = float(amount or 0)
        direction = self.category_direction(category)
        if direction == "Recette":
            return abs(value)
        if direction == "Dépense":
            return -abs(value)
        return value

    def normalize_existing_amounts_for_category(self, conn: sqlite3.Connection, category: str, direction: str) -> None:
        direction = self.normalize_category_direction(direction)
        if direction == "Neutre":
            return
        sign_sql = "ABS(amount)" if direction == "Recette" else "-ABS(amount)"
        conn.execute(
            f"UPDATE transactions SET amount = {sign_sql}, tx_type = CASE WHEN {sign_sql} >= 0 THEN 'Crédit' ELSE 'Débit' END, updated_at = CURRENT_TIMESTAMP WHERE category = ? AND source = 'Manuel'",
            (category,),
        )
        conn.execute(
            f"UPDATE recurring_items SET amount = {sign_sql}, updated_at = CURRENT_TIMESTAMP WHERE category = ?",
            (category,),
        )

    def add_category(self, name: str, kind: str = "Dépense", color: str = "#64748B", budget_enabled: bool = True, direction: str | None = None) -> int:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("Le nom de catégorie est obligatoire.")
        kind = kind or "Dépense"
        direction = self.normalize_category_direction(direction or self.default_direction_for_kind(kind))
        color = color or "#64748B"
        budget_value = 1 if (budget_enabled and direction == "Dépense") else 0
        with self.connect() as conn:
            existing = conn.execute("SELECT id FROM categories WHERE LOWER(name) = LOWER(?)", (clean_name,)).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE categories
                    SET kind = ?, direction = ?, color = ?, budget_enabled = ?, deleted_at = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (kind, direction, color, budget_value, existing["id"]),
                )
                category_id = int(existing["id"])
            else:
                cur = conn.execute(
                    """
                    INSERT INTO categories(name, kind, direction, color, budget_enabled, is_system, uuid)
                    VALUES (?, ?, ?, ?, ?, 0, ?)
                    """,
                    (clean_name, kind, direction, color, budget_value, str(uuid4())),
                )
                category_id = int(cur.lastrowid)
            self.normalize_existing_amounts_for_category(conn, clean_name, direction)
        self.seal_database_to_encrypted_vault()
        return category_id

    def get_category(self, category_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()

    def update_category(self, category_id: int, name: str, kind: str, color: str, budget_enabled: bool, direction: str | None = None) -> None:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("Le nom de catégorie est obligatoire.")
        kind = kind or "Dépense"
        direction = self.normalize_category_direction(direction or self.default_direction_for_kind(kind))
        color = color or "#64748B"
        budget_value = 1 if (budget_enabled and direction == "Dépense") else 0
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
            if not row:
                raise ValueError("Catégorie introuvable.")
            old_name = row["name"]
            duplicate = conn.execute(
                "SELECT id FROM categories WHERE LOWER(name) = LOWER(?) AND id <> ? AND deleted_at IS NULL",
                (clean_name, category_id),
            ).fetchone()
            if duplicate:
                raise ValueError("Une catégorie active porte déjà ce nom.")

            if clean_name != old_name:
                conn.execute("UPDATE transactions SET category = ?, updated_at = CURRENT_TIMESTAMP WHERE category = ?", (clean_name, old_name))
                conn.execute("UPDATE recurring_items SET category = ?, updated_at = CURRENT_TIMESTAMP WHERE category = ?", (clean_name, old_name))
                self._rename_budget_category(conn, old_name, clean_name)

            conn.execute(
                """
                UPDATE categories
                SET name = ?, kind = ?, direction = ?, color = ?, budget_enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (clean_name, kind, direction, color, budget_value, category_id),
            )
            self.normalize_existing_amounts_for_category(conn, clean_name, direction)
        self.seal_database_to_encrypted_vault()

    def _rename_budget_category(self, conn: sqlite3.Connection, old_name: str, new_name: str) -> None:
        rows = list(conn.execute(
            "SELECT * FROM budgets WHERE category = ? AND deleted_at IS NULL ORDER BY month",
            (old_name,),
        ))
        for row in rows:
            existing = conn.execute(
                "SELECT * FROM budgets WHERE month = ? AND category = ? AND deleted_at IS NULL AND id <> ?",
                (row["month"], new_name, row["id"]),
            ).fetchone()
            if existing:
                merged_notes = (existing["notes"] or "").strip()
                extra_note = f"Fusionné depuis {old_name}" if not merged_notes else f"{merged_notes} | Fusionné depuis {old_name}"
                conn.execute(
                    """
                    UPDATE budgets
                    SET planned_amount = planned_amount + ?, notes = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (float(row["planned_amount"] or 0), extra_note, existing["id"]),
                )
                conn.execute("UPDATE budgets SET deleted_at = CURRENT_TIMESTAMP, status = 'Fusionné', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
            else:
                conn.execute("UPDATE budgets SET category = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_name, row["id"]))

    def delete_category(self, category_id: int, replacement: str = "À catégoriser") -> None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
            if not row:
                raise ValueError("Catégorie introuvable.")
            name = row["name"]
            if name == replacement:
                raise ValueError("La catégorie de remplacement ne peut pas être supprimée.")
            replacement_row = conn.execute("SELECT id FROM categories WHERE name = ? AND deleted_at IS NULL", (replacement,)).fetchone()
            if not replacement_row:
                conn.execute(
                    "INSERT OR IGNORE INTO categories(name, kind, direction, color, is_system, budget_enabled, uuid) VALUES (?, 'Neutre', 'Neutre', '#A16207', 1, 0, ?)",
                    (replacement, str(uuid4())),
                )
            conn.execute("UPDATE transactions SET category = ?, status = 'À catégoriser', updated_at = CURRENT_TIMESTAMP WHERE category = ?", (replacement, name))
            conn.execute("UPDATE recurring_items SET category = ?, updated_at = CURRENT_TIMESTAMP WHERE category = ?", (replacement, name))
            conn.execute("UPDATE budgets SET deleted_at = CURRENT_TIMESTAMP, status = 'Supprimé', updated_at = CURRENT_TIMESTAMP WHERE category = ? AND deleted_at IS NULL", (name,))
            conn.execute("UPDATE categories SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (category_id,))
        self.seal_database_to_encrypted_vault()

    def list_transactions(self, search: str = "", account_id: int | None = None, only_uncategorized: bool = False) -> list[sqlite3.Row]:
        params: list = []
        where = []
        if search:
            where.append("(LOWER(t.label) LIKE ? OR LOWER(COALESCE(t.category, '')) LIKE ?)")
            like = f"%{search.lower()}%"
            params.extend([like, like])
        if account_id:
            where.append("t.account_id = ?")
            params.append(account_id)
        if only_uncategorized:
            where.append("(t.category IS NULL OR t.category = '' OR t.category = 'À catégoriser' OR t.status = 'À catégoriser')")
        sql_where = "WHERE " + " AND ".join(where) if where else ""
        with self.connect() as conn:
            return list(
                conn.execute(
                    f"""
                    SELECT t.*, a.name AS account_name, a.bank AS bank
                    FROM transactions t
                    JOIN accounts a ON a.id = t.account_id
                    {sql_where}
                    ORDER BY t.tx_date DESC, t.id DESC
                    LIMIT 500
                    """,
                    params,
                )
            )

    def insert_transaction(self, account_id: int, tx_date: str, label: str, category: str | None, amount: float, source: str, import_batch_id: int | None = None, *, beneficiary: str | None = None, currency: str = 'EUR', source_line: int | None = None, source_profile: str | None = None, raw_payload: str | None = None, source_identifier: str | None = None, preserve_direction: bool = False) -> bool:
        if source == "Manuel" and not preserve_direction:
            amount = self.normalize_amount_for_category(category, amount)
        tx_type = "Crédit" if amount >= 0 else "Débit"
        status = "Validée" if category else "À catégoriser"
        if source == "Manuel":
            categorization_status = "manual" if category else "to_categorize"
            categorized_by = "manual" if category else None
            categorized_at = datetime.now().isoformat(timespec="seconds") if category else None
        else:
            categorization_status = "to_categorize"
            categorized_by = "import_default" if category else None
            categorized_at = None
        signature = self.make_signature(account_id, tx_date, label, amount)
        clean_beneficiary = (beneficiary or extract_counterparty(label)).strip() or None
        rules = self.reconciliation_rules()
        transaction_day = date.fromisoformat(tx_date)
        ForecastReconciliationService(self).generate_occurrences(
            transaction_day - timedelta(days=rules.date_tolerance_days),
            transaction_day + timedelta(days=rules.date_tolerance_days),
        )
        with self.connect() as conn:
            exists = conn.execute("SELECT id FROM transactions WHERE signature = ?", (signature,)).fetchone()
            if exists:
                return False
            cursor = conn.execute(
                """
                INSERT INTO transactions(account_id, tx_date, label, beneficiary, category, amount, tx_type, status, source, import_batch_id, signature,
                                         categorization_status, categorized_by, categorization_rule_id, categorized_at,
                                         currency, source_line, source_profile, raw_payload, source_identifier)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
                """,
                (account_id, tx_date, label, clean_beneficiary, category, amount, tx_type, status, source, import_batch_id, signature,
                 categorization_status, categorized_by, categorized_at,
                 currency or 'EUR', source_line, source_profile, raw_payload, source_identifier),
            )
            qualify_and_persist_transaction(conn, int(cursor.lastrowid), rules)
            return True

    def reconciliation_summary_for_import_batch(self, import_batch_id: int) -> dict[str, int]:
        summary = {"auto": 0, "to_review": 0, "without_forecast": 0}
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT state.status, COUNT(*) AS item_count
                FROM transaction_reconciliation_state state
                JOIN transactions transaction_row
                  ON transaction_row.id = state.transaction_id
                WHERE transaction_row.import_batch_id = ?
                GROUP BY state.status
                """,
                (import_batch_id,),
            ).fetchall()
        mapping = {
            "reconciled": "auto",
            "has_proposal": "to_review",
            "without_forecast": "without_forecast",
        }
        for row in rows:
            key = mapping.get(str(row["status"]))
            if key is not None:
                summary[key] = int(row["item_count"])
        return summary


    def get_transaction(self, transaction_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT t.*, a.name AS account_name, a.bank AS bank
                FROM transactions t
                JOIN accounts a ON a.id = t.account_id
                WHERE t.id = ?
                """,
                (transaction_id,),
            ).fetchone()

    def update_transaction(self, transaction_id: int, data: dict) -> None:
        """Update all editable fields of an existing transaction.

        R7.1 fixes issue #2: transaction edition is no longer limited to the
        category. Updating the amount/date/account recalculates the signature,
        type and downstream dashboards/budgets because they read from
        transactions dynamically.
        """
        row = self.get_transaction(transaction_id)
        if not row:
            raise ValueError("Transaction introuvable.")

        payload = {
            "account_id": data.get("account_id", row["account_id"]),
            "tx_date": data.get("tx_date", row["tx_date"]),
            "label": (data.get("label") or row["label"] or "Opération").strip(),
            "beneficiary": (data.get("beneficiary") or extract_counterparty(data.get("label") or row["label"] or "")).strip() or None,
            "category": data.get("category", row["category"]),
            "amount": float(data.get("amount", row["amount"]) or 0),
            "status": data.get("status", row["status"] or "Validée"),
            "source": data.get("source", row["source"] or "Manuel"),
        }
        if payload["source"] == "Manuel" and not data.get("direction_explicit", False):
            payload["amount"] = self.normalize_amount_for_category(payload["category"], payload["amount"])
        payload["tx_type"] = "Crédit" if payload["amount"] >= 0 else "Débit"
        if not payload["category"]:
            payload["status"] = "À catégoriser"
        payload["signature"] = self.make_signature(
            int(payload["account_id"]),
            str(payload["tx_date"]),
            str(payload["label"]),
            float(payload["amount"]),
        )

        categorization_status = "manual" if payload["category"] else "to_categorize"
        categorized_by = "manual" if payload["category"] else None

        with self.connect() as conn:
            conn.execute(
                """
                UPDATE transactions
                SET account_id = :account_id,
                    tx_date = :tx_date,
                    label = :label,
                    beneficiary = :beneficiary,
                    category = :category,
                    amount = :amount,
                    tx_type = :tx_type,
                    status = :status,
                    source = :source,
                    signature = :signature,
                    categorization_status = :categorization_status,
                    categorized_by = :categorized_by,
                    categorization_rule_id = NULL,
                    categorized_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :transaction_id
                """,
                {
                    **payload,
                    "categorization_status": categorization_status,
                    "categorized_by": categorized_by,
                    "transaction_id": transaction_id,
                },
            )
            conn.execute(
                """
                UPDATE forecast_occurrences
                SET actual_date = :tx_date,
                    actual_amount = :amount,
                    amount_delta = ROUND(:amount - expected_amount, 2),
                    updated_at = CURRENT_TIMESTAMP
                WHERE actual_transaction_id = :transaction_id
                """,
                {
                    "tx_date": payload["tx_date"],
                    "amount": payload["amount"],
                    "transaction_id": transaction_id,
                },
            )
            reevaluate_transaction(
                conn,
                transaction_id,
                self.reconciliation_rules(conn),
                reason="Transaction modifiée",
            )
        self.seal_database_to_encrypted_vault()


    def update_transaction_category(self, transaction_id: int, category: str | None) -> None:
        status = "Validée" if category else "À catégoriser"
        with self.connect() as conn:
            row = conn.execute("SELECT amount, source FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
            amount = float(row["amount"] or 0) if row else 0.0
            if row and row["source"] == "Manuel":
                amount = self.normalize_amount_for_category(category, amount)
            tx_type = "Crédit" if amount >= 0 else "Débit"
            categorization_status = "manual" if category else "to_categorize"
            categorized_by = "manual" if category else None
            conn.execute(
                """
                UPDATE transactions
                SET category = ?, amount = ?, tx_type = ?, status = ?,
                    categorization_status = ?, categorized_by = ?, categorization_rule_id = NULL,
                    categorized_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (category, amount, tx_type, status, categorization_status, categorized_by, transaction_id),
            )
            reevaluate_transaction(
                conn,
                transaction_id,
                self.reconciliation_rules(conn),
                reason="Catégorie de transaction modifiée",
            )

    def delete_transaction(self, transaction_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))


    def update_transactions_category(self, transaction_ids: list[int], category: str | None) -> int:
        if not transaction_ids:
            return 0
        status = "Validée" if category else "À catégoriser"
        placeholders = ",".join("?" for _ in transaction_ids)
        with self.connect() as conn:
            categorization_status = "manual" if category else "to_categorize"
            categorized_by = "manual" if category else None
            cur = conn.execute(
                f"""
                UPDATE transactions
                SET category = ?, status = ?, categorization_status = ?, categorized_by = ?,
                    categorization_rule_id = NULL, categorized_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
                """,
                [category, status, categorization_status, categorized_by, *transaction_ids],
            )
            direction = self.category_direction(category)
            if category and direction != "Neutre":
                sign_sql = "ABS(amount)" if direction == "Recette" else "-ABS(amount)"
                conn.execute(
                    f"UPDATE transactions SET amount = {sign_sql}, tx_type = CASE WHEN {sign_sql} >= 0 THEN 'Crédit' ELSE 'Débit' END, updated_at = CURRENT_TIMESTAMP WHERE source = 'Manuel' AND id IN ({placeholders})",
                    transaction_ids,
                )
            for transaction_id in transaction_ids:
                reevaluate_transaction(
                    conn,
                    int(transaction_id),
                    self.reconciliation_rules(conn),
                    reason="Catégorie de transaction modifiée en lot",
                )
            return int(cur.rowcount or 0)

    def update_transactions_status(self, transaction_ids: list[int], status: str) -> int:
        if not transaction_ids:
            return 0
        placeholders = ",".join("?" for _ in transaction_ids)
        with self.connect() as conn:
            cur = conn.execute(
                f"UPDATE transactions SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                [status, *transaction_ids],
            )
            return int(cur.rowcount or 0)

    def delete_transactions(self, transaction_ids: list[int]) -> int:
        if not transaction_ids:
            return 0
        placeholders = ",".join("?" for _ in transaction_ids)
        with self.connect() as conn:
            conn.execute(f"DELETE FROM categorization_rule_logs WHERE transaction_id IN ({placeholders})", transaction_ids)
            conn.execute(
                f"""
                UPDATE forecast_occurrences
                SET actual_transaction_id = NULL,
                    actual_date = NULL,
                    actual_amount = NULL,
                    amount_delta = NULL,
                    match_confidence = NULL,
                    match_reason = NULL,
                    status = CASE
                        WHEN expected_date < date('now') THEN 'overdue'
                        ELSE 'planned'
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE actual_transaction_id IN ({placeholders})
                """,
                transaction_ids,
            )
            cur = conn.execute(f"DELETE FROM transactions WHERE id IN ({placeholders})", transaction_ids)
            return int(cur.rowcount or 0)


    def create_import_batch(self, file_name: str, account_id: int, *, parser_profile: str | None = None, source_fingerprint: str | None = None, diagnostic_summary: str | None = None, header_line: int | None = None) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO import_batches(file_name, account_id, parser_profile, source_fingerprint, diagnostic_summary, header_line)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (file_name, account_id, parser_profile, source_fingerprint, diagnostic_summary, header_line),
            )
            return int(cur.lastrowid)

    def update_import_batch(self, batch_id: int, imported: int, duplicates: int, errors: int) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE import_batches
                SET imported_count = ?, duplicate_count = ?, error_count = ?, status = 'Importé'
                WHERE id = ?
                """,
                (imported, duplicates, errors, batch_id),
            )

    def transaction_exists(self, account_id: int, tx_date: str, label: str, amount: float) -> bool:
        signature = self.make_signature(account_id, tx_date, label, amount)
        with self.connect() as conn:
            row = conn.execute("SELECT id FROM transactions WHERE signature = ?", (signature,)).fetchone()
            return row is not None

    def list_recent_import_batches(self, limit: int = 8) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT b.*, a.name AS account_name, a.bank AS bank, a.identifier AS account_identifier,
                           (SELECT COUNT(*) FROM transactions t WHERE t.import_batch_id = b.id) AS linked_transactions
                    FROM import_batches b
                    JOIN accounts a ON a.id = b.account_id
                    ORDER BY b.created_at DESC, b.id DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            )

    def get_import_batch(self, batch_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT b.*, a.name AS account_name, a.bank AS bank, a.identifier AS account_identifier,
                       (SELECT COUNT(*) FROM transactions t WHERE t.import_batch_id = b.id) AS linked_transactions
                FROM import_batches b
                JOIN accounts a ON a.id = b.account_id
                WHERE b.id = ?
                """,
                (batch_id,),
            ).fetchone()

    def cancel_import_batch(self, batch_id: int) -> int:
        """Cancel an import batch safely.

        Automatic categorization logs can reference imported transactions.
        Delete those logs before deleting transactions to avoid SQLite
        FOREIGN KEY constraint failures.
        """
        with self.connect() as conn:
            batch = conn.execute("SELECT status FROM import_batches WHERE id = ?", (batch_id,)).fetchone()
            if not batch or batch["status"] == "Annulé":
                return 0

            transaction_ids = [
                int(row["id"])
                for row in conn.execute("SELECT id FROM transactions WHERE import_batch_id = ?", (batch_id,))
            ]

            if transaction_ids:
                placeholders = ",".join("?" for _ in transaction_ids)
                conn.execute(
                    f"DELETE FROM categorization_rule_logs WHERE import_batch_id = ? OR transaction_id IN ({placeholders})",
                    [batch_id, *transaction_ids],
                )
                # R6: linked forecast occurrences must be reset before the
                # imported real transactions are deleted.
                conn.execute(
                    f"""
                    UPDATE forecast_occurrences
                    SET actual_transaction_id = NULL,
                        actual_date = NULL,
                        actual_amount = NULL,
                        amount_delta = NULL,
                        match_confidence = NULL,
                        match_reason = NULL,
                        status = CASE
                            WHEN expected_date < date('now') THEN 'overdue'
                            ELSE 'planned'
                        END,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE actual_transaction_id IN ({placeholders})
                    """,
                    transaction_ids,
                )
            else:
                conn.execute("DELETE FROM categorization_rule_logs WHERE import_batch_id = ?", (batch_id,))

            deleted = conn.execute("DELETE FROM transactions WHERE import_batch_id = ?", (batch_id,)).rowcount
            conn.execute(
                """
                UPDATE import_batches
                SET status = 'Annulé', canceled_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (batch_id,),
            )
            return int(deleted or 0)

    def account_summary(self) -> dict[str, float]:
        rows = [row for row in self.list_accounts() if row["status"] == "Actif"]
        summary = {
            "solde_net": 0.0,
            "liquidites": 0.0,
            "epargne": 0.0,
            "investissements": 0.0,
            "dettes": 0.0,
            "comptes_courants": 0.0,
        }
        for row in rows:
            typ = row["account_type"]
            total = row["calculated_balance"] or 0
            summary["solde_net"] += total
            if typ == "Compte courant":
                summary["liquidites"] += total
                summary["comptes_courants"] += total
            elif typ == "Compte épargne":
                summary["epargne"] += total
                summary["liquidites"] += total
            elif typ == "Compte investissement":
                summary["investissements"] += total
            elif typ == "Compte crédit":
                summary["dettes"] += abs(total)
        return summary

    def dashboard_current_month(self) -> str:
        """Current calendar month used by the Dashboard.

        The Dashboard must reflect the real current month, not the historical
        demo/current_month setting that can remain on an old month.
        """
        return date.today().strftime("%Y-%m")

    def dashboard_metrics(self) -> dict[str, float]:
        summary = self.account_summary()
        with self.connect() as conn:
            current_month = self.dashboard_current_month()
            tx_rows = list(
                conn.execute(
                    """
                    SELECT category, amount
                    FROM transactions
                    WHERE tx_date LIKE ?
                    """,
                    (current_month + "%",),
                )
            )
            revenus = sum(float(row["amount"] or 0) for row in tx_rows if is_true_income(row["category"], float(row["amount"] or 0)))
            depenses = abs(sum(float(row["amount"] or 0) for row in tx_rows if is_current_expense(row["category"], float(row["amount"] or 0))))
        liquidites_disponibles = summary["liquidites"]
        patrimoine_net = self.net_worth_breakdown()["net_worth"]
        start_date = self.default_forecast_start_date()
        forecast_30 = self.cash_forecast(start_date, 30, "Réaliste")["end_balance"]
        return {
            "cash": liquidites_disponibles,
            "forecast_30": forecast_30,
            "forecast_start_date": start_date,
            "patrimoine_net": patrimoine_net,
            "revenus": revenus,
            "depenses": depenses,
            "month": current_month,
        }

    def expenses_by_category(self) -> dict[str, float]:
        current_month = self.get_setting("current_month", "2026-06")
        with self.connect() as conn:
            rows = list(
                conn.execute(
                    """
                    SELECT COALESCE(category, 'À catégoriser') AS category, amount
                    FROM transactions
                    WHERE amount < 0
                      AND tx_date LIKE ?
                    """,
                    (current_month + "%",),
                )
            )
        totals: dict[str, float] = {}
        for row in rows:
            category = row["category"]
            amount = float(row["amount"] or 0)
            if is_current_expense(category, amount):
                totals[category or "À catégoriser"] = totals.get(category or "À catégoriser", 0) + abs(amount)
        raw = sorted(totals.items(), key=lambda item: item[1], reverse=True)
        top = raw[:5]
        other = sum(value for _, value in raw[5:])
        data = {label: value for label, value in top}
        if other:
            data["Autres"] = other
        return data

    def list_assets(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(conn.execute("SELECT * FROM assets ORDER BY value DESC"))


    @staticmethod
    def normalize_asset_payload(data: dict) -> dict:
        payload = dict(data)
        category = str(payload.get("category") or "")
        asset_type = str(payload.get("asset_type") or "")
        value = float(payload.get("value") or 0)
        passive_keywords = ("crédit", "credit", "dette", "passif", "emprunt", "prêt", "pret")
        if any(word in category.lower() or word in asset_type.lower() for word in passive_keywords):
            value = -abs(value)
        payload["value"] = value
        details = payload.get("details_json", "{}")
        if isinstance(details, dict):
            details = json.dumps(details, ensure_ascii=False)
        payload["details_json"] = str(details or "{}")
        return payload


    def add_asset(self, data: dict) -> int:
        payload = self.normalize_asset_payload(data)
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO assets(name, category, asset_type, value, valuation_date, valuation_mode, comment, details_json, status)
                VALUES (:name, :category, :asset_type, :value, :valuation_date, :valuation_mode, :comment, :details_json, :status)
                """,
                payload,
            )
            asset_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO asset_values(asset_id, valuation_date, value, source, comment) VALUES (?, ?, ?, ?, ?)",
                (asset_id, payload["valuation_date"], payload["value"], payload["valuation_mode"], payload.get("comment", "")),
            )
        self.seal_database_to_encrypted_vault()
        return asset_id



    def get_asset(self, asset_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()

    def update_asset(self, asset_id: int, data: dict) -> None:
        row = self.get_asset(asset_id)
        if not row:
            raise ValueError("Élément patrimonial introuvable.")
        merged = {key: row[key] for key in row.keys()}
        merged.update(data)
        payload = self.normalize_asset_payload(merged)
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE assets
                SET name = :name,
                    category = :category,
                    asset_type = :asset_type,
                    value = :value,
                    valuation_date = :valuation_date,
                    valuation_mode = :valuation_mode,
                    comment = :comment,
                    details_json = :details_json,
                    status = :status,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :asset_id
                """,
                {"asset_id": asset_id, **payload},
            )
            conn.execute(
                "INSERT INTO asset_values(asset_id, valuation_date, value, source, comment) VALUES (?, ?, ?, ?, ?)",
                (asset_id, payload["valuation_date"], payload["value"], payload["valuation_mode"], payload.get("comment", "")),
            )
        self.seal_database_to_encrypted_vault()

    def delete_asset(self, asset_id: int) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM asset_values WHERE asset_id = ?", (asset_id,))
            conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        self.seal_database_to_encrypted_vault()

    def asset_history(self, asset_id: int) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT valuation_date, value, source, comment, created_at
                    FROM asset_values
                    WHERE asset_id = ?
                    ORDER BY valuation_date DESC, id DESC
                    """,
                    (asset_id,),
                )
            )


    def update_asset_value(self, asset_id: int, value: float, valuation_date: str, source: str = "Manuelle", comment: str = "") -> None:
        row = self.get_asset(asset_id)
        if row:
            payload = self.normalize_asset_payload({
                "category": row["category"],
                "asset_type": row["asset_type"],
                "value": value,
            })
            value = payload["value"]
        with self.connect() as conn:
            conn.execute(
                "UPDATE assets SET value = ?, valuation_date = ?, valuation_mode = ?, comment = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (value, valuation_date, source, comment, asset_id),
            )
            conn.execute(
                "INSERT INTO asset_values(asset_id, valuation_date, value, source, comment) VALUES (?, ?, ?, ?, ?)",
                (asset_id, valuation_date, value, source, comment),
            )
        self.seal_database_to_encrypted_vault()


    def net_worth_breakdown(self) -> dict[str, float]:
        """Single source of truth for assets, liabilities and net worth.

        Business rule (validated 22/10/2026): net worth includes the liquidity
        of the active current and savings accounts, computed live from the
        accounts. Used by the Dashboard and by the Patrimoine screen.
        """
        with self.connect() as conn:
            rows = list(
                conn.execute(
                    "SELECT name, category, asset_type, value FROM assets WHERE status = 'Actif'"
                )
            )
        asset_values = [
            float(row["value"] or 0)
            for row in rows
            if float(row["value"] or 0) > 0 and is_patrimonial_asset(row["name"], row["category"], row["asset_type"])
        ]
        liability_values = [
            abs(float(row["value"] or 0))
            for row in rows
            if float(row["value"] or 0) < 0 and is_patrimonial_asset(row["name"], row["category"], row["asset_type"])
        ]
        liquidities = round(float(self.account_summary()["liquidites"] or 0), 2)
        assets_total = round(sum(asset_values) + max(liquidities, 0.0), 2)
        liabilities_total = round(sum(liability_values) + max(-liquidities, 0.0), 2)
        return {
            "assets": assets_total,
            "liabilities": liabilities_total,
            "liquidities": liquidities,
            "net_worth": round(assets_total - liabilities_total, 2),
        }

    def asset_summary(self) -> dict[str, float]:
        with self.connect() as conn:
            rows = list(
                conn.execute(
                    "SELECT name, category, asset_type, value FROM assets WHERE status = 'Actif'"
                )
            )
        totals: dict[str, float] = {}
        for row in rows:
            if not is_patrimonial_asset(row["name"], row["category"], row["asset_type"]):
                continue
            category = row["category"]
            totals[category] = totals.get(category, 0.0) + float(row["value"] or 0)
        liquidities = round(float(self.account_summary()["liquidites"] or 0), 2)
        if liquidities:
            totals["Liquidités"] = totals.get("Liquidités", 0.0) + liquidities
        return totals


    def asset_value_history(self) -> list[dict]:
        """Toutes les valorisations stockées (actifs et passifs), triées par date."""
        with self.connect() as conn:
            return [
                {"asset_id": int(row["asset_id"]), "valuation_date": str(row["valuation_date"]), "value": float(row["value"] or 0)}
                for row in conn.execute("SELECT asset_id, valuation_date, value FROM asset_values ORDER BY valuation_date, id")
            ]

    def patrimonio_evolution(self, mode: str = "net") -> list[dict[str, float | str]]:
        """Return patrimonial evolution based on real asset valuation history.

        The previous prototype used a hardcoded line series in the Patrimoine page.
        V0.3.4 replaces it with data calculated from asset_values and assets.

        mode:
        - "net": sum of active assets and liabilities at each valuation date.
        - "assets": sum of positive active assets only.
        - "liabilities": absolute sum of negative active liabilities only.
        """
        with self.connect() as conn:
            assets = list(conn.execute("""
                SELECT id, value, valuation_date, status
                FROM assets
                WHERE status = 'Actif'
                  AND LOWER(name || ' ' || category || ' ' || asset_type) NOT LIKE '%compte courant%'
                  AND LOWER(name || ' ' || category || ' ' || asset_type) NOT LIKE '%compte bancaire%'
                  AND LOWER(name || ' ' || category || ' ' || asset_type) NOT LIKE '%liquidit%'
                  AND LOWER(name || ' ' || category || ' ' || asset_type) NOT LIKE '%livret%'
                  AND LOWER(name || ' ' || category || ' ' || asset_type) NOT LIKE '%épargne%'
                  AND LOWER(name || ' ' || category || ' ' || asset_type) NOT LIKE '%epargne%'
                  AND LOWER(name || ' ' || category || ' ' || asset_type) NOT LIKE '%dépôt%'
                  AND LOWER(name || ' ' || category || ' ' || asset_type) NOT LIKE '%depot%'
                  AND LOWER(name || ' ' || category || ' ' || asset_type) NOT LIKE '%découvert%'
                  AND LOWER(name || ' ' || category || ' ' || asset_type) NOT LIKE '%decouvert%'
            """))
            value_rows = list(
                conn.execute(
                    """
                    SELECT av.asset_id, av.valuation_date, av.value
                    FROM asset_values av
                    JOIN assets a ON a.id = av.asset_id
                    WHERE a.status = 'Actif'
                      AND LOWER(a.name || ' ' || a.category || ' ' || a.asset_type) NOT LIKE '%compte courant%'
                      AND LOWER(a.name || ' ' || a.category || ' ' || a.asset_type) NOT LIKE '%compte bancaire%'
                      AND LOWER(a.name || ' ' || a.category || ' ' || a.asset_type) NOT LIKE '%liquidit%'
                      AND LOWER(a.name || ' ' || a.category || ' ' || a.asset_type) NOT LIKE '%livret%'
                      AND LOWER(a.name || ' ' || a.category || ' ' || a.asset_type) NOT LIKE '%épargne%'
                      AND LOWER(a.name || ' ' || a.category || ' ' || a.asset_type) NOT LIKE '%epargne%'
                      AND LOWER(a.name || ' ' || a.category || ' ' || a.asset_type) NOT LIKE '%dépôt%'
                      AND LOWER(a.name || ' ' || a.category || ' ' || a.asset_type) NOT LIKE '%depot%'
                      AND LOWER(a.name || ' ' || a.category || ' ' || a.asset_type) NOT LIKE '%découvert%'
                      AND LOWER(a.name || ' ' || a.category || ' ' || a.asset_type) NOT LIKE '%decouvert%'
                    ORDER BY av.valuation_date, av.asset_id
                    """
                )
            )

        if not assets:
            return []

        valuations_by_asset: dict[int, list[tuple[str, float]]] = {}
        dates: set[str] = set()
        for row in value_rows:
            asset_id = int(row["asset_id"])
            valuation_date = str(row["valuation_date"])
            value = float(row["value"] or 0)
            valuations_by_asset.setdefault(asset_id, []).append((valuation_date, value))
            dates.add(valuation_date)

        for asset in assets:
            dates.add(str(asset["valuation_date"]))

        ordered_dates = sorted(dates)
        result: list[dict[str, float | str]] = []
        for valuation_date in ordered_dates:
            total = 0.0
            for asset in assets:
                asset_id = int(asset["id"])
                current_value = None
                for value_date, value in valuations_by_asset.get(asset_id, []):
                    if value_date <= valuation_date:
                        current_value = value
                    else:
                        break
                if current_value is None:
                    if str(asset["valuation_date"]) <= valuation_date:
                        current_value = float(asset["value"] or 0)
                    else:
                        continue

                if mode == "assets":
                    total += current_value if current_value > 0 else 0
                elif mode == "liabilities":
                    total += abs(current_value) if current_value < 0 else 0
                else:
                    total += current_value

            result.append({"date": valuation_date, "value": total})
        return result



    def list_recurring_items(self, active_only: bool = True) -> list[sqlite3.Row]:
        where = "WHERE r.status = 'Actif'" if active_only else ""
        with self.connect() as conn:
            return list(
                conn.execute(
                    f"""
                    SELECT r.*, a.name AS account_name, a.bank AS bank
                    FROM recurring_items r
                    LEFT JOIN accounts a ON a.id = r.account_id
                    {where}
                    ORDER BY r.next_date, r.name
                    """
                )
            )

    def add_recurring_item(self, data: dict) -> int:
        payload = dict(data)
        payload["amount"] = self.normalize_amount_for_category(payload.get("category"), payload.get("amount", 0))
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO recurring_items(account_id, name, category, amount, frequency, next_date, end_date, scenario, status)
                VALUES (:account_id, :name, :category, :amount, :frequency, :next_date, :end_date, :scenario, :status)
                """,
                payload,
            )
            return int(cursor.lastrowid)

    def get_recurring_item(self, item_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT r.*, a.name AS account_name, a.bank AS bank
                FROM recurring_items r
                LEFT JOIN accounts a ON a.id = r.account_id
                WHERE r.id = ?
                """,
                (item_id,),
            ).fetchone()

    def update_recurring_item(self, item_id: int, data: dict) -> None:
        payload = dict(data)
        payload["amount"] = self.normalize_amount_for_category(payload.get("category"), payload.get("amount", 0))
        payload["item_id"] = item_id
        with self.connect() as conn:
            occurrence_ids = [
                int(row[0])
                for row in conn.execute(
                    """
                    SELECT id FROM forecast_occurrences
                    WHERE source_type = 'recurring'
                      AND source_id = ?
                      AND deleted_at IS NULL
                    """,
                    (item_id,),
                ).fetchall()
            ]
            conn.execute(
                """
                UPDATE recurring_items
                SET account_id = :account_id,
                    name = :name,
                    category = :category,
                    amount = :amount,
                    frequency = :frequency,
                    next_date = :next_date,
                    end_date = :end_date,
                    scenario = :scenario,
                    status = :status,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :item_id
                """,
                payload,
            )
            if occurrence_ids:
                placeholders = ",".join("?" for _ in occurrence_ids)
                direction = "credit" if float(payload["amount"]) >= 0 else "debit"
                occurrence_status = (
                    "planned" if payload.get("status") == "Actif" else "cancelled"
                )
                conn.execute(
                    f"""
                    UPDATE forecast_occurrences
                    SET account_id = ?, expected_amount = ?, expected_label = ?,
                        expected_category = ?, direction = ?, status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id IN ({placeholders})
                    """,
                    (
                        payload["account_id"],
                        payload["amount"],
                        payload["name"],
                        payload.get("category") or "Prévisionnel",
                        direction,
                        occurrence_status,
                        *occurrence_ids,
                    ),
                )
                reevaluate_for_occurrences(
                    conn,
                    occurrence_ids,
                    self.reconciliation_rules(conn),
                    reason="Prévision récurrente modifiée",
                )

    def delete_recurring_item(self, item_id: int) -> None:
        with self.connect() as conn:
            occurrence_ids = [
                int(row[0])
                for row in conn.execute(
                    """
                    SELECT id FROM forecast_occurrences
                    WHERE source_type = 'recurring' AND source_id = ?
                    """,
                    (item_id,),
                ).fetchall()
            ]
            affected_transaction_ids = affected_transactions_for_occurrences(
                conn, occurrence_ids, self.reconciliation_rules(conn)
            )
            conn.execute(
                """
                DELETE FROM forecast_occurrences
                WHERE source_type = 'recurring' AND source_id = ?
                """,
                (item_id,),
            )
            conn.execute("DELETE FROM recurring_items WHERE id = ?", (item_id,))
            for transaction_id in affected_transaction_ids:
                reevaluate_transaction(
                    conn,
                    transaction_id,
                    self.reconciliation_rules(conn),
                    reason="Prévision récurrente supprimée",
                )

    def update_recurring_item_status(self, item_id: int, status: str) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE recurring_items SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, item_id),
            )
            occurrence_ids = [
                int(row[0])
                for row in conn.execute(
                    """
                    SELECT id FROM forecast_occurrences
                    WHERE source_type = 'recurring'
                      AND source_id = ?
                      AND deleted_at IS NULL
                    """,
                    (item_id,),
                ).fetchall()
            ]
            if occurrence_ids:
                placeholders = ",".join("?" for _ in occurrence_ids)
                occurrence_status = "planned" if status == "Actif" else "cancelled"
                conn.execute(
                    f"""
                    UPDATE forecast_occurrences
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id IN ({placeholders})
                    """,
                    (occurrence_status, *occurrence_ids),
                )
                reevaluate_for_occurrences(
                    conn,
                    occurrence_ids,
                    self.reconciliation_rules(conn),
                    reason="Statut de prévision récurrente modifié",
                )

    @staticmethod
    def add_period(source: date, frequency: str) -> date:
        if frequency in {"Ponctuel", "Une fois", "Ponctuel / une seule fois"}:
            return source + timedelta(days=36500)
        if frequency == "Hebdomadaire":
            return source + timedelta(days=7)
        if frequency == "Trimestriel":
            month = source.month + 3
        elif frequency == "Annuel":
            month = source.month + 12
        else:
            month = source.month + 1
        year = source.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        return date(year, month, min(source.day, 28))

    def forecast_events(self, start_date: str = "2026-06-23", horizon_days: int = 90, scenario: str = "Réaliste", account_id: int | None = None) -> list[dict]:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = start + timedelta(days=horizon_days)
        events: list[dict] = []

        params: list = [start_date, end.isoformat()]
        where_account = ""
        if account_id is not None:
            where_account = " AND t.account_id = ?"
            params.append(account_id)

        with self.connect() as conn:
            manual = list(
                conn.execute(
                    f"""
                    SELECT t.tx_date AS event_date, t.label AS name, t.category, t.amount, 'Transaction future' AS source,
                           a.name AS account_name, a.id AS account_id
                    FROM transactions t
                    JOIN accounts a ON a.id = t.account_id
                    WHERE t.tx_date > ? AND t.tx_date <= ?{where_account}
                    ORDER BY t.tx_date
                    """,
                    params,
                )
            )
        for row in manual:
            events.append({
                "date": row["event_date"],
                "name": row["name"],
                "category": row["category"] or "À catégoriser",
                "amount": float(row["amount"] or 0),
                "source": row["source"],
                "account": row["account_name"],
                "account_id": row["account_id"],
                "recurring_id": None,
                "scenario": "Tous",
            })

        suppressed_occurrences: set[tuple[int, str]] = set()
        moved_occurrences = []
        with self.connect() as conn:
            occ_params: list = [
                start_date,
                end.isoformat(),
                start_date,
                end.isoformat(),
            ]
            occ_account = ""
            if account_id is not None:
                occ_account = " AND o.account_id = ?"
                occ_params.append(account_id)
            for occurrence in conn.execute(
                f"""
                SELECT o.source_id, o.expected_date, o.original_expected_date,
                       o.expected_amount, o.expected_label, o.expected_category,
                       o.status, o.actual_transaction_id, o.remaining_amount,
                       o.account_id, a.name AS account_name, r.scenario
                FROM forecast_occurrences o
                LEFT JOIN accounts a ON a.id = o.account_id
                LEFT JOIN recurring_items r ON r.id = o.source_id
                WHERE o.source_type = 'recurring'
                  AND o.deleted_at IS NULL
                  AND o.source_id IS NOT NULL
                  AND (
                        (COALESCE(o.original_expected_date, o.expected_date) > ?
                         AND COALESCE(o.original_expected_date, o.expected_date) <= ?)
                     OR (o.expected_date > ? AND o.expected_date <= ?)
                  ){occ_account}
                """,
                occ_params,
            ):
                status = str(occurrence["status"] or "")
                has_real = occurrence["actual_transaction_id"] is not None
                expected_date = str(occurrence["expected_date"])
                original_date = str(occurrence["original_expected_date"] or expected_date)
                source_id = int(occurrence["source_id"])
                was_rescheduled = original_date != expected_date

                if was_rescheduled:
                    suppressed_occurrences.add((source_id, original_date))
                    if (
                        status in {"planned", "overdue", "to_review", "partially_matched"}
                        and not has_real
                        and start_date < expected_date <= end.isoformat()
                    ):
                        moved_occurrences.append(occurrence)
                elif status in {"auto_matched", "ignored", "cancelled"} or (
                    status in {"confirmed", "to_review"} and has_real
                ):
                    suppressed_occurrences.add((source_id, expected_date))

        for occurrence in moved_occurrences:
            occurrence_scenario = str(occurrence["scenario"] or "Réaliste")
            if scenario != "Optimiste" and occurrence_scenario == "Optimiste":
                continue
            amount = float(occurrence["expected_amount"] or 0)
            if occurrence["status"] == "partially_matched" and occurrence["remaining_amount"] is not None:
                remaining = abs(float(occurrence["remaining_amount"] or 0))
                amount = remaining if amount >= 0 else -remaining
            events.append({
                "date": occurrence["expected_date"],
                "name": occurrence["expected_label"] or "Récurrence",
                "category": occurrence["expected_category"] or "Prévisionnel",
                "amount": amount,
                "source": "Récurrence décalée",
                "account": occurrence["account_name"] or "Compte",
                "account_id": occurrence["account_id"],
                "recurring_id": occurrence["source_id"],
                "scenario": occurrence_scenario,
                "original_date": occurrence["original_expected_date"] or occurrence["expected_date"],
            })

        for item in self.list_recurring_items(active_only=True):
            if account_id is not None and item["account_id"] != account_id:
                continue
            if scenario != "Optimiste" and item["scenario"] == "Optimiste":
                continue
            next_date = datetime.strptime(item["next_date"], "%Y-%m-%d").date()
            end_date = datetime.strptime(item["end_date"], "%Y-%m-%d").date() if item["end_date"] else end
            while next_date <= end and next_date <= end_date:
                if next_date > start:
                    if (int(item["id"]), next_date.isoformat()) in suppressed_occurrences:
                        next_date = self.add_period(next_date, item["frequency"])
                        continue
                    amount = float(item["amount"] or 0)
                    # V0.4.6: the displayed and calculated recurrence amount must
                    # remain the amount entered by the user. Scenario analysis will
                    # be handled later through explicit scenario rules, not by
                    # silently modifying the recurrence value.
                    events.append({
                        "date": next_date.isoformat(),
                        "name": item["name"],
                        "category": item["category"] or "Prévisionnel",
                        "amount": amount,
                        "source": "Récurrence",
                        "account": item["account_name"] or "Compte",
                        "account_id": item["account_id"],
                        "recurring_id": item["id"],
                        "scenario": item["scenario"],
                    })
                next_date = self.add_period(next_date, item["frequency"])


        # R7.1: connect personalized scenarios to the forecast engine.
        # Built-in prudent/realistic/optimistic recurrence filtering is kept.
        # If the selected scenario matches a custom scenario name, its events
        # are added on top of the reference forecast.
        scenario_name = str(scenario or "").strip()
        built_in_scenarios = {"Prudent", "Réaliste", "Optimiste"}
        if scenario_name and scenario_name not in built_in_scenarios:
            credit_types = {"cash_in", "recurring_income", "loan_start", "asset_sale"}
            debit_types = {"cash_out", "recurring_expense", "loan_payment", "liability_repayment", "investment", "asset_purchase"}
            recurring_frequencies = {
                "once": "Ponctuel",
                "monthly": "Mensuel",
                "yearly": "Annuel",
            }
            with self.connect() as conn:
                scenario_row = conn.execute(
                    "SELECT id, name FROM scenarios WHERE name = ? AND deleted_at IS NULL AND is_active = 1 ORDER BY id LIMIT 1",
                    (scenario_name,),
                ).fetchone()
                scenario_events = []
                if scenario_row:
                    scenario_events = list(
                        conn.execute(
                            """
                            SELECT e.*, a.name AS account_name
                            FROM scenario_events e
                            LEFT JOIN accounts a ON a.id = e.account_id
                            WHERE e.scenario_id = ?
                              AND e.deleted_at IS NULL
                              AND e.is_active = 1
                            ORDER BY e.event_date, e.id
                            """,
                            (scenario_row["id"],),
                        )
                    )
            for event in scenario_events:
                if account_id is not None and event["account_id"] is not None and event["account_id"] != account_id:
                    continue
                current = datetime.strptime(event["event_date"], "%Y-%m-%d").date()
                event_end = datetime.strptime(event["end_date"], "%Y-%m-%d").date() if event["end_date"] else end
                frequency = event["frequency"] or "once"
                duration = int(event["duration_months"] or 0)
                if duration and frequency == "monthly":
                    month = current.month - 1 + max(0, duration - 1)
                    year = current.year + month // 12
                    month = month % 12 + 1
                    limited_end = date(year, month, min(current.day, 28))
                    event_end = min(event_end, limited_end)
                while current <= end and current <= event_end:
                    if current > start:
                        raw_amount = abs(float(event["amount"] or 0))
                        if event["event_type"] in credit_types:
                            amount = raw_amount
                        elif event["event_type"] in debit_types:
                            amount = -raw_amount
                        else:
                            amount = float(event["amount"] or 0)
                        events.append({
                            "date": current.isoformat(),
                            "name": event["label"],
                            "category": "Scénario",
                            "amount": amount,
                            "source": "Scénario",
                            "account": event["account_name"] or "Compte scénario",
                            "account_id": event["account_id"],
                            "recurring_id": None,
                            "scenario": scenario_name,
                        })
                    if frequency == "monthly":
                        current = self.add_period(current, "Mensuel")
                    elif frequency == "yearly":
                        current = self.add_period(current, "Annuel")
                    else:
                        break


        return sorted(events, key=lambda event: (event["date"], event["amount"]))

    def forecast_scenario_presets(self) -> list[dict]:
        """Return the editable assumptions used by the three standard scenarios."""
        presets: list[dict] = []
        for name, defaults in FORECAST_SCENARIO_PRESETS.items():
            income_percent = float(defaults["income_percent"])
            expense_percent = float(defaults["expense_percent"])
            raw_value = self.get_user_preference(f"forecast.scenario.{name}", "")
            if raw_value:
                try:
                    saved = json.loads(raw_value)
                    income_percent = self._forecast_percent(saved.get("income_percent"), income_percent)
                    expense_percent = self._forecast_percent(saved.get("expense_percent"), expense_percent)
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass
            presets.append({
                "name": name,
                "description": defaults["description"],
                "incomePercent": income_percent,
                "expensePercent": expense_percent,
                "color": defaults["color"],
            })
        return presets

    def update_forecast_scenario_preset(
        self,
        scenario: str,
        income_percent: float,
        expense_percent: float,
    ) -> dict:
        """Persist standard-scenario coefficients without changing real transactions."""
        name = str(scenario or "").strip()
        if name not in FORECAST_SCENARIO_PRESETS:
            raise ValueError("Ce scénario standard n’existe pas.")
        income = self._forecast_percent(income_percent, -1)
        expense = self._forecast_percent(expense_percent, -1)
        if income < 0 or expense < 0:
            raise ValueError("Les coefficients doivent être compris entre 0 et 300 %.")
        value = json.dumps(
            {"income_percent": income, "expense_percent": expense},
            ensure_ascii=False,
            sort_keys=True,
        )
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO user_preferences(key, value, scope)
                VALUES (?, ?, 'forecast')
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    scope = excluded.scope,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (f"forecast.scenario.{name}", value),
            )
        self.seal_database_to_encrypted_vault()
        return next(item for item in self.forecast_scenario_presets() if item["name"] == name)

    @staticmethod
    def _forecast_percent(value, default: float) -> float:
        try:
            parsed = round(float(value), 2)
        except (TypeError, ValueError):
            return default
        return parsed if 0 <= parsed <= 300 else default

    def apply_forecast_scenario_preset(self, events: list[dict], scenario: str) -> list[dict]:
        """Adjust only recurrence forecasts; posted and future bank transactions stay exact."""
        presets = {item["name"]: item for item in self.forecast_scenario_presets()}
        preset = presets.get(scenario, presets["Réaliste"])
        adjusted_events: list[dict] = []
        for event in events:
            adjusted = dict(event)
            amount = float(adjusted.get("amount") or 0)
            source = str(adjusted.get("source") or "")
            if source.startswith("Récurrence"):
                percent = (
                    float(preset["incomePercent"])
                    if amount >= 0
                    else float(preset["expensePercent"])
                )
                adjusted["original_amount"] = amount
                adjusted["amount"] = round(amount * percent / 100, 2)
                adjusted["scenario_adjustment_percent"] = percent
            adjusted_events.append(adjusted)
        return adjusted_events

    def cash_forecast(self, start_date: str = "2026-06-23", horizon_days: int = 90, scenario: str = "Réaliste", account_id: int | None = None) -> dict:
        """Daily cash projection for the selected period."""
        if account_id is None:
            starting_cash = float(self.account_summary_at_date(start_date)["liquidites"])
            account_label = "Tous les comptes"
        else:
            accounts = {row["id"]: row for row in self.list_accounts()}
            account = accounts.get(account_id)
            snapshot = self.account_balance_at_date(account_id, start_date)
            if account and snapshot:
                starting_cash = float(snapshot.calculated_balance)
                parts = [account["bank"], account["name"]]
                if account["identifier"]:
                    parts.append(account["identifier"])
                account_label = " — ".join([part for part in parts if part])
            else:
                starting_cash = 0.0
                account_label = "Compte introuvable"
        raw_events = self.forecast_events(start_date, horizon_days, scenario, account_id=account_id)
        if account_id is None:
            # Vue « Tous les comptes » : les comptes archivés ou clos sont exclus du total
            # (comme le solde de départ), pour que la courbe reste cohérente.
            active_ids = {int(row["id"]) for row in self.list_accounts() if row["status"] == "Actif"}
            raw_events = [
                event for event in raw_events
                if event.get("account_id") is None or int(event["account_id"]) in active_ids
            ]
        events = self.apply_forecast_scenario_preset(raw_events, scenario)
        start = datetime.strptime(start_date, "%Y-%m-%d").date()

        events_by_day: dict[str, list[dict]] = {}
        for event in events:
            events_by_day.setdefault(event["date"], []).append(event)

        labels: list[str] = []
        balances: list[float] = []
        daily_points: list[dict] = []
        balance = starting_cash

        for offset in range(horizon_days + 1):
            current_date = start + timedelta(days=offset)
            key = current_date.isoformat()
            day_events = events_by_day.get(key, [])
            day_in = sum(float(event["amount"] or 0) for event in day_events if float(event["amount"] or 0) > 0)
            day_out = abs(sum(float(event["amount"] or 0) for event in day_events if float(event["amount"] or 0) < 0))
            day_net = sum(float(event["amount"] or 0) for event in day_events)
            balance += day_net

            labels.append(current_date.strftime("%d/%m"))
            balances.append(balance)
            daily_points.append({
                "date": key,
                "label": current_date.strftime("%d/%m"),
                "balance": balance,
                "events": day_events,
                "in": day_in,
                "out": day_out,
                "net": day_net,
            })

        min_balance = min(balances) if balances else starting_cash
        end_balance = balances[-1] if balances else starting_cash
        if min_balance < 0:
            alert = "Trésorerie négative sur la période"
            alert_level = "critical"
            alert_detail = "Point bas inférieur à 0 €."
        elif min_balance < 5000:
            alert = "Trésorerie sous le seuil de 5 000 €"
            alert_level = "warning"
            alert_detail = "Point bas inférieur au seuil de vigilance de 5 000 €."
        else:
            alert = "Aucune alerte critique"
            alert_level = "ok"
            alert_detail = "Point bas supérieur ou égal au seuil de vigilance."

        return {
            "starting_cash": starting_cash,
            "end_balance": end_balance,
            "min_balance": min_balance,
            "labels": labels,
            "balances": balances,
            "daily_points": daily_points,
            "events": events,
            "upcoming": [event for event in events if event["date"] >= start_date][:10],
            "total_in": sum(event["amount"] for event in events if event["amount"] > 0),
            "total_out": abs(sum(event["amount"] for event in events if event["amount"] < 0)),
            "alert": alert,
            "alert_level": alert_level,
            "alert_detail": alert_detail,
            "account_label": account_label,
            "account_id": account_id,
        }



    def default_forecast_start_date(self) -> str:
        """Return the most reliable dashboard forecast start date.

        We use the latest calculated date of active liquid accounts. This avoids
        a dashboard curve starting from a hardcoded date and keeps the dashboard
        aligned with the latest imported/entered banking data.
        """
        rows = [
            row for row in self.list_accounts()
            if row["status"] == "Actif" and row["account_type"] in {"Compte courant", "Compte épargne"}
        ]
        dates = [str(row["calculated_date"]) for row in rows if row["calculated_date"]]
        if dates:
            return max(dates)
        return date.today().isoformat()

    @staticmethod
    def sample_forecast_points(labels: list[str], balances: list[float], horizon_days: int) -> tuple[list[str], list[float]]:
        """Keep dashboard chart readable while using real daily forecast data."""
        if not labels or not balances:
            return [], []
        wanted = {0, horizon_days}
        # Weekly landmarks, plus end date.
        for offset in range(7, horizon_days + 1, 7):
            wanted.add(offset)
        indices = [idx for idx in sorted(wanted) if 0 <= idx < len(labels)]
        return [labels[idx] for idx in indices], [balances[idx] for idx in indices]

    def dashboard_forecast_chart(self, horizon_days: int = 60) -> dict:
        """Real dashboard forecast chart derived from the forecast engine.

        The old dashboard used hardcoded optimistic/realistic/prudent curves.
        V0.4.8 routes the dashboard through `cash_forecast()`, which itself
        applies the centralized initial-balance and recurrence business rules.
        """
        start_date = self.default_forecast_start_date()
        series: dict[str, list[float]] = {}
        labels: list[str] = []

        for scenario in ["Optimiste", "Réaliste", "Prudent"]:
            forecast = self.cash_forecast(start_date, horizon_days, scenario)
            sampled_labels, sampled_values = self.sample_forecast_points(
                forecast["labels"],
                forecast["balances"],
                horizon_days,
            )
            if not labels:
                labels = sampled_labels
            series[scenario] = sampled_values

        realistic = self.cash_forecast(start_date, horizon_days, "Réaliste")
        return {
            "start_date": start_date,
            "labels": labels,
            "series": series,
            "alert": realistic["alert"],
            "alert_level": realistic.get("alert_level", "ok"),
            "alert_detail": realistic.get("alert_detail", ""),
            "min_balance": realistic["min_balance"],
            "end_balance": realistic["end_balance"],
            "total_in": realistic["total_in"],
            "total_out": realistic["total_out"],
            "events_count": len(realistic["events"]),
        }


    def is_feature_enabled(self, key: str) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT enabled FROM feature_flags WHERE key = ?", (key,)).fetchone()
        return bool(row["enabled"]) if row else False

    def feature_flags_report(self) -> dict:
        with self.connect() as conn:
            rows = list(conn.execute("SELECT key, enabled, tier, description FROM feature_flags ORDER BY key"))
        return {
            "total_flags": len(rows),
            "premium_flags": sum(1 for row in rows if row["tier"] == "Premium"),
            "enabled_flags": sum(1 for row in rows if int(row["enabled"] or 0) == 1),
            "flags": [dict(row) for row in rows],
        }

    def translation_value(self, locale: str, key: str) -> str:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT value FROM translations WHERE locale = ? AND key = ?",
                (locale, key),
            ).fetchone()
        return row["value"] if row else ""

    def get_user_preference(self, key: str, default: str = "") -> str:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM user_preferences WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def premium_foundation_report(self) -> dict:
        with self.connect() as conn:
            flags = conn.execute("SELECT COUNT(*) AS c FROM feature_flags").fetchone()["c"]
            premium_flags = conn.execute("SELECT COUNT(*) AS c FROM feature_flags WHERE tier = 'Premium'").fetchone()["c"]
            currencies = conn.execute("SELECT COUNT(*) AS c FROM currencies").fetchone()["c"]
            enabled_currencies = conn.execute("SELECT COUNT(*) AS c FROM currencies WHERE enabled = 1").fetchone()["c"]
            translations = conn.execute("SELECT COUNT(*) AS c FROM translations").fetchone()["c"]
            preferences = conn.execute("SELECT COUNT(*) AS c FROM user_preferences").fetchone()["c"]
            audit_events = conn.execute("SELECT COUNT(*) AS c FROM audit_log").fetchone()["c"]
            uuid_tables = {}
            for table in ["accounts", "transactions", "import_batches", "recurring_items", "assets", "asset_values", "budgets", "categories", "scenarios", "scenario_events"]:
                total = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
                with_uuid = conn.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE uuid IS NOT NULL AND uuid <> ''").fetchone()["c"]
                uuid_tables[table] = {"total": total, "with_uuid": with_uuid}

        return {
            "schema_version": self.schema_version(),
            "feature_flags": flags,
            "premium_flags": premium_flags,
            "currencies": currencies,
            "enabled_currencies": enabled_currencies,
            "translations": translations,
            "preferences": preferences,
            "audit_events": audit_events,
            "uuid_tables": uuid_tables,
            "default_currency": self.get_setting("currency", "EUR"),
            "default_locale": self.get_user_preference("locale.default", "fr"),
            "premium_mode": self.get_user_preference("premium.mode", "free"),
            "open_banking_prepared": self.get_user_preference("open_banking.prepared", "false") == "true",
        }

    RECONCILIATION_SETTING_CASTS = {
        "reconciliation.auto_threshold": int,
        "reconciliation.review_threshold": int,
        "reconciliation.ambiguity_min_delta": int,
        "reconciliation.date_tolerance_days": int,
        "reconciliation.amount_tolerance_absolute": float,
        "reconciliation.amount_tolerance_relative": float,
        "reconciliation.label_similarity_minimum": float,
        "reconciliation.same_account_required": lambda value: str(value).strip().casefold() in {"1", "true", "oui", "yes"},
        "reconciliation.same_direction_required": lambda value: str(value).strip().casefold() in {"1", "true", "oui", "yes"},
        "reconciliation.date_weight": int,
        "reconciliation.amount_weight": int,
        "reconciliation.label_weight": int,
        "reconciliation.category_weight": int,
        "reconciliation.counterparty_match_bonus": int,
        "reconciliation.external_reference_match_bonus": int,
    }

    def reconciliation_rules(
        self,
        conn: sqlite3.Connection | None = None,
    ) -> ReconciliationRules:
        defaults = ReconciliationRules()
        if conn is None:
            with self.connect() as owned_conn:
                return self.reconciliation_rules(owned_conn)
        values = {}
        for key, cast in self.RECONCILIATION_SETTING_CASTS.items():
            row = conn.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,),
            ).fetchone()
            field_name = key.removeprefix("reconciliation.")
            values[field_name] = (
                cast(row["value"]) if row is not None
                else getattr(defaults, field_name)
            )
        return ReconciliationRules(**values)

    def set_reconciliation_settings(self, values: dict[str, object]) -> ReconciliationRules:
        """Validate and save a complete rule edit in one SQLite transaction."""
        unknown = sorted(set(values) - set(self.RECONCILIATION_SETTING_CASTS))
        if unknown:
            raise ValueError("Paramètres de rapprochement inconnus : " + ", ".join(unknown))
        with self.connect() as conn:
            current = self.reconciliation_rules(conn).snapshot()
            merged = dict(current)
            for key, raw_value in values.items():
                field_name = key.removeprefix("reconciliation.")
                merged[field_name] = self.RECONCILIATION_SETTING_CASTS[key](raw_value)
            validated = ReconciliationRules(**merged)
            changed = False
            for field_name, normalized in validated.snapshot().items():
                key = f"reconciliation.{field_name}"
                if key not in values:
                    continue
                stored = (
                    "true" if normalized is True
                    else "false" if normalized is False
                    else str(normalized)
                )
                previous = conn.execute(
                    "SELECT value FROM settings WHERE key = ?",
                    (key,),
                ).fetchone()
                if previous is None or str(previous["value"]) != stored:
                    changed = True
                conn.execute(
                    """
                    INSERT INTO settings(key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (key, stored),
                )
            if changed:
                reevaluate_all_transactions(
                    conn,
                    validated,
                    reason="Règles de rapprochement modifiées",
                )
            return validated

    def get_setting(self, key: str, default: str = "") -> str:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        if key in self.RECONCILIATION_SETTING_CASTS:
            self.set_reconciliation_settings({key: value})
            return
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO settings(key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )

    def create_backup(self, target_dir: str | Path | None = None) -> Path:
        """Create an encrypted Valoria backup (.vvb).

        V0.6.0 changes backup format from plain .db to encrypted .vvb.
        """
        target = Path(target_dir) if target_dir else self.backup_dir
        target.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = self.encrypted_backup_path(target, stamp)
        if not self.path.exists():
            raise FileNotFoundError("Base de données introuvable.")
        self.seal_database_to_encrypted_vault()
        self.crypto.encrypt_file(
            self.path,
            backup,
            metadata={
                "kind": "encrypted_backup",
                "source": self.path.name,
                "schema_version": SCHEMA_VERSION,
                "created_by": "Valoria Vision",
            },
        )
        self.set_setting("last_backup_path", str(backup))
        self.set_setting("last_backup_encrypted", "true")
        return backup

    def restore_backup(self, backup_path: str | Path) -> None:
        source = Path(backup_path)
        if not source.exists():
            raise FileNotFoundError(f"Sauvegarde introuvable : {source}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        safety = self.create_backup(self.path.parent / "backups")

        if self.crypto.is_encrypted_file(source):
            self.crypto.decrypt_file(source, self.path)
        else:
            # Legacy support for older .db backups created before V0.6.0.
            shutil.copy2(source, self.path)

        with self.connect() as conn:
            self.apply_migrations(conn)
            self.set_schema_version(conn, SCHEMA_VERSION)

        self.seal_database_to_encrypted_vault()
        self.set_setting("last_restore_source", str(source))
        self.set_setting("pre_restore_backup", str(safety))


    def data_quality_report(self) -> dict:
        """Technical and business consistency report used by Settings > Diagnostic.

        V0.6.0 adds business controls so the user can verify Dashboard,
        expenses and forecast consistency after a recette session.
        """
        with self.connect() as conn:
            orphan_transactions = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM transactions t
                LEFT JOIN accounts a ON a.id = t.account_id
                WHERE a.id IS NULL
                """
            ).fetchone()["c"]
            orphan_imports = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM transactions t
                LEFT JOIN import_batches b ON b.id = t.import_batch_id
                WHERE t.import_batch_id IS NOT NULL AND b.id IS NULL
                """
            ).fetchone()["c"]
            accounts = conn.execute("SELECT COUNT(*) AS c FROM accounts").fetchone()["c"]
            transactions = conn.execute("SELECT COUNT(*) AS c FROM transactions").fetchone()["c"]
            imports = conn.execute("SELECT COUNT(*) AS c FROM import_batches").fetchone()["c"]
            recurring = conn.execute("SELECT COUNT(*) AS c FROM recurring_items").fetchone()["c"]
            assets = conn.execute("SELECT COUNT(*) AS c FROM assets").fetchone()["c"]
            budgets = conn.execute("SELECT COUNT(*) AS c FROM budgets WHERE deleted_at IS NULL").fetchone()["c"]
            categories_count = conn.execute("SELECT COUNT(*) AS c FROM categories WHERE deleted_at IS NULL").fetchone()["c"]
            current_month = self.get_setting("current_month", "2026-06")
            tx_rows = list(
                conn.execute(
                    """
                    SELECT category, amount
                    FROM transactions
                    WHERE tx_date LIKE ?
                    """,
                    (current_month + "%",),
                )
            )
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]

        month_income = round(sum(float(row["amount"] or 0) for row in tx_rows if is_true_income(row["category"], float(row["amount"] or 0))), 2)
        month_expenses = round(abs(sum(float(row["amount"] or 0) for row in tx_rows if is_current_expense(row["category"], float(row["amount"] or 0)))), 2)
        metrics = self.dashboard_metrics()
        dashboard_income = round(float(metrics.get("revenus", 0) or 0), 2)
        dashboard_expenses = round(float(metrics.get("depenses", 0) or 0), 2)
        forecast = self.cash_forecast(self.default_forecast_start_date(), 30, "Réaliste")

        return {
            "accounts": accounts,
            "transactions": transactions,
            "import_batches": imports,
            "recurring_items": recurring,
            "assets": assets,
            "budgets": budgets,
            "categories": categories_count,
            "orphan_transactions": orphan_transactions,
            "orphan_import_links": orphan_imports,
            "schema_version": self.schema_version(),
            "sqlite_integrity": integrity,
            "current_month": current_month,
            "dashboard_revenues": dashboard_income,
            "month_revenues_from_transactions": month_income,
            "revenues_gap": round(dashboard_income - month_income, 2),
            "dashboard_expenses": dashboard_expenses,
            "month_expenses_from_transactions": month_expenses,
            "expenses_gap": round(dashboard_expenses - month_expenses, 2),
            "forecast_start_date": self.default_forecast_start_date(),
            "forecast_min_balance": round(float(forecast.get("min_balance", 0) or 0), 2),
            "forecast_alert": forecast.get("alert", ""),
            "forecast_alert_level": forecast.get("alert_level", "ok"),
            "db_size_kb": round(self.path.stat().st_size / 1024, 1) if self.path.exists() else 0,
        }

    def security_audit_report(self) -> dict:
        """V0.6.0 security foundation report."""
        report = self.data_quality_report()
        enc = self.database_encryption_status()
        last_backup = self.get_setting("last_backup_path", "")
        return {
            "version": "V0.6.8.1",
            "base_reference": "V0.4.21 validée",
            "sqlite_file": str(self.path),
            "sqlite_exists": self.path.exists(),
            "sqlite_size_kb": round(self.path.stat().st_size / 1024, 1) if self.path.exists() else 0,
            "encrypted_vault_exists": enc["encrypted_vault_exists"],
            "encrypted_vault_path": enc["encrypted_vault_path"],
            "sqlite_encrypted": enc["encrypted_vault_exists"],
            "backups_encrypted": last_backup.endswith(".vvb") or self.get_setting("last_backup_encrypted", "false") == "true",
            "last_backup_path": last_backup,
            "master_password_enabled": self.get_setting("security.master_password_enabled", "false") == "true",
            "master_password_algorithm": self.get_setting("security.master_password_algorithm", ""),
            "session_timeout_minutes": self.get_setting("security.session_timeout_minutes", "10"),
            "crypto_available": enc["crypto_available"],
            "key_storage": enc["key_storage"],
            "go_no_go_beta": "GO technique sécurité locale initiale : base/sauvegardes chiffrées et mot de passe maître activable. À compléter par tests utilisateur avant bêta.",
            "sensitive_tables": [
                "accounts", "transactions", "recurring_items", "assets",
                "asset_values", "import_batches", "settings",
            ],
            "counts": {
                "accounts": report.get("accounts", 0),
                "transactions": report.get("transactions", 0),
                "recurring_items": report.get("recurring_items", 0),
                "assets": report.get("assets", 0),
                "import_batches": report.get("import_batches", 0),
            },
            "next_actions": [
                "Tester création du mot de passe maître.",
                "Tester verrouillage manuel et verrouillage après inactivité.",
                "Préparer dérivation de clé depuis mot de passe maître.",
                "Préparer keyring/coffre OS pour futurs secrets Open Banking.",
            ],
        }

