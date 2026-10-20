from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from app.database import Database
from app.migrations.r8_reconciliation import apply_r8_reconciliation_foundation
from app.services.forecast_reconciliation_service import ForecastReconciliationService


class RescheduleRecurringOccurrencesTests(unittest.TestCase):
    """Overdue recurring occurrences can be moved together without shifting the template."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp_dir.name) / "valoria-test.db")
        with self.db.connect() as conn:
            self.db.create_schema(conn)
            self.db.apply_forecast_reconciliation_foundation(conn)
            self.db.apply_r7_2_foundation(conn)
            self.db.apply_reconciliation_multi_link_foundation(conn)
            apply_r8_reconciliation_foundation(conn)
            self.account_id = int(
                conn.execute(
                    """
                    INSERT INTO accounts(
                        name, bank, account_type, identifier,
                        reference_balance, reference_date, status
                    )
                    VALUES ('Compte test', 'Banque test', 'Courant', ?, 1000,
                            '2026-01-01', 'Actif')
                    """,
                    (str(uuid4()),),
                ).lastrowid
            )
            self.recurring_id = int(
                conn.execute(
                    """
                    INSERT INTO recurring_items(
                        account_id, name, category, amount, frequency,
                        next_date, scenario, status
                    )
                    VALUES (?, 'Salaire', 'Revenus', 2000, 'Mensuel',
                            '2026-09-15', 'Réaliste', 'Actif')
                    """,
                    (self.account_id,),
                ).lastrowid
            )
            self.september_id = self._insert_occurrence(
                conn, "2026-09-15", "overdue"
            )
            self.october_id = self._insert_occurrence(
                conn, "2026-10-15", "overdue"
            )
            self.future_id = self._insert_occurrence(
                conn, "2026-11-15", "planned"
            )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _insert_occurrence(self, conn, expected_date: str, status: str) -> int:
        return int(
            conn.execute(
                """
                INSERT INTO forecast_occurrences(
                    uuid, source_type, source_id, account_id,
                    expected_date, original_expected_date,
                    expected_amount, expected_label, expected_category,
                    direction, status
                )
                VALUES (?, 'recurring', ?, ?, ?, ?, 2000,
                        'Salaire', 'Revenus', 'credit', ?)
                """,
                (
                    str(uuid4()),
                    self.recurring_id,
                    self.account_id,
                    expected_date,
                    expected_date,
                    status,
                ),
            ).lastrowid
        )

    def test_batch_reschedule_preserves_origins_and_updates_forecast(self) -> None:
        service = ForecastReconciliationService(self.db)

        eligible = service.list_reschedulable_occurrences(
            self.account_id,
            "2026-10-17",
        )
        self.assertEqual(
            [row["id"] for row in eligible],
            [self.september_id, self.october_id],
        )

        count, message = service.reschedule_occurrences(
            [self.september_id, self.october_id],
            "2026-10-18",
            reference_date="2026-10-17",
        )

        self.assertEqual(count, 2)
        self.assertIn("18/10/2026", message)
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, expected_date, original_expected_date, status,
                       rescheduled_at
                FROM forecast_occurrences
                WHERE id IN (?, ?)
                ORDER BY id
                """,
                (self.september_id, self.october_id),
            ).fetchall()
            audit_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM audit_log
                WHERE event_type = 'occurrence_rescheduled'
                """
            ).fetchone()[0]

        self.assertEqual([row["expected_date"] for row in rows], ["2026-10-18", "2026-10-18"])
        self.assertEqual(
            [row["original_expected_date"] for row in rows],
            ["2026-09-15", "2026-10-15"],
        )
        self.assertTrue(all(row["status"] == "planned" for row in rows))
        self.assertTrue(all(row["rescheduled_at"] for row in rows))
        self.assertEqual(audit_count, 2)

        service.generate_occurrences("2026-09-01", "2026-11-30")
        with self.db.connect() as conn:
            original_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM forecast_occurrences
                WHERE source_id = ?
                  AND original_expected_date IN ('2026-09-15', '2026-10-15')
                """,
                (self.recurring_id,),
            ).fetchone()[0]
        self.assertEqual(original_count, 2)

        events = self.db.forecast_events(
            "2026-10-17",
            horizon_days=2,
            scenario="Réaliste",
            account_id=self.account_id,
        )
        moved = [event for event in events if event["source"] == "Récurrence décalée"]
        self.assertEqual(len(moved), 2)
        self.assertTrue(all(event["date"] == "2026-10-18" for event in moved))
        self.assertEqual(
            {event["original_date"] for event in moved},
            {"2026-09-15", "2026-10-15"},
        )

    def test_batch_is_atomic_when_one_occurrence_is_not_due(self) -> None:
        service = ForecastReconciliationService(self.db)

        count, message = service.reschedule_occurrences(
            [self.october_id, self.future_id],
            "2026-10-20",
            reference_date="2026-10-17",
        )

        self.assertEqual(count, 0)
        self.assertIn("postérieure", message)
        with self.db.connect() as conn:
            october = conn.execute(
                "SELECT expected_date FROM forecast_occurrences WHERE id = ?",
                (self.october_id,),
            ).fetchone()
        self.assertEqual(october["expected_date"], "2026-10-15")

    def test_target_date_must_be_after_reference_date(self) -> None:
        count, message = ForecastReconciliationService(self.db).reschedule_occurrences(
            [self.october_id],
            "2026-10-17",
            reference_date="2026-10-17",
        )

        self.assertEqual(count, 0)
        self.assertIn("strictement postérieure", message)


if __name__ == "__main__":
    unittest.main()
