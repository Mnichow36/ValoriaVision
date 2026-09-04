from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.database import Database
from app.ui.dashboard_page import DashboardPage
from app.ui.transactions_page import TransactionDialog


def make_db() -> Database:
    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db = Database(Path(tmp.name) / "regressions_2_78.db")
    db.encrypted_db_path = Path(tmp.name) / "regressions_2_78.vvdb"
    db._tmp = tmp
    db.initialize()
    return db


def transaction_by_label(db: Database, label: str):
    with db.connect() as conn:
        return conn.execute("SELECT * FROM transactions WHERE label = ?", (label,)).fetchone()


def test_issue_2_dialog_preserves_debit_and_allows_repeated_edits() -> None:
    app = QApplication.instance() or QApplication([])
    db = make_db()
    account_id = int(db.list_accounts()[0]["id"])
    label = "REGRESSION ISSUE 2 DIALOG"
    assert db.insert_transaction(account_id, "2031-01-10", label, "Alimentation", -65.40, "Import bancaire")

    row = transaction_by_label(db, label)
    dialog = TransactionDialog(db.list_accounts(), db.category_names(), row=row)
    assert dialog.direction.currentText() == "Débit"
    assert dialog.amount.value() == 65.40
    first_edit = dialog.data()
    assert first_edit["tx_type"] == "Débit"
    assert first_edit["amount"] == -65.40
    first_edit["label"] = f"{label} MODIFIEE"
    db.update_transaction(int(row["id"]), first_edit)
    dialog.close()

    updated = db.get_transaction(int(row["id"]))
    assert updated["amount"] == -65.40
    assert updated["tx_type"] == "Débit"

    second_dialog = TransactionDialog(db.list_accounts(), db.category_names(), row=updated)
    assert second_dialog.direction.currentText() == "Débit"
    second_dialog.amount.setValue(70.25)
    db.update_transaction(int(row["id"]), second_dialog.data())
    second_dialog.close()
    app.processEvents()

    updated_again = db.get_transaction(int(row["id"]))
    assert updated_again["amount"] == -70.25
    assert updated_again["tx_type"] == "Débit"


def test_issue_2_preserves_explicit_direction_for_every_transaction_origin() -> None:
    db = make_db()
    account_id = int(db.list_accounts()[0]["id"])

    for index, source in enumerate(("Manuel", "Import bancaire", "Démo"), start=1):
        label = f"REGRESSION ISSUE 2 {source}"
        assert db.insert_transaction(
            account_id,
            f"2031-02-0{index}",
            label,
            "Alimentation",
            -10.0,
            source,
        )
        row = transaction_by_label(db, label)
        transaction_id = int(row["id"])
        db.update_transaction(transaction_id, {"amount": 25.0, "tx_type": "Débit", "label": label})
        debit = db.get_transaction(transaction_id)
        assert debit["amount"] == -25.0, source
        assert debit["tx_type"] == "Débit", source
        assert debit["source"] == source, source

        db.update_transaction(transaction_id, {"amount": 30.0, "tx_type": "Crédit", "label": label})
        credit = db.get_transaction(transaction_id)
        assert credit["amount"] == 30.0, source
        assert credit["tx_type"] == "Crédit", source
        assert credit["source"] == source, source


def test_issue_2_new_manual_transaction_respects_explicit_direction() -> None:
    db = make_db()
    account_id = int(db.list_accounts()[0]["id"])
    assert db.insert_transaction(
        account_id,
        "2031-03-01",
        "CREDIT EXPLICITE",
        "Alimentation",
        12.34,
        "Manuel",
        respect_amount_sign=True,
    )
    row = transaction_by_label(db, "CREDIT EXPLICITE")
    assert row["amount"] == 12.34
    assert row["tx_type"] == "Crédit"


def test_issue_78_dashboard_greeting_is_neutral_and_no_demo_firstname_remains() -> None:
    assert DashboardPage.GREETING_TITLE == "Bonjour"
    app_root = Path(__file__).resolve().parents[1] / "app"
    forbidden = "fran" + "çois"
    offenders = [
        path.relative_to(app_root).as_posix()
        for path in app_root.rglob("*.py")
        if forbidden.casefold() in path.read_text(encoding="utf-8").casefold()
    ]
    assert offenders == []


if __name__ == "__main__":
    test_issue_2_dialog_preserves_debit_and_allows_repeated_edits()
    test_issue_2_preserves_explicit_direction_for_every_transaction_origin()
    test_issue_2_new_manual_transaction_respects_explicit_direction()
    test_issue_78_dashboard_greeting_is_neutral_and_no_demo_firstname_remains()
    print("OK - régressions #2 et #78 couvertes")
