from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

_PATCHED = False

CONFIG_TABLES = [
    "settings",
    "schema_meta",
    "categories",
    "categorization_rules",
    "scenarios",
    "scenario_events",
    "feature_flags",
    "currencies",
    "translations",
    "budgets",
    "recurring_items",
]
BUSINESS_TABLES = [
    "accounts",
    "transactions",
    "import_batches",
    "assets",
    "asset_values",
    "forecast_occurrences",
]


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table,)).fetchone()
    return row is not None


def _table_count(conn: sqlite3.Connection, table: str) -> int | None:
    if not _table_exists(conn, table):
        return None
    return int(conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()[0] or 0)


def _manifest_from_connection(conn: sqlite3.Connection) -> dict[str, Any]:
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    config = {table: _table_count(conn, table) for table in CONFIG_TABLES}
    business = {table: _table_count(conn, table) for table in BUSINESS_TABLES}
    missing = [table for table, count in config.items() if count is None]
    if integrity != "ok":
        raise RuntimeError(f"La sauvegarde SQLite n'est pas saine : {integrity}")
    if missing:
        raise RuntimeError("Tables de configuration absentes de la sauvegarde : " + ", ".join(missing))
    return {
        "format": "ValoriaVisionCompleteEncryptedBackup",
        "version": 4,
        "kind": "complete_database_backup_memory_snapshot",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "sqlite_integrity": integrity,
        "configuration_tables": config,
        "business_tables": business,
        "restores_settings": True,
        "restores_categories": True,
        "restores_rules": True,
        "restores_scenarios": True,
        "restores_recurring_items": True,
    }


def _sqlite_database_bytes_without_temp_file(source_path: Path) -> tuple[bytes, dict[str, Any]]:
    """Create a consistent SQLite image without writing a snapshot .db file.

    This avoids WinError 32 on Windows/OneDrive/antivirus, because no temporary
    SQLite file has to be reopened by the crypto layer.
    """
    source_conn = sqlite3.connect(source_path, timeout=30)
    memory_conn = sqlite3.connect(":memory:")
    try:
        source_conn.execute("PRAGMA wal_checkpoint(FULL)")
    except Exception:
        pass
    try:
        source_conn.backup(memory_conn)
        memory_conn.commit()
        manifest = _manifest_from_connection(memory_conn)
        try:
            payload = memory_conn.serialize()
        except AttributeError as exc:
            raise RuntimeError(
                "Cette version de Python ne permet pas la sauvegarde SQLite en mémoire. "
                "Utilisez le build GitHub Actions ou une version Python compatible."
            ) from exc
        if not payload:
            raise RuntimeError("La sauvegarde SQLite en mémoire est vide.")
        return payload, manifest
    finally:
        memory_conn.close()
        source_conn.close()


def _validate_sqlite_bytes(payload: bytes) -> dict[str, Any]:
    conn = sqlite3.connect(":memory:")
    try:
        try:
            conn.deserialize(payload)
        except AttributeError as exc:
            raise RuntimeError("Cette version de Python ne permet pas de contrôler la sauvegarde en mémoire.") from exc
        return _manifest_from_connection(conn)
    finally:
        conn.close()


def _read_history(db) -> list[str]:
    raw = db.get_setting("backup_history", "[]") or "[]"
    try:
        values = json.loads(raw)
    except Exception:
        values = []
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if value]


def _write_history(db, path: Path) -> None:
    normalized = str(path)
    history = [item for item in _read_history(db) if item != normalized]
    history.insert(0, normalized)
    db.set_setting("backup_history", json.dumps(history[:20], ensure_ascii=False))


def _refresh_settings_after_restore(page: Any) -> None:
    """Refresh all Settings tabs, including embedded pages such as rules."""
    try:
        page.report = page.db.data_quality_report()
        page.security = page.db.security_audit_report()
        page.premium = page.db.premium_foundation_report()
        page.status = page.compute_status()

        page.populate_overview_tab()
        page.populate_backup_tab()
        page.populate_security_tab()
        page.populate_diagnostic_tab()
        page.populate_business_tab()
        page.populate_maintenance_tab()
        page.populate_categories_tab()

        # Embedded pages keep their own widgets and do not get rebuilt by
        # SettingsPage.refresh(). Force them to reload after restore.
        rules = getattr(page, "rules_tab", None)
        for method_name in ("refresh", "load_rules", "reload", "populate"):
            method = getattr(rules, method_name, None)
            if callable(method):
                try:
                    method()
                    break
                except Exception:
                    pass

        try:
            page.tabs.setCurrentWidget(page.backup_tab)
        except Exception:
            pass
        if getattr(page, "drawer_visible", False):
            page.close_drawer()
    except Exception:
        try:
            page.refresh()
        except Exception:
            pass


