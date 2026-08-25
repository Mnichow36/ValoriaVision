from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import time
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


def _snapshot_manifest(db_path: Path) -> dict[str, Any]:
    with sqlite3.connect(db_path, timeout=10) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        config = {table: _table_count(conn, table) for table in CONFIG_TABLES}
        business = {
            table: _table_count(conn, table)
            for table in ["accounts", "transactions", "import_batches", "assets", "asset_values", "forecast_occurrences"]
        }
    missing = [table for table, count in config.items() if count is None]
    if integrity != "ok":
        raise RuntimeError(f"La sauvegarde SQLite n'est pas saine : {integrity}")
    if missing:
        raise RuntimeError("Tables de configuration absentes de la sauvegarde : " + ", ".join(missing))
    return {
        "format": "ValoriaVisionCompleteEncryptedBackup",
        "version": 3,
        "kind": "complete_database_backup",
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


def _create_sqlite_snapshot(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()

    source_conn = sqlite3.connect(source, timeout=15)
    target_conn = sqlite3.connect(target, timeout=15)
    try:
        try:
            source_conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass
        source_conn.backup(target_conn)
        target_conn.commit()
    finally:
        target_conn.close()
        source_conn.close()

    # Windows / OneDrive / antivirus can keep a short handle on the freshly
    # created SQLite file. Validate by opening it after the handles are closed.
    last_error: Exception | None = None
    for _ in range(10):
        try:
            with sqlite3.connect(target, timeout=5) as conn:
                conn.execute("PRAGMA integrity_check").fetchone()
            return
        except Exception as exc:  # pragma: no cover - OS timing dependent
            last_error = exc
            time.sleep(0.2)
    if last_error:
        raise RuntimeError(f"Snapshot SQLite temporaire indisponible : {last_error}")


def _read_bytes_with_retry(path: Path) -> bytes:
    last_error: Exception | None = None
    for _ in range(15):
        try:
            return path.read_bytes()
        except OSError as exc:  # WinError 32 on some Windows builds
            last_error = exc
            time.sleep(0.2)
    if last_error:
        raise RuntimeError(
            "Le snapshot temporaire de sauvegarde est encore verrouillé par Windows. "
            "Fermez les fenêtres Valoria Vision ouvertes et réessayez. Détail : " + str(last_error)
        )
    raise RuntimeError("Impossible de lire le snapshot temporaire de sauvegarde.")


def _write_backup_history(db, path: Path) -> None:
    raw = db.get_setting("backup_history", "[]") or "[]"
    try:
        history = json.loads(raw)
    except Exception:
        history = []
    if not isinstance(history, list):
        history = []
    normalized = str(path)
    history = [str(item) for item in history if str(item) != normalized]
    history.insert(0, normalized)
    db.set_setting("backup_history", json.dumps(history[:20], ensure_ascii=False))


def _refresh_settings_page(page, keep_backup_tab: bool = True) -> None:
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
        if keep_backup_tab:
            page.tabs.setCurrentWidget(page.backup_tab)
        if getattr(page, "drawer_visible", False):
            page.close_drawer()
    except Exception:
        try:
            page.refresh()
        except Exception:
            pass


def apply_r7_2_backup_reliability_patch() -> None:
    """Lot 5.3.3 — reliable complete backup on Windows.

    Fixes WinError 32 during creation by reading the validated SQLite snapshot
    with a retry loop and encrypting bytes in memory instead of asking the crypto
    layer to read the temporary file directly.
    """
    global _PATCHED
    if _PATCHED:
        return

    from app.database import BACKUP_DIR, SCHEMA_VERSION, Database

    def create_complete_encrypted_backup_reliable(self: Database, target_path: str | Path | None = None) -> Path:
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
            _create_sqlite_snapshot(self.path, snapshot)
            manifest = _snapshot_manifest(snapshot)
            manifest["schema_version"] = SCHEMA_VERSION
            payload = _read_bytes_with_retry(snapshot)
            encrypted = self.crypto.encrypt_bytes(payload, manifest)
            target.write_bytes(encrypted)

        self.set_setting("last_backup_path", str(target))
        self.set_setting("last_backup_encrypted", "true")
        self.set_setting("last_backup_completed_at", datetime.now().isoformat(timespec="seconds"))
        _write_backup_history(self, target)
        self.seal_database_to_encrypted_vault()
        return target

    def restore_complete_encrypted_backup_reliable(self: Database, source_path: str | Path) -> Path:
        source = Path(source_path)
        if not source.exists():
            raise RuntimeError(f"Sauvegarde introuvable : {source}")

        with tempfile.TemporaryDirectory(prefix="valoria_restore_complete_") as tmp:
            restored = Path(tmp) / "restored_valoria_vision.db"
            self.crypto.decrypt_file(source, restored)
            _snapshot_manifest(restored)

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
        _write_backup_history(self, source)
        self.seal_database_to_encrypted_vault()
        return self.path

    Database.create_complete_encrypted_backup = create_complete_encrypted_backup_reliable
    Database.restore_complete_encrypted_backup = restore_complete_encrypted_backup_reliable
    Database.create_encrypted_backup = create_complete_encrypted_backup_reliable
    Database.restore_encrypted_backup = restore_complete_encrypted_backup_reliable
    Database.backup_encrypted = create_complete_encrypted_backup_reliable
    Database.restore_backup_encrypted = restore_complete_encrypted_backup_reliable

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
                _refresh_settings_page(self)
                QMessageBox.information(
                    self,
                    "Sauvegarde créée",
                    "Sauvegarde chiffrée complète créée avec succès.\n\n"
                    f"Fichier : {output}\n\n"
                    "La liste des dernières sauvegardes a été mise à jour.",
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
                _refresh_settings_page(self)
                QMessageBox.information(
                    self,
                    "Sauvegarde restaurée",
                    "Sauvegarde chiffrée complète restaurée avec succès.\n\n"
                    "L’écran Sauvegarde a été rafraîchi immédiatement.",
                )
            except Exception as exc:
                QMessageBox.critical(self, "Erreur de restauration", str(exc))

        SettingsPage.create_backup = create_backup_ui
        SettingsPage.restore_backup = restore_backup_ui
    except Exception:
        pass

    _PATCHED = True
