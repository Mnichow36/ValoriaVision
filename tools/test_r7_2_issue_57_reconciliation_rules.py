from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.services.forecast_reconciliation_service import ForecastReconciliationService
from app.ui.reconciliation_page import ReconciliationRulesDialog
from tools.test_r7_2_issue_49_reconciliation_scope import add_occurrence, make_db


def transaction(db, label: str):
    with db.connect() as conn:
        return conn.execute("SELECT * FROM transactions WHERE label = ?", (label,)).fetchone()


def occurrence(db, occurrence_id: int):
    with db.connect() as conn:
        return conn.execute("SELECT * FROM forecast_occurrences WHERE id = ?", (occurrence_id,)).fetchone()


def test_issue_57_rules_are_persistent_safe_and_configurable() -> None:
    db = make_db()
    service = ForecastReconciliationService(db)
    defaults = service.rules_config()
    assert defaults == service.DEFAULT_RULES

    saved = service.save_rules_config(
        {
            "require_same_account": False,
            "require_same_direction": False,
            "date_tolerance_days": 10,
            "amount_tolerance_abs": 3.5,
            "amount_tolerance_percent": 4.0,
            "label_similarity_min": 70,
            "auto_threshold": 95,
            "review_threshold": 65,
        }
    )
    # Account and direction are mandatory safeguards even when a caller tries
    # to disable them. The remaining business parameters are persisted.
    assert saved["require_same_account"] is True
    assert saved["require_same_direction"] is True
    assert saved["date_tolerance_days"] == 10
    assert saved["amount_tolerance_abs"] == 3.5
    assert saved["amount_tolerance_percent"] == 4.0
    assert saved["label_similarity_min"] == 70
    assert service.decision_for_score(95) == "automatic"
    assert service.decision_for_score(65) == "to_review"
    assert service.decision_for_score(64) == "unmatched"

    reloaded = ForecastReconciliationService(db).rules_config()
    assert reloaded == saved

    try:
        service.save_rules_config({"auto_threshold": 70, "review_threshold": 70})
    except ValueError:
        pass
    else:
        raise AssertionError("Les seuils incohérents doivent être refusés.")

    db.set_setting("reconciliation.date_tolerance_days", "valeur-invalide")
    assert ForecastReconciliationService(db).rules_config()["date_tolerance_days"] == 5


def test_issue_57_mandatory_account_direction_and_date_gates() -> None:
    db = make_db()
    service = ForecastReconciliationService(db)
    first_account = int(db.list_accounts()[0]["id"])
    db.add_account(
        {
            "name": "Compte secondaire #57",
            "bank": "Test",
            "account_type": "Compte courant",
            "identifier": "ISSUE57-B",
            "reference_balance": 0,
            "reference_date": "2040-01-01",
            "initial_balance": 0,
            "initial_date": "2040-01-01",
            "currency": "EUR",
            "status": "Actif",
        }
    )
    second_account = max(int(row["id"]) for row in db.list_accounts())

    add_occurrence(db, first_account, day="2040-01-10", label="DATE LIMITE", amount=-100, source_id=5701)
    assert db.insert_transaction(first_account, "2040-01-17", "DATE LIMITE", "Test", -100, "Manuel")
    dated_tx = transaction(db, "DATE LIMITE")
    assert service.find_candidates(dated_tx) == []
    service.save_rules_config({"date_tolerance_days": 10, "auto_threshold": 90, "review_threshold": 60})
    assert service.find_candidates(dated_tx)

    other_account_occurrence = add_occurrence(
        db, second_account, day="2040-02-01", label="AUTRE COMPTE", amount=-50, source_id=5702
    )
    assert db.insert_transaction(first_account, "2040-02-01", "AUTRE COMPTE", "Test", -50, "Manuel")
    other_account_tx = transaction(db, "AUTRE COMPTE")
    assert all(int(item["occurrence"]["id"]) != other_account_occurrence for item in service.find_candidates(other_account_tx))

    opposite_occurrence = add_occurrence(
        db, first_account, day="2040-03-01", label="SENS OPPOSE", amount=75, source_id=5703
    )
    assert db.insert_transaction(first_account, "2040-03-01", "SENS OPPOSE", "Test", -75, "Manuel")
    opposite_tx = transaction(db, "SENS OPPOSE")
    assert all(int(item["occurrence"]["id"]) != opposite_occurrence for item in service.find_candidates(opposite_tx))

    # Direct settings tampering must not weaken the two mandatory protections.
    db.set_setting("reconciliation.require_same_account", "false")
    db.set_setting("reconciliation.require_same_direction", "false")
    hardened = ForecastReconciliationService(db)
    assert hardened.rules_config()["require_same_account"] is True
    assert hardened.rules_config()["require_same_direction"] is True
    assert hardened.compute_match_score(occurrence(db, opposite_occurrence), opposite_tx)[0] == 0


