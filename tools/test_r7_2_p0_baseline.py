from __future__ import annotations

import tempfile
from pathlib import Path

from app.database import Database
from app.services.categorization_rule_service import CategorizationRuleService


def make_db() -> Database:
    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    root = Path(tmp.name)
    db = Database(root / "p0_baseline.db")
    db.encrypted_db_path = root / "p0_baseline.vvdb"
    db._tmp = tmp
    db.initialize()
    return db


def transaction_by_label(db: Database, label: str):
    with db.connect() as conn:
        return conn.execute("SELECT * FROM transactions WHERE label = ?", (label,)).fetchone()


def asset_payload(name: str, category: str, asset_type: str, value: float) -> dict:
    return {
        "name": name,
        "category": category,
        "asset_type": asset_type,
        "value": value,
        "valuation_date": "2031-04-01",
        "valuation_mode": "Manuelle",
        "comment": "Recette P0",
        "status": "Actif",
    }


def clear_assets(db: Database) -> None:
    with db.connect() as conn:
        conn.execute("DELETE FROM asset_values")
        conn.execute("DELETE FROM assets")


def test_issue_11_manual_rule_application_targets_only_eligible_transactions() -> None:
    db = make_db()
    service = CategorizationRuleService(db)
    account_id = int(db.list_accounts()[0]["id"])
    category_id = service.category_id_by_name("Alimentation")
    assert category_id is not None

    rule_id = service.create_rule({
        "name": "Boulangerie débit",
        "match_field": "label",
        "match_operator": "contains",
        "match_value": "BOULANGERIE",
        "transaction_type": "Débit",
        "target_category_id": category_id,
        "confidence": 100,
        "priority": 1,
        "is_active": True,
    })
    assert rule_id > 0

    assert db.insert_transaction(account_id, "2031-04-02", "CB BOULANGERIE CENTRE", None, -8.50, "Import bancaire")
    assert db.insert_transaction(account_id, "2031-04-03", "VIREMENT BOULANGERIE", None, 8.50, "Import bancaire")
    debit = transaction_by_label(db, "CB BOULANGERIE CENTRE")
    credit = transaction_by_label(db, "VIREMENT BOULANGERIE")

    result = service.apply_rules_to_transactions([int(debit["id"]), int(credit["id"])], force=True)
    assert result == {
        "processed": 2,
        "auto": 1,
        "to_review": 0,
        "to_categorize": 1,
        "skipped": 0,
        "rules_used": 1,
    }

    categorized = db.get_transaction(int(debit["id"]))
    untouched = db.get_transaction(int(credit["id"]))
    assert categorized["category"] == "Alimentation"
    assert categorized["amount"] == -8.50
    assert categorized["tx_type"] == "Débit"
    assert categorized["categorized_by"] == "auto_rule"
    assert untouched["category"] is None
    assert untouched["amount"] == 8.50
    assert untouched["tx_type"] == "Crédit"


def test_issue_23_asset_can_be_modified_then_deleted_with_its_history() -> None:
    db = make_db()
    clear_assets(db)
    db.add_asset(asset_payload("Appartement recette", "Immobilier", "Appartement", 100_000))
    rows = db.list_assets()
    assert len(rows) == 1
    asset_id = int(rows[0]["id"])

    db.update_asset(asset_id, {
        "name": "Appartement recette modifié",
        "value": 110_000,
        "valuation_date": "2031-05-01",
        "comment": "Valeur mise à jour",
    })
    updated = db.get_asset(asset_id)
    assert updated["name"] == "Appartement recette modifié"
    assert updated["value"] == 110_000
    assert len(db.asset_history(asset_id)) == 2

    db.delete_asset(asset_id)
    assert db.get_asset(asset_id) is None
    assert db.asset_history(asset_id) == []


def test_issues_24_25_liabilities_and_net_worth_are_consistent_everywhere() -> None:
    db = make_db()
    clear_assets(db)
    db.add_asset(asset_payload("Bien immobilier", "Immobilier", "Appartement", 100_000))
    db.add_asset(asset_payload("Emprunt restant", "Dettes", "Crédit immobilier", 25_000))

    rows = {row["name"]: row for row in db.list_assets()}
    assert rows["Bien immobilier"]["value"] == 100_000
    assert rows["Emprunt restant"]["value"] == -25_000

    summary = db.asset_summary()
    assert summary["Immobilier"] == 100_000
    assert summary["Dettes"] == -25_000

    db.default_forecast_start_date = lambda: "2031-04-01"
    db.cash_forecast = lambda start_date, horizon_days, scenario: {"end_balance": 0.0}
    metrics = db.dashboard_metrics()
    assert metrics["patrimoine_net"] == 75_000

    net_evolution = db.patrimonio_evolution("net")
    asset_evolution = db.patrimonio_evolution("assets")
    liability_evolution = db.patrimonio_evolution("liabilities")
    assert net_evolution[-1]["value"] == 75_000
    assert asset_evolution[-1]["value"] == 100_000
    assert liability_evolution[-1]["value"] == 25_000


if __name__ == "__main__":
    test_issue_11_manual_rule_application_targets_only_eligible_transactions()
    test_issue_23_asset_can_be_modified_then_deleted_with_its_history()
    test_issues_24_25_liabilities_and_net_worth_are_consistent_everywhere()
    print("OK - socle P0 #11, #23, #24 et #25 couvert")
