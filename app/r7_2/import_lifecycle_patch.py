from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_PATCHED = False


@dataclass(frozen=True)
class ImportCancellationResult:
    batch_id: int
    status: str
    deleted_transactions: int
    message: str


class ImportCancellationError(RuntimeError):
    pass


def apply_r7_2_import_lifecycle_patch() -> None:
    """Lot 4 — controlled import cancellation and synchronized cleanup.

    Scope:
    - cancel only transactions that belong to the selected import batch;
    - never delete manual transactions, even if an old migration accidentally
      linked them to a batch;
    - reset forecast occurrences linked to deleted imported transactions;
    - delete categorization logs linked to the batch / deleted transactions;
    - mark the import batch as cancelled and audit the action;
    - keep the historical `cancel_import_batch()` API returning an integer so
      existing UI code remains compatible.
    """
    global _PATCHED
    if _PATCHED:
        return

    from app.database import Database

    original_apply_migrations = Database.apply_migrations

    def apply_migrations_with_import_lifecycle(self, conn):
        original_apply_migrations(self, conn)
        self.ensure_columns(conn, "import_batches", {
            "canceled_deleted_count": "INTEGER NOT NULL DEFAULT 0",
            "canceled_reason": "TEXT",
            "updated_at": "TEXT",
        })
        conn.execute("UPDATE import_batches SET status = 'Importé' WHERE status IS NULL OR status = ''")

    def cancel_import_batch_result(self, batch_id: int, reason: str | None = None) -> ImportCancellationResult:
        reason = (reason or "Annulation utilisateur").strip() or "Annulation utilisateur"
        with self.connect() as conn:
            batch = conn.execute(
                "SELECT * FROM import_batches WHERE id = ?",
                (batch_id,),
            ).fetchone()
            if not batch:
                return ImportCancellationResult(batch_id, "not_found", 0, "Lot d'import introuvable.")
            if batch["status"] == "Annulé":
                return ImportCancellationResult(batch_id, "already_cancelled", 0, "Lot d'import déjà annulé.")

            imported_rows = list(conn.execute(
                """
                SELECT id FROM transactions
                WHERE import_batch_id = ?
                  AND source <> 'Manuel'
                ORDER BY id
                """,
                (batch_id,),
            ))
            transaction_ids = [int(row["id"]) for row in imported_rows]

            manual_linked = conn.execute(
                """
                SELECT COUNT(*) AS c FROM transactions
                WHERE import_batch_id = ?
                  AND source = 'Manuel'
                """,
                (batch_id,),
            ).fetchone()["c"]

            deleted = 0
            if transaction_ids:
                placeholders = ",".join("?" for _ in transaction_ids)

                conn.execute(
                    f"DELETE FROM categorization_rule_logs WHERE import_batch_id = ? OR transaction_id IN ({placeholders})",
                    [batch_id, *transaction_ids],
                )

                conn.execute(
                    f"""
                    UPDATE forecast_occurrences
                    SET actual_transaction_id = NULL,
                        actual_date = NULL,
                        actual_amount = NULL,
                        amount_delta = NULL,
                        match_confidence = NULL,
                        match_reason = NULL,
                        match_type = NULL,
                        status = CASE
                            WHEN expected_date < date('now') THEN 'overdue'
                            ELSE 'planned'
                        END,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE actual_transaction_id IN ({placeholders})
                    """,
                    transaction_ids,
                )

                cur = conn.execute(
                    f"DELETE FROM transactions WHERE id IN ({placeholders}) AND source <> 'Manuel'",
                    transaction_ids,
                )
                deleted = int(cur.rowcount or 0)
            else:
                conn.execute("DELETE FROM categorization_rule_logs WHERE import_batch_id = ?", (batch_id,))

            conn.execute(
                """
                UPDATE import_batches
                SET status = 'Annulé',
                    canceled_at = CURRENT_TIMESTAMP,
                    canceled_deleted_count = ?,
                    canceled_reason = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (deleted, reason, batch_id),
            )

            try:
                self.audit_event(
                    conn,
                    "import_batch_cancelled",
                    "import_batches",
                    str(batch_id),
                    f"Lot d'import annulé : {deleted} transaction(s) supprimée(s).",
                    {
                        "batch_id": batch_id,
                        "file_name": batch["file_name"],
                        "account_id": batch["account_id"],
                        "deleted_transactions": deleted,
                        "manual_linked_transactions_preserved": int(manual_linked or 0),
                        "reason": reason,
                    },
                )
            except Exception:
                # Audit must not make cancellation fail after financial cleanup.
                pass

        self.seal_database_to_encrypted_vault()
        message = f"{deleted} transaction(s) importée(s) supprimée(s)."
        if manual_linked:
            message += f" {int(manual_linked)} transaction(s) manuelle(s) liée(s) préservée(s)."
        return ImportCancellationResult(batch_id, "cancelled", deleted, message)

    def cancel_import_batch_compat(self, batch_id: int) -> int:
        return int(self.cancel_import_batch_result(batch_id).deleted_transactions)

    def import_batch_cancellation_audit(self, batch_id: int) -> list[Any]:
        with self.connect() as conn:
            return list(conn.execute(
                """
                SELECT * FROM audit_log
                WHERE event_type = 'import_batch_cancelled'
                  AND entity = 'import_batches'
                  AND entity_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (str(batch_id),),
            ))

    Database.apply_migrations = apply_migrations_with_import_lifecycle
    Database.cancel_import_batch_result = cancel_import_batch_result
    Database.cancel_import_batch = cancel_import_batch_compat
    Database.import_batch_cancellation_audit = import_batch_cancellation_audit

    _PATCHED = True
