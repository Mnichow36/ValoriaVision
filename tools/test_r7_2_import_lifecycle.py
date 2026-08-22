from __future__ import annotations

import tempfile
from pathlib import Path

from app.database import Database
from app.r7_2.import_integrity import apply_r7_2_import_integrity_patch
from app.r7_2.import_lifecycle_patch import apply_r7_2_import_lifecycle_patch


SG_LABEL = "CARTE X6425 18/06 — SC-INTERMARCHE"


def make_db() -> Database:
    tmp = tempfile.TemporaryDirectory()
    path = Path(tmp.name) / "lot4_import_lifecycle.db"
    db = Database(path)
    db._tmp = tmp  # keep temp directory alive during test
    apply_r7_2_import_integrity_patch()
    apply_r7_2_import_lifecycle_patch()
    db.initialize()
    return db


def test_cancel_import_batch_preserves_manual_transactions_and_allows_reimport():
    db = make_db()

    account_id = 1
    batch_id = db.create_import_batch("00050384255.csv", account_id, parser_profile="Société Générale CSV")

    ok_1 = db.insert_transaction(
        account_id,
        "2026-06-19",
        SG_LABEL,
        None,
        -26.58,
        "Import bancaire",
        batch_id,
        currency="EUR",
        source_line=4,
        source_profile="Société Générale CSV",
        raw_payload='{"reference":"A"}',
        source_identifier="SG-LINE-A",
    )
    ok_2 = db.insert_transaction(
        account_id,
        "2026-06-20",
        "VIREMENT TEST",
        None,
        100.00,
        "Import bancaire",
        batch_id,
        currency="EUR",
        source_line=5,
        source_profile="Société Générale CSV",
        raw_payload='{"reference":"B"}',
        source_identifier="SG-LINE-B",
    )
    db.update_import_batch(batch_id, 2, 0, 0)

    # Simulate a historical bad link: a manual transaction must never be deleted
    # by import cancellation, even if import_batch_id is accidentally set.
    db.insert_transaction(account_id, "2026-06-21", "MANUEL PRESERVE", "Loisirs", 42.0, "Manuel")
    with db.connect() as conn:
        manual_id = conn.execute("SELECT id FROM transactions WHERE label = 'MANUEL PRESERVE'").fetchone()["id"]
        conn.execute("UPDATE transactions SET import_batch_id = ? WHERE id = ?", (batch_id, manual_id))

    assert ok_1 is True
    assert ok_2 is True

    result = db.cancel_import_batch_result(batch_id)
    assert result.status == "cancelled"
    assert result.deleted_transactions == 2

    with db.connect() as conn:
        imported_left = conn.execute("SELECT COUNT(*) AS c FROM transactions WHERE source <> 'Manuel' AND import_batch_id = ?", (batch_id,)).fetchone()["c"]
        manual_left = conn.execute("SELECT COUNT(*) AS c FROM transactions WHERE id = ?", (manual_id,)).fetchone()["c"]
        batch = conn.execute("SELECT * FROM import_batches WHERE id = ?", (batch_id,)).fetchone()
    assert imported_left == 0
    assert manual_left == 1
    assert batch["status"] == "Annulé"
    assert batch["canceled_deleted_count"] == 2

    audit = db.import_batch_cancellation_audit(batch_id)
    assert audit, "L'annulation doit être tracée dans audit_log"

    # Reimport after cancellation must be possible because original signatures
    # were removed with the imported transactions.
    second_batch_id = db.create_import_batch("00050384255.csv", account_id, parser_profile="Société Générale CSV")
    ok_reimport = db.insert_transaction(
        account_id,
        "2026-06-19",
        SG_LABEL,
        None,
        -26.58,
        "Import bancaire",
        second_batch_id,
        currency="EUR",
        source_line=4,
        source_profile="Société Générale CSV",
        raw_payload='{"reference":"A"}',
        source_identifier="SG-LINE-A",
    )
    assert ok_reimport is True

    # A second import without cancellation must be detected as duplicate.
    third_batch_id = db.create_import_batch("00050384255.csv", account_id, parser_profile="Société Générale CSV")
    ok_duplicate = db.insert_transaction(
        account_id,
        "2026-06-19",
        SG_LABEL,
        None,
        -26.58,
        "Import bancaire",
        third_batch_id,
        currency="EUR",
        source_line=4,
        source_profile="Société Générale CSV",
        raw_payload='{"reference":"A"}',
        source_identifier="SG-LINE-A",
    )
    assert ok_duplicate is False


if __name__ == "__main__":
    test_cancel_import_batch_preserves_manual_transactions_and_allows_reimport()
    print("OK — cycle de vie imports Lot 4")
