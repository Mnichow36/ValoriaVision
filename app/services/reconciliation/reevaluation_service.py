from __future__ import annotations

import hashlib
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



def _input_fingerprint(
    conn: sqlite3.Connection,
    transaction_id: int,
    rules: ReconciliationRules,
) -> str:
    transaction = conn.execute(
        """
        SELECT account_id, tx_date, amount, label, tx_type, category
        FROM transactions WHERE id = ?
        """,
        (transaction_id,),
    ).fetchone()
    if transaction is None:
        raise ValueError(f"Transaction introuvable : {transaction_id}")
    start_end = conn.execute(
        """
        SELECT date(?, ?), date(?, ?)
        """,
        (
            transaction["tx_date"],
            f"-{rules.date_tolerance_days} days",
            transaction["tx_date"],
            f"+{rules.date_tolerance_days} days",
        ),
    ).fetchone()
    occurrences = conn.execute(
        """
        SELECT id, account_id, expected_date, expected_amount, expected_label,
               direction, expected_category, status, deleted_at
        FROM forecast_occurrences
        WHERE account_id = ?
          AND expected_date BETWEEN ? AND ?
        ORDER BY id
        """,
        (transaction["account_id"], start_end[0], start_end[1]),
    ).fetchall()
    payload = {
        "transaction": dict(transaction),
        "occurrences": [dict(row) for row in occurrences],
        "rules": rules.snapshot(),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _unchanged_result(
    conn: sqlite3.Connection,
    transaction_id: int,
    fingerprint: str,
) -> PersistedQualification | None:
    row = conn.execute(
        """
        SELECT payload_json
        FROM reconciliation_events
        WHERE entity_type = 'transaction'
          AND entity_id = ?
          AND event_type = 'qualification_reevaluated'
        ORDER BY id DESC LIMIT 1
        """,
        (transaction_id,),
    ).fetchone()
    if row is None:
        return None
    try:
        previous_fingerprint = json.loads(row["payload_json"]).get("input_fingerprint")
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if previous_fingerprint != fingerprint:
        return None

    state = conn.execute(
        "SELECT status FROM transaction_reconciliation_state WHERE transaction_id = ?",
        (transaction_id,),
    ).fetchone()
    status = state["status"] if state else "unclassified"
    if status == "reconciled":
        entity = conn.execute(
            """
            SELECT r.id FROM reconciliations r
            JOIN reconciliation_members rm ON rm.reconciliation_id = r.id
            WHERE rm.transaction_id = ? AND r.status IN ('automatic', 'confirmed')
            ORDER BY r.id DESC LIMIT 1
            """,
            (transaction_id,),
        ).fetchone()
        return PersistedQualification("reconciled", "reconciliation", int(entity[0])) if entity else None
    if status == "has_proposal":
        entity = conn.execute(
            """
            SELECT p.id FROM reconciliation_proposals p
            JOIN reconciliation_proposal_members pm ON pm.proposal_id = p.id
            WHERE pm.transaction_id = ? AND p.status = 'proposed'
            ORDER BY p.id DESC LIMIT 1
            """,
            (transaction_id,),
        ).fetchone()
        return PersistedQualification("has_proposal", "proposal", int(entity[0])) if entity else None
    if status == "without_forecast":
        return PersistedQualification("without_forecast", None, None)
    return None


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


def cancel_reconciliations_for_occurrence(
    conn: sqlite3.Connection,
    occurrence_id: int,
    *,
    reason: str = "Rapprochement annulé par l’utilisateur",
) -> tuple[int, ...]:
    """Cancel active R8 links for one occurrence and release their members."""
    rows = conn.execute(
        """
        SELECT DISTINCT r.id, rm_tx.transaction_id
        FROM reconciliations r
        JOIN reconciliation_members rm_occ
          ON rm_occ.reconciliation_id = r.id
         AND rm_occ.occurrence_id = ?
        LEFT JOIN reconciliation_members rm_tx
          ON rm_tx.reconciliation_id = r.id
         AND rm_tx.transaction_id IS NOT NULL
        WHERE r.status IN ('automatic', 'confirmed')
        ORDER BY r.id, rm_tx.transaction_id
        """,
        (occurrence_id,),
    ).fetchall()
    reconciliation_ids = tuple(dict.fromkeys(int(row["id"]) for row in rows))
    transaction_ids = tuple(
        dict.fromkeys(
            int(row["transaction_id"])
            for row in rows
            if row["transaction_id"] is not None
        )
    )
    for reconciliation_id in reconciliation_ids:
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
            "reconciliation_cancelled",
            reason,
            {
                "occurrence_id": occurrence_id,
                "released_transaction_ids": list(transaction_ids),
            },
        )
    return transaction_ids


def reevaluate_transaction(
    conn: sqlite3.Connection,
    transaction_id: int,
    rules: ReconciliationRules | None = None,
    *,
    reason: str = "Source de rapprochement modifiée",
) -> PersistedQualification:
    """Invalidate the previous decision and atomically calculate a new one."""
    rules = rules or ReconciliationRules()
    conn.execute("SAVEPOINT r8_reevaluate_transaction")
    try:
        fingerprint = _input_fingerprint(conn, transaction_id, rules)
        unchanged = _unchanged_result(conn, transaction_id, fingerprint)
        if unchanged is not None:
            conn.execute("RELEASE SAVEPOINT r8_reevaluate_transaction")
            return unchanged
        previous = conn.execute(
            """
            SELECT status, reason
            FROM transaction_reconciliation_state
            WHERE transaction_id = ?
            """,
            (transaction_id,),
        ).fetchone()
        _invalidate_transaction_decision(conn, transaction_id, reason)
        result = qualify_and_persist_transaction(conn, transaction_id, rules)
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
                "input_fingerprint": fingerprint,
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
