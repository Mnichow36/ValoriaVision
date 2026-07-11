from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 390_000
MIN_PASSWORD_LENGTH = 8


@dataclass
class PasswordCheck:
    ok: bool
    message: str


class AuthService:
    """Master password service for Valoria Vision V0.6.0.

    The master password is not stored. Only a salted PBKDF2 hash is stored in
    the local settings table. In a later version, this password can be used to
    derive the database encryption key directly.
    """

    def __init__(self, db) -> None:
        self.db = db

    def is_configured(self) -> bool:
        return self.db.get_setting("security.master_password_enabled", "false") == "true"

    def password_policy(self, password: str) -> PasswordCheck:
        if len(password or "") < MIN_PASSWORD_LENGTH:
            return PasswordCheck(False, "Le mot de passe doit contenir au moins 8 caractères.")
        if password.strip() != password:
            return PasswordCheck(False, "Le mot de passe ne doit pas commencer ou finir par un espace.")
        return PasswordCheck(True, "OK")

    def _derive(self, password: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> bytes:
        return hashlib.pbkdf2_hmac(
            PBKDF2_ALGORITHM,
            password.encode("utf-8"),
            salt,
            iterations,
        )

    def set_master_password(self, password: str) -> None:
        policy = self.password_policy(password)
        if not policy.ok:
            raise ValueError(policy.message)

        salt = secrets.token_bytes(32)
        digest = self._derive(password, salt)
        self.db.set_setting("security.master_password_enabled", "true")
        self.db.set_setting("security.master_password_algorithm", f"PBKDF2-HMAC-{PBKDF2_ALGORITHM.upper()}")
        self.db.set_setting("security.master_password_iterations", str(PBKDF2_ITERATIONS))
        self.db.set_setting("security.master_password_salt", base64.b64encode(salt).decode("ascii"))
        self.db.set_setting("security.master_password_hash", base64.b64encode(digest).decode("ascii"))
        self.db.set_setting("security.session_timeout_minutes", self.db.get_setting("security.session_timeout_minutes", "10"))

    def verify_master_password(self, password: str) -> bool:
        if not self.is_configured():
            return False
        try:
            iterations = int(self.db.get_setting("security.master_password_iterations", str(PBKDF2_ITERATIONS)))
            salt = base64.b64decode(self.db.get_setting("security.master_password_salt", ""))
            expected = base64.b64decode(self.db.get_setting("security.master_password_hash", ""))
        except Exception:
            return False
        actual = self._derive(password, salt, iterations)
        return hmac.compare_digest(actual, expected)

    def session_timeout_minutes(self) -> int:
        try:
            return max(1, int(self.db.get_setting("security.session_timeout_minutes", "10")))
        except ValueError:
            return 10

    def audit_status(self) -> dict:
        return {
            "master_password_enabled": self.is_configured(),
            "algorithm": self.db.get_setting("security.master_password_algorithm", ""),
            "iterations": self.db.get_setting("security.master_password_iterations", ""),
            "session_timeout_minutes": self.session_timeout_minutes(),
        }
