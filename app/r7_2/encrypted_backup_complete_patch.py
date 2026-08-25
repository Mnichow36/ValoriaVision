from __future__ import annotations

import shutil
import sqlite3
import tempfile
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

SENSITIVE_TABLES_EXCLUDED: list[str] = []


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _table_count(conn: sqlite3.Connection, table: str) -> int | None:
    if not _table_exists(conn, table):
        return None
    return int(conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()[0] or 0)


def _configuration_manifest(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        tables = {table: _table_count(conn, table) for table in CONFIG_TABLES}
        business_tables = {
            table: _table_count(conn, table)
            for table in [
                "accounts",
                "transactions",
                "import_batches",
                "assets",
                "asset_values",
                "forecast_occurrences",
            ]
        }
    return {
        "format": "ValoriaVisionCompleteEncryptedBackup",
        "version": 2,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "sqlite_integrity": integrity,
        "configuration_tables": tables,
        "business_tables": business_tables,
        "sensitive_tables_excluded": SENSITIVE_TABLES_EXCLUDED,
    }


def _make_sqlite_snapshot(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    source_conn = sqlite3.connect(source)
    try:
        try:
            source_conn.execute("PRAGMA wal_checkpoint(FULL)")
        except Exception:
            pass
        target_conn = sqlite3.connect(target)
        try:
            source_conn.backup(target_conn)
        finally:
            target_conn.close()
    finally:
        source_conn.close()


def _validate_snapshot(path: Path) -> dict[str, Any]:
    manifest = _configuration_manifest(path)
    if manifest["sqlite_integrity"] != "ok":
        raise RuntimeError(f"La sauvegarde SQLite n'est pas saine : {manifest['sqlite_integrity']}")
    missing = [table for table, count in manifest["configuration_tables"].items() if count is None]
    if missing:
        raise RuntimeError("Tables de configuration absentes de la sauvegarde : " + ", ".join(missing))
    return manifest


def _refresh_settings_page(page: Any, drawer_title: str | None = None) -> None:
    """Refresh Settings after backup/restore without requiring app restart."""
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
        if getattr(page, "drawer_visible", False):
            title = drawer_title or page.drawer_title.text()
            if "sécurité" in title.lower() or "securite" in title.lower():
                page.open_drawer("Audit sécurité", page.security_detail())
            elif "diagnostic" in title.lower():
                page.open_drawer("Diagnostic technique", page.diagnostic_detail())
            elif "analyse" in title.lower():
                page.populate_analysis_drawer()
            else:
                page.close_drawer()
    except Exception:
        # Fallback: keep the old broad refresh behavior if a future screen changes.
        try:
            page.refresh()
        except Exception:
            pass


def apply_r7_2_encrypted_backup_complete_patch() -> None:
    """Lot 5.3 — complete encrypted backup/restore for settings and app config."""
    global _PATCHED
    if _PATCHED:
        return

    from app.database import Database, BACKUP_DIR, DATA_DIR, SCHEMA_VERSION

    def create_complete_encrypted_backup(self: Database, target_path: str | Path | None = None) -> Path:
        if not self.path.exists():
            raise RuntimeError("Aucune base Valoria Vision active à sauvegarder.")

        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = Path(target_path) if target_path else BACKUP_DIR / f"valoria_vision_backup_complete_{stamp}.vvb"
        if target.suffix.lower() != ".vvb":
            target = target.with_suffix(".vvb")
        target.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="valoria_backup_complete_") as tmp:
            snapshot = Path(tmp) / "valoria_vision_snapshot.db"
            _make_sqlite_snapshot(self.path, snapshot)
            manifest = _validate_snapshot(snapshot)
            manifest.update({
                "kind": "complete_database_backup",
                "source": self.path.name,
                "schema_version": SCHEMA_VERSION,
                "restores_settings": True,
                "restores_categories": True,
                "restores_rules": True,
                "restores_scenarios": True,
                "restores_recurring_items": True,
            })
            self.crypto.encrypt_file(snapshot, target, metadata=manifest)

        self.set_setting("last_backup_path", str(target))
        self.set_setting("last_backup_encrypted", "true")
        self.set_setting("last_backup_completed_at", datetime.now().isoformat(timespec="seconds"))
        self.seal_database_to_encrypted_vault()
        return target

    def restore_complete_encrypted_backup(self: Database, source_path: str | Path) -> Path:
        source = Path(source_path)
        if not source.exists():
            raise RuntimeError(f"Sauvegarde introuvable : {source}")

        with tempfile.TemporaryDirectory(prefix="valoria_restore_complete_") as tmp:
            restored = Path(tmp) / "restored_valoria_vision.db"
            self.crypto.decrypt_file(source, restored)
            _validate_snapshot(restored)

            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if self.path.exists():
                rollback = BACKUP_DIR / f"valoria_vision_before_restore_{stamp}.db"
                shutil.copy2(self.path, rollback)

            self.path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(restored, self.path)

        with self.connect() as conn:
            self.create_schema(conn)
            self.apply_migrations(conn)
            self.set_schema_version(conn, SCHEMA_VERSION)
        self.set_setting("last_restore_source", str(source))
        self.set_setting("last_restore_completed_at", datetime.now().isoformat(timespec="seconds"))
        self.set_setting("last_backup_path", str(source))
        self.set_setting("last_backup_encrypted", "true")
        self.seal_database_to_encrypted_vault()
        return self.path

    def encrypted_backup_manifest(self: Database, backup_path: str | Path) -> dict[str, Any]:
        source = Path(backup_path)
        with tempfile.TemporaryDirectory(prefix="valoria_backup_manifest_") as tmp:
            restored = Path(tmp) / "inspect.db"
            self.crypto.decrypt_file(source, restored)
            return _validate_snapshot(restored)

    Database.create_complete_encrypted_backup = create_complete_encrypted_backup
    Database.restore_complete_encrypted_backup = restore_complete_encrypted_backup
    Database.encrypted_backup_manifest = encrypted_backup_manifest
    Database.create_encrypted_backup = create_complete_encrypted_backup
    Database.restore_encrypted_backup = restore_complete_encrypted_backup
    Database.backup_encrypted = create_complete_encrypted_backup
    Database.restore_backup_encrypted = restore_complete_encrypted_backup

    try:
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        from app.ui.settings_page import SettingsPage

        def create_backup_complete_ui(self: SettingsPage) -> None:
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
                _refresh_settings_page(self, "Audit sécurité")
                QMessageBox.information(
                    self,
                    "Sauvegarde créée",
                    "Sauvegarde chiffrée complète créée avec succès.\n\n"
                    f"Fichier : {output}\n\n"
                    "L'état sauvegarde et l'audit sécurité ont été rafraîchis.",
                )
            except Exception as exc:
                QMessageBox.critical(self, "Erreur de sauvegarde", str(exc))

        def restore_backup_complete_ui(self: SettingsPage) -> None:
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
                _refresh_settings_page(self, "Audit sécurité")
                QMessageBox.information(
                    self,
                    "Sauvegarde restaurée",
                    "Sauvegarde chiffrée complète restaurée avec succès.\n\n"
                    "Les paramètres, catégories, règles, scénarios et données métier ont été restaurés.\n"
                    "L'écran Paramètres a été rafraîchi immédiatement.",
                )
            except Exception as exc:
                QMessageBox.critical(self, "Erreur de restauration", str(exc))

        SettingsPage.create_backup = create_backup_complete_ui
        SettingsPage.restore_backup = restore_backup_complete_ui
    except Exception:
        pass

    _PATCHED = True
