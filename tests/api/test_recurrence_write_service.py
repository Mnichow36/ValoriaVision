from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.recurrence_write_service import RecurrenceWriteService


class StubConnection:
    def __init__(self) -> None:
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, query, params):
        self.queries.append((query, params))
        return [(901,), (902,)]


class StubDatabase:
    def __init__(self) -> None:
        self.created = None
        self.connection = StubConnection()

    def list_accounts(self):
        return [
            {"id": 7, "name": "Compte courant", "status": "Actif"},
            {"id": 8, "name": "Ancien compte", "status": "Clos"},
        ]

    def list_categories(self):
        return [
            {"id": 3, "name": "Logement", "kind": "Dépense", "direction": "Dépense"},
            {"id": 4, "name": "Salaire", "kind": "Revenu", "direction": "Recette"},
        ]

    @staticmethod
    def default_direction_for_kind(kind):
        return "Recette" if kind == "Revenu" else "Dépense"

    def add_recurring_item(self, data):
        self.created = data
        return 42

    def connect(self):
        return self.connection

    def reconciliation_rules(self, conn):
        return "rules"


class RecurrenceWriteServiceTest(unittest.TestCase):
    @patch("app.services.recurrence_write_service.reevaluate_for_occurrences")
    @patch("app.services.recurrence_write_service.ForecastReconciliationService")
    def test_creates_signed_recurrence_and_generates_reconciliation_occurrences(
        self,
        reconciliation_service,
        reevaluate,
    ):
        database = StubDatabase()
        generator = reconciliation_service.return_value
        service = RecurrenceWriteService(database)

        result = service.create(
            {
                "account_id": 7,
                "name": "Loyer Dupont",
                "category": "Logement",
                "direction": "Débit",
                "amount": 950,
                "frequency": "Mensuel",
                "next_date": "2026-11-05",
                "end_date": "2027-05-05",
                "scenario": "Réaliste",
            }
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["recurringItemId"], 42)
        self.assertEqual(result["generatedOccurrences"], 2)
        self.assertEqual(database.created["amount"], -950)
        self.assertEqual(database.created["next_date"], "2026-11-05")
        generator.generate_occurrences.assert_called_once()
        reevaluate.assert_called_once_with(
            database.connection,
            [901, 902],
            "rules",
            reason="Nouvelle prévision récurrente",
        )

    @patch("app.services.recurrence_write_service.ForecastReconciliationService")
    def test_rejects_direction_incompatible_with_category(self, reconciliation_service):
        with self.assertRaisesRegex(ValueError, "attend un débit"):
            RecurrenceWriteService(StubDatabase()).create(
                {
                    "account_id": 7,
                    "name": "Loyer",
                    "category": "Logement",
                    "direction": "Crédit",
                    "amount": 950,
                    "frequency": "Mensuel",
                    "next_date": "2026-11-05",
                    "scenario": "Réaliste",
                }
            )
        reconciliation_service.assert_not_called()

    def test_rejects_end_date_before_first_due_date(self):
        with self.assertRaisesRegex(ValueError, "date de fin"):
            RecurrenceWriteService(StubDatabase()).create(
                {
                    "account_id": 7,
                    "name": "Salaire",
                    "category": "Salaire",
                    "direction": "Crédit",
                    "amount": 3000,
                    "frequency": "Mensuel",
                    "next_date": "2026-11-28",
                    "end_date": "2026-10-28",
                    "scenario": "Réaliste",
                }
            )


if __name__ == "__main__":
    unittest.main()
