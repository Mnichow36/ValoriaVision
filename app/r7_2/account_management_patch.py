from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.theme import euro, format_date_fr
from app.widgets import primary_button, secondary_button

_PATCHED = False


SUPPORTED_COMMON_CURRENCIES = [
    "EUR", "USD", "GBP", "CHF", "PLN", "CAD", "AUD", "JPY", "NOK", "SEK", "DKK"
]


def normalize_iban(value: str | None) -> str:
    """Normalize an IBAN for storage and matching.

    Spaces and separators are removed; letters are uppercased. The result is
    not country-limited: it prepares Valoria Vision for future international
    and multi-currency account handling.
    """
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()


def format_iban(value: str | None) -> str:
    normalized = normalize_iban(value)
    return " ".join(normalized[index:index + 4] for index in range(0, len(normalized), 4))


def iban_checksum_valid(value: str | None) -> bool:
    iban = normalize_iban(value)
    if not re.match(r"^[A-Z]{2}\d{2}[A-Z0-9]{8,30}$", iban):
        return False
    rearranged = iban[4:] + iban[:4]
    numeric = ""
    for char in rearranged:
        if char.isdigit():
            numeric += char
        elif char.isalpha():
            numeric += str(ord(char) - 55)
        else:
            return False
    remainder = 0
    for char in numeric:
        remainder = (remainder * 10 + int(char)) % 97
    return remainder == 1


def normalize_account_number(value: str | None) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def mask_rib(value: Any) -> str:
    text = normalize_account_number(str(value or ""))
    if not text:
        return "—"
    if text.startswith("****"):
        return text
    digits = re.sub(r"\D+", "", text)
    source = digits or re.sub(r"[^A-Za-z0-9]", "", text)
    return f"**** {source[-4:]}" if source else "—"


def mask_iban(value: Any) -> str:
    iban = normalize_iban(str(value or ""))
    if not iban:
        return "—"
    if len(iban) <= 12:
        return mask_rib(iban)
    return f"{iban[:6]}...{iban[-5:]}"


def account_number_from_row(row) -> str:
    if row is None:
        return ""
    try:
        if "account_number" in row.keys():
            return row["account_number"] or ""
    except Exception:
        pass
    try:
        return row["identifier"] or ""
    except Exception:
        return ""


def iban_from_row(row) -> str:
    try:
        if row is not None and "iban" in row.keys():
            return row["iban"] or ""
    except Exception:
        pass
    return ""


def account_display_identifier(row) -> str:
    account_number = account_number_from_row(row)
    iban = iban_from_row(row)
    if account_number:
        return mask_rib(account_number)
    if iban:
        return mask_iban(iban)
    try:
        return mask_rib(row["identifier"])
    except Exception:
        return "—"


def import_matching_identifier(account_number: str, iban: str, legacy_identifier: str = "") -> str:
    """Keep historical `accounts.identifier` useful for existing import code.

    The import matcher still reads `identifier`. We therefore fill it with the
    most discriminating value available without exposing it directly in the UI.
    """
    account_number = normalize_account_number(account_number)
    iban = normalize_iban(iban)
    legacy_identifier = str(legacy_identifier or "").strip()
    return account_number or iban or legacy_identifier


def payload_for_account(data: dict, existing=None, include_balance: bool = True) -> dict:
    payload = dict(data or {})
    existing_identifier = ""
    if existing is not None:
        try:
            existing_identifier = existing["identifier"] or ""
        except Exception:
            existing_identifier = ""
    account_number = normalize_account_number(payload.get("account_number") or payload.get("rib") or payload.get("identifier") or "")
    iban = normalize_iban(payload.get("iban") or "")
    payload["account_number"] = account_number
    payload["iban"] = iban
    payload["identifier"] = import_matching_identifier(account_number, iban, existing_identifier)
    payload["currency"] = (payload.get("currency") or "EUR").strip().upper()
    payload["status"] = payload.get("status") or "Actif"
    if include_balance:
        initial_balance = float(payload.get("initial_balance", payload.get("reference_balance", 0)) or 0)
        initial_date = payload.get("initial_date", payload.get("reference_date"))
        payload["initial_balance"] = initial_balance
        payload["initial_date"] = initial_date
        payload["reference_balance"] = initial_balance
        payload["reference_date"] = initial_date
    return payload


