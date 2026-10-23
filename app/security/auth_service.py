from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import time
from dataclasses import dataclass

PBKDF2_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 390_000
MIN_PASSWORD_LENGTH = 10

# Délai imposé après N échecs consécutifs (secondes). Au-delà du dernier palier,
# le dernier délai s'applique. Le compteur est conservé en base : redémarrer
# l'application ne remet donc pas les essais à zéro.
LOCKOUT_STEPS: tuple[tuple[int, int], ...] = ((3, 30), (4, 60), (5, 300), (6, 900))

COMMON_PASSWORDS = frozenset(
    {
        "password", "password1", "motdepasse", "motdepasse1", "motdepasse123",
        "azerty", "azertyuiop", "azerty123", "qwertyuiop", "qwerty123",
        "123456789", "1234567890", "0123456789", "azertyazerty",
        "valoria", "valoriavision", "valoria123", "bienvenue", "bonjour123",
    }
)


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
        password = password or ""
        if len(password) < MIN_PASSWORD_LENGTH:
            return PasswordCheck(False, f"Le mot de passe doit contenir au moins {MIN_PASSWORD_LENGTH} caractères.")
        if password.strip() != password:
            return PasswordCheck(False, "Le mot de passe ne doit pas commencer ou finir par un espace.")
        if password.lower() in COMMON_PASSWORDS:
            return PasswordCheck(False, "Ce mot de passe est trop courant. Choisissez-en un autre.")
        classes = sum(
            bool(re.search(pattern, password))
            for pattern in (r"[a-zà-öø-ÿ]", r"[A-ZÀ-ÖØ-Þ]", r"\d", r"[^\w\s]|_")
        )
        if classes < 3:
            return PasswordCheck(
                False,
                "Mélangez au moins trois types de caractères : minuscules, majuscules, chiffres, symboles.",
            )
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
        self.reset_failures()
        self.record_event("auth.setup", "Mot de passe maître créé.")

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

    # ------------------------------------------------------------------
    # Protection contre les essais répétés
    # ------------------------------------------------------------------
    def _int_setting(self, key: str) -> int:
        try:
            return int(float(self.db.get_setting(key, "0") or 0))
        except ValueError:
            return 0

    def lock_remaining_seconds(self, now: float | None = None) -> int:
        """Secondes restantes avant qu'un nouvel essai soit accepté (0 = libre)."""
        until = self._int_setting("security.locked_until")
        remaining = until - int(now if now is not None else time.time())
        return max(0, remaining)

    def failed_attempts(self) -> int:
        return self._int_setting("security.failed_attempts")

    def register_failure(self, now: float | None = None) -> int:
        """Enregistre un échec et retourne le délai imposé (0 si aucun)."""
        attempts = self.failed_attempts() + 1
        self.db.set_setting("security.failed_attempts", str(attempts))
        delay = 0
        for threshold, seconds in LOCKOUT_STEPS:
            if attempts >= threshold:
                delay = seconds
        if delay:
            self.db.set_setting(
                "security.locked_until", str(int(now if now is not None else time.time()) + delay)
            )
        return delay

    def reset_failures(self) -> None:
        if self.failed_attempts() or self._int_setting("security.locked_until"):
            self.db.set_setting("security.failed_attempts", "0")
            self.db.set_setting("security.locked_until", "0")

    # ------------------------------------------------------------------
    # Journal de sécurité (table audit_log, entité « security »)
    # ------------------------------------------------------------------
    def record_event(self, event_type: str, message: str, metadata: dict | None = None) -> None:
        try:
            with self.db.connect() as conn:
                self.db.audit_event(conn, event_type, "security", None, message, metadata)
        except Exception:  # le journal ne doit jamais empêcher de se connecter
            pass

    def recent_events(self, limit: int = 30) -> list[dict]:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT event_type, message, created_at
                FROM audit_log
                WHERE entity = 'security'
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(1, min(int(limit), 200)),),
            ).fetchall()
        return [
            {"type": r["event_type"], "message": r["message"], "at": r["created_at"]} for r in rows
        ]

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
