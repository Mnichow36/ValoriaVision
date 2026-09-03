from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import uuid4

from app.database import Database
from app.services.forecast_reconciliation_service import ForecastReconciliationService


START = "2026-06-01"
END = "2026-06-30"


def make_db() -> Database:
    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db = Database(Path(tmp.name) / "issue_49.db")
    db._tmp = tmp
    db.initialize()
    return db


def add_occurrence(db: Database, account_id: int, *, day: str, label: str, amount: float,
                   status: str = "planned", source_type: str = "recurring",
                   source_id: int | None = None, actual_amount: float | None = None) -> int:
    with db.connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO forecast_occurrences(
                uuid, source_type, source_id, account_id, expected_date,
                expected_amount, expected_label, expected_category, direction,
                status, actual_amount, amount_delta
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Test', ?, ?, ?, ?)
            """,
            (
                str(uuid4()), source_type, source_id, account_id, day, amount, label,
                "credit" if amount >= 0 else "debit", status, actual_amount,
                None if actual_amount is None else round(actual_amount - amount, 2),
            ),
        )
        return int(cursor.lastrowid)


def test_issue_49_exhaustive_scope_and_uniform_filters() -> None:
    db = make_db()
    service = ForecastReconciliationService(db)
    account_id = int(db.list_accounts()[0]["id"])

    assert db.insert_transaction(account_id, "2026-06-10", "IMPORT ELIGIBLE", "Test", -10, "Import bancaire")
    assert db.insert_transaction(account_id, "2026-06-11", "MANUEL ELIGIBLE", "Test", -20, "Manuel")

    recurring_id = add_occurrence(db, account_id, day="2026-06-12", label="RECURRENCE", amount=-30, source_id=101)
    one_off_id = add_occurrence(db, account_id, day="2026-06-13", label="PONCTUEL", amount=40, source_type="one_off", source_id=102)
    partial_id = add_occurrence(
        db, account_id, day="2026-06-14", label="PARTIEL", amount=-100,
        status="to_review", source_id=103, actual_amount=-60,
    )
    add_occurrence(db, account_id, day="2026-06-15", label="FINALISE", amount=-50, status="confirmed", source_id=104)

    dataset = service.build_reconciliation_dataset(START, END, account_id, "active")
    assert {row["label"] for row in dataset["transactions"]} == {"IMPORT ELIGIBLE", "MANUEL ELIGIBLE"}
    assert {int(row["id"]) for row in dataset["occurrences"]} == {recurring_id, one_off_id, partial_id}
    assert dataset["summary"]["active"] == 3
    assert dataset["summary"]["finalized"] == 1
    assert dataset["source_counts"]["transactions_loaded"] == 2
    assert dataset["source_counts"]["transactions_displayed"] == 2
    assert dataset["source_counts"]["occurrences_displayed"] == 3

    planned = service.build_reconciliation_dataset(START, END, account_id, "planned")
    assert {int(row["id"]) for row in planned["occurrences"]} == {recurring_id, one_off_id}
    review = service.build_reconciliation_dataset(START, END, account_id, "to_review")
    assert [int(row["id"]) for row in review["occurrences"]] == [partial_id]
    assert review["summary"] == dataset["summary"], "Les KPI doivent garder le même périmètre compte/date."


def test_issue_49_default_dataset_never_silently_truncates() -> None:
    db = make_db()
    service = ForecastReconciliationService(db)
    account_id = int(db.list_accounts()[0]["id"])

    with db.connect() as conn:
        conn.executemany(
            """
            INSERT INTO transactions(account_id, tx_date, label, amount, tx_type, source)
            VALUES (?, '2026-06-20', ?, -1, 'Débit', 'Manuel')
            """,
            [(account_id, f"MANUEL {index:04d}") for index in range(0, 525)],
        )

    dataset = service.build_reconciliation_dataset(START, END, account_id, "active")
    assert len(dataset["transactions"]) == 525
    assert dataset["source_counts"]["transactions_loaded"] == 525
    assert dataset["source_counts"]["transactions_displayed"] == 525


if __name__ == "__main__":
    test_issue_49_exhaustive_scope_and_uniform_filters()
    test_issue_49_default_dataset_never_silently_truncates()
    print("OK - issue #49 périmètre Rapprochements exhaustif et cohérent")
