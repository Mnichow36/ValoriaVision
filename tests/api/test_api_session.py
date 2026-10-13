from __future__ import annotations

import unittest

from app.security.api_session import ApiSessionStore


class ApiSessionStoreTest(unittest.TestCase):
    def test_token_is_memory_only_and_expires_after_inactivity(self):
        now = [100.0]
        store = ApiSessionStore(timeout_seconds=60, clock=lambda: now[0])

        token, expires_in = store.create()

        self.assertEqual(expires_in, 60)
        self.assertNotIn(token, store._sessions)
        self.assertTrue(store.validate(token))

        now[0] = 150.0
        self.assertTrue(store.validate(token))
        now[0] = 211.0
        self.assertFalse(store.validate(token))

    def test_revoke_invalidates_session(self):
        store = ApiSessionStore(timeout_seconds=60)
        token, _ = store.create()

        store.revoke(token)

        self.assertFalse(store.validate(token))


if __name__ == "__main__":
    unittest.main()
