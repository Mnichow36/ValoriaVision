from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from uuid import uuid4

from app.services.reconciliation.models import (
    CandidateScore,
    QualificationResult,
    TransactionInput,
)
from app.services.reconciliation.rules import ReconciliationRules


@dataclass(frozen=True)
class PersistedQualification:
    status: str
    entity_type: str | None
    entity_id: int | None


def _score_details(candidate: CandidateScore | None) -> str:
    if candidate is None:
        return json.dumps({"criteria": []}, ensure_ascii=False, sort_keys=True)
    return json.dumps(
        {
            "score": candidate.score,
            "date_delta_days": candidate.date_delta_days,
            "amount_delta": candidate.amount_delta,
            "criteria": [asdict(item) for item in candidate.criteria],
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _expire_active_proposals(conn: sqlite3.Connection, transaction_id: int) -> None:
    conn.execute(
        """
        UPDATE reconciliation_proposals
        SET status = 'expired', updated_at = CURRENT_TIMESTAMP
        WHERE status = 'proposed'
          AND id IN (
              SELECT proposal_id
              FROM reconciliation_proposal_members
              WHERE transaction_id = ?
          )
        """,
        (transaction_id,),
    )


def _upsert_state(
    conn: sqlite3.Connection,
    transaction_id: int,
    status: str,
    reason: str,
) -> None:
    conn.execute(
        """
        INSERT INTO transaction_reconciliation_state(
            transaction_id, status, reason, last_evaluated_at
        )
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(transaction_id) DO UPDATE SET
            status = excluded.status,
            reason = excluded.reason,
            last_evaluated_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        """,
        (transaction_id, status, reason),
    )


def _event(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: int,
    event_type: str,
    reason: str,
    payload: dict[str, object],
    dedup_key: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO reconciliation_events(
            uuid, entity_type, entity_id, event_type,
            reason, payload_json, dedup_key
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid4()),
            entity_type,
            entity_id,
            event_type,
            reason,
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            dedup_key,
        ),
    )


def _active_reconciliation(
    conn: sqlite3.Connection,
    transaction_id: int,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT r.id, r.status
        FROM reconciliations r
        JOIN reconciliation_members rm ON rm.reconciliation_id = r.id
        WHERE rm.transaction_id = ?
          AND r.status IN ('automatic', 'confirmed')
        ORDER BY r.id DESC
        LIMIT 1
        """,
        (transaction_id,),
    ).fetchone()


def persist_qualification(
    conn: sqlite3.Connection,
    transaction: TransactionInput,
    result: QualificationResult,
    rules: ReconciliationRules,
) -> PersistedQualification:
    """Persist one R8 decision without mutating transaction or forecast sources."""
    if result.transaction_id != transaction.id:
        raise ValueError("La qualification ne correspond pas à la transaction")

    conn.execute("SAVEPOINT r8_persist_qualification")
    try:
        existing = _active_reconciliation(conn, transaction.id)
        if existing is not None:
            _upsert_state(
                conn,
                transaction.id,
                "reconciled",
                "Rapprochement actif déjà présent",
            )
            conn.execute("RELEASE SAVEPOINT r8_persist_qualification")
            return PersistedQualification(
                status="reconciled",
                entity_type="reconciliation",
                entity_id=int(existing["id"]),
            )

        _expire_active_proposals(conn, transaction.id)
        rules_json = json.dumps(rules.snapshot(), ensure_ascii=False, sort_keys=True)

        if result.status == "without_forecast":
            _upsert_state(conn, transaction.id, "without_forecast", result.reason)
            _event(
                conn,
                "transaction",
                transaction.id,
                "qualified_without_forecast",
                result.reason,
                {"transaction_id": transaction.id},
                f"r8:without-forecast:{transaction.id}",
            )
            persisted = PersistedQualification("without_forecast", None, None)

        elif result.status == "review":
            best = result.best_candidate
            if best is None:
                raise ValueError("Une proposition nécessite au moins un candidat")
            cursor = conn.execute(
                """
                INSERT INTO reconciliation_proposals(
                    uuid, status, score, confidence_level,
                    score_details_json, rules_snapshot_json, ambiguity_delta
                )
                VALUES (?, 'proposed', ?, 'review', ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    best.score,
                    _score_details(best),
                    rules_json,
                    result.ambiguity_delta,
                ),
            )
            proposal_id = int(cursor.lastrowid)
            conn.execute(
                """
                INSERT INTO reconciliation_proposal_members(
                    proposal_id, member_type, transaction_id, role,
                    amount_snapshot, date_snapshot, label_snapshot
                )
                VALUES (?, 'transaction', ?, 'actual', ?, ?, ?)
                """,
                (
                    proposal_id,
                    transaction.id,
                    transaction.amount,
                    transaction.tx_date.isoformat(),
                    transaction.label,
                ),
            )
            for candidate in result.candidates:
                forecast = candidate.forecast
                conn.execute(
                    """
                    INSERT INTO reconciliation_proposal_members(
                        proposal_id, member_type, occurrence_id, role,
                        amount_snapshot, date_snapshot, label_snapshot
                    )
                    VALUES (?, 'occurrence', ?, 'candidate', ?, ?, ?)
                    """,
                    (
                        proposal_id,
                        forecast.id,
                        forecast.expected_amount,
                        forecast.expected_date.isoformat(),
                        forecast.expected_label,
                    ),
                )
            _upsert_state(conn, transaction.id, "has_proposal", result.reason)
            _event(
                conn,
                "proposal",
                proposal_id,
                "proposal_created",
                result.reason,
                {
                    "transaction_id": transaction.id,
                    "candidate_ids": [
                        candidate.forecast.id for candidate in result.candidates
                    ],
                    "score": best.score,
                    "ambiguity_delta": result.ambiguity_delta,
                },
            )
            persisted = PersistedQualification("has_proposal", "proposal", proposal_id)

        elif result.status == "automatic":
            best = result.best_candidate
            if best is None:
                raise ValueError("Un rapprochement automatique nécessite un candidat")
            cursor = conn.execute(
                """
                INSERT INTO reconciliations(
                    uuid, status, match_type, score,
                    score_details_json, rules_snapshot_json
                )
                VALUES (?, 'automatic', 'automatic', ?, ?, ?)
                """,
                (str(uuid4()), best.score, _score_details(best), rules_json),
            )
            reconciliation_id = int(cursor.lastrowid)
            conn.execute(
                """
                INSERT INTO reconciliation_members(
                    reconciliation_id, member_type, transaction_id, role,
                    amount_snapshot, date_snapshot, label_snapshot
                )
                VALUES (?, 'transaction', ?, 'actual', ?, ?, ?)
                """,
                (
                    reconciliation_id,
                    transaction.id,
                    transaction.amount,
                    transaction.tx_date.isoformat(),
                    transaction.label,
                ),
            )
            forecast = best.forecast
            conn.execute(
                """
                INSERT INTO reconciliation_members(
                    reconciliation_id, member_type, occurrence_id, role,
                    amount_snapshot, date_snapshot, label_snapshot
                )
                VALUES (?, 'occurrence', ?, 'forecast', ?, ?, ?)
                """,
                (
                    reconciliation_id,
                    forecast.id,
                    forecast.expected_amount,
                    forecast.expected_date.isoformat(),
                    forecast.expected_label,
                ),
            )
            _upsert_state(conn, transaction.id, "reconciled", result.reason)
            _event(
                conn,
                "reconciliation",
                reconciliation_id,
                "automatic_reconciliation_created",
                result.reason,
                {
                    "transaction_id": transaction.id,
                    "occurrence_id": forecast.id,
                    "score": best.score,
                },
            )
            persisted = PersistedQualification(
                "reconciled", "reconciliation", reconciliation_id
            )
        else:
            raise ValueError(f"Qualification inconnue : {result.status}")

        conn.execute("RELEASE SAVEPOINT r8_persist_qualification")
        return persisted
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT r8_persist_qualification")
        conn.execute("RELEASE SAVEPOINT r8_persist_qualification")
        raise

