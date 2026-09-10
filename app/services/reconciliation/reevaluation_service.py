from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from app.services.reconciliation.database_service import qualify_and_persist_transaction
from app.services.reconciliation.persistence_service import PersistedQualification
from app.services.reconciliation.rules import ReconciliationRules


@dataclass(frozen=True)
class ReevaluationSummary:
    transaction_ids: tuple[int, ...]
    results: tuple[PersistedQualification, ...]


def _event(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: int,
    event_type: str,
    reason: str,
    payload: dict[str, object],
) -> None:
    from uuid import uuid4

    conn.execute(
        """
        INSERT INTO reconciliation_events(
            uuid, entity_type, entity_id, event_type, reason, payload_json
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid4()),
            entity_type,
            entity_id,
            event_type,
            reason,
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
        ),
    )


def _invalidate_transaction_decision(
    conn: sqlite3.Connection,
    transaction_id: int,
    reason: str,
) -> None:
    reconciliations = conn.execute(
        """
        SELECT DISTINCT r.id, r.status
        FROM reconciliations r
        JOIN reconciliation_members rm ON rm.reconciliation_id = r.id
        WHERE rm.transaction_id = ?
          AND r.status IN ('automatic', 'confirmed')
        ORDER BY r.id
        """,
        (transaction_id,),
    ).fetchall()
    for row in reconciliations:
        reconciliation_id = int(row["id"])
        conn.execute(
            """
            UPDATE reconciliations
            SET status = 'cancelled',
                cancelled_at = CURRENT_TIMESTAMP,
                cancel_reason = ?
            WHERE id = ? AND status IN ('automatic', 'confirmed')
            """,
            (reason, reconciliation_id),
        )
        _event(
            conn,
            "reconciliation",
            reconciliation_id,
            "reconciliation_invalidated",
            reason,
            {"transaction_id": transaction_id, "previous_status": row["status"]},
        )


def reevaluate_transaction(
    conn: sqlite3.Connection,
    transaction_id: int,
    rules: ReconciliationRules | None = None,
    *,
    reason: str = "Source de rapprochement modifiée",
) -> PersistedQualification:
    """Invalidate the previous decision and atomically calculate a new one."""
    conn.execute("SAVEPOINT r8_reevaluate_transaction")
    try:
        previous = conn.execute(
            """
            SELECT status, reason
            FROM transaction_reconciliation_state
            WHERE transaction_id = ?
            """,
            (transaction_id,),
        ).fetchone()
        _invalidate_transaction_decision(conn, transaction_id, reason)
        result = qualify_and_persist_transaction(
            conn, transaction_id, rules or ReconciliationRules()
        )
        _event(
            conn,
            "transaction",
            transaction_id,
            "qualification_reevaluated",
            reason,
            {
                "previous_status": previous["status"] if previous else "unclassified",
                "previous_reason": previous["reason"] if previous else None,
                "new_status": result.status,
                "new_entity_type": result.entity_type,
                "new_entity_id": result.entity_id,
            },
        )
        conn.execute("RELEASE SAVEPOINT r8_reevaluate_transaction")
        return result
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT r8_reevaluate_transaction")
        conn.execute("RELEASE SAVEPOINT r8_reevaluate_transaction")
        raise


def affected_transactions_for_occurrences(
    conn: sqlite3.Connection,
    occurrence_ids: list[int] | tuple[int, ...],
    rules: ReconciliationRules | None = None,
) -> tuple[int, ...]:
    """Return linked and potentially compatible transactions for occurrences."""
    ids = tuple(dict.fromkeys(int(item) for item in occurrence_ids))
    if not ids:
        return ()
    rules = rules or ReconciliationRules()
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"""
        SELECT DISTINCT transaction_id
        FROM (
            SELECT rm.transaction_id AS transaction_id
            FROM reconciliation_members rm
            WHERE rm.occurrence_id IN ({placeholders})
            UNION
            SELECT rpm.transaction_id AS transaction_id
            FROM reconciliation_proposal_members rpm
            WHERE rpm.proposal_id IN (
                SELECT proposal_id
                FROM reconciliation_proposal_members
                WHERE occurrence_id IN ({placeholders})
            )
            UNION
            SELECT t.id AS transaction_id
            FROM transactions t
            JOIN forecast_occurrences fo
              ON fo.id IN ({placeholders})
             AND fo.account_id = t.account_id
             AND julianday(t.tx_date) BETWEEN
                 julianday(fo.expected_date) - ?
                 AND julianday(fo.expected_date) + ?
            WHERE fo.deleted_at IS NULL
        )
        WHERE transaction_id IS NOT NULL
        ORDER BY transaction_id
        """,
        (*ids, *ids, *ids, rules.date_tolerance_days, rules.date_tolerance_days),
    ).fetchall()
    return tuple(int(row[0]) for row in rows)


def reevaluate_for_occurrences(
    conn: sqlite3.Connection,
    occurrence_ids: list[int] | tuple[int, ...],
    rules: ReconciliationRules | None = None,
    *,
    reason: str = "Prévision ou occurrence modifiée",
) -> ReevaluationSummary:
    rules = rules or ReconciliationRules()
    transaction_ids = affected_transactions_for_occurrences(
        conn, occurrence_ids, rules
    )
    results = tuple(
        reevaluate_transaction(conn, transaction_id, rules, reason=reason)
        for transaction_id in transaction_ids
    )
    return ReevaluationSummary(transaction_ids, results)


def reevaluate_all_transactions(
    conn: sqlite3.Connection,
    rules: ReconciliationRules | None = None,
    *,
    reason: str = "Paramètres de rapprochement modifiés",
) -> ReevaluationSummary:
    transaction_ids = tuple(
        int(row[0])
        for row in conn.execute("SELECT id FROM transactions ORDER BY id").fetchall()
    )
    rules = rules or ReconciliationRules()
    results = tuple(
        reevaluate_transaction(conn, transaction_id, rules, reason=reason)
        for transaction_id in transaction_ids
    )
    return ReevaluationSummary(transaction_ids, results)
