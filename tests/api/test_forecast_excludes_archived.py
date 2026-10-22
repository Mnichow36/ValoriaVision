from __future__ import annotations

import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from app.database import Database


def build_database(root: str) -> Database:
    database = Database(Path(root) / "valoria.db")
    with database.connect() as conn:
        database.create_schema(conn)
        database.apply_migrations(conn)
        database.seed_if_empty(conn)
        database.seed_recurring_items(conn)
    return database


class ForecastExcludesArchivedTest(unittest.TestCase):
    def test_archived_account_events_leave_the_global_total_but_stay_selectable(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            today = date.today().isoformat()
            with database.connect() as conn:
                account = conn.execute("SELECT id FROM accounts WHERE status = 'Actif' ORDER BY id LIMIT 1").fetchone()
                account_id = int(account["id"])
                conn.execute(
                    "INSERT INTO transactions (account_id, tx_date, label, amount, category, tx_type) VALUES (?, ?, 'FUTUR TEST', -777, 'Test', 'Débit')",
                    ((account_id), (date.today() + timedelta(days=3)).isoformat()),
                )
            before = database.cash_forecast(today, 10, "Réaliste")
            self.assertTrue(any(e["name"] == "FUTUR TEST" for e in before["events"]))
            database.update_account_status(account_id, "Archivé")
            after = database.cash_forecast(today, 10, "Réaliste")
            self.assertFalse(any(e["name"] == "FUTUR TEST" for e in after["events"]))
            single = database.cash_forecast(today, 10, "Réaliste", account_id=account_id)
            self.assertTrue(any(e["name"] == "FUTUR TEST" for e in single["events"]))


if __name__ == "__main__":
    unittest.main()
