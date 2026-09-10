from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import uuid4

from app.database import Database
from app.services.forecast_reconciliation_service import ForecastReconciliationService


class T04ExactProposalTests(unittest.TestCase):
    def test_exact_salary_pair_produces_visible_proposal(self) -> None:
        with TemporaryDirectory() as temp_dir:
            database = Database(Path(temp_dir) / "t04.db")
            with database.connect() as connection:
                database.create_schema(connection)
                database.apply_migrations(connection)
                account_id = connection.execute(
                    """
                    INSERT INTO accounts(name, bank, account_type, reference_date)
                    VALUES ('Société Générale CC', 'Société Générale', 'Compte courant', '2026-09-01')
                    """
                ).lastrowid
                transaction_id = connection.execute(
                    """
                    INSERT INTO transactions(
                        account_id, tx_date, label, category, amount, tx_type, source
                    ) VALUES (?, '2026-09-06', 'VIR RECU DE: URSSAF', 'Revenus', 180.0, 'Crédit', 'Import')
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
                              180.0, 'Salaire', 'Revenus', 'credit', 'overdue')
                    """,
                    (str(uuid4()), account_id),
                ).lastrowid

            service = ForecastReconciliationService(database)
            proposals = service.prepare_best_proposals(
                '2026-06-01',
                '2026-09-30',
                account_id=account_id,
            )

            self.assertEqual(1, len(proposals))
            self.assertEqual(transaction_id, proposals[0]['transaction_id'])
            self.assertEqual(occurrence_id, proposals[0]['occurrence_id'])
            self.assertGreaterEqual(int(proposals[0]['score']), 90)


if __name__ == '__main__':
    unittest.main()
