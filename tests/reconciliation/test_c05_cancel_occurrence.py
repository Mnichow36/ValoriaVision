from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from app.database import Database
from app.migrations.r8_reconciliation import apply_r8_reconciliation_foundation
from app.services.forecast_reconciliation_service import ForecastReconciliationService


class CancelOccurrenceRegressionTests(unittest.TestCase):
    """C05: cancelling an occurrence must persist and update status counters."""

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
                    VALUES ('Compte test', 'Banque test', 'Courant', ?, 0,
                            '2026-01-01', 'Actif')
                    """,
                    (str(uuid4()),),
                ).lastrowid
            )
            self.occurrence_id = int(
                conn.execute(
                    """
                    INSERT INTO forecast_occurrences(
                        uuid, source_type, account_id, expected_date,
                        expected_amount, expected_label, expected_category,
                        direction, status
                    )
                    VALUES (?, 'recurring', ?, '2026-07-21', -15.99,
                            'Netflix', 'Loisirs', 'debit', 'overdue')
                    """,
                    (str(uuid4()), self.account_id),
                ).lastrowid
            )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_cancel_occurrence_persists_status_reason_audit_and_counters(self) -> None:
        service = ForecastReconciliationService(self.db)

        ok, message = service.cancel_occurrence(
            self.occurrence_id,
            "Annulation recette C05",
        )

        self.assertTrue(ok)
        self.assertIn("annulée", message.lower())
        with self.db.connect() as conn:
            occurrence = conn.execute(
                """
                SELECT status, cancelled_reason
                FROM forecast_occurrences
                WHERE id = ?
                """,
                (self.occurrence_id,),
            ).fetchone()
            audit = conn.execute(
                """
                SELECT event_type, metadata_json
                FROM audit_log
                WHERE entity = 'forecast_occurrence'
                  AND entity_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (str(self.occurrence_id),),
            ).fetchone()

        self.assertEqual(occurrence["status"], "cancelled")
        self.assertEqual(occurrence["cancelled_reason"], "Annulation recette C05")
        self.assertEqual(audit["event_type"], "occurrence_cancelled")

        dataset = service.build_reconciliation_dataset(
            start_date="2026-06-01",
            end_date="2026-07-31",
            status="all",
        )
        self.assertEqual(dataset["summary"]["active"], 0)
        self.assertEqual(dataset["summary"]["overdue"], 0)
        self.assertEqual(dataset["summary"]["cancelled"], 1)
        self.assertEqual(dataset["summary"]["all"], 1)


if __name__ == "__main__":
    unittest.main()
