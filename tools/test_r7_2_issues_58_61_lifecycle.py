from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.database import Database
from app.services.forecast_reconciliation_service import ForecastReconciliationService
from app.ui.reconciliation_page import ReconciliationPage


START = "2031-05-01"
END = "2031-07-31"


def make_db() -> Database:
    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    root = Path(tmp.name)
    db = Database(root / "issues_58_61.db")
    db.encrypted_db_path = root / "issues_58_61.vvdb"
    db._tmp = tmp
    db.initialize()
    with db.connect() as conn:
        conn.execute("DELETE FROM forecast_reconciliation_proposals")
        conn.execute("DELETE FROM forecast_reconciliation_links")
        conn.execute("DELETE FROM forecast_occurrences")
    return db


def add_occurrence(
    db: Database,
    account_id: int,
    expected_date: str,
    label: str,
    amount: float,
    status: str = "planned",
    source_type: str = "one_off",
) -> int:
    with db.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO forecast_occurrences(
                uuid, source_type, account_id, expected_date, expected_amount,
                expected_label, expected_category, direction, status,
                remaining_amount
            ) VALUES (?, ?, ?, ?, ?, ?, 'Test', ?, ?, ?)
            """,
            (
                str(uuid4()),
                source_type,
                account_id,
                expected_date,
                amount,
                label,
                "credit" if amount >= 0 else "debit",
                status,
                abs(amount),
            ),
        )
        return int(cursor.lastrowid)


def transaction_id(db: Database, label: str) -> int:
    with db.connect() as conn:
        return int(conn.execute("SELECT id FROM transactions WHERE label = ?", (label,)).fetchone()["id"])


def test_issue_58_ignored_occurrence_can_be_restored_with_traceability() -> None:
    db = make_db()
    service = ForecastReconciliationService(db)
    account_id = int(db.list_accounts()[0]["id"])
    occurrence_id = add_occurrence(db, account_id, "2031-05-01", "IGNORER PUIS RESTAURER", -40)

    assert service.ignore_occurrence(occurrence_id, "Dépense supprimée") == (
        True,
        "Occurrence ignorée et conservée dans l’historique.",
    )
    ignored = service.occurrence_details(occurrence_id)
    assert ignored["occurrence"]["status"] == "ignored"
    assert ignored["occurrence"]["ignored_reason"] == "Dépense supprimée"
    assert [event["event_type"] for event in ignored["history"]] == ["occurrence_ignored"]
    assert ReconciliationPage.available_occurrence_actions("ignored", False) == ["restore", "info"]

    assert service.restore_occurrence(occurrence_id, "2031-06-01")[0]
    restored = service.occurrence_details(occurrence_id)
    assert restored["occurrence"]["status"] == "overdue"
    assert restored["occurrence"]["ignored_reason"] == "Dépense supprimée"
    assert [event["event_type"] for event in restored["history"]] == [
        "occurrence_ignored",
        "occurrence_restored",
    ]


def test_issue_59_occurrence_can_be_cancelled_and_remains_in_history() -> None:
    db = make_db()
    service = ForecastReconciliationService(db)
    account_id = int(db.list_accounts()[0]["id"])
    occurrence_id = add_occurrence(db, account_id, "2031-06-15", "ANNULATION EXPLICITE", -75)

    ok, message = service.cancel_occurrence(occurrence_id, "Contrat résilié")
    assert ok, message
    details = service.occurrence_details(occurrence_id)
    assert details["occurrence"]["status"] == "cancelled"
    assert details["occurrence"]["cancelled_reason"] == "Contrat résilié"
    assert details["history"][-1]["event_type"] == "occurrence_cancelled"
    assert ReconciliationPage.available_occurrence_actions("cancelled", False) == ["info"]

    dataset = service.build_reconciliation_dataset(START, END, account_id, "cancelled")
    assert [int(row["id"]) for row in dataset["occurrences"]] == [occurrence_id]
    assert dataset["transactions"] == []
    assert dataset["summary"]["cancelled"] == 1


def test_issue_60_information_contains_business_data_links_and_history() -> None:
    db = make_db()
    service = ForecastReconciliationService(db)
    account_id = int(db.list_accounts()[0]["id"])
    assert db.insert_transaction(account_id, "2031-06-20", "FACTURE INFO", "Test", -100, "Démo")
    tx_id = transaction_id(db, "FACTURE INFO")
    occurrence_id = add_occurrence(db, account_id, "2031-06-20", "FACTURE INFO", -100)

    matched, message = service.confirm_manual_match(occurrence_id, tx_id)
    assert matched == 1, message
    details = service.occurrence_details(occurrence_id)
    occurrence = details["occurrence"]
    assert occurrence["expected_date"] == "2031-06-20"
    assert occurrence["expected_label"] == "FACTURE INFO"
    assert occurrence["expected_amount"] == -100
    assert occurrence["status"] == "confirmed"
    assert occurrence["account_name"]
    assert len(details["links"]) == 1
    assert details["links"][0]["transaction_id"] == tx_id
    assert details["links"][0]["match_type"] == "manual"
    assert details["links"][0]["active"] == 1
    assert details["history"][-1]["event_type"] == "reconciliation_linked"

    cancelled, cancel_message = service.cancel_match(occurrence_id)
    assert cancelled, cancel_message
    historical = service.occurrence_details(occurrence_id)
    assert historical["links"][0]["active"] == 0
    assert historical["history"][-1]["event_type"] == "reconciliation_cancelled"


def test_issue_61_status_filters_keep_transactions_and_occurrences_coherent() -> None:
    db = make_db()
    service = ForecastReconciliationService(db)
    account_id = int(db.list_accounts()[0]["id"])
    assert db.insert_transaction(account_id, "2031-06-20", "TRANSACTION LIEE", "Test", -100, "Démo")
    assert db.insert_transaction(account_id, "2031-06-21", "TRANSACTION SANS RAPPORT", "Test", -55, "Démo")
    linked_tx_id = transaction_id(db, "TRANSACTION LIEE")
    unrelated_tx_id = transaction_id(db, "TRANSACTION SANS RAPPORT")
    matched_occurrence_id = add_occurrence(db, account_id, "2031-06-20", "TRANSACTION LIEE", -100)
    assert service.confirm_manual_match(matched_occurrence_id, linked_tx_id)[0] == 1

    confirmed = service.build_reconciliation_dataset(START, END, account_id, "confirmed")
    assert [int(row["id"]) for row in confirmed["occurrences"]] == [matched_occurrence_id]
    assert [int(row["id"]) for row in confirmed["transactions"]] == [linked_tx_id]
    assert unrelated_tx_id not in {int(row["id"]) for row in confirmed["transactions"]}
    assert ReconciliationPage.available_occurrence_actions("confirmed", True) == ["cancel_match", "info"]

    assert db.insert_transaction(account_id, "2031-07-10", "PROPOSITION CIBLE", "Test", -80, "Démo")
    proposal_tx_id = transaction_id(db, "PROPOSITION CIBLE")
    proposal_occurrence_id = add_occurrence(db, account_id, "2031-07-10", "PROPOSITION CIBLE", -80)
    proposal_tx = db.get_transaction(proposal_tx_id)
    candidate = service.find_candidates(proposal_tx)[0]
    assert int(candidate["occurrence"]["id"]) == proposal_occurrence_id
    assert service._save_proposal(candidate)

    review = service.build_reconciliation_dataset(START, END, account_id, "to_review")
    assert [int(row["id"]) for row in review["occurrences"]] == [proposal_occurrence_id]
    assert [int(row["id"]) for row in review["transactions"]] == [proposal_tx_id]

    proposal_id = int(review["proposals"][0]["id"])
    assert service.reject_proposal(proposal_id)[0]
    after_rejection = service.build_reconciliation_dataset(START, END, account_id, "to_review")
    assert after_rejection["occurrences"] == []
    assert after_rejection["transactions"] == []


if __name__ == "__main__":
    test_issue_58_ignored_occurrence_can_be_restored_with_traceability()
    test_issue_59_occurrence_can_be_cancelled_and_remains_in_history()
    test_issue_60_information_contains_business_data_links_and_history()
    test_issue_61_status_filters_keep_transactions_and_occurrences_coherent()
    print("OK - cycle de vie Rapprochements #58 à #61 couvert")
