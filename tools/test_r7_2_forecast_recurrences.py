from __future__ import annotations

from pathlib import Path
import tempfile

from app.database import Database
from app.r7_2.forecast_recurrences_patch import apply_r7_2_forecast_recurrences_patch


def test_recurring_end_date_and_one_off_event() -> None:
    apply_r7_2_forecast_recurrences_patch()
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "lot5_forecast.db")
        db.initialize()

        accounts = db.list_accounts()
        assert accounts, "La base de test doit contenir au moins un compte."
        account_id = int(accounts[0]["id"])

        recurring_payload = {
            "account_id": account_id,
            "name": "Lot 5 Loyer test",
            "category": "Logement",
            "amount": 1200.0,
            "frequency": "Mensuel",
            "next_date": "2026-09-05",
            "end_date": "2026-12-05",
            "scenario": "Réaliste",
            "status": "Actif",
        }
        recurring_id = db.add_forecast_recurring_item_lot5(recurring_payload)
        rows = [r for r in db.list_recurring_items(active_only=False) if r["id"] == recurring_id]
        assert len(rows) == 1
        assert rows[0]["end_date"] == "2026-12-05"
        assert rows[0]["amount"] < 0, "La catégorie Logement doit normaliser le montant en dépense."

        update_payload = {
            "account_id": account_id,
            "name": "Lot 5 Loyer modifié",
            "category": "Logement",
            "amount": 1300.0,
            "frequency": "Mensuel",
            "next_date": "2026-09-06",
            "end_date": "2027-01-06",
            "scenario": "Réaliste",
            "status": "Actif",
        }
        db.update_forecast_recurring_item_lot5(recurring_id, update_payload)
        row = db.get_recurring_item(recurring_id)
        assert row is not None
        assert row["name"] == "Lot 5 Loyer modifié"
        assert row["next_date"] == "2026-09-06"
        assert row["end_date"] == "2027-01-06"
        assert float(row["amount"]) == -1300.0

        one_off_payload = {
            "account_id": account_id,
            "name": "Lot 5 Prime ponctuelle",
            "category": "Revenus",
            "amount": 500.0,
            "frequency": "Ponctuel",
            "next_date": "2026-10-10",
            "end_date": None,
            "scenario": "Réaliste",
            "status": "Actif",
        }
        one_off_id = db.add_forecast_recurring_item_lot5(one_off_payload)
        row = db.get_recurring_item(one_off_id)
        assert row is not None
        assert row["frequency"] == "Ponctuel"
        assert row["end_date"] == "2026-10-10"
        assert row["amount"] > 0, "La catégorie Revenus doit normaliser le montant en recette."

        db.delete_forecast_recurring_item_lot5(one_off_id)
        assert db.get_recurring_item(one_off_id) is None


if __name__ == "__main__":
    test_recurring_end_date_and_one_off_event()
    print("OK — Prévisionnel / récurrences Lot 5")
