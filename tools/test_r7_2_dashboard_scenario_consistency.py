from __future__ import annotations

from app.database import Database


def main() -> None:
    db = object.__new__(Database)

    db.default_forecast_start_date = lambda: "2026-08-27"
    db.sample_forecast_points = lambda labels, balances, horizon_days: (labels, balances)

    forecasts = {
        "Prudent": {
            "labels": ["27/08", "26/10"],
            "balances": [10000.0, 8200.0],
            "starting_cash": 10000.0,
            "alert": "Vigilance",
            "alert_level": "warning",
            "alert_detail": "Prudent",
            "min_balance": 8000.0,
            "end_balance": 8200.0,
            "total_in": 4500.0,
            "total_out": 6300.0,
            "events": [{"id": 1}],
        },
        "Réaliste": {
            "labels": ["27/08", "26/10"],
            "balances": [10000.0, 9000.0],
            "starting_cash": 10000.0,
            "alert": "Aucune alerte critique",
            "alert_level": "ok",
            "alert_detail": "Réaliste",
            "min_balance": 8800.0,
            "end_balance": 9000.0,
            "total_in": 5000.0,
            "total_out": 6000.0,
            "events": [{"id": 1}, {"id": 2}],
        },
        "Optimiste": {
            "labels": ["27/08", "26/10"],
            "balances": [10000.0, 9800.0],
            "starting_cash": 10000.0,
            "alert": "Aucune alerte critique",
            "alert_level": "ok",
            "alert_detail": "Optimiste",
            "min_balance": 9600.0,
            "end_balance": 9800.0,
            "total_in": 5500.0,
            "total_out": 5700.0,
            "events": [{"id": 1}],
        },
    }

    def fake_cash_forecast(start_date, horizon_days, scenario, account_id=None):
        assert start_date == "2026-08-27"
        assert horizon_days == 60
        assert account_id is None
        return forecasts[scenario]

    db.cash_forecast = fake_cash_forecast

    report = Database.dashboard_forecast_chart(db, 60)

    assert report["start_date"] == "2026-08-27"
    assert report["end_balance_by_scenario"] == {
        "Optimiste": 9800.0,
        "Réaliste": 9000.0,
        "Prudent": 8200.0,
    }
    assert report["end_balance"] == 9000.0
    assert report["min_balance"] == 8800.0
    assert report["alert"] == "Aucune alerte critique"
    assert report["alert_detail"] == "Réaliste"

    # La référence reste bien encadrée par les deux variantes.
    assert report["end_balance_by_scenario"]["Prudent"] < report["end_balance_by_scenario"]["Réaliste"]
    assert report["end_balance_by_scenario"]["Réaliste"] < report["end_balance_by_scenario"]["Optimiste"]

    print("OK - Lot 6.2 : Dashboard et Prévisionnel partagent les trois scénarios standards")


if __name__ == "__main__":
    main()