class AccountIdentityDialog(QDialog):
    def __init__(self, parent=None, row=None, include_balance: bool = True) -> None:
        super().__init__(parent)
        self.row = row
        self.include_balance = include_balance
        self.setWindowTitle("Modifier le compte" if row is not None else "Ajouter un compte")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        intro = QLabel(
            "Les informations de compte servent aux imports bancaires. "
            "Les valeurs complètes sont conservées en base, mais masquées dans l’interface."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#64748B;")
        layout.addWidget(intro)

        form = QFormLayout()
        self.name = QLineEdit()
        self.bank = QLineEdit()
        self.account_type = QComboBox()
        self.account_type.addItems(["Compte courant", "Compte épargne", "Compte investissement", "Compte crédit", "Compte espèces", "Autre"])
        self.account_number = QLineEdit()
        self.account_number.setPlaceholderText("N° de compte, RIB partiel ou identifiant bancaire")
        self.iban = QLineEdit()
        self.iban.setPlaceholderText("IBAN international, exemple FR76... / DE... / CH...")
        self.currency = QComboBox()
        self.currency.addItems(SUPPORTED_COMMON_CURRENCIES)
        self.status = QComboBox()
        self.status.addItems(["Actif", "Archivé", "Clos"])

        form.addRow("Nom du compte", self.name)
        form.addRow("Banque", self.bank)
        form.addRow("Type", self.account_type)
        form.addRow("N° de compte / RIB", self.account_number)
        form.addRow("IBAN", self.iban)

        if include_balance:
            self.balance = QDoubleSpinBox()
            self.balance.setRange(-100000000, 100000000)
            self.balance.setDecimals(2)
            self.balance.setSuffix(" €")
            self.reference_date = QDateEdit(QDate.currentDate())
            self.reference_date.setCalendarPopup(True)
            form.addRow("Solde initial", self.balance)
            form.addRow("Date initiale", self.reference_date)
        else:
            locked = QLabel("Géré uniquement par “Mettre à jour le solde initial”.")
            locked.setWordWrap(True)
            locked.setStyleSheet("color:#64748B;")
            form.addRow("Solde initial", locked)

        form.addRow("Devise", self.currency)
        form.addRow("Statut", self.status)
        layout.addLayout(form)

        self.warning = QLabel("")
        self.warning.setWordWrap(True)
        self.warning.setStyleSheet("color:#B45309;")
        layout.addWidget(self.warning)
        self.iban.textChanged.connect(self.update_iban_warning)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if row is not None:
            self.populate(row)

    def populate(self, row) -> None:
        self.name.setText(row["name"] or "")
        self.bank.setText(row["bank"] or "")
        index = self.account_type.findText(row["account_type"] or "")
        self.account_type.setCurrentIndex(index if index >= 0 else 0)
        self.account_number.setText(account_number_from_row(row))
        self.iban.setText(format_iban(iban_from_row(row)))
        currency_index = self.currency.findText((row["currency"] or "EUR").upper())
        if currency_index < 0:
            self.currency.addItem((row["currency"] or "EUR").upper())
            currency_index = self.currency.findText((row["currency"] or "EUR").upper())
        self.currency.setCurrentIndex(currency_index if currency_index >= 0 else 0)
        status_index = self.status.findText(row["status"] or "Actif")
        self.status.setCurrentIndex(status_index if status_index >= 0 else 0)
        if self.include_balance:
            self.balance.setValue(float(row["effective_initial_balance"] if "effective_initial_balance" in row.keys() else row["reference_balance"] or 0))
            date_text = row["effective_initial_date"] if "effective_initial_date" in row.keys() else row["reference_date"]
            self.reference_date.setDate(QDate.fromString(date_text, "yyyy-MM-dd") if date_text else QDate.currentDate())

    def update_iban_warning(self) -> None:
        text = self.iban.text().strip()
        if not text:
            self.warning.setText("")
            return
        if iban_checksum_valid(text):
            self.warning.setText("")
        else:
            self.warning.setText("IBAN à vérifier : la structure ou la clé de contrôle ne semblent pas valides. L’enregistrement reste possible pour les cas d’import incomplets.")

    def validate_and_accept(self) -> None:
        if not self.name.text().strip():
            QMessageBox.warning(self, "Compte", "Le nom du compte est obligatoire.")
            return
        if not self.bank.text().strip():
            QMessageBox.warning(self, "Compte", "La banque est obligatoire.")
            return
        self.accept()

    def data(self) -> dict:
        data = {
            "name": self.name.text().strip() or "Nouveau compte",
            "bank": self.bank.text().strip() or "Banque",
            "account_type": self.account_type.currentText(),
            "account_number": normalize_account_number(self.account_number.text()),
            "iban": normalize_iban(self.iban.text()),
            "currency": self.currency.currentText(),
            "status": self.status.currentText(),
        }
        data["identifier"] = import_matching_identifier(data["account_number"], data["iban"])
        if self.include_balance:
            data.update({
                "initial_balance": float(self.balance.value()),
                "initial_date": self.reference_date.date().toString("yyyy-MM-dd"),
                "reference_balance": float(self.balance.value()),
                "reference_date": self.reference_date.date().toString("yyyy-MM-dd"),
            })
        return data


def apply_r7_2_account_management_patch() -> None:
    """Lot 3 — account identity, international IBAN and controlled edit/delete."""
    global _PATCHED
    if _PATCHED:
        return

    from app.database import Database
    import app.ui.accounts_page as accounts_module
    from app.ui.accounts_page import AccountsPage

    original_apply_migrations = Database.apply_migrations

    def apply_migrations_with_account_identity(self, conn):
        original_apply_migrations(self, conn)
        self.ensure_columns(conn, "accounts", {
            "account_number": "TEXT",
            "iban": "TEXT",
        })
        conn.execute(
            """
            UPDATE accounts
            SET account_number = CASE
                    WHEN account_number IS NULL OR account_number = '' THEN identifier
                    ELSE account_number
                END
            WHERE identifier IS NOT NULL AND identifier <> ''
        """
        )
        conn.execute("UPDATE accounts SET iban = UPPER(REPLACE(COALESCE(iban, ''), ' ', '')) WHERE iban IS NOT NULL")

    def add_account_with_identity(self, data: dict) -> None:
        payload = payload_for_account(data, include_balance=True)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO accounts(
                    name, bank, account_type, identifier, account_number, iban,
                    reference_balance, reference_date, initial_balance, initial_date, currency, status
                )
                VALUES (
                    :name, :bank, :account_type, :identifier, :account_number, :iban,
                    :reference_balance, :reference_date, :initial_balance, :initial_date, :currency, :status
                )
                """,
                payload,
            )
        self.seal_database_to_encrypted_vault()

    def update_account_identity(self, account_id: int, data: dict) -> None:
        existing = None
        with self.connect() as conn:
            existing = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        payload = payload_for_account(data, existing=existing, include_balance=False)
        payload["id"] = account_id
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE accounts
                SET name = :name,
                    bank = :bank,
                    account_type = :account_type,
                    identifier = :identifier,
                    account_number = :account_number,
                    iban = :iban,
                    currency = :currency,
                    status = :status,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """,
                payload,
            )
        self.seal_database_to_encrypted_vault()

    def dependency_counts(self, account_id: int) -> dict[str, int]:
        checks = {
            "transactions": "SELECT COUNT(*) AS c FROM transactions WHERE account_id = ?",
            "imports": "SELECT COUNT(*) AS c FROM import_batches WHERE account_id = ?",
            "recurrences": "SELECT COUNT(*) AS c FROM recurring_items WHERE account_id = ?",
            "occurrences": "SELECT COUNT(*) AS c FROM forecast_occurrences WHERE account_id = ?",
        }
        counts: dict[str, int] = {}
        with self.connect() as conn:
            for key, sql in checks.items():
                try:
                    counts[key] = int(conn.execute(sql, (account_id,)).fetchone()["c"] or 0)
                except Exception:
                    counts[key] = 0
        counts["total"] = sum(counts.values())
        return counts

    def delete_account_if_empty(self, account_id: int) -> tuple[str, dict[str, int]]:
        counts = self.account_dependency_counts(account_id)
        if counts["total"] > 0:
            return "blocked", counts
        with self.connect() as conn:
            conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        self.seal_database_to_encrypted_vault()
        return "deleted", counts

    def archive_account(self, account_id: int) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE accounts SET status = 'Archivé', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (account_id,))
        self.seal_database_to_encrypted_vault()

    Database.apply_migrations = apply_migrations_with_account_identity
    Database.add_account = add_account_with_identity
    Database.update_account_identity = update_account_identity
    Database.update_account = update_account_identity
    Database.account_dependency_counts = dependency_counts
    Database.delete_account_if_empty = delete_account_if_empty
    Database.archive_account = archive_account

    accounts_module.AccountDialog = AccountIdentityDialog

    original_build_detail_panel = AccountsPage.build_detail_panel
    original_refresh = AccountsPage.refresh

    def build_detail_panel_with_account_actions(self):
        panel = original_build_detail_panel(self)
        layout = panel.layout()
        self.edit_account_btn = secondary_button("Modifier le compte")
        self.edit_account_btn.clicked.connect(self.open_edit_account_dialog)
        self.delete_account_btn = secondary_button("Supprimer / archiver")
        self.delete_account_btn.clicked.connect(self.delete_or_archive_selected_account)
        insert_at = max(0, layout.count() - 1)
        layout.insertWidget(insert_at, self.edit_account_btn)
        layout.insertWidget(insert_at + 1, self.delete_account_btn)
        return panel

    def refresh_with_account_identity(self):
        original_refresh(self)
        if hasattr(self, "table"):
            self.table.setHorizontalHeaderLabels(["Compte", "Banque", "Type", "N° / IBAN", "Solde initial", "Date initiale", "Solde actuel", "Calculé au", "Actions"])
            for row_index, row in enumerate(getattr(self, "account_rows", []) or []):
                item = self.table.item(row_index, 3)
                if item is not None:
                    item.setText(account_display_identifier(row))

    def update_detail_with_account_identity(self) -> None:
        row = self.selected_account()
        if row is None:
            return
        if not getattr(self, "detail_visible", False):
            self.detail_visible = True
            self.apply_detail_panel_state()
        movement = row["post_reference_movements"] or 0
        initial_balance = row["effective_initial_balance"] if "effective_initial_balance" in row.keys() else row["reference_balance"]
        initial_date = row["effective_initial_date"] if "effective_initial_date" in row.keys() else row["reference_date"]
        account_number = account_number_from_row(row)
        iban = iban_from_row(row)
        iban_status = ""
        if iban:
            iban_status = " — IBAN valide" if iban_checksum_valid(iban) else " — IBAN à vérifier"
        self.detail_content.setText(
            f"<b>{row['name']}</b><br>"
            f"Banque : {row['bank']}<br>"
            f"Type : {row['account_type']}<br>"
            f"N° de compte / RIB : {mask_rib(account_number)}<br>"
            f"IBAN : {mask_iban(iban)}{iban_status}<br>"
            f"Devise : {row['currency']}<br>"
            f"Statut : {row['status']}<br><br>"
            f"<b>Solde initial</b><br>"
            f"{euro(initial_balance)} au {format_date_fr(initial_date)}<br><br>"
            f"<b>Solde actuel calculé</b><br>"
            f"{euro(row['calculated_balance'])} au {format_date_fr(row['calculated_date'])}<br>"
            f"Mouvements après solde initial : {euro(movement)}<br><br>"
            f"<b>Association import</b><br>"
            f"Compte reconnu via N° de compte / RIB ou IBAN, valeurs complètes masquées à l’affichage."
        )

    def populate_cards_with_account_identity(self, rows) -> None:
        if not hasattr(self, "cards_grid"):
            return
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for index, row in enumerate(rows):
            from app.widgets import Card
            card = Card()
            card.setMinimumHeight(168)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(16, 14, 16, 14)
            layout.setSpacing(6)
            current_balance = float(row["calculated_balance"] or 0)
            initial_balance = row["effective_initial_balance"] if "effective_initial_balance" in row.keys() else row["reference_balance"]
            initial_date = row["effective_initial_date"] if "effective_initial_date" in row.keys() else row["reference_date"]
            title = QLabel(f"<b>{row['name']}</b><br><span style='color:#64748B'>{row['bank']} — {row['account_type']}</span>")
            title.setWordWrap(True)
            balance = QLabel(euro(current_balance))
            balance.setStyleSheet(f"font-size:24px; font-weight: bold; color:{'#16A34A' if current_balance >= 0 else '#DC2626'};")
            meta = QLabel(
                f"Solde initial : {euro(initial_balance)} au {format_date_fr(initial_date)}<br>"
                f"N° / IBAN : {account_display_identifier(row)}"
            )
            meta.setWordWrap(True)
            meta.setStyleSheet("color:#64748B; font-size:12px;")
            btn = secondary_button("Voir transactions")
            btn.clicked.connect(lambda _checked=False, account_id=row["id"]: self.open_transactions_for_account(account_id))
            layout.addWidget(title)
            layout.addWidget(balance)
            layout.addWidget(meta)
            layout.addStretch(1)
            layout.addWidget(btn)
            self.cards_grid.addWidget(card, index // 3, index % 3)
        if not rows:
            empty = QLabel("Aucun compte ne correspond aux filtres sélectionnés.")
            empty.setStyleSheet("color:#64748B; padding:24px;")
            self.cards_grid.addWidget(empty, 0, 0)

    def open_edit_account_dialog(self) -> None:
        row = self.selected_account()
        if row is None:
            QMessageBox.information(self, "Compte", "Sélectionnez un compte à modifier.")
            return
        dialog = AccountIdentityDialog(self, row=row, include_balance=False)
        if dialog.exec() == QDialog.Accepted:
            self.db.update_account_identity(int(row["id"]), dialog.data())
            QMessageBox.information(self, "Compte", "Compte mis à jour. Le solde initial n’a pas été modifié.")
            self.refresh()

    def delete_or_archive_selected_account(self) -> None:
        row = self.selected_account()
        if row is None:
            QMessageBox.information(self, "Compte", "Sélectionnez un compte.")
            return
        result, counts = self.db.delete_account_if_empty(int(row["id"]))
        if result == "deleted":
            QMessageBox.information(self, "Compte supprimé", "Le compte vide a été supprimé.")
            self.refresh()
            return
        message = (
            "Ce compte contient des données liées. Pour préserver l'historique, il ne peut pas être supprimé directement.\n\n"
            f"Transactions : {counts.get('transactions', 0)}\n"
            f"Imports : {counts.get('imports', 0)}\n"
            f"Récurrences : {counts.get('recurrences', 0)}\n"
            f"Occurrences prévisionnelles : {counts.get('occurrences', 0)}\n\n"
            "Voulez-vous passer ce compte au statut Archivé ?"
        )
        answer = QMessageBox.question(self, "Archiver le compte", message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.db.archive_account(int(row["id"]))
            QMessageBox.information(self, "Compte archivé", "Le compte a été passé au statut Archivé.")
            self.refresh()

    AccountsPage.build_detail_panel = build_detail_panel_with_account_actions
    AccountsPage.refresh = refresh_with_account_identity
    AccountsPage.update_detail = update_detail_with_account_identity
    AccountsPage.populate_cards = populate_cards_with_account_identity
    AccountsPage.open_edit_account_dialog = open_edit_account_dialog
    AccountsPage.delete_or_archive_selected_account = delete_or_archive_selected_account

    _PATCHED = True
