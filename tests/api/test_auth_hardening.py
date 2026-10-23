from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import HTTPException

from app.api.main import PasswordPayload, create_app
from app.database import Database
from app.security.auth_service import AuthService


def _database(root: str) -> Database:
    database = Database(Path(root) / "valoria.db")
    with database.connect() as conn:
        database.create_schema(conn)
        database.apply_migrations(conn)
    return database


def _route(app, path: str, method: str):
    return next(r.endpoint for r in app.routes if r.path == path and method in r.methods)


class PasswordPolicyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.auth = AuthService(_database(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_rejects_short_common_and_monotone_passwords(self):
        for bad in ("Court1!", "motdepasse123", "abcdefghijkl", "ABCDEFGH1234", "  Espaces12!  "):
            self.assertFalse(self.auth.password_policy(bad).ok, bad)

    def test_accepts_mixed_passwords(self):
        for good in ("MotDePasse123!", "TEST12-secure", "phrase Longue 2026"):
            self.assertTrue(self.auth.password_policy(good).ok, good)


class LockoutTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.database = _database(self.tmp.name)
        self.auth = AuthService(self.database)
        self.auth.set_master_password("MotDePasse123!")

    def tearDown(self):
        self.tmp.cleanup()

    def test_delay_grows_and_is_persisted(self):
        now = 1_000.0
        self.assertEqual(self.auth.register_failure(now), 0)
        self.assertEqual(self.auth.register_failure(now), 0)
        self.assertEqual(self.auth.register_failure(now), 30)
        self.assertEqual(self.auth.lock_remaining_seconds(now + 10), 20)
        self.assertEqual(self.auth.lock_remaining_seconds(now + 31), 0)
        self.assertEqual(self.auth.register_failure(now), 60)
        self.assertEqual(self.auth.register_failure(now), 300)
        self.assertEqual(self.auth.register_failure(now), 900)
        self.assertEqual(self.auth.register_failure(now), 900)
        # un nouveau service sur la même base voit le même état (survit au redémarrage)
        self.assertEqual(AuthService(self.database).failed_attempts(), 7)

    def test_unlock_route_locks_then_refuses_even_the_right_password(self):
        app = create_app(self.database)
        unlock = _route(app, "/api/v1/auth/unlock", "POST")
        bad = PasswordPayload(password="mauvais")
        for _ in range(2):
            with self.assertRaises(HTTPException) as ctx:
                unlock(bad, None)
            self.assertEqual(ctx.exception.status_code, 401)
        with self.assertRaises(HTTPException) as ctx:
            unlock(bad, None)
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("Retry-After", ctx.exception.headers)
        with self.assertRaises(HTTPException) as ctx:
            unlock(PasswordPayload(password="MotDePasse123!"), None)
        self.assertEqual(ctx.exception.status_code, 429)

    def test_success_resets_counter_and_is_journaled(self):
        app = create_app(self.database)
        unlock = _route(app, "/api/v1/auth/unlock", "POST")
        with self.assertRaises(HTTPException):
            unlock(PasswordPayload(password="mauvais"), None)
        result = unlock(PasswordPayload(password="MotDePasse123!"), None)
        self.assertIn("token", result)
        self.assertEqual(self.auth.failed_attempts(), 0)
        types = [e["type"] for e in self.auth.recent_events()]
        self.assertEqual(types[:2], ["auth.unlock_success", "auth.unlock_failure"])
        self.assertIn("auth.setup", types)

    def test_journal_route_needs_a_session_and_never_exposes_secrets(self):
        app = create_app(self.database)
        journal = _route(app, "/api/v1/security/journal", "GET")
        with self.assertRaises(HTTPException) as ctx:
            journal(None, None)
        self.assertEqual(ctx.exception.status_code, 401)
        token = _route(app, "/api/v1/auth/unlock", "POST")(PasswordPayload(password="MotDePasse123!"), None)["token"]
        events = journal(token, None)["events"]
        self.assertTrue(events)
        self.assertNotIn("MotDePasse123", str(events))


if __name__ == "__main__":
    unittest.main()
