from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

_PATCHED = False


def _format_file_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} Mo"
    return f"{size / 1024:.1f} Ko"


def _format_mtime(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "Date inconnue"


def _read_backup_history(db) -> list[str]:
    raw = db.get_setting("backup_history", "[]") or "[]"
    try:
        values = json.loads(raw)
    except Exception:
        values = []
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if value]


def _write_backup_history(db, path: str) -> None:
    history = _read_backup_history(db)
    normalized = str(path)
    history = [item for item in history if item != normalized]
    history.insert(0, normalized)
    history = history[:20]
    db.set_setting("backup_history", json.dumps(history, ensure_ascii=False))


def apply_r7_2_settings_backup_ux_patch() -> None:
    """Lot 5.3.2 — centralise backup/restore UX in the Backup tab.

    Backup and restore actions must not be duplicated in Security or
    Maintenance. The Backup tab becomes the single place for actions, status and
    recent backup history.
    """
    global _PATCHED
    if _PATCHED:
        return

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QFileDialog, QLabel, QMessageBox, QVBoxLayout

    from app.database import BACKUP_DIR
    from app.ui.settings_page import SettingsPage
    from app.widgets import Card, secondary_button

    def refresh_after_backup_action(self: SettingsPage, drawer_title: str | None = None) -> None:
        try:
            self.refresh()
            if drawer_title:
                self.open_drawer(drawer_title, self.security_detail() if "sécurité" in drawer_title.lower() else self.diagnostic_detail())
        except Exception:
            # Refresh must never hide the success of a completed backup/restore.
            pass

    def known_backup_paths(self: SettingsPage) -> list[Path]:
        candidates: list[Path] = []

        # Backups created through Valoria and tracked in settings.
        for value in _read_backup_history(self.db):
            try:
                candidates.append(Path(value))
            except Exception:
                pass

        last_path = self.db.get_setting("last_backup_path", "") or ""
        if last_path:
            try:
                candidates.append(Path(last_path))
            except Exception:
                pass

        # Default internal backup directory.
        try:
            if BACKUP_DIR.exists():
                candidates.extend(BACKUP_DIR.glob("*.vvb"))
        except Exception:
            pass

        dedup: dict[str, Path] = {}
        for path in candidates:
            try:
                if path.exists() and path.suffix.lower() == ".vvb":
                    dedup[str(path.resolve())] = path
            except Exception:
                continue

        return sorted(dedup.values(), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)[:10]

    def backup_history_card(self: SettingsPage) -> Card:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel("Dernières sauvegardes effectuées")
        title.setStyleSheet("font-size:18px; font-weight:bold; color:#0F172A;")
        layout.addWidget(title)

        backups = known_backup_paths(self)
        if not backups:
            empty = QLabel("Aucune sauvegarde chiffrée récente trouvée.")
            empty.setStyleSheet("color:#64748B;")
            empty.setWordWrap(True)
            layout.addWidget(empty)
            return card

        hint = QLabel("Liste des 10 dernières sauvegardes .vvb connues. Pour restaurer, utilisez le bouton “Restaurer une sauvegarde” ci-dessus et choisissez le fichier souhaité.")
        hint.setStyleSheet("color:#64748B;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        for index, path in enumerate(backups, start=1):
            try:
                size = _format_file_size(path.stat().st_size)
            except Exception:
                size = "Taille inconnue"
            row = QLabel(f"{index}. {_format_mtime(path)} — {path.name} — {size}\n{path}")
            row.setWordWrap(True)
            row.setTextInteractionFlags(Qt.TextSelectableByMouse)
            row.setStyleSheet(
                "QLabel { background:#F8FAFC; border:1px solid #E5E7EB; "
                "border-radius:10px; padding:8px; color:#0F172A; }"
            )
            layout.addWidget(row)

        return card

    def create_backup_centralized_ui(self: SettingsPage) -> None:
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
            self.db.set_setting("last_backup_path", str(output))
            self.db.set_setting("last_backup_encrypted", "true")
            _write_backup_history(self.db, str(output))
            QMessageBox.information(
                self,
                "Sauvegarde créée",
                "Sauvegarde chiffrée complète créée avec succès.\n\n"
                f"Fichier : {output}\n\n"
                "Cette sauvegarde inclut les paramètres, catégories, règles, scénarios et données métier.",
            )
            refresh_after_backup_action(self)
            try:
                self.tabs.setCurrentWidget(self.backup_tab)
            except Exception:
                pass
        except Exception as exc:
            QMessageBox.critical(self, "Erreur de sauvegarde", str(exc))

    def restore_backup_centralized_ui(self: SettingsPage) -> None:
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
            self.db.set_setting("last_restore_source", str(path))
            _write_backup_history(self.db, str(path))
            QMessageBox.information(
                self,
                "Sauvegarde restaurée",
                "Sauvegarde chiffrée complète restaurée avec succès.\n\n"
                "Les paramètres, catégories, règles, scénarios et données métier ont été rechargés.",
            )
            refresh_after_backup_action(self)
            try:
                self.tabs.setCurrentWidget(self.backup_tab)
            except Exception:
                pass
        except Exception as exc:
            QMessageBox.critical(self, "Erreur de restauration", str(exc))

    def populate_backup_tab_centralized(self: SettingsPage) -> None:
        layout = self.reset_tab(self.backup_tab)

        layout.addWidget(self.action_card(
            "Sauvegarde de la base",
            "Créez une sauvegarde chiffrée complète .vvb ou restaurez une sauvegarde Valoria. Cet onglet est le seul point d’entrée pour les actions de sauvegarde/restauration.",
            [
                ("Créer une sauvegarde chiffrée maintenant", self.create_backup),
                ("Restaurer une sauvegarde", self.restore_backup),
            ],
        ))

        layout.addWidget(self.summary_card(
            "État sauvegarde",
            [
                ("Dernière sauvegarde", self.db.get_setting("last_backup_path", "Aucune") or "Aucune"),
                ("Sauvegardes chiffrées", "Oui" if self.security["backups_encrypted"] else "Non"),
                ("Base chiffrée", "Oui" if self.security["sqlite_encrypted"] else "Non"),
                ("Taille base", f"{self.report['db_size_kb']} Ko"),
            ],
            "Voir détail sécurité",
            lambda: self.open_drawer("Audit sécurité", self.security_detail()),
        ))

        layout.addWidget(backup_history_card(self))
        layout.addStretch(1)

    def populate_security_tab_without_backup_actions(self: SettingsPage) -> None:
        layout = self.reset_tab(self.security_tab)
        layout.addWidget(self.summary_card(
            "Sécurité locale",
            [
                ("Vault base chiffré", "Oui" if self.security["sqlite_encrypted"] else "Non"),
                ("Sauvegardes chiffrées", "Oui" if self.security["backups_encrypted"] else "Non"),
                ("Clé locale", self.security["key_storage"]),
                ("Mot de passe maître", "Oui" if self.security["master_password_enabled"] else "Non"),
                ("Verrouillage session", f"{self.security.get('session_timeout_minutes', '10')} min"),
                ("Algorithme MDP", self.security.get("master_password_algorithm", "") or "Non initialisé"),
            ],
            "Voir le détail sécurité",
            lambda: self.open_drawer("Audit sécurité", self.security_detail()),
        ))
        layout.addStretch(1)

    def populate_maintenance_tab_without_backup_actions(self: SettingsPage) -> None:
        layout = self.reset_tab(self.maintenance_tab)
        layout.addWidget(self.summary_card(
            "Maintenance",
            [
                ("Intégrité SQLite", self.report["sqlite_integrity"]),
                ("Version schéma", f"V{self.report['schema_version']}"),
                ("Transactions sans compte", str(self.report["orphan_transactions"])),
                ("Liens import orphelins", str(self.report["orphan_import_links"])),
            ],
            "Voir rapport maintenance",
            lambda: self.open_drawer("Maintenance", self.maintenance_detail()),
        ))

        layout.addWidget(self.summary_card(
            "Socle Premium & évolutivité",
            [
                ("Feature flags", f"{self.premium['feature_flags']} dont {self.premium['premium_flags']} Premium"),
                ("Devises préparées", f"{self.premium['currencies']} — actives : {self.premium['enabled_currencies']}"),
                ("Traductions", f"{self.premium['translations']} clés"),
                ("Préférences", str(self.premium["preferences"])),
                ("Audit events", str(self.premium["audit_events"])),
            ],
            "Voir détail Premium",
            lambda: self.open_drawer("Socle Premium & évolutivité", self.premium_detail()),
        ))
        layout.addStretch(1)

    SettingsPage.create_backup = create_backup_centralized_ui
    SettingsPage.restore_backup = restore_backup_centralized_ui
    SettingsPage.populate_backup_tab = populate_backup_tab_centralized
    SettingsPage.populate_security_tab = populate_security_tab_without_backup_actions
    SettingsPage.populate_maintenance_tab = populate_maintenance_tab_without_backup_actions

    _PATCHED = True
