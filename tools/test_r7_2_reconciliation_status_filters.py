from __future__ import annotations

from app.services.forecast_reconciliation_service import ForecastReconciliationService


def main() -> None:
    service = object.__new__(ForecastReconciliationService)

    transactions = [
        {"id": 1, "linked_occurrence_id": 101},
        {"id": 2, "linked_occurrence_id": 102},
        {"id": 3, "linked_occurrence_id": None},
        {"id": 4, "linked_occurrence_id": None},
    ]

    confirmed = [{"id": 101, "status": "confirmed", "actual_transaction_id": 1}]
    auto = [{"id": 102, "status": "auto_matched", "actual_transaction_id": 2}]
    ignored = [{"id": 103, "status": "ignored", "actual_transaction_id": None}]
    cancelled = [{"id": 104, "status": "cancelled", "actual_transaction_id": None}]
    active = [
        {"id": 105, "status": "planned", "actual_transaction_id": None},
        {"id": 106, "status": "overdue", "actual_transaction_id": None},
    ]

    assert [row["id"] for row in service._transactions_for_status(transactions, confirmed, "confirmed")] == [1]
    assert [row["id"] for row in service._transactions_for_status(transactions, auto, "auto_matched")] == [2]
    assert service._transactions_for_status(transactions, ignored, "ignored") == []
    assert service._transactions_for_status(transactions, cancelled, "cancelled") == []
    assert [row["id"] for row in service._transactions_for_status(transactions, active, "active")] == [3, 4]
    assert [row["id"] for row in service._transactions_for_status(transactions, active, "planned")] == [3, 4]
    assert [row["id"] for row in service._transactions_for_status(transactions, active, "all")] == [1, 2, 3, 4]

    print("OK - Lot 7.2 : les transactions suivent le statut des occurrences")


if __name__ == "__main__":
    main()
