from __future__ import annotations

from app.services.forecast_reconciliation_service import ForecastReconciliationService
from tools.test_r7_2_issue_49_reconciliation_scope import add_occurrence, make_db


def transaction_id(db, label: str) -> int:
    with db.connect() as conn:
        return int(conn.execute("SELECT id FROM transactions WHERE label = ?", (label,)).fetchone()["id"])


def occurrence(db, occurrence_id: int):
    with db.connect() as conn:
        return conn.execute("SELECT * FROM forecast_occurrences WHERE id = ?", (occurrence_id,)).fetchone()


def test_issue_82_partial_rollup_and_cancel() -> None:
    db = make_db()
    service = ForecastReconciliationService(db)
    account_id = int(db.list_accounts()[0]["id"])
    occurrence_id = add_occurrence(db, account_id, day="2030-06-15", label="ALIMENTATION 150", amount=-150, source_id=8201)

    assert db.insert_transaction(account_id, "2030-06-15", "COURSES 100", "Alimentation", -100, "Manuel")
    assert db.insert_transaction(account_id, "2030-06-16", "COURSES 35", "Alimentation", -35, "Import bancaire")
    first_id = transaction_id(db, "COURSES 100")
    second_id = transaction_id(db, "COURSES 35")

    ok, _ = service.add_reconciliation_link(occurrence_id, first_id)
    assert ok
    row = occurrence(db, occurrence_id)
    assert row["status"] == "partially_matched"
    assert float(row["actual_amount"]) == -100
    assert float(row["matched_amount"]) == 100
    assert float(row["remaining_amount"]) == 50

    ok, _ = service.add_reconciliation_link(occurrence_id, second_id)
    assert ok
    row = occurrence(db, occurrence_id)
    assert row["status"] == "partially_matched"
    assert float(row["actual_amount"]) == -135
    assert float(row["matched_amount"]) == 135
    assert float(row["remaining_amount"]) == 15
    assert row["match_type"] == "multi"

    ok, _ = service.cancel_reconciliation_link(occurrence_id, second_id)
    assert ok
    row = occurrence(db, occurrence_id)
    assert row["status"] == "partially_matched"
    assert float(row["matched_amount"]) == 100
    assert float(row["remaining_amount"]) == 50

    ok, _ = service.cancel_reconciliation_link(occurrence_id, first_id)
    assert ok
    row = occurrence(db, occurrence_id)
    assert row["status"] == "planned"
    assert row["actual_amount"] is None
    assert row["actual_transaction_id"] is None
    assert float(row["matched_amount"]) == 0
    assert float(row["remaining_amount"]) == 150


def test_issue_82_one_transaction_can_be_allocated_to_multiple_occurrences() -> None:
    db = make_db()
    service = ForecastReconciliationService(db)
    account_id = int(db.list_accounts()[0]["id"])
    first_occurrence = add_occurrence(db, account_id, day="2030-06-20", label="PREVISION A", amount=-60, source_id=8202)
    second_occurrence = add_occurrence(db, account_id, day="2030-06-20", label="PREVISION B", amount=-40, source_id=8203)
    assert db.insert_transaction(account_id, "2030-06-20", "PAIEMENT GROUPE 100", "Test", -100, "Import bancaire")
    tx_id = transaction_id(db, "PAIEMENT GROUPE 100")

    assert service.add_reconciliation_link(first_occurrence, tx_id, applied_amount=60)[0]
    assert service.add_reconciliation_link(second_occurrence, tx_id, applied_amount=40)[0]
    assert occurrence(db, first_occurrence)["status"] == "confirmed"
    assert occurrence(db, second_occurrence)["status"] == "confirmed"

    with db.connect() as conn:
        links = conn.execute(
            "SELECT COUNT(*) AS count, SUM(applied_amount) AS total FROM forecast_reconciliation_links WHERE transaction_id = ? AND deleted_at IS NULL",
            (tx_id,),
        ).fetchone()
    assert int(links["count"]) == 2
    assert float(links["total"]) == 100
    assert not service.add_reconciliation_link(first_occurrence, tx_id, applied_amount=1)[0]


def test_issue_82_overage_remains_visible() -> None:
    db = make_db()
    service = ForecastReconciliationService(db)
    account_id = int(db.list_accounts()[0]["id"])
    occurrence_id = add_occurrence(db, account_id, day="2030-06-25", label="PREVISION 150", amount=-150, source_id=8204)
    assert db.insert_transaction(account_id, "2030-06-25", "REALISE 170", "Test", -170, "Manuel")
    tx_id = transaction_id(db, "REALISE 170")

    assert service.add_reconciliation_link(occurrence_id, tx_id, applied_amount=170)[0]
    row = occurrence(db, occurrence_id)
    assert row["status"] == "confirmed"
    assert float(row["matched_amount"]) == 170
    assert float(row["remaining_amount"]) == 0
    assert float(row["overage_amount"]) == 20


if __name__ == "__main__":
    test_issue_82_partial_rollup_and_cancel()
    test_issue_82_one_transaction_can_be_allocated_to_multiple_occurrences()
    test_issue_82_overage_remains_visible()
    print("OK - issue #82 socle multi-liens et rapprochement partiel")