def apply_r7_2_backup_memory_snapshot_patch() -> None:
    """Lot 5.3.4 — backup without temporary SQLite file and stronger UI refresh."""
    global _PATCHED
    if _PATCHED:
        return

    from app.database import BACKUP_DIR, SCHEMA_VERSION, Database

    def create_complete_backup_memory(self: Database, target_path: str | Path | None = None) -> Path:
        if not self.path.exists():
            raise RuntimeError("Aucune base Valoria Vision active à sauvegarder.")

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = Path(target_path) if target_path else BACKUP_DIR / f"valoria_vision_backup_complete_{stamp}.vvb"
        if target.suffix.lower() != ".vvb":
            target = target.with_suffix(".vvb")
        target.parent.mkdir(parents=True, exist_ok=True)

        payload, manifest = _sqlite_database_bytes_without_temp_file(self.path)
        manifest["schema_version"] = SCHEMA_VERSION
        encrypted = self.crypto.encrypt_bytes(payload, manifest)
        target.write_bytes(encrypted)

        self.set_setting("last_backup_path", str(target))
        self.set_setting("last_backup_encrypted", "true")
        self.set_setting("last_backup_completed_at", datetime.now().isoformat(timespec="seconds"))
        _write_history(self, target)
        self.seal_database_to_encrypted_vault()
        return target

    def restore_complete_backup_memory(self: Database, source_path: str | Path) -> Path:
        source = Path(source_path)
        if not source.exists():
            raise RuntimeError(f"Sauvegarde introuvable : {source}")

        payload = self.crypto.decrypt_bytes(source.read_bytes())
        _validate_sqlite_bytes(payload)

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if self.path.exists():
            rollback = BACKUP_DIR / f"valoria_vision_before_restore_{stamp}.db"
            rollback.write_bytes(self.path.read_bytes())

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(payload)

        with self.connect() as conn:
            self.create_schema(conn)
            self.apply_migrations(conn)
            self.set_schema_version(conn, SCHEMA_VERSION)
        self.set_setting("last_restore_source", str(source))
        self.set_setting("last_restore_completed_at", datetime.now().isoformat(timespec="seconds"))
        self.set_setting("last_backup_path", str(source))
        self.set_setting("last_backup_encrypted", "true")
        _write_history(self, source)
        self.seal_database_to_encrypted_vault()
        return self.path

    Database.create_complete_encrypted_backup = create_complete_backup_memory
    Database.restore_complete_encrypted_backup = restore_complete_backup_memory
    Database.create_encrypted_backup = create_complete_backup_memory
    Database.restore_encrypted_backup = restore_complete_backup_memory
    Database.backup_encrypted = create_complete_backup_memory
    Database.restore_backup_encrypted = restore_complete_backup_memory

    try:
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from app.ui.settings_page import SettingsPage

        def create_backup_ui(self: SettingsPage) -> None:
            default_name = f"valoria_vision_backup_complete_{datetime.now().strftime('%Y%m%d_%H%M%S')}.vvb"
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Créer une sauvegarde chiffrée complète",
                str(BACKUP_DIR / default_name),
                "Sauvegarde Valoria chiffrée (*.vvb)",
            )
            if not path:
                return
            try:
                output = self.db.create_complete_encrypted_backup(Path(path))
                _refresh_settings_after_restore(self)
                QMessageBox.information(
                    self,
                    "Sauvegarde créée",
                    "Sauvegarde chiffrée complète créée avec succès.\n\n"
                    f"Fichier : {output}\n\n"
                    "La liste des dernières sauvegardes a été mise à jour immédiatement.",
                )
            except Exception as exc:
                QMessageBox.critical(self, "Erreur de sauvegarde", str(exc))

        def restore_backup_ui(self: SettingsPage) -> None:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Restaurer une sauvegarde chiffrée complète",
                str(BACKUP_DIR),
                "Sauvegarde Valoria chiffrée (*.vvb)",
            )
            if not path:
                return
            answer = QMessageBox.question(
                self,
                "Restaurer la sauvegarde",
                "La restauration va remplacer la base locale actuelle par la sauvegarde sélectionnée.\n\n"
                "Une copie de sécurité de la base actuelle sera créée avant remplacement.\n\n"
                "Continuer ?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            try:
                self.db.restore_complete_encrypted_backup(Path(path))
                _refresh_settings_after_restore(self)
                QMessageBox.information(
                    self,
                    "Sauvegarde restaurée",
                    "Sauvegarde chiffrée complète restaurée avec succès.\n\n"
                    "Les onglets Sauvegarde, Règles auto, Catégories et Paramètres ont été rafraîchis.",
                )
            except Exception as exc:
                QMessageBox.critical(self, "Erreur de restauration", str(exc))

        SettingsPage.create_backup = create_backup_ui
        SettingsPage.restore_backup = restore_backup_ui
    except Exception:
        pass

    _PATCHED = True
