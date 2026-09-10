from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QColorDialog,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.theme import euro_precise, format_date_fr
from app.widgets import Card, KpiCard, PageHeader, primary_button, secondary_button
from app.ui.charts_lab_page import PlotlyChartsLab
from app.ui.categorization_rules_page import CategorizationRulesPage
from app.ui.reconciliation_rules_page import ReconciliationRulesPage



class CategoryDialog(QDialog):
    COLOR_PRESETS = [
        "#2563EB", "#16A34A", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4",
        "#10B981", "#F97316", "#0EA5E9", "#A855F7", "#EC4899", "#64748B",
        "#0F766E", "#84CC16", "#EAB308", "#14B8A6", "#6366F1", "#475569",
    ]

    def __init__(self, parent=None, row: dict | None = None) -> None:
        super().__init__(parent)
        self.row = row or {}
        self.setWindowTitle("Catégorie")
        self.setMinimumWidth(430)
        self.build()

    def build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        title = QLabel("Catégorie")
        title.setStyleSheet("font-size:20px; font-weight: bold;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.name = QLineEdit()
        self.name.setText(str(self.row.get("name", "")))
        self.name.setPlaceholderText("Ex. Scolarité, Animaux, Vacances…")

        self.kind = QComboBox()
        self.kind.addItems(["Dépense", "Revenu", "Neutre", "Investissement", "Épargne"])
        if self.row.get("kind"):
            self.kind.setCurrentText(str(self.row.get("kind")))

        self.direction = QComboBox()
        self.direction.addItems(["Dépense", "Recette", "Neutre"])
        if self.row.get("direction"):
            self.direction.setCurrentText(str(self.row.get("direction")))
        else:
            self.direction.setCurrentText(self.default_direction_for_kind(self.kind.currentText()))

        self.color_value = str(self.row.get("color", "#64748B") or "#64748B")

        self.color_widget = QWidget()
        color_layout = QVBoxLayout(self.color_widget)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setSpacing(8)

        color_top = QHBoxLayout()
        self.color_preview = QPushButton(self.color_value)
        self.color_preview.setCursor(Qt.PointingHandCursor)
        self.color_preview.clicked.connect(self.open_color_dialog)
        self.color_preview.setMinimumHeight(34)
        self.color_preview.setToolTip("Choisir une couleur personnalisée")
        color_top.addWidget(self.color_preview)

        custom_color_btn = secondary_button("Palette système")
        custom_color_btn.clicked.connect(self.open_color_dialog)
        color_top.addWidget(custom_color_btn)
        color_layout.addLayout(color_top)

        palette = QGridLayout()
        palette.setHorizontalSpacing(6)
        palette.setVerticalSpacing(6)
        for index, color in enumerate(self.COLOR_PRESETS):
            btn = QPushButton("")
            btn.setFixedSize(26, 26)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(color)
            btn.setStyleSheet(
                f"QPushButton {{ background:{color}; border:1px solid #CBD5E1; border-radius:13px; }}"
                "QPushButton:hover { border:2px solid #0F172A; }"
            )
            btn.clicked.connect(lambda checked=False, selected=color: self.set_color(selected))
            palette.addWidget(btn, index // 9, index % 9)
        color_layout.addLayout(palette)
        self.update_color_preview()

        self.budget_enabled = QCheckBox("Disponible dans le module Budgets")
        self.budget_enabled.setChecked(bool(int(self.row.get("budget_enabled", 1) or 0)))
        self.kind.currentTextChanged.connect(self.update_direction_from_kind)
        self.direction.currentTextChanged.connect(self.update_budget_default)

        form.addRow("Nom", self.name)
        form.addRow("Type", self.kind)
        form.addRow("Sens", self.direction)
        form.addRow("Couleur", self.color_widget)
        form.addRow("Budget", self.budget_enabled)
        layout.addLayout(form)

        hint = QLabel("Le sens pilote automatiquement le signe des montants saisis manuellement : Recette = montant positif, Dépense = montant négatif. Les catégories Dépense peuvent être proposées dans les budgets.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748B; background:#F8FAFC; border-radius:12px; padding:10px;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Enregistrer")
        buttons.button(QDialogButtonBox.Cancel).setText("Annuler")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.update_budget_default(self.kind.currentText())

    def set_color(self, color: str) -> None:
        if not color:
            return
        self.color_value = color
        self.update_color_preview()

    def update_color_preview(self) -> None:
        self.color_preview.setText(self.color_value)
        self.color_preview.setStyleSheet(
            f"QPushButton {{ background:{self.color_value}; color:white; border:1px solid #CBD5E1; "
            "border-radius:10px; padding:8px 10px; font-weight: bold; }} "
            "QPushButton:hover { border:2px solid #0F172A; }"
        )

    def open_color_dialog(self) -> None:
        color = QColorDialog.getColor(QColor(self.color_value), self, "Choisir une couleur de catégorie")
        if color.isValid():
            self.set_color(color.name())

    def default_direction_for_kind(self, kind: str) -> str:
        if kind == "Revenu":
            return "Recette"
        if kind == "Neutre":
            return "Neutre"
        return "Dépense"

    def update_direction_from_kind(self, kind: str) -> None:
        if not self.row:
            self.direction.setCurrentText(self.default_direction_for_kind(kind))
        self.update_budget_default(self.direction.currentText())

    def update_budget_default(self, direction: str) -> None:
        self.budget_enabled.setEnabled(direction == "Dépense")
        if direction != "Dépense":
            self.budget_enabled.setChecked(False)
        elif not self.row:
            self.budget_enabled.setChecked(True)

    def data(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "kind": self.kind.currentText(),
            "direction": self.direction.currentText(),
            "color": self.color_value or "#64748B",
            "budget_enabled": self.budget_enabled.isChecked(),
        }


class SettingsPage(QWidget):
    """Settings page redesigned in V0.6.0 with tabs and a right detail drawer."""

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.drawer_visible = False
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(16)

        self.report: dict = {}
        self.security: dict = {}
        self.premium: dict = {}
        self.status = "À contrôler"

        self.build()

    def build(self) -> None:
        self.analysis_btn = secondary_button("Analyse de la base")
        self.analysis_btn.clicked.connect(self.open_analysis_drawer)

        self.layout.addWidget(
            PageHeader(
                "Paramètres",
                "Sauvegardes, restauration, sécurité, catégories et contrôle technique",
                [self.analysis_btn],
            )
        )

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.overview_tab = self.make_scroll_tab()
        self.backup_tab = self.make_scroll_tab()
        self.security_tab = self.make_scroll_tab()
        self.diagnostic_tab = self.make_scroll_tab()
        self.business_tab = self.make_scroll_tab()
        self.maintenance_tab = self.make_scroll_tab()
        self.categories_tab = self.make_scroll_tab()
        self.rules_tab = CategorizationRulesPage(self.db)
        self.reconciliation_rules_tab = ReconciliationRulesPage(self.db)
        self.charts_lab_tab = PlotlyChartsLab(self.db)

        self.tabs.addTab(self.overview_tab, "Vue d’ensemble")
        self.tabs.addTab(self.backup_tab, "Sauvegarde")
        self.tabs.addTab(self.security_tab, "Sécurité")
        self.tabs.addTab(self.diagnostic_tab, "Diagnostic")
        self.tabs.addTab(self.business_tab, "Cohérence métier")
        self.tabs.addTab(self.maintenance_tab, "Maintenance")
        self.tabs.addTab(self.categories_tab, "Catégories")
        self.tabs.addTab(self.rules_tab, "Catégorisation")
        self.tabs.addTab(self.reconciliation_rules_tab, "Rapprochements")
        self.tabs.addTab(self.charts_lab_tab, "Charts réels")

        content_layout.addWidget(self.tabs, stretch=1)

        self.drawer = self.build_drawer()
        self.drawer_visible = False
        self.drawer.setVisible(False)
        content_layout.addWidget(self.drawer)

        self.layout.addWidget(content, stretch=1)
        self.refresh()

    def build_actions_card(self) -> Card:
        actions = Card()
        action_layout = QVBoxLayout(actions)
        action_layout.setContentsMargins(22, 22, 22, 22)
        action_layout.setSpacing(12)

        title = QLabel("Sauvegarde chiffrée")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        subtitle = QLabel("Créez une sauvegarde chiffrée .vvb ou restaurez une sauvegarde Valoria.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#64748B;")

        buttons = QHBoxLayout()
        backup_btn = primary_button("Créer une sauvegarde chiffrée maintenant")
        backup_btn.clicked.connect(self.create_backup)
        restore_btn = secondary_button("Restaurer une sauvegarde")
        restore_btn.clicked.connect(self.restore_backup)
        buttons.addWidget(backup_btn)
        buttons.addWidget(restore_btn)

        action_layout.addWidget(title)
        action_layout.addWidget(subtitle)
        action_layout.addLayout(buttons)
        return actions

    def make_scroll_tab(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        page = QWidget()
        page.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 8, 8)
        layout.setSpacing(12)
        scroll.setWidget(page)
        return scroll

    def tab_layout(self, tab: QScrollArea) -> QVBoxLayout:
        return tab.widget().layout()

    def build_drawer(self) -> QFrame:
        drawer = QFrame()
        drawer.setObjectName("SettingsDrawer")
        drawer.setFixedWidth(460)
        drawer.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        drawer.setStyleSheet(
            "QFrame#SettingsDrawer {"
            "background:#FFFFFF;"
            "border:1px solid #E5E7EB;"
            "border-radius:18px;"
            "}"
        )

        layout = QVBoxLayout(drawer)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        self.drawer_title = QLabel("Analyse de la base")
        self.drawer_title.setWordWrap(True)
        self.drawer_title.setStyleSheet("font-size:18px; font-weight: bold; color:#0F172A;")
        close_btn = QPushButton("×")
        close_btn.setFixedSize(34, 34)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton {background:#F8FAFC; border:1px solid #E5E7EB; border-radius:17px; "
            "font-size:20px; font-weight: bold; color:#334155;} "
            "QPushButton:hover {background:#EAF1FF; color:#2563EB;}"
        )
        close_btn.clicked.connect(self.close_drawer)
        header.addWidget(self.drawer_title)
        header.addStretch(1)
        header.addWidget(close_btn)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        content = QWidget()
        content.setStyleSheet("background:transparent;")
        self.drawer_layout = QVBoxLayout(content)
        self.drawer_layout.setContentsMargins(0, 0, 4, 0)
        self.drawer_layout.setSpacing(12)
        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)

        return drawer

    def close_drawer(self) -> None:
        self.drawer_visible = False
        self.drawer.setVisible(False)

    def open_analysis_drawer(self) -> None:
        self.drawer_visible = True
        self.drawer.setVisible(True)
        self.populate_analysis_drawer()

    def open_drawer(self, title: str, content: str) -> None:
        self.drawer_title.setText(title)
        self.clear_layout(self.drawer_layout)

        label = QLabel(content)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setStyleSheet("color:#475569;")
        self.drawer_layout.addWidget(label)
        self.drawer_layout.addStretch(1)

        self.drawer_visible = True
        self.drawer.setVisible(True)

    def refresh(self) -> None:
        self.report = self.db.data_quality_report()
        self.security = self.db.security_audit_report()
        self.premium = self.db.premium_foundation_report()
        self.status = self.compute_status()

        self.refresh_kpis()
        self.populate_overview_tab()
        self.populate_backup_tab()
        self.populate_security_tab()
        self.populate_diagnostic_tab()
        self.populate_business_tab()
        self.populate_maintenance_tab()
        self.populate_categories_tab()
        self.reconciliation_rules_tab.load_rules()

    def compute_status(self) -> str:
        ok = (
            self.report["orphan_transactions"] == 0
            and self.report["orphan_import_links"] == 0
            and self.report["sqlite_integrity"] == "ok"
            and abs(self.report["expenses_gap"]) < 0.01
            and abs(self.report["revenues_gap"]) < 0.01
        )
        return "OK" if ok else "À contrôler"

    def refresh_kpis(self) -> None:
        if getattr(self, "drawer_visible", False) and self.drawer_title.text() == "Analyse de la base":
            self.populate_analysis_drawer()

    def populate_analysis_drawer(self) -> None:
        self.drawer_title.setText("Analyse de la base")
        self.clear_layout(self.drawer_layout)

        cards = [
            KpiCard("Comptes", str(self.report["accounts"]), "En base SQLite", "blue"),
            KpiCard("Transactions", str(self.report["transactions"]), "Opérations enregistrées", "green"),
            KpiCard("Récurrences", str(self.report["recurring_items"]), "Modèles prévisionnels", "purple"),
            KpiCard("Actifs", str(self.report["assets"]), "Patrimoine", "blue"),
            KpiCard("Schéma DB", f"V{self.report['schema_version']}", "Migration active", "blue"),
        ]
        for card in cards:
            self.drawer_layout.addWidget(card)

        report_btn = secondary_button("Voir le rapport complet")
        report_btn.clicked.connect(lambda: self.open_drawer("Rapport complet", self.overview_detail()))
        self.drawer_layout.addWidget(report_btn)
        self.drawer_layout.addStretch(1)

    def populate_overview_tab(self) -> None:
        layout = self.reset_tab(self.overview_tab)

        layout.addWidget(self.summary_card(
            "Vue d’ensemble",
            [
                ("Statut global", self.status),
                ("SQLite", f"{self.report['sqlite_integrity']} — {self.report['db_size_kb']} Ko"),
                ("Schéma", f"V{self.report['schema_version']}"),
                ("Base chiffrée", "Oui" if self.security["sqlite_encrypted"] else "Non"),
                ("Sauvegardes chiffrées", "Oui" if self.security["backups_encrypted"] else "Non"),
                ("Mot de passe maître", "Oui" if self.security["master_password_enabled"] else "Non"),
                ("Mode", self.premium["premium_mode"]),
                ("Devise / Langue", f"{self.premium['default_currency']} / {self.premium['default_locale']}"),
            ],
            "Voir le rapport complet",
            lambda: self.open_drawer("Rapport complet", self.overview_detail()),
        ))

        layout.addWidget(self.summary_card(
            "Résumé cohérence",
            [
                ("Revenus", f"Écart {euro_precise(self.report['revenues_gap'])}"),
                ("Dépenses", f"Écart {euro_precise(self.report['expenses_gap'])}"),
                ("Prévisionnel", self.report["forecast_alert"]),
                ("Point bas J+30", euro_precise(self.report["forecast_min_balance"])),
            ],
            "Voir les contrôles",
            lambda: self.open_drawer("Contrôles de cohérence", self.business_detail()),
        ))
        layout.addStretch(1)

    def populate_backup_tab(self) -> None:
        layout = self.reset_tab(self.backup_tab)

        layout.addWidget(self.action_card(
            "Sauvegarde de la base",
            "Créez une sauvegarde chiffrée .vvb ou restaurez une sauvegarde Valoria. Cette fonction est déplacée ici pour libérer la hauteur de l’écran Paramètres.",
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
        layout.addStretch(1)

    def populate_security_tab(self) -> None:
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

        actions = self.action_card(
            "Actions sécurité",
            "Utilisez ces actions pour contrôler la protection locale des données.",
            [
                ("Créer une sauvegarde chiffrée", self.create_backup),
                ("Restaurer une sauvegarde", self.restore_backup),
                ("Voir le détail sécurité", lambda: self.open_drawer("Audit sécurité", self.security_detail())),
            ],
        )
        layout.addWidget(actions)
        layout.addStretch(1)

    def populate_diagnostic_tab(self) -> None:
        layout = self.reset_tab(self.diagnostic_tab)
        layout.addWidget(self.summary_card(
            "Diagnostic technique",
            [
                ("Intégrité SQLite", self.report["sqlite_integrity"]),
                ("Taille base", f"{self.report['db_size_kb']} Ko"),
                ("Version schéma", f"V{self.report['schema_version']}"),
                ("Transactions sans compte", str(self.report["orphan_transactions"])),
                ("Liens import orphelins", str(self.report["orphan_import_links"])),
                ("Dernière sauvegarde", self.db.get_setting("last_backup_path", "Aucune") or "Aucune"),
            ],
            "Voir le rapport technique",
            lambda: self.open_drawer("Diagnostic technique", self.diagnostic_detail()),
        ))
        layout.addStretch(1)

    def populate_business_tab(self) -> None:
        layout = self.reset_tab(self.business_tab)
        layout.addWidget(self.summary_card(
            "Dashboard / Transactions",
            [
                ("Revenus Dashboard", euro_precise(self.report["dashboard_revenues"])),
                ("Revenus Transactions", euro_precise(self.report["month_revenues_from_transactions"])),
                ("Écart revenus", euro_precise(self.report["revenues_gap"])),
                ("Dépenses Dashboard", euro_precise(self.report["dashboard_expenses"])),
                ("Dépenses Transactions", euro_precise(self.report["month_expenses_from_transactions"])),
                ("Écart dépenses", euro_precise(self.report["expenses_gap"])),
            ],
            "Voir détail métier",
            lambda: self.open_drawer("Cohérence métier", self.business_detail()),
        ))

        layout.addWidget(self.summary_card(
            "Prévisionnel",
            [
                ("Date de départ", format_date_fr(self.report["forecast_start_date"])),
                ("Point bas J+30", euro_precise(self.report["forecast_min_balance"])),
                ("Alerte", self.report["forecast_alert"]),
            ],
            "Voir règles appliquées",
            lambda: self.open_drawer("Prévisionnel — règles", self.forecast_rules_detail()),
        ))
        layout.addStretch(1)

    def populate_maintenance_tab(self) -> None:
        layout = self.reset_tab(self.maintenance_tab)
        layout.addWidget(self.action_card(
            "Maintenance",
            "Actions de sauvegarde, restauration et contrôle. Les opérations lourdes resteront ici pour ne pas encombrer la vue principale.",
            [
                ("Créer une sauvegarde chiffrée", self.create_backup),
                ("Restaurer une sauvegarde", self.restore_backup),
                ("Voir rapport maintenance", lambda: self.open_drawer("Maintenance", self.maintenance_detail())),
            ],
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

    def populate_categories_tab(self) -> None:
        layout = self.reset_tab(self.categories_tab)

        header = Card()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        texts = QVBoxLayout()
        title = QLabel("Gestion des catégories")
        title.setStyleSheet("font-size:18px; font-weight: bold;")
        subtitle = QLabel("Les catégories alimentent les transactions, les récurrences, les budgets et les graphiques.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#64748B;")
        texts.addWidget(title)
        texts.addWidget(subtitle)

        self.add_category_btn = QPushButton("+ Ajouter une catégorie")
        self.add_category_btn.setMinimumWidth(240)
        self.add_category_btn.setMinimumHeight(42)
        self.add_category_btn.setCursor(Qt.PointingHandCursor)
        self.add_category_btn.setStyleSheet(
            "QPushButton {"
            "background:#2563EB;"
            "color:#FFFFFF;"
            "border:1px solid #2563EB;"
            "border-radius:14px;"
            "padding:10px 18px;"
            "font-size:14px;"
            "font-weight: bold;"
            "} "
            "QPushButton:hover {background:#1D4ED8; border-color:#1D4ED8;}"
        )
        self.add_category_btn.clicked.connect(self.open_add_category_dialog)

        top_row.addLayout(texts, 1)
        top_row.addStretch(1)
        top_row.addWidget(self.add_category_btn, 0, Qt.AlignRight | Qt.AlignTop)
        header_layout.addLayout(top_row)

        quick_add_btn = QPushButton("+ Ajouter une catégorie")
        quick_add_btn.setMinimumHeight(38)
        quick_add_btn.setCursor(Qt.PointingHandCursor)
        quick_add_btn.setStyleSheet(
            "QPushButton {"
            "background:#EFF6FF;"
            "color:#1D4ED8;"
            "border:1px solid #BFDBFE;"
            "border-radius:12px;"
            "font-weight: bold;"
            "} "
            "QPushButton:hover {background:#DBEAFE;}"
        )
        quick_add_btn.clicked.connect(self.open_add_category_dialog)
        header_layout.addWidget(quick_add_btn)
        layout.addWidget(header)

        table = QTableWidget(0, 10)
        table.setHorizontalHeaderLabels(["Nom", "Type", "Sens", "Budget", "Tx", "Réc.", "Budgets", "Syst.", "Couleur", "Actions"])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setFocusPolicy(Qt.NoFocus)
        table.setMinimumHeight(620)
        table.setWordWrap(False)
        table.horizontalHeader().setStretchLastSection(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(9, QHeaderView.Fixed)

        rows = self.db.category_usage_summary()
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [
                row["name"],
                row["kind"],
                row.get("direction", ""),
                "Oui" if row["budget_enabled"] else "Non",
                str(row["tx_count"]),
                str(row["recurring_count"]),
                str(row["budget_count"]),
                "Oui" if row["is_system"] else "Non",
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if c in {2, 3, 4, 5, 6, 7}:
                    item.setTextAlignment(Qt.AlignCenter)
                table.setItem(r, c, item)

            color = row.get("color") or "#64748B"
            color_item = QTableWidgetItem(color)
            color_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            color_item.setTextAlignment(Qt.AlignCenter)
            try:
                color_item.setBackground(QColor(color))
            except Exception:
                color_item.setBackground(QColor("#64748B"))
            table.setItem(r, 8, color_item)

            action_box = QWidget()
            action_layout = QHBoxLayout(action_box)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(6)
            edit_btn = QPushButton("Modifier")
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.clicked.connect(lambda checked=False, data=row: self.open_edit_category_dialog(data))
            delete_btn = QPushButton("Supprimer")
            delete_btn.setCursor(Qt.PointingHandCursor)
            delete_btn.clicked.connect(lambda checked=False, data=row: self.delete_category(data))
            action_layout.addWidget(edit_btn)
            action_layout.addWidget(delete_btn)
            table.setCellWidget(r, 9, action_box)

        table.setColumnWidth(1, 90)
        table.setColumnWidth(2, 90)
        table.setColumnWidth(3, 62)
        table.setColumnWidth(4, 48)
        table.setColumnWidth(5, 52)
        table.setColumnWidth(6, 66)
        table.setColumnWidth(7, 54)
        table.setColumnWidth(8, 92)
        table.setColumnWidth(9, 170)
        layout.addWidget(table, stretch=1)

    def open_add_category_dialog(self) -> None:
        dialog = CategoryDialog(self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.data()
            try:
                self.db.add_category(data["name"], data["kind"], data["color"], data["budget_enabled"], data["direction"])
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "Catégorie", str(exc))

    def open_edit_category_dialog(self, row: dict) -> None:
        dialog = CategoryDialog(self, row=row)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.data()
            try:
                self.db.update_category(int(row["id"]), data["name"], data["kind"], data["color"], data["budget_enabled"], data["direction"])
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "Catégorie", str(exc))

    def delete_category(self, row: dict) -> None:
        message = (
            f"Supprimer la catégorie « {row['name']} » ?\n\n"
            "Les transactions et récurrences liées seront replacées en « À catégoriser ».\n"
            "Les budgets liés à cette catégorie seront retirés des budgets actifs."
        )
        answer = QMessageBox.question(self, "Supprimer une catégorie", message)
        if answer != QMessageBox.Yes:
            return
        try:
            self.db.delete_category(int(row["id"]))
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Catégorie", str(exc))

    def summary_card(
        self,
        title: str,
        rows: list[tuple[str, str]],
        button_text: str | None = None,
        callback: Callable | None = None,
    ) -> Card:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size:18px; font-weight: bold; color:#0F172A;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        for i, (label, value) in enumerate(rows):
            left = QLabel(label)
            left.setStyleSheet("color:#64748B; font-weight: bold;")
            left.setWordWrap(True)
            right = QLabel(str(value))
            right.setWordWrap(True)
            right.setTextInteractionFlags(Qt.TextSelectableByMouse)
            right.setStyleSheet("color:#0F172A; font-weight: bold;")
            grid.addWidget(left, i, 0)
            grid.addWidget(right, i, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 2)
        layout.addLayout(grid)

        if button_text and callback:
            btn = secondary_button(button_text)
            btn.clicked.connect(callback)
            layout.addWidget(btn)

        return card

    def action_card(self, title: str, text: str, actions: list[tuple[str, Callable]]) -> Card:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size:18px; font-weight: bold;")
        title_label.setWordWrap(True)
        body = QLabel(text)
        body.setWordWrap(True)
        body.setStyleSheet("color:#64748B;")

        layout.addWidget(title_label)
        layout.addWidget(body)

        for label, callback in actions:
            btn = secondary_button(label)
            btn.clicked.connect(callback)
            layout.addWidget(btn)

        return card

    def reset_tab(self, tab: QScrollArea) -> QVBoxLayout:
        layout = self.tab_layout(tab)
        self.clear_layout(layout)
        return layout

    def clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())

    def overview_detail(self) -> str:
        return (
            f"Statut global : {self.status}\n"
            f"SQLite : {self.report['sqlite_integrity']} — {self.report['db_size_kb']} Ko\n"
            f"Schéma : V{self.report['schema_version']}\n\n"
            f"Base chiffrée : {'Oui' if self.security['sqlite_encrypted'] else 'Non'}\n"
            f"Sauvegardes chiffrées : {'Oui' if self.security['backups_encrypted'] else 'Non'}\n"
            f"Mot de passe maître : {'Oui' if self.security['master_password_enabled'] else 'Non'}\n\n"
            f"Feature flags : {self.premium['feature_flags']}\n"
            f"Devises préparées : {self.premium['currencies']}\n"
            f"Traductions préparées : {self.premium['translations']}\n"
        )

    def security_detail(self) -> str:
        return (
            f"Vault base chiffré : {'Oui' if self.security['sqlite_encrypted'] else 'Non'}\n"
            f"Chemin vault : {self.security.get('encrypted_vault_path', '')}\n"
            f"Sauvegardes chiffrées : {'Oui' if self.security['backups_encrypted'] else 'Non'}\n"
            f"Dernière sauvegarde : {self.security.get('last_backup_path', '') or 'Aucune'}\n"
            f"Clé locale : {self.security['key_storage']}\n"
            f"Mot de passe maître : {'Oui' if self.security['master_password_enabled'] else 'Non'}\n"
            f"Algorithme : {self.security.get('master_password_algorithm', '') or 'Non initialisé'}\n"
            f"Verrouillage session : {self.security.get('session_timeout_minutes', '10')} min\n\n"
            f"Décision : {self.security['go_no_go_beta']}"
        )

    def diagnostic_detail(self) -> str:
        return (
            f"Intégrité SQLite : {self.report['sqlite_integrity']}\n"
            f"Taille base : {self.report['db_size_kb']} Ko\n"
            f"Schéma : V{self.report['schema_version']}\n"
            f"Comptes : {self.report['accounts']}\n"
            f"Transactions : {self.report['transactions']}\n"
            f"Récurrences : {self.report['recurring_items']}\n"
            f"Actifs : {self.report['assets']}\n"
            f"Budgets : {self.report.get('budgets', 0)}\n"
            f"Imports : {self.report['import_batches']}\n"
            f"Transactions sans compte : {self.report['orphan_transactions']}\n"
            f"Liens import orphelins : {self.report['orphan_import_links']}\n"
            f"Dernière sauvegarde : {self.db.get_setting('last_backup_path', 'Aucune') or 'Aucune'}"
        )

    def business_detail(self) -> str:
        return (
            f"Mois contrôlé : {self.report['current_month']}\n\n"
            f"Revenus Dashboard : {euro_precise(self.report['dashboard_revenues'])}\n"
            f"Revenus Transactions : {euro_precise(self.report['month_revenues_from_transactions'])}\n"
            f"Écart revenus : {euro_precise(self.report['revenues_gap'])}\n\n"
            f"Dépenses Dashboard : {euro_precise(self.report['dashboard_expenses'])}\n"
            f"Dépenses Transactions : {euro_precise(self.report['month_expenses_from_transactions'])}\n"
            f"Écart dépenses : {euro_precise(self.report['expenses_gap'])}\n\n"
            f"Prévisionnel — date de départ : {format_date_fr(self.report['forecast_start_date'])}\n"
            f"Point bas J+30 : {euro_precise(self.report['forecast_min_balance'])}\n"
            f"Alerte : {self.report['forecast_alert']}\n"
        )

    def forecast_rules_detail(self) -> str:
        return (
            "Règles principales du prévisionnel :\n\n"
            "1. Le cash de départ est calculé à la date sélectionnée.\n"
            "2. Les transactions réelles et les récurrences de la période sont intégrées.\n"
            "3. Point bas < 0 € : alerte critique.\n"
            "4. Point bas < 5 000 € : vigilance.\n"
            "5. Point bas ≥ 5 000 € : aucune alerte critique.\n"
        )

    def premium_detail(self) -> str:
        lines = [
            f"Feature flags : {self.premium['feature_flags']}",
            f"Flags Premium : {self.premium['premium_flags']}",
            f"Devises préparées : {self.premium['currencies']}",
            f"Devises actives : {self.premium['enabled_currencies']}",
            f"Traductions : {self.premium['translations']}",
            f"Préférences : {self.premium['preferences']}",
            f"Audit events : {self.premium['audit_events']}",
            f"Mode : {self.premium['premium_mode']}",
            f"Devise : {self.premium['default_currency']}",
            f"Langue : {self.premium['default_locale']}",
            f"Open Banking préparé : {'Oui' if self.premium['open_banking_prepared'] else 'Non'}",
            "",
            "État des UUID :",
        ]
        for table, values in self.premium["uuid_tables"].items():
            lines.append(f"- {table} : {values['with_uuid']} / {values['total']}")
        return "\n".join(lines)

    def maintenance_detail(self) -> str:
        return (
            "Maintenance disponible en V0.6.0 :\n\n"
            "- créer une sauvegarde chiffrée ;\n"
            "- restaurer une sauvegarde Valoria ;\n"
            "- consulter l’état technique ;\n"
            "- vérifier les écarts métier ;\n"
            "- consulter le socle Premium.\n\n"
            "Les futures actions de réparation ou nettoyage seront ajoutées dans cet onglet."
        )

    def create_backup(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choisir le dossier de sauvegarde")
        if not directory:
            return
        try:
            backup = self.db.create_backup(Path(directory))
            QMessageBox.information(self, "Sauvegarde chiffrée créée", f"Sauvegarde chiffrée créée :\n{backup}")
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Erreur sauvegarde", str(exc))

    def restore_backup(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une sauvegarde Valoria",
            "",
            "Sauvegarde Valoria (*.vvb);;Ancienne sauvegarde SQLite (*.db);;Tous les fichiers (*.*)",
        )
        if not path:
            return
        confirm = QMessageBox.question(
            self,
            "Restaurer une sauvegarde",
            "Voulez-vous restaurer cette sauvegarde ?\n\nUne sauvegarde de sécurité de la base actuelle sera créée avant restauration.",
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self.db.restore_backup(path)
            QMessageBox.information(
                self,
                "Restauration terminée",
                "La sauvegarde a été restaurée. Les écrans seront recalculés au prochain affichage.",
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Erreur restauration", str(exc))
