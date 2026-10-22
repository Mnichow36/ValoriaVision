from __future__ import annotations

import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from fastapi import HTTPException

from app.api.main import ReconciliationCancelPayload, create_app
from app.database import Database
from app.services.accounts_read_service import AccountsReadService
from app.services.forecast_reconciliation_service import ForecastReconciliationService
from app.services.reconciliation_read_service import ReconciliationReadService, display_status
from app.services.transactions_read_service import TransactionsReadService


def build_database(root: str) -> Database:
    database = Database(Path(root) / "valoria.db")
    with database.connect() as conn:
        database.create_schema(conn)
        database.apply_migrations(conn)
        database.seed_if_empty(conn)
        database.seed_recurring_items(conn)
    return database


def make_pair(database: Database, *, expected: float = -100.0, actual: float = -100.0) -> tuple[int, int, int]:
    """Create one real transaction and one forecast occurrence of a recurrence."""
    today = date.today().isoformat()
    with database.connect() as conn:
        account_id = int(conn.execute("SELECT id FROM accounts WHERE status = 'Actif' ORDER BY id LIMIT 1").fetchone()["id"])
        recurring = conn.execute("SELECT id, name FROM recurring_items ORDER BY id LIMIT 1").fetchone()
        tx_id = int(
            conn.execute(
                "INSERT INTO transactions(account_id, tx_date, label, category, amount, tx_type, status, source, signature) "
                "VALUES (?, ?, 'PRELEVEMENT TEST LIEN', 'Logement', ?, 'Débit', 'Validée', 'test', ?)",
                (account_id, today, actual, str(uuid4())),
            ).lastrowid
        )
        occurrence_id = int(
            conn.execute(
                "INSERT INTO forecast_occurrences(uuid, source_type, source_id, account_id, expected_date, "
                "expected_amount, expected_label, expected_category, direction, status) "
                "VALUES (?, 'recurring', ?, ?, ?, ?, 'Loyer test', 'Logement', 'debit', 'planned')",
                (str(uuid4()), recurring["id"], account_id, (date.today() - timedelta(days=1)).isoformat(), expected),
            ).lastrowid
        )
    return account_id, tx_id, occurrence_id


