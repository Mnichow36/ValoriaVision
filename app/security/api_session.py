from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Callable


@dataclass
class _Session:
    expires_at: float


class ApiSessionStore:
    """Keep short-lived API sessions in memory only.

    Raw tokens are returned once to the UI. Only their SHA-256 digest is kept
    by the Python process, and every authenticated request renews the inactivity
    deadline configured by the existing master-password service.
    """

    def __init__(
        self,
        timeout_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.timeout_seconds = max(60, int(timeout_seconds))
        self.clock = clock
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create(self) -> tuple[str, int]:
        token = secrets.token_urlsafe(32)
        now = self.clock()
        with self._lock:
            self._purge_expired(now)
            self._sessions[self._digest(token)] = _Session(
                expires_at=now + self.timeout_seconds
            )
        return token, self.timeout_seconds

    def validate(self, token: str | None, *, touch: bool = True) -> bool:
        if not token:
            return False
        now = self.clock()
        digest = self._digest(token)
        with self._lock:
            self._purge_expired(now)
            session = self._sessions.get(digest)
            if session is None:
                return False
            if touch:
                session.expires_at = now + self.timeout_seconds
            return True

    def revoke(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            self._sessions.pop(self._digest(token), None)

    def _purge_expired(self, now: float) -> None:
        expired = [key for key, value in self._sessions.items() if value.expires_at <= now]
        for key in expired:
            self._sessions.pop(key, None)
