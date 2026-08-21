from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.database import DATA_DIR, Database
from app.widgets import Card, KpiCard, PageHeader, primary_button, secondary_button


@dataclass
class ReportItem:
    path: Path
    kind: str
    module: str
    title: str
    created_label: str
    file_name: str
    account: str = ""
    imported: int = 0
    duplicates: int = 0
    errors: int = 0
    lines: int = 0


class ReportsPage(QWidget):
    """Centralised reports screen.

    Lot 3: first useful version of the Reports menu.
    It centralises generated import audit reports while keeping the module open
    for future business reports: budgets, forecasts, reconciliation, assets and
    exports.
    """

    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.reports_dir = DATA_DIR / "reports" / "imports"
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(28, 24, 28, 24)
        self.layout.setSpacing(16)
        self.build()

    def build(self) -> None:
        refresh_btn = secondary_button("Rafraîchir")
        refresh_btn.clicked.connect(self.refresh)
        open_folder_btn = primary_button("Ouvrir le dossier des rapports")
        open_folder_btn.clicked.connect(lambda: self.open_path(self.reports_dir))
        self.layout.addWidget(
            PageHeader(
                "Rapports",
                "Rapports techniques et métiers générés par Valoria Vision.",
                [refresh_btn, open_folder_btn],
            )
        )

        intro = Card()
        intro_layout = QVBoxLayout(intro)
        intro_layout.setContentsMargins(18, 16, 18, 16)
        title = QLabel("Centre de rapports")
        title.setStyleSheet("font-size:18px; font-weight:bold;")
        text = QLabel(
            "Cet écran centralise progressivement les rapports issus des modules : "
            "imports bancaires, transactions, rapprochements, prévisionnel, budgets, patrimoine et scénarios.\n\n"
            "Première version : consultation des rapports d’import générés automatiquement."
        )
        text.setWordWrap(True)
        text.setStyleSheet("color:#64748B;")
        intro_layout.addWidget(title)
        intro_layout.addWidget(text)
        self.layout.addWidget(intro)

        self.kpi_grid = QGridLayout()
        self.kpi_grid.setSpacing(14)
        self.layout.addLayout(self.kpi_grid)

        section = QLabel("Rapports d’import bancaire")
        section.setStyleSheet("font-size:18px; font-weight:bold; margin-top:4px;")
        self.layout.addWidget(section)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.container = QWidget()
        self.reports_layout = QVBoxLayout(self.container)
        self.reports_layout.setContentsMargins(0, 0, 8, 0)
        self.reports_layout.setSpacing(12)
        self.scroll.setWidget(self.container)
        self.layout.addWidget(self.scroll, stretch=1)
        self.refresh()

    def refresh(self) -> None:
        reports = self.scan_import_reports()
        self.populate_kpis(reports)
        self.populate_reports(reports)

    def populate_kpis(self, reports: list[ReportItem]) -> None:
        while self.kpi_grid.count():
            item = self.kpi_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        total_imported = sum(item.imported for item in reports)
        total_duplicates = sum(item.duplicates for item in reports)
        total_errors = sum(item.errors for item in reports)
        cards = [
            KpiCard("Rapports disponibles", str(len(reports)), "Rapports d’import détectés", "blue"),
            KpiCard("Lignes importées", str(total_imported), "Transactions importées dans les rapports", "green"),
            KpiCard("Doublons", str(total_duplicates), "Doublons signalés", "purple"),
            KpiCard("Erreurs / rejets", str(total_errors), "Lignes non importées", "red"),
        ]
        for col, card in enumerate(cards):
            self.kpi_grid.addWidget(card, 0, col)

    def populate_reports(self, reports: list[ReportItem]) -> None:
        while self.reports_layout.count():
            item = self.reports_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not reports:
            empty = Card()
            layout = QVBoxLayout(empty)
            layout.setContentsMargins(18, 18, 18, 18)
            title = QLabel("Aucun rapport d’import trouvé")
            title.setStyleSheet("font-size:16px; font-weight:bold;")
            text = QLabel(
                "Les prochains rapports d’import générés depuis le module Transactions "
                "apparaîtront ici automatiquement."
            )
            text.setWordWrap(True)
            text.setStyleSheet("color:#64748B;")
            layout.addWidget(title)
            layout.addWidget(text)
            self.reports_layout.addWidget(empty)
            self.reports_layout.addStretch(1)
            return

        for report in reports:
            self.reports_layout.addWidget(self.report_card(report))
        self.reports_layout.addStretch(1)

    def report_card(self, report: ReportItem) -> Card:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(f"<b>{report.title}</b><br><span style='color:#64748B'>{report.created_label}</span>")
        title.setWordWrap(True)
        badge = QLabel(report.kind)
        badge.setStyleSheet(
            "background:#EEF2FF; color:#2563EB; border-radius:10px; padding:6px 10px; font-weight:bold;"
        )
        header.addWidget(title, stretch=1)
        header.addWidget(badge)
        layout.addLayout(header)

        meta = QLabel(
            f"Fichier : {report.file_name}<br>"
            f"Compte : {report.account or '—'}<br>"
            f"Importées : {report.imported}  •  Doublons : {report.duplicates}  •  Erreurs/rejets : {report.errors}  •  Lignes auditées : {report.lines}"
        )
        meta.setWordWrap(True)
        meta.setStyleSheet("color:#475569;")
        layout.addWidget(meta)

        actions = QHBoxLayout()
        open_btn = primary_button("Ouvrir le rapport")
        open_btn.clicked.connect(lambda _checked=False, path=report.path: self.open_path(path))
        folder_btn = secondary_button("Ouvrir le dossier")
        folder_btn.clicked.connect(lambda _checked=False, path=report.path.parent: self.open_path(path))
        actions.addStretch(1)
        actions.addWidget(folder_btn)
        actions.addWidget(open_btn)
        layout.addLayout(actions)
        return card

    def scan_import_reports(self) -> list[ReportItem]:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        reports: list[ReportItem] = []
        for path in sorted(self.reports_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True):
            reports.append(self.parse_import_report(path))
        return reports

    def parse_import_report(self, path: Path) -> ReportItem:
        text = ""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = ""

        file_name = self.extract_value(text, "Fichier") or path.name
        account = self.extract_value(text, "Compte") or self.extract_value(text, "Compte cible")
        imported = self.extract_int(text, "Transactions importées")
        duplicates = self.extract_int(text, "Doublons ignorés") or self.extract_int(text, "Doublons")
        errors = (
            self.extract_int(text, "Erreurs / rejets")
            or self.extract_int(text, "Erreurs")
            or self.extract_int(text, "Lignes rejetées")
        )
        lines = self.extract_int(text, "Lignes auditées")
        created = self.extract_value(text, "Généré le") or self.file_mtime_label(path)
        title = f"Import — {file_name}"
        return ReportItem(
            path=path,
            kind="Import bancaire",
            module="Transactions",
            title=title,
            created_label=created,
            file_name=file_name,
            account=account or "",
            imported=imported,
            duplicates=duplicates,
            errors=errors,
            lines=lines,
        )

    @staticmethod
    def extract_value(text: str, label: str) -> str:
        pattern = re.compile(rf"^\s*{re.escape(label)}\s*:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
        match = pattern.search(text or "")
        return match.group(1).strip() if match else ""

    @staticmethod
    def extract_int(text: str, label: str) -> int:
        value = ReportsPage.extract_value(text, label)
        if not value:
            return 0
        match = re.search(r"-?\d+", value.replace(" ", ""))
        return int(match.group(0)) if match else 0

    @staticmethod
    def file_mtime_label(path: Path) -> str:
        try:
            return path.stat().st_mtime_ns and path.stat().st_mtime and __import__("datetime").datetime.fromtimestamp(path.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
        except Exception:
            return "Date inconnue"

    def open_path(self, path: Path) -> None:
        try:
            target = Path(path)
            if not target.exists():
                QMessageBox.warning(self, "Rapport introuvable", f"Chemin introuvable :\n{target}")
                return
            if sys.platform.startswith("win"):
                os.startfile(str(target))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except Exception as exc:
            QMessageBox.warning(self, "Ouverture impossible", str(exc))
