from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date

from app.services.forecast_reconciliation_service import ForecastReconciliationService


class FakeDatabase:
    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self._prepare()

    def _prepare(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE accounts (
                id INTEGER PRIMARY KEY,
                name TEXT,
                bank TEXT,
                status TEXT
            );

            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY,
                account_id INTEGER NOT NULL,
                tx_date TEXT NOT NULL,
                label TEXT,
                category TEXT,
                amount REAL NOT NULL,
                source TEXT,
                deleted_at TEXT
            );

            CREATE TABLE forecast_occurrences (
                id INTEGER PRIMARY KEY,
                actual_transaction_id INTEGER,
                expected_label TEXT,
                status TEXT,
                deleted_at TEXT
            );
            """
        )
        self.conn.execute(
            "INSERT INTO accounts(id, name, bank, status) VALUES (1, 'Compte courant', 'Crédit Agricole', 'Actif')"
        )
        rows = [
            (1, 1, "2026-08-10", "Import SG", "Alimentation", -10.0, "Import bancaire", None),
            (2, 1, "2026-08-11", "Manuelle", "Loisirs", -20.0, "Manuel", None),
            (3, 1, "2026-08-12", "Historique démo", "Logement", -30.0, "Démo", None),
            (4, 1, "2026-08-13", "Ancienne origine", "Énergie", -40.0, "Import CSV historique", None),
            (5, 1, "2026-08-14", "Origine vide", "Santé", -50.0, None, None),
            (6, 1, "2026-08-15", "Supprimée", "Santé", -60.0, "Manuel", "2026-08-20"),
        ]
        self.conn.executemany(
            """
            INSERT INTO transactions(
                id, account_id, tx_date, label, category, amount, source, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self.conn.commit()

    @contextmanager
    def connect(self):
        yield self.conn


def main() -> None:
    db = FakeDatabase()
    service = ForecastReconciliationService(db)

    rows = service._eligible_transactions(
        start=date(2026, 8, 1),
        end=date(2026, 8, 31),
        account_id=1,
    )

    ids = [int(row["id"]) for row in rows]
    sources = {row["source"] for row in rows}

    assert ids == [5, 4, 3, 2, 1]
    assert "Import bancaire" in sources
    assert "Manuel" in sources
    assert "Démo" in sources
    assert "Import CSV historique" in sources
    assert None in sources
    assert 6 not in ids

    print("OK - Lot 7.1 : toutes les transactions réelles sont éligibles indépendamment de leur origine")


if __name__ == "__main__":
    main()
