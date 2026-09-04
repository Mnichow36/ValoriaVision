from __future__ import annotations

import tempfile
from pathlib import Path

from app.database import Database
from app.r7_2.forecast_recurrences_patch import apply_r7_2_forecast_recurrences_patch
from app.services.forecast_reconciliation_service import ForecastReconciliationService


def make_db() -> Database:
    apply_r7_2_forecast_recurrences_patch()
    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    root = Path(tmp.name)
    db = Database(root / "forecast_lifecycle.db")
    db.encrypted_db_path = root / "forecast_lifecycle.vvdb"
    db._tmp = tmp
    db.initialize()
    with db.connect() as conn:
        conn.execute("DELETE FROM forecast_reconciliation_proposals")
        conn.execute("DELETE FROM forecast_reconciliation_links")
        conn.execute("DELETE FROM forecast_occurrences")
        conn.execute("DELETE FROM recurring_items")
    return db


def recurring_payload(account_id: int, name: str, frequency: str, next_date: str, end_date: str | None) -> dict:
    return {
        "account_id": account_id,
        "name": name,
        "category": "Logement",
        "amount": 100.0,
        "frequency": frequency,
        "next_date": next_date,
        "end_date": end_date,
        "scenario": "Tous",
        "status": "Actif",
    }


def test_issues_8_12_one_off_and_recurring_occurrences_are_persistent() -> None:
    db = make_db()
    service = ForecastReconciliationService(db)
    account_id = int(db.list_accounts()[0]["id"])

    recurring_id = db.add_forecast_recurring_item_lot5(
        recurring_payload(account_id, "LOYER RECETTE", "Mensuel", "2031-05-01", "2031-07-01")
    )
    one_off_id = db.add_forecast_recurring_item_lot5(
        recurring_payload(account_id, "DEPENSE PONCTUELLE", "Ponctuel", "2031-05-10", None)
    )
    assert db.get_recurring_item(recurring_id)["amount"] == -100.0
    assert db.get_recurring_item(one_off_id)["end_date"] == "2031-05-10"

    generated = service.generate_occurrences("2031-05-01", "2031-07-31")
    assert generated == 4
    with db.connect() as conn:
        recurring_dates = [
            row["expected_date"]
            for row in conn.execute(
                "SELECT expected_date FROM forecast_occurrences WHERE source_id = ? ORDER BY expected_date",
                (recurring_id,),
            )
        ]
        one_off_dates = [
            row["expected_date"]
            for row in conn.execute(
                "SELECT expected_date FROM forecast_occurrences WHERE source_id = ? ORDER BY expected_date",
                (one_off_id,),
            )
        ]
    assert recurring_dates == ["2031-05-01", "2031-06-01", "2031-07-01"]
    assert one_off_dates == ["2031-05-10"]

    assert service.generate_occurrences("2031-05-01", "2031-07-31") == 0
    assert len(service.list_occurrences("all", "2031-05-01", "2031-07-31", account_id)) == 4


def test_issue_17_overdue_transition_and_counters_are_idempotent() -> None:
    db = make_db()
    service = ForecastReconciliationService(db)
    account_id = int(db.list_accounts()[0]["id"])
    db.add_forecast_recurring_item_lot5(
        recurring_payload(account_id, "ECHEANCE PASSEE", "Ponctuel", "2031-05-01", None)
    )
    db.add_forecast_recurring_item_lot5(
        recurring_payload(account_id, "ECHEANCE FUTURE", "Ponctuel", "2031-06-01", None)
    )
    assert service.generate_occurrences("2031-05-01", "2031-06-30") == 2

    assert service.mark_overdue("2031-05-15") == 1
    assert service.mark_overdue("2031-05-15") == 0
    dataset = service.build_reconciliation_dataset("2031-05-01", "2031-06-30", account_id, "all")
    assert dataset["summary"]["overdue"] == 1
    assert dataset["summary"]["planned"] == 1
    assert dataset["summary"]["all"] == 2

    overdue = service.list_occurrences("overdue", "2031-05-01", "2031-06-30", account_id)
    planned = service.list_occurrences("planned", "2031-05-01", "2031-06-30", account_id)
    assert [row["expected_label"] for row in overdue] == ["ECHEANCE PASSEE"]
    assert [row["expected_label"] for row in planned] == ["ECHEANCE FUTURE"]


if __name__ == "__main__":
    test_issues_8_12_one_off_and_recurring_occurrences_are_persistent()
    test_issue_17_overdue_transition_and_counters_are_idempotent()
    print("OK - porte Prévisionnel #8, #12 et #17 couverte")