class ReconciliationCancelHistoryTest(unittest.TestCase):
    def test_status_cycle_hides_the_confirmed_status(self):
        self.assertEqual(display_status("confirmed"), "matched")
        self.assertEqual(display_status("auto_matched"), "matched")
        self.assertEqual(display_status("confirmed", remaining=8.0), "amount_gap")
        self.assertEqual(display_status("partially_matched"), "amount_gap")
        self.assertEqual(display_status("overdue"), "overdue")

    def test_matched_transaction_shows_the_badge_with_its_recurrence(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            account_id, tx_id, occurrence_id = make_pair(database)
            changed, _ = ForecastReconciliationService(database).confirm_manual_match(occurrence_id, tx_id)
            self.assertEqual(changed, 1)

            transactions = TransactionsReadService(database).snapshot()["transactions"]
            row = next(item for item in transactions if item["id"] == tx_id)
            self.assertTrue(row["reconciliation"]["reconciled"])
            self.assertEqual(row["reconciliation"]["occurrenceId"], occurrence_id)
            self.assertTrue(row["reconciliation"]["label"])

            account = next(a for a in AccountsReadService(database).snapshot()["accounts"] if a["id"] == account_id)
            listed = next(item for item in account["transactions"] if item["id"] == tx_id)
            self.assertTrue(listed["reconciliation"]["reconciled"])

            others = [item for item in transactions if item["id"] != tx_id]
            self.assertTrue(all(not item["reconciliation"]["reconciled"] for item in others))

    def test_cancel_keeps_the_link_in_the_history(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            _, tx_id, occurrence_id = make_pair(database)
            service = ReconciliationReadService(database)
            ForecastReconciliationService(database).confirm_manual_match(occurrence_id, tx_id)

            result = service.cancel_reconciliation(occurrence_id, tx_id)
            self.assertTrue(result["success"], result["message"])

            # Le lien n'est plus actif : la transaction n'est plus « rapprochée »…
            self.assertEqual(database.reconciliation_links(), [])
            transactions = TransactionsReadService(database).snapshot()["transactions"]
            self.assertFalse(next(i for i in transactions if i["id"] == tx_id)["reconciliation"]["reconciled"])
            # … mais la trace est conservée avec sa date d'annulation.
            history = service.history(transaction_id=tx_id)["items"]
            self.assertEqual(len(history), 1)
            self.assertFalse(history[0]["active"])
            self.assertTrue(history[0]["cancelledAt"])
            self.assertEqual(history[0]["occurrenceId"], occurrence_id)
            self.assertTrue(history[0]["recurrenceName"])
            # La transaction et la prévision existent toujours, l'occurrence est restaurée.
            with database.connect() as conn:
                self.assertIsNotNone(conn.execute("SELECT id FROM transactions WHERE id = ?", (tx_id,)).fetchone())
                occurrence = conn.execute("SELECT status FROM forecast_occurrences WHERE id = ?", (occurrence_id,)).fetchone()
            self.assertIn(occurrence["status"], {"planned", "overdue"})

    def test_rematch_after_cancel_creates_a_second_history_line(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            _, tx_id, occurrence_id = make_pair(database)
            service = ReconciliationReadService(database)
            engine = ForecastReconciliationService(database)
            engine.confirm_manual_match(occurrence_id, tx_id)
            service.cancel_reconciliation(occurrence_id, tx_id)
            engine.confirm_manual_match(occurrence_id, tx_id)

            history = service.history(occurrence_id=occurrence_id)["items"]
            self.assertEqual(sorted(item["active"] for item in history), [False, True])

    def test_cancel_without_link_is_reported_not_silent(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            _, tx_id, occurrence_id = make_pair(database)

            result = ReconciliationReadService(database).cancel_reconciliation(occurrence_id, tx_id)
            self.assertFalse(result["success"])
            self.assertTrue(result["message"])

    def test_counters_do_not_depend_on_the_selected_filter(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            _, tx_id, occurrence_id = make_pair(database)
            ForecastReconciliationService(database).confirm_manual_match(occurrence_id, tx_id)
            service = ReconciliationReadService(database)

            active = service.snapshot(status="active")
            finalized = service.snapshot(status="finalized")
            matched = service.snapshot(status="matched")

            self.assertEqual(active["summary"], finalized["summary"])
            self.assertEqual(active["summary"], matched["summary"])
            self.assertEqual(finalized["view"]["transactionsTitle"], "Transactions rapprochées")
            self.assertEqual(active["view"]["transactionsTitle"], "Transactions à rapprocher")
            # Le filtre « Finalisées » ne liste que des éléments réellement rapprochés.
            self.assertIn(tx_id, [row["id"] for row in finalized["transactions"]])
            self.assertTrue(all(row["reconciled"] for row in finalized["transactions"]))
            self.assertNotIn(tx_id, [row["id"] for row in active["transactions"]])

    def test_amount_gap_filter_matches_the_displayed_status(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            _, tx_id, occurrence_id = make_pair(database, expected=-110.0, actual=-100.0)
            ForecastReconciliationService(database).confirm_manual_match(occurrence_id, tx_id)
            service = ReconciliationReadService(database)

            gap = service.snapshot(status="amount_gap")
            ids = {row["id"]: row for row in gap["occurrences"]}
            self.assertIn(occurrence_id, ids)
            self.assertEqual(ids[occurrence_id]["displayStatus"], "amount_gap")
            self.assertEqual(ids[occurrence_id]["statusLabel"], "Écart de montant")
            self.assertNotIn(occurrence_id, [row["id"] for row in service.snapshot(status="matched")["occurrences"]])

    def test_income_received_late_is_listed_for_manual_matching(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            today = date.today()
            with database.connect() as conn:
                account_id = int(conn.execute("SELECT id FROM accounts WHERE status = 'Actif' ORDER BY id LIMIT 1").fetchone()["id"])
                recurring_id = int(conn.execute("SELECT id FROM recurring_items ORDER BY id LIMIT 1").fetchone()["id"])
                tx_id = int(conn.execute(
                    "INSERT INTO transactions(account_id, tx_date, label, category, amount, tx_type, status, source, signature) "
                    "VALUES (?, ?, 'VIREMENT RETRAITE TEST', 'Revenus', 1690.0, 'Crédit', 'Validée', 'test', ?)",
                    (account_id, today.isoformat(), str(uuid4())),
                ).lastrowid)
                occurrence_id = int(conn.execute(
                    "INSERT INTO forecast_occurrences(uuid, source_type, source_id, account_id, expected_date, "
                    "expected_amount, expected_label, expected_category, direction, status) "
                    "VALUES (?, 'recurring', ?, ?, ?, 1690.0, 'Retraite test', 'Revenus', 'credit', 'planned')",
                    (str(uuid4()), recurring_id, account_id, (today - timedelta(days=11)).isoformat()),
                ).lastrowid)

            service = ReconciliationReadService(database)
            snapshot = service.snapshot()
            row = next(item for item in snapshot["transactions"] if item["id"] == tx_id)
            self.assertEqual(row["manualCandidate"]["occurrenceId"], occurrence_id)
            self.assertEqual(row["manualCandidate"]["dayGap"], 11)
            self.assertIn(occurrence_id, [item["id"] for item in snapshot["occurrences"]])
            # Et le rapprochement manuel est bien possible.
            changed, _ = ForecastReconciliationService(database).confirm_manual_match(occurrence_id, tx_id)
            self.assertEqual(changed, 1)

    def test_user_can_change_date_and_amount_gaps(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            service = ReconciliationReadService(database)

            defaults = service.snapshot()["rules"]
            self.assertEqual(defaults["dateToleranceDays"], 5)
            self.assertEqual(defaults["manualWindowDays"], 45)

            result = service.update_rules({
                "dateToleranceDays": 8,
                "amountTolerancePercent": 3,
                "manualWindowDays": 20,
                "manualAmountTolerancePercent": 15,
            })
            self.assertTrue(result["success"], result["message"])
            rules = ReconciliationReadService(database).snapshot()["rules"]
            self.assertEqual(rules["dateToleranceDays"], 8)
            self.assertEqual(rules["amountTolerancePercent"], 3.0)
            self.assertEqual(rules["manualWindowDays"], 20)
            self.assertEqual(rules["manualAmountTolerancePercent"], 15.0)
            # Les seuils non modifiés sont conservés.
            self.assertEqual(rules["automaticThreshold"], 90)

    def test_invalid_gaps_are_refused_with_a_clear_message(self):
        with TemporaryDirectory() as root:
            service = ReconciliationReadService(build_database(root))
            self.assertFalse(service.update_rules({"dateToleranceDays": -1})["success"])
            self.assertFalse(service.update_rules({"manualAmountTolerancePercent": 250})["success"])
            refused = service.update_rules({"dateToleranceDays": 30, "manualWindowDays": 10})
            self.assertFalse(refused["success"])
            self.assertIn("fenêtre", refused["message"])

    def test_manual_window_setting_controls_the_late_income_listing(self):
        with TemporaryDirectory() as root:
            database = build_database(root)
            today = date.today()
            with database.connect() as conn:
                account_id = int(conn.execute("SELECT id FROM accounts WHERE status = 'Actif' ORDER BY id LIMIT 1").fetchone()["id"])
                recurring_id = int(conn.execute("SELECT id FROM recurring_items ORDER BY id LIMIT 1").fetchone()["id"])
                tx_id = int(conn.execute(
                    "INSERT INTO transactions(account_id, tx_date, label, category, amount, tx_type, status, source, signature) "
                    "VALUES (?, ?, 'VIREMENT RETRAITE', 'Revenus', 802.0, 'Crédit', 'Validée', 'test', ?)",
                    (account_id, today.isoformat(), str(uuid4())),
                ).lastrowid)
                conn.execute(
                    "INSERT INTO forecast_occurrences(uuid, source_type, source_id, account_id, expected_date, "
                    "expected_amount, expected_label, expected_category, direction, status) "
                    "VALUES (?, 'recurring', ?, ?, ?, 802.0, 'Retraite 2', 'Revenus', 'credit', 'planned')",
                    (str(uuid4()), recurring_id, account_id, (today - timedelta(days=20)).isoformat()),
                )
            service = ReconciliationReadService(database)
            ids = lambda: [row["id"] for row in service.snapshot()["transactions"]]
            self.assertIn(tx_id, ids())
            service.update_rules({"manualWindowDays": 10})
            self.assertNotIn(tx_id, ids())

    def test_cancel_route_requires_a_session_and_reports_errors(self):
        with TemporaryDirectory() as root:
            app = create_app(build_database(root))
            endpoint = next(route.endpoint for route in app.routes if route.path == "/api/v1/reconciliation/links/cancel")
            with self.assertRaises(HTTPException) as raised:
                endpoint(ReconciliationCancelPayload(occurrence_id=1, transaction_id=1), None, None)
            self.assertEqual(raised.exception.status_code, 401)
            paths = {route.path for route in app.routes}
            self.assertIn("/api/v1/reconciliation/history", paths)


if __name__ == "__main__":
    unittest.main()