def test_issue_57_amount_label_reference_score_and_automatic_audit() -> None:
    db = make_db()
    service = ForecastReconciliationService(db)
    account_id = int(db.list_accounts()[0]["id"])

    amount_occurrence = add_occurrence(
        db, account_id, day="2040-04-01", label="MONTANT TEST", amount=-100, source_id=5704
    )
    assert db.insert_transaction(account_id, "2040-04-01", "MONTANT TEST", "Test", -103, "Manuel")
    amount_tx = transaction(db, "MONTANT TEST")
    base_score, base_reason = service.compute_match_score(occurrence(db, amount_occurrence), amount_tx)
    assert "montant à vérifier +12" in base_reason
    service.save_rules_config({"amount_tolerance_abs": 3, "auto_threshold": 90, "review_threshold": 60})
    tolerant_score, tolerant_reason = service.compute_match_score(occurrence(db, amount_occurrence), amount_tx)
    assert tolerant_score == base_score + 8
    assert "montant proche +20" in tolerant_reason

    label_occurrence = add_occurrence(
        db, account_id, day="2040-05-01", label="NETFLIX", amount=-15.99, source_id=5705
    )
    assert db.insert_transaction(account_id, "2040-05-01", "NETFLIY", "Autre", -15.99, "Manuel")
    label_tx = transaction(db, "NETFLIY")
    service.save_rules_config({"label_similarity_min": 95, "auto_threshold": 90, "review_threshold": 60})
    strict_score, strict_reason = service.compute_match_score(occurrence(db, label_occurrence), label_tx)
    assert "libellé compatible" not in strict_reason
    service.save_rules_config({"label_similarity_min": 70, "auto_threshold": 90, "review_threshold": 60})
    relaxed_score, relaxed_reason = service.compute_match_score(occurrence(db, label_occurrence), label_tx)
    assert relaxed_score == strict_score + 5, (strict_score, strict_reason, relaxed_score, relaxed_reason)
    assert "libellé compatible +5" in relaxed_reason

    automatic_occurrence = add_occurrence(
        db, account_id, day="2040-06-01", label="LOYER REF 5706", amount=-800, source_id=5706
    )
    batch_id = db.create_import_batch("issue57.csv", account_id, parser_profile="Test #57")
    assert db.insert_transaction(
        account_id,
        "2040-06-01",
        "LOYER REF 5706",
        "Logement",
        -800,
        "Import bancaire",
        batch_id,
        source_line=1,
        source_profile="Test #57",
        source_identifier="REF-5706",
    )
    result = service.reconcile_import_batch(batch_id)
    assert result["auto"] == 1
    linked = occurrence(db, automatic_occurrence)
    assert linked["status"] == "auto_matched"
    assert "référence bancaire compatible +5" in (linked["match_reason"] or "")
    with db.connect() as conn:
        tx_count_before_cancel = conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE source_identifier = 'REF-5706'"
        ).fetchone()[0]
        audit_count = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE event_type = 'reconciliation_linked' AND entity_id = ?",
            (str(automatic_occurrence),),
        ).fetchone()[0]
    assert audit_count >= 1
    assert service.cancel_match(automatic_occurrence)[0]
    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE source_identifier = 'REF-5706'"
        ).fetchone()[0] == tx_count_before_cancel


def test_issue_57_configuration_dialog_exposes_only_safe_controls() -> None:
    app = QApplication.instance() or QApplication([])
    db = make_db()
    config = ForecastReconciliationService(db).rules_config()
    dialog = ReconciliationRulesDialog(config)
    assert dialog.require_same_account.isChecked() and not dialog.require_same_account.isEnabled()
    assert dialog.require_same_direction.isChecked() and not dialog.require_same_direction.isEnabled()
    assert dialog.data()["date_tolerance_days"] == config["date_tolerance_days"]
    assert dialog.data()["auto_threshold"] == config["auto_threshold"]
    assert dialog.data()["review_threshold"] == config["review_threshold"]
    dialog.close()
    app.processEvents()


if __name__ == "__main__":
    test_issue_57_rules_are_persistent_safe_and_configurable()
    test_issue_57_mandatory_account_direction_and_date_gates()
    test_issue_57_amount_label_reference_score_and_automatic_audit()
    test_issue_57_configuration_dialog_exposes_only_safe_controls()
    print("OK - issue #57 règles de rapprochement configurables, sûres et auditables")
