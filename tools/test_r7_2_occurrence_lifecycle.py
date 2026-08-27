from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from app.services.forecast_reconciliation_service import ForecastReconciliationService


class FakeDatabase:
    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE forecast_occurrences (
                id INTEGER PRIMARY KEY,
                expected_date TEXT NOT NULL,
                status TEXT NOT NULL,
                actual_transaction_id INTEGER,
                actual_date TEXT,
                actual_amount REAL,
                amount_delta REAL,
                match_confidence INTEGER,
                match_reason TEXT,
                match_type TEXT,
                ignored_reason TEXT,
                cancelled_reason TEXT,
                cancelled_at TEXT,
                reactivated_at TEXT,
                deleted_at TEXT,
                updated_at TEXT
            );
            """
        )
        self.conn.executemany(
            """
            INSERT INTO forecast_occurrences(
                id, expected_date, status, actual_transaction_id, ignored_reason
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                (1, "2099-01-01", "planned", None, None),
                (2, "2000-01-01", "ignored", None, "Test ignorance"),
                (3, "2099-02-01", "confirmed", 99, None),
            ],
        )
        self.conn.commit()

    @contextmanager
    def connect(self):
        yield self.conn


def row(db, occurrence_id: int):
    return db.conn.execute(
        "SELECT * FROM forecast_occurrences WHERE id = ?",
        (occurrence_id,),
    ).fetchone()


def main() -> None:
    db = FakeDatabase()
    service = ForecastReconciliationService(db)

    ok, message = service.cancel_occurrence(1, "Opération devenue sans objet")
    assert ok == 1, message
    current = row(db, 1)
    assert current["status"] == "cancelled"
    assert current["cancelled_reason"] == "Opération devenue sans objet"
    assert current["cancelled_at"] is not None

    ok, message = service.reactivate_occurrence(1)
    assert ok == 1, message
    current = row(db, 1)
    assert current["status"] == "planned"
    assert current["reactivated_at"] is not None
    assert current["cancelled_reason"] == "Opération devenue sans objet"

    ok, message = service.reactivate_occurrence(2)
    assert ok == 1, message
    current = row(db, 2)
    assert current["status"] == "overdue"
    assert current["ignored_reason"] == "Test ignorance"

    ok, _ = service.cancel_occurrence(3, "Ne doit pas passer")
    assert ok == 0
    assert row(db, 3)["status"] == "confirmed"

    ok, message = service.ignore_occurrence(1, "Ignorée après réactivation")
    assert ok == 1, message
    assert row(db, 1)["status"] == "ignored"

    print("OK - Lot 7.2 : annulation, ignorance et remise à traiter validées")


if __name__ == "__main__":
    main()
