from __future__ import annotations

from pathlib import Path
import tempfile

from app.database import Database


def test_recurring_end_date_and_one_off_event() -> None:
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
        db.add_recurring_item(recurring_payload)
        rows = [r for r in db.list_recurring_items(active_only=False) if r["name"] == "Lot 5 Loyer test"]
        assert len(rows) == 1
        assert rows[0]["end_date"] == "2026-12-05"
        assert rows[0]["amount"] < 0, "La catégorie Logement doit normaliser le montant en dépense."

        one_off_payload = {
            "account_id": account_id,
            "name": "Lot 5 Prime ponctuelle",
            "category": "Revenus",
            "amount": 500.0,
            "frequency": "Ponctuel",
            "next_date": "2026-10-10",
            "end_date": "2026-10-10",
            "scenario": "Réaliste",
            "status": "Actif",
        }
        db.add_recurring_item(one_off_payload)
        rows = [r for r in db.list_recurring_items(active_only=False) if r["name"] == "Lot 5 Prime ponctuelle"]
        assert len(rows) == 1
        assert rows[0]["frequency"] == "Ponctuel"
        assert rows[0]["end_date"] == "2026-10-10"
        assert rows[0]["amount"] > 0, "La catégorie Revenus doit normaliser le montant en recette."


if __name__ == "__main__":
    test_recurring_end_date_and_one_off_event()
    print("OK — Prévisionnel / récurrences Lot 5")
