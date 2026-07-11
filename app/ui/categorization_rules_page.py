from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.services.categorization_rule_service import CategorizationRuleService
from app.widgets import Card, primary_button, secondary_button


class CategorizationRuleDialog(QDialog):
    def __init__(self, db: Database, parent=None, row=None) -> None:
        super().__init__(parent)
        self.db = db
        self.service = CategorizationRuleService(db)
        self.row = row
        self.setWindowTitle("Modifier la règle" if row else "Nouvelle règle de catégorisation")
        self.resize(620, 560)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name = QLineEdit()
        self.description = QTextEdit()
        self.description.setMaximumHeight(70)
        self.active = QCheckBox("Règle active")
        self.active.setChecked(True)
        self.priority = QSpinBox()
        self.priority.setRange(1, 9999)
        self.priority.setValue(100)

        self.match_field = QComboBox()
        for key, label in CategorizationRuleService.MATCH_FIELDS.items():
            self.match_field.addItem(label, key)

        self.match_operator = QComboBox()
        for key, label in CategorizationRuleService.OPERATORS.items():
            self.match_operator.addItem(label, key)

        self.match_value = QLineEdit()
        self.match_value.setPlaceholderText("Ex. CARREFOUR, EDF, NETFLIX")

        self.transaction_type = QComboBox()
        for value in CategorizationRuleService.TRANSACTION_TYPES:
            self.transaction_type.addItem(value, value)

        self.account = QComboBox()
        self.account.addItem("Tous les comptes", None)
        for acc in self.db.list_accounts():
            self.account.addItem(f"{acc['name']} — {acc['bank']}", acc["id"])

        self.min_amount = QDoubleSpinBox()
        self.min_amount.setRange(0, 100000000)
        self.min_amount.setDecimals(2)
        self.min_amount.setSpecialValueText("Aucun")
        self.min_amount.setSuffix(" €")
        self.max_amount = QDoubleSpinBox()
        self.max_amount.setRange(0, 100000000)
        self.max_amount.setDecimals(2)
        self.max_amount.setSpecialValueText("Aucun")
        self.max_amount.setSuffix(" €")

        self.category = QComboBox()
        for row_cat in self.db.category_usage_summary():
            if not row_cat.get("deleted_at"):
                self.category.addItem(row_cat["name"], row_cat["id"])
        if self.category.count() == 0:
            self.category.addItem("Aucune catégorie disponible", None)

        self.confidence = QSpinBox()
        self.confidence.setRange(1, 100)
        self.confidence.setValue(100)
        self.confidence.setSuffix(" %")

        form.addRow("Nom", self.name)
        form.addRow("Description", self.description)
        form.addRow("Actif", self.active)
        form.addRow("Priorité", self.priority)
        form.addRow("Champ", self.match_field)
        form.addRow("Opérateur", self.match_operator)
        form.addRow("Valeur", self.match_value)
        form.addRow("Type flux", self.transaction_type)
        form.addRow("Compte", self.account)
        form.addRow("Montant min.", self.min_amount)
        form.addRow("Montant max.", self.max_amount)
        form.addRow("Catégorie cible", self.category)
        form.addRow("Confiance", self.confidence)
        layout.addLayout(form)

        hint = QLabel("Les règles actives sont appliquées par priorité croissante lors des imports. La première règle correspondante gagne.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748B;")
        layout.addWidget(hint)

        if row:
            self.populate(row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def populate(self, row) -> None:
        self.name.setText(row["name"] or "")
        self.description.setPlainText(row["description"] or "")
        self.active.setChecked(bool(row["is_active"]))
        self.priority.setValue(int(row["priority"] or 100))
        idx = self.match_field.findData(row["match_field"])
        self.match_field.setCurrentIndex(idx if idx >= 0 else 0)
        idx = self.match_operator.findData(row["match_operator"])
        self.match_operator.setCurrentIndex(idx if idx >= 0 else 0)
        self.match_value.setText(row["match_value"] or "")
        self.transaction_type.setCurrentText(row["transaction_type"] or "Tous")
        if row["account_id"]:
            idx = self.account.findData(row["account_id"])
            if idx >= 0:
                self.account.setCurrentIndex(idx)
        if row["min_amount"] is not None:
            self.min_amount.setValue(float(row["min_amount"]))
        if row["max_amount"] is not None:
            self.max_amount.setValue(float(row["max_amount"]))
        idx = self.category.findData(row["target_category_id"])
        self.category.setCurrentIndex(idx if idx >= 0 else 0)
        self.confidence.setValue(int(row["confidence"] or 100))

    def data(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "description": self.description.toPlainText().strip(),
            "is_active": self.active.isChecked(),
            "priority": int(self.priority.value()),
            "match_field": self.match_field.currentData(),
            "match_operator": self.match_operator.currentData(),
            "match_value": self.match_value.text().strip(),
            "transaction_type": self.transaction_type.currentData(),
            "account_id": self.account.currentData(),
            "min_amount": None if self.min_amount.value() == 0 else float(self.min_amount.value()),
            "max_amount": None if self.max_amount.value() == 0 else float(self.max_amount.value()),
            "target_category_id": self.category.currentData(),
            "confidence": int(self.confidence.value()),
        }


class CategorizationRulesPage(QWidget):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.service = CategorizationRuleService(db)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 12, 8, 8)
        self.layout.setSpacing(12)
        self.build()

    def build(self) -> None:
        header = Card()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        text_box = QVBoxLayout()
        title = QLabel("Règles de catégorisation automatique")
        title.setStyleSheet("font-size:18px; font-weight: bold;")
        subtitle = QLabel("Créez des règles appliquées automatiquement aux transactions importées.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#64748B;")
        text_box.addWidget(title)
        text_box.addWidget(subtitle)
        add_btn = primary_button("+ Nouvelle règle")
        add_btn.clicked.connect(self.add_rule)
        header_layout.addLayout(text_box, 1)
        header_layout.addWidget(add_btn)
        self.layout.addWidget(header)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["Actif", "Priorité", "Nom", "Conditions", "Catégorie cible", "Dernière utilisation", "Applications", "Validité", "Actions"])
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 64)
        self.table.setColumnWidth(1, 74)
        self.table.setColumnWidth(4, 130)
        self.table.setColumnWidth(5, 130)
        self.table.setColumnWidth(6, 96)
        self.table.setColumnWidth(7, 100)
        self.table.setColumnWidth(8, 240)
        self.layout.addWidget(self.table, stretch=1)
        self.refresh()

    def refresh(self) -> None:
        rows = self.service.list_rules()
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            valid = "OK" if row["target_category"] and not row["target_deleted"] else "Catégorie invalide"
            values = [
                "Oui" if row["is_active"] else "Non",
                str(row["priority"]),
                row["name"],
                self.service.rule_summary(row),
                row["target_category"] or "—",
                row["last_used_at"] or "Jamais",
                str(row["usage_count"] or 0),
                valid,
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                if c in {0, 1, 6, 7}:
                    item.setTextAlignment(Qt.AlignCenter)
                if c == 2:
                    item.setData(Qt.UserRole, int(row["id"]))
                self.table.setItem(r, c, item)

            actions = QWidget()
            action_layout = QHBoxLayout(actions)
            action_layout.setContentsMargins(0, 0, 0, 0)
            edit_btn = QPushButton("Modifier")
            toggle_btn = QPushButton("Désactiver" if row["is_active"] else "Activer")
            delete_btn = QPushButton("Supprimer")
            edit_btn.clicked.connect(lambda checked=False, rule_id=int(row["id"]): self.edit_rule(rule_id))
            toggle_btn.clicked.connect(lambda checked=False, rule_id=int(row["id"]), active=not bool(row["is_active"]): self.toggle_rule(rule_id, active))
            delete_btn.clicked.connect(lambda checked=False, rule_id=int(row["id"]): self.delete_rule(rule_id))
            action_layout.addWidget(edit_btn)
            action_layout.addWidget(toggle_btn)
            action_layout.addWidget(delete_btn)
            self.table.setCellWidget(r, 8, actions)

    def selected_rule_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 2)
        return int(item.data(Qt.UserRole)) if item else None

    def add_rule(self) -> None:
        if not self.db.category_names():
            QMessageBox.information(self, "Règle", "Créez d’abord au moins une catégorie.")
            return
        dialog = CategorizationRuleDialog(self.db, self)
        if dialog.exec() == QDialog.Accepted:
            try:
                self.service.create_rule(dialog.data())
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "Règle", str(exc))

    def edit_rule(self, rule_id: int | None = None) -> None:
        rule_id = rule_id or self.selected_rule_id()
        if not rule_id:
            return
        row = self.service.get_rule(rule_id)
        if not row:
            QMessageBox.warning(self, "Règle", "Règle introuvable.")
            return
        dialog = CategorizationRuleDialog(self.db, self, row=row)
        if dialog.exec() == QDialog.Accepted:
            try:
                self.service.update_rule(rule_id, dialog.data())
                self.refresh()
            except Exception as exc:
                QMessageBox.critical(self, "Règle", str(exc))

    def toggle_rule(self, rule_id: int, active: bool) -> None:
        self.service.set_rule_active(rule_id, active)
        self.refresh()

    def delete_rule(self, rule_id: int) -> None:
        if QMessageBox.question(self, "Supprimer la règle", "Supprimer cette règle de catégorisation ?") != QMessageBox.Yes:
            return
        self.service.delete_rule(rule_id)
        self.refresh()
