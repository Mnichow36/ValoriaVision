from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from app.security.auth_service import AuthService


class MasterPasswordDialog(QDialog):
    """Setup/unlock dialog for the local master password."""

    def __init__(self, auth: AuthService, mode: str = "unlock", parent=None) -> None:
        super().__init__(parent)
        self.auth = auth
        self.mode = mode
        self.setModal(True)
        self.setMinimumWidth(440)
        self.setWindowTitle("Valoria Vision — Sécurité")
        self.attempts = 0
        self.build()

    def build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(14)

        if self.mode == "setup":
            title = "Créer le mot de passe maître"
            text = (
                "Ce mot de passe protège l’accès à Valoria Vision sur ce poste. "
                "Il ne doit pas être oublié."
            )
        else:
            title = "Déverrouiller Valoria Vision"
            text = "Saisissez le mot de passe maître pour accéder à l’application."

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size:22px; font-weight: bold; color:#0F172A;")
        title_label.setWordWrap(True)

        subtitle = QLabel(text)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color:#64748B;")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Mot de passe maître")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self.try_accept)

        layout.addWidget(title_label)
        layout.addWidget(subtitle)
        layout.addWidget(self.password_input)

        if self.mode == "setup":
            self.confirm_input = QLineEdit()
            self.confirm_input.setPlaceholderText("Confirmer le mot de passe maître")
            self.confirm_input.setEchoMode(QLineEdit.Password)
            self.confirm_input.returnPressed.connect(self.try_accept)
            hint = QLabel("Minimum 8 caractères. Le mot de passe n’est pas stocké, seul son hash salé est conservé.")
            hint.setWordWrap(True)
            hint.setStyleSheet("color:#64748B; font-size:12px;")
            layout.addWidget(self.confirm_input)
            layout.addWidget(hint)
        else:
            self.confirm_input = None

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color:#DC2626; font-weight: bold;")
        layout.addWidget(self.error_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Valider")
        buttons.button(QDialogButtonBox.Cancel).setText("Quitter")
        buttons.accepted.connect(self.try_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def try_accept(self) -> None:
        password = self.password_input.text()

        if self.mode == "setup":
            confirm = self.confirm_input.text() if self.confirm_input else ""
            if password != confirm:
                self.error_label.setText("Les deux mots de passe ne correspondent pas.")
                return
            try:
                self.auth.set_master_password(password)
            except Exception as exc:
                self.error_label.setText(str(exc))
                return
            QMessageBox.information(self, "Sécurité activée", "Le mot de passe maître est activé.")
            self.accept()
            return

        if self.auth.verify_master_password(password):
            self.accept()
            return

        self.attempts += 1
        self.password_input.clear()
        self.error_label.setText("Mot de passe incorrect.")
        if self.attempts >= 5:
            QMessageBox.critical(self, "Accès refusé", "Trop de tentatives incorrectes.")
            self.reject()
