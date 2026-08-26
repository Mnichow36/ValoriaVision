from __future__ import annotations

from contextlib import contextmanager

from app.database import Database


class FakeConnection:
    def execute(self, sql, params=()):
        normalized = " ".join(str(sql).split())
        if "FROM transactions t" in normalized:
            return []
        if "FROM forecast_occurrences" in normalized:
            return []
        raise AssertionError(f"Requête inattendue : {normalized}")


class FakeDatabase:
    add_period = staticmethod(Database.add_period)

    @contextmanager
    def connect(self):
        yield FakeConnection()

    def list_recurring_items(self, active_only=True):
        return [
            {
                "id": 1,
                "account_id": 10,
                "account_name": "Compte test",
                "name": "Ancienne récurrence optimiste",
                "category": "Logement",
                "amount": -1000.0,
                "frequency": "Mensuel",
                "next_date": "2026-09-01",
                "end_date": None,
                "scenario": "Optimiste",
                "status": "Actif",
            }
        ]


def main() -> None:
    db = FakeDatabase()

    realiste = Database.forecast_events(
        db,
        start_date="2026-08-27",
        horizon_days=40,
        scenario="Réaliste",
        account_id=10,
    )
    prudent = Database.forecast_events(
        db,
        start_date="2026-08-27",
        horizon_days=40,
        scenario="Prudent",
        account_id=10,
    )
    optimiste = Database.forecast_events(
        db,
        start_date="2026-08-27",
        horizon_days=40,
        scenario="Optimiste",
        account_id=10,
    )

    for events in (realiste, prudent, optimiste):
        assert len(events) == 2
        assert all(event["name"] == "Ancienne récurrence optimiste" for event in events)
        assert all(event["scenario"] == "Tous" for event in events)

    print("OK - Lot 6.2 : aucune récurrence standard n'est filtrée par son ancien scénario")


if __name__ == "__main__":
    main()
