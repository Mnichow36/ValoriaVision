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


    def test_close_competing_candidates_require_review_without_allocation(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database = Database(Path(temp_dir) / "ambiguity.db")
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
                    ) VALUES (?, '2026-09-20', 'Assurance habitation', 'Assurances',
                              -100.50, 'Débit', 'Saisie')
                    """,
                    (account_id,),
                ).lastrowid
                for source_id, expected_date, amount, label in (
                    (101, '2026-09-20', -100.00, 'Assurance habitation A'),
                    (102, '2026-09-21', -101.00, 'Assurance habitation B'),
                ):
                    connection.execute(
                        """
                        INSERT INTO forecast_occurrences(
                            uuid, source_type, source_id, account_id, expected_date,
                            expected_amount, expected_label, expected_category,
                            direction, status
                        ) VALUES (?, 'recurring', ?, ?, ?, ?, ?, 'Assurances',
                                  'debit', 'planned')
                        """,
                        (str(uuid4()), source_id, account_id, expected_date, amount, label),
                    )

            service = ForecastReconciliationService(database)
            proposals = service.prepare_best_proposals(
                '2026-09-01', '2026-10-01', account_id=account_id
            )

            self.assertEqual(len(proposals), 1)
            self.assertEqual(proposals[0]["transaction_id"], transaction_id)
            with database.connect() as connection:
                links = connection.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM forecast_reconciliation_links
                    WHERE transaction_id = ? AND deleted_at IS NULL
                    """,
                    (transaction_id,),
                ).fetchone()["count"]
                partial = connection.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM forecast_occurrences
                    WHERE status = 'partially_matched'
                    """
                ).fetchone()["count"]
            self.assertEqual(links, 0)
            self.assertEqual(partial, 0)

            accepted, _ = service.confirm_proposal(int(proposals[0]["id"]))
            self.assertTrue(accepted)

            # Re-run the engine exactly as the UI does after manual validation.
            service.prepare_best_proposals(
                '2026-09-01', '2026-10-01', account_id=account_id
            )
            with database.connect() as connection:
                occurrence_a = connection.execute(
                    """
                    SELECT status, matched_amount, remaining_amount, overage_amount
                    FROM forecast_occurrences WHERE source_id = 101
                    """
                ).fetchone()
                occurrence_b = connection.execute(
                    """
                    SELECT status, matched_amount, remaining_amount, overage_amount
                    FROM forecast_occurrences WHERE source_id = 102
                    """
                ).fetchone()
                allocations = connection.execute(
                    """
                    SELECT occurrence_id, applied_amount
                    FROM forecast_reconciliation_links
                    WHERE transaction_id = ? AND deleted_at IS NULL
                    """,
                    (transaction_id,),
                ).fetchall()

            self.assertEqual("confirmed", occurrence_a["status"])
            self.assertAlmostEqual(100.50, float(occurrence_a["matched_amount"]))
            self.assertAlmostEqual(0.0, float(occurrence_a["remaining_amount"]))
            self.assertAlmostEqual(0.50, float(occurrence_a["overage_amount"]))
            self.assertEqual("planned", occurrence_b["status"])
            self.assertIn(occurrence_b["matched_amount"], (None, 0, 0.0))
            self.assertIn(occurrence_b["remaining_amount"], (None, 101, 101.0))
            self.assertIn(occurrence_b["overage_amount"], (None, 0, 0.0))
            self.assertEqual(1, len(allocations))
            self.assertAlmostEqual(100.50, float(allocations[0]["applied_amount"]))


if __name__ == "__main__":
    unittest.main()
