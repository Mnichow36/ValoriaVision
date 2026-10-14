from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.services.reconciliation_read_service import ReconciliationReadService


class StubDatabase:
    def list_accounts(self):
        return [
            {"id": 1, "name": "Compte courant", "bank": "Banque A", "status": "Actif"},
            {"id": 2, "name": "Ancien compte", "bank": "Banque B", "status": "Archivé"},
        ]


class StubEngine:
    def __init__(self, database):
        self.database = database
        self.received = None

    def rules_config(self):
        return {"auto_match_threshold": 90, "review_threshold": 60, "date_tolerance_days": 5}

    def status_label(self, status):
        return {"to_review": "À vérifier"}.get(status, status)

    def build_reconciliation_dataset(self, **filters):
        self.received = filters
        transaction = {
            "id": 7,
            "tx_date": "2026-10-12",
            "label": "Loyer octobre",
            "amount": -900,
            "allocated_amount": 0,
            "category": "Logement",
            "account_id": 1,
            "account_name": "Compte courant",
            "bank": "Banque A",
            "proposal_occurrence_id": 11,
        }
        occurrence = {
            "id": 11,
            "expected_date": "2026-10-10",
            "expected_label": "Loyer",
            "expected_amount": -900,
            "expected_category": "Logement",
            "direction": "debit",
            "account_id": 1,
            "account_name": "Compte courant",
            "bank": "Banque A",
            "status": "to_review",
            "matched_amount": 0,
            "remaining_amount": 900,
        }
        self.transaction = transaction
        self.occurrence = occurrence
        return {
            "transactions": [transaction],
            "occurrences": [occurrence],
            "proposals": [{"id": 91, "transaction_id": 7, "occurrence_id": 11}],
            "summary": {"active": 3, "to_review": 1, "partially_matched": 0, "auto_matched": 4, "confirmed": 2},
        }

    def find_candidates(self, transaction):
        return [{"transaction": transaction, "occurrence": self.occurrence, "score": 96, "reason": "montant exact +25"}]

    def decision_for_candidates(self, candidates):
        return "automatic"

    def confirm_proposal(self, proposal_id):
        return True, f"Proposition {proposal_id} validée."

    def reject_proposal(self, proposal_id):
        return True, f"Proposition {proposal_id} rejetée."

    def confirm_manual_match(self, occurrence_id, transaction_id, *, include_overage=False):
        return 1, f"Affectation {occurrence_id}/{transaction_id}/{include_overage}."


class ReconciliationReadServiceTest(unittest.TestCase):
    def test_builds_one_coherent_reconciliation_snapshot(self):
        engine = StubEngine(None)
        service = ReconciliationReadService(
            StubDatabase(),
            engine_factory=lambda database: engine,
            now_provider=lambda: datetime(2026, 10, 14, 16, 0, tzinfo=timezone.utc),
        )

        snapshot = service.snapshot(account_id=1, status="active")

        self.assertEqual(engine.received["account_id"], 1)
        self.assertEqual(snapshot["summary"]["matched"], 6)
        self.assertEqual(snapshot["summary"]["averageScore"], 96)
        self.assertEqual(snapshot["transactions"][0]["remainingAmount"], 900.0)
        self.assertEqual(snapshot["occurrences"][0]["statusLabel"], "À vérifier")
        self.assertEqual(snapshot["suggestions"][0]["proposalId"], 91)
        self.assertEqual(snapshot["accounts"], [{"id": 1, "name": "Compte courant", "bank": "Banque A"}])

    def test_delegates_secure_actions_to_the_existing_engine(self):
        engine = StubEngine(None)
        service = ReconciliationReadService(StubDatabase(), engine_factory=lambda database: engine)

        self.assertEqual(service.confirm_proposal(91), {"success": True, "message": "Proposition 91 validée."})
        self.assertEqual(service.reject_proposal(91), {"success": True, "message": "Proposition 91 rejetée."})
        self.assertEqual(
            service.confirm_manual_match(11, 7, include_overage=True),
            {"success": True, "message": "Affectation 11/7/True."},
        )


if __name__ == "__main__":
    unittest.main()
