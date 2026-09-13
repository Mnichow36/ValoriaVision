from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from app.database import Database
from app.services.forecast_reconciliation_service import ForecastReconciliationService


class T04ExactProposalTests(unittest.TestCase):
    def _database_with_exact_pair(self, name: str):
        temp_dir = TemporaryDirectory()
        database = Database(Path(temp_dir.name) / name)
        with database.connect() as connection:
            database.create_schema(connection)
            database.apply_migrations(connection)
            account_id = connection.execute(
                """
                INSERT INTO accounts(name, bank, account_type, reference_date)
                VALUES ('Société Générale CC', 'Société Générale',
                        'Compte courant', '2026-09-01')
                """
            ).lastrowid
            transaction_id = connection.execute(
                """
                INSERT INTO transactions(
                    account_id, tx_date, label, category, amount, tx_type, source
                ) VALUES (?, '2026-09-06', 'Retraite', 'Revenus',
                          1470.0, 'Crédit', 'Import')
                """,
                (account_id,),
            ).lastrowid
            occurrence_id = connection.execute(
                """
                INSERT INTO forecast_occurrences(
                    uuid, source_type, source_id, account_id, expected_date,
                    expected_amount, expected_label, expected_category,
                    direction, status
                ) VALUES (?, 'recurring', 1, ?, '2026-09-06',
                          1470.70, 'Retraite 1', 'Revenus', 'credit', 'overdue')
                """,
                (str(uuid4()), account_id),
            ).lastrowid
        return temp_dir, database, account_id, transaction_id, occurrence_id

    def test_score_at_auto_threshold_is_linked_automatically(self) -> None:
        temp_dir, database, account_id, transaction_id, occurrence_id = (
            self._database_with_exact_pair("t04-auto.db")
        )
        self.addCleanup(temp_dir.cleanup)
        service = ForecastReconciliationService(database)

        proposals = service.prepare_best_proposals(
            "2026-06-01",
            "2026-09-30",
            account_id=account_id,
        )

        self.assertEqual([], proposals)
        with database.connect() as connection:
            occurrence = connection.execute(
                """
                SELECT status, actual_transaction_id, matched_amount,
                       remaining_amount, match_type, match_confidence
                FROM forecast_occurrences WHERE id = ?
                """,
                (occurrence_id,),
            ).fetchone()
            link = connection.execute(
                """
                SELECT transaction_id, match_type, confidence
                FROM forecast_reconciliation_links
                WHERE occurrence_id = ? AND deleted_at IS NULL
                """,
                (occurrence_id,),
            ).fetchone()
        self.assertEqual("auto_matched", occurrence["status"])
        self.assertEqual(transaction_id, occurrence["actual_transaction_id"])
        self.assertEqual("automatic", occurrence["match_type"])
        self.assertGreaterEqual(int(occurrence["match_confidence"]), 90)
        self.assertAlmostEqual(1470.0, float(occurrence["matched_amount"]))
        self.assertAlmostEqual(0.70, float(occurrence["remaining_amount"]))
        self.assertEqual(transaction_id, link["transaction_id"])
        self.assertEqual("automatic", link["match_type"])

    def test_existing_review_proposal_is_promoted_to_automatic(self) -> None:
        temp_dir, database, account_id, transaction_id, occurrence_id = (
            self._database_with_exact_pair("t04-pending.db")
        )
        self.addCleanup(temp_dir.cleanup)
        with database.connect() as connection:
            proposal_id = connection.execute(
                """
                INSERT INTO forecast_reconciliation_proposals(
                    uuid, occurrence_id, transaction_id, score, reason, status
                ) VALUES (?, ?, ?, 100, 'proposition existante', 'to_review')
                """,
                (str(uuid4()), occurrence_id, transaction_id),
            ).lastrowid
            connection.execute(
                """
                UPDATE forecast_occurrences SET status = 'to_review'
                WHERE id = ?
                """,
                (occurrence_id,),
            )

        service = ForecastReconciliationService(database)
        proposals = service.prepare_best_proposals(
            "2026-06-01",
            "2026-09-30",
            account_id=account_id,
            reconsider_rejected=True,
        )

        self.assertEqual([], proposals)
        with database.connect() as connection:
            proposal = connection.execute(
                "SELECT status FROM forecast_reconciliation_proposals WHERE id = ?",
                (proposal_id,),
            ).fetchone()
            occurrence = connection.execute(
                "SELECT status, match_type FROM forecast_occurrences WHERE id = ?",
                (occurrence_id,),
            ).fetchone()
        self.assertEqual("accepted", proposal["status"])
        self.assertEqual("auto_matched", occurrence["status"])
        self.assertEqual("automatic", occurrence["match_type"])

    def test_amount_outside_configured_tolerance_is_excluded(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database = Database(Path(temp_dir) / "t04-amount-tolerance.db")
            with database.connect() as connection:
                database.create_schema(connection)
                database.apply_migrations(connection)
                account_id = connection.execute(
                    """
                    INSERT INTO accounts(name, bank, account_type, reference_date)
                    VALUES ('Société Générale CC', 'Société Générale',
                            'Compte courant', '2026-09-01')
                    """
                ).lastrowid
                connection.execute(
                    """
                    INSERT INTO transactions(
                        account_id, tx_date, label, category, amount, tx_type, source
                    ) VALUES (?, '2026-09-01', 'Retraite 2', 'Revenus',
                              901.60, 'Crédit', 'Saisie')
                    """,
                    (account_id,),
                )
                connection.execute(
                    """
                    INSERT INTO forecast_occurrences(
                        uuid, source_type, source_id, account_id, expected_date,
                        expected_amount, expected_label, expected_category,
                        direction, status
                    ) VALUES (?, 'recurring', 2, ?, '2026-09-01',
                              801.55, 'Retraite 2', 'Revenus',
                              'credit', 'overdue')
                    """,
                    (str(uuid4()), account_id),
                )

            service = ForecastReconciliationService(database)
            self.assertEqual(
                [],
                service.prepare_best_proposals(
                    "2026-06-01",
                    "2026-09-30",
                    account_id=account_id,
                ),
            )


if __name__ == "__main__":
    unittest.main()
