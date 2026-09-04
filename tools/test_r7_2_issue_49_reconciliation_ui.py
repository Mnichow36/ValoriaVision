from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QApplication

from app.services.forecast_reconciliation_service import ForecastReconciliationService
from app.ui.reconciliation_page import ReconciliationPage
from tools.test_r7_2_issue_49_reconciliation_scope import add_occurrence, make_db


def kpi_value(page: ReconciliationPage, key: str) -> int:
    return int(page.kpi_buttons[key].text().rsplit("  ", 1)[1])


def test_issue_49_ui_lists_filters_and_kpis_refresh_without_restart() -> None:
    app = QApplication.instance() or QApplication([])
    db = make_db()
    account_id = int(db.list_accounts()[0]["id"])

    assert db.insert_transaction(account_id, "2030-06-10", "IMPORT UI", "Test", -10, "Import bancaire")
    assert db.insert_transaction(account_id, "2030-06-11", "MANUEL UI", "Test", -20, "Manuel")
    planned_id = add_occurrence(db, account_id, day="2030-06-12", label="PREVUE UI", amount=-30, source_id=201)
    review_id = add_occurrence(db, account_id, day="2030-06-13", label="A VERIFIER UI", amount=-40, status="to_review", source_id=202)
    add_occurrence(db, account_id, day="2030-06-14", label="FINALISEE UI", amount=-50, status="confirmed", source_id=203)
    seed_service = ForecastReconciliationService(db)
    with db.connect() as conn:
        ambiguous_tx = conn.execute("SELECT * FROM transactions WHERE label = 'IMPORT UI'").fetchone()
    candidates = seed_service.find_candidates(ambiguous_tx)
    assert candidates
    assert seed_service._save_proposal(candidates[0])

    page = ReconciliationPage(db)
    page.start_date.setDate(QDate(2030, 6, 1))
    page.end_date.setDate(QDate(2030, 6, 30))
    page.account_filter.setCurrentIndex(page.account_filter.findData(account_id))
    page.refresh()
    app.processEvents()

    assert page.transactions_table.rowCount() == 2
    assert page.occurrences_table.rowCount() == 2
    assert page.proposals_table.rowCount() == 1
    assert kpi_value(page, "active") == 2
    assert kpi_value(page, "all") == 3
    assert kpi_value(page, "planned") == 1
    assert kpi_value(page, "to_review") == 1
    assert kpi_value(page, "confirmed") == 1

    page.set_status_filter("planned")
    app.processEvents()
    assert page.occurrences_table.rowCount() == 1
    assert int(page.occurrences_table.item(0, 1).data(256)) == planned_id
    assert kpi_value(page, "all") == 3

    page.set_status_filter("to_review")
    app.processEvents()
    assert page.occurrences_table.rowCount() == 1
    assert int(page.occurrences_table.item(0, 1).data(256)) == review_id

    # A new eligible row becomes visible on refresh; no application restart.
    assert db.insert_transaction(account_id, "2030-06-15", "AJOUT SANS REDEMARRAGE", "Test", -60, "Manuel")
    page.refresh()
    app.processEvents()
    assert page.transactions_table.rowCount() == 3

    # Transactions without a coherent candidate remain stored but are excluded
    # from the active reconciliation queue by issue #82.
    with db.connect() as conn:
        conn.executemany(
            """
            INSERT INTO transactions(account_id, tx_date, label, amount, tx_type, source)
            VALUES (?, '2030-06-20', ?, -1, 'Débit', 'Manuel')
            """,
            [(account_id, f"UI BULK {index:04d}") for index in range(0, 505)],
        )
    page.refresh()
    app.processEvents()
    assert page.transactions_table.rowCount() == 3
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] >= 508

    page.close()


def test_reconciliation_target_layout_statuses_and_selected_pair_proposal() -> None:
    app = QApplication.instance() or QApplication([])
    db = make_db()
    account_id = int(db.list_accounts()[0]["id"])
    assert db.insert_transaction(account_id, "2030-06-12", "NETFLIX", "Abonnement", -15.99, "Manuel")
    add_occurrence(db, account_id, day="2030-06-12", label="Netflix", amount=-15.99, source_id=301)

    page = ReconciliationPage(db)
    page.resize(1600, 950)
    page.show()
    page.start_date.setDate(QDate(2030, 6, 1))
    page.end_date.setDate(QDate(2030, 6, 30))
    page.account_filter.setCurrentIndex(page.account_filter.findData(account_id))
    page.refresh()
    app.processEvents()

    assert page.main_splitter.orientation() == Qt.Vertical
    assert page.top_splitter.orientation() == Qt.Horizontal
    assert page.bottom_splitter.orientation() == Qt.Horizontal
    assert page.transactions_table.horizontalScrollBar().maximum() == 0
    assert page.occurrences_table.horizontalScrollBar().maximum() == 0
    assert all(button.height() >= 36 for button in page.kpi_buttons.values())
    assert all(button.text().strip() and button.text().rsplit("  ", 1)[-1].isdigit() for button in page.kpi_buttons.values())

    page.transactions_table.selectRow(0)
    page.occurrences_table.selectRow(0)
    app.processEvents()
    assert page.proposals_table.rowCount() == 1
    assert "Proposition calculée" in page.proposal_feedback.text()
    assert page.selected_proposal_id() is not None
    page.close()


if __name__ == "__main__":
    test_issue_49_ui_lists_filters_and_kpis_refresh_without_restart()
    test_reconciliation_target_layout_statuses_and_selected_pair_proposal()
    print("OK - issue #49 interface, filtres, KPI et rafraîchissement sans redémarrage")
