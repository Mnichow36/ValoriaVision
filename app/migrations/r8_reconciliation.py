from __future__ import annotations

import json
import sqlite3
from uuid import uuid4


R8_TRANSACTION_STATES = ("unclassified", "without_forecast", "has_proposal", "reconciled")
R8_PROPOSAL_STATUSES = ("proposed", "rejected", "expired", "converted")
R8_RECONCILIATION_STATUSES = ("automatic", "confirmed", "cancelled")


def apply_r8_reconciliation_foundation(conn: sqlite3.Connection) -> None:
    """Create the R8 reconciliation model and migrate R7.2 links non-destructively.

    Phase 1 deliberately keeps all legacy forecast_occurrences reconciliation
    columns and statuses untouched. The current R7.2 engine and forecast code
    continue to work while R8 services are implemented on top of the new model.

    The migration is idempotent and may safely run on every application start.
    """
    _create_schema(conn)
    _ensure_transaction_states(conn)
    _migrate_legacy_confirmed_matches(conn)
    _migrate_legacy_proposals(conn)


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS transaction_reconciliation_state (
            transaction_id INTEGER PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'unclassified'
                CHECK(status IN ('unclassified', 'without_forecast', 'has_proposal', 'reconciled')),
            reason TEXT,
            last_evaluated_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(transaction_id) REFERENCES transactions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS reconciliation_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'proposed'
                CHECK(status IN ('proposed', 'rejected', 'expired', 'converted')),
            score INTEGER CHECK(score IS NULL OR (score >= 0 AND score <= 100)),
            confidence_level TEXT,
            score_details_json TEXT,
            rules_snapshot_json TEXT,
            ambiguity_delta REAL,
            legacy_occurrence_id INTEGER UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT
        );

        CREATE TABLE IF NOT EXISTS reconciliation_proposal_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proposal_id INTEGER NOT NULL,
            member_type TEXT NOT NULL CHECK(member_type IN ('transaction', 'occurrence')),
            transaction_id INTEGER,
            occurrence_id INTEGER,
            role TEXT NOT NULL DEFAULT 'candidate',
            amount_snapshot REAL,
            date_snapshot TEXT,
            label_snapshot TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK(
                (member_type = 'transaction' AND transaction_id IS NOT NULL AND occurrence_id IS NULL)
                OR
                (member_type = 'occurrence' AND occurrence_id IS NOT NULL AND transaction_id IS NULL)
            ),
            FOREIGN KEY(proposal_id) REFERENCES reconciliation_proposals(id) ON DELETE CASCADE,
            FOREIGN KEY(transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
            FOREIGN KEY(occurrence_id) REFERENCES forecast_occurrences(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS reconciliations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL
                CHECK(status IN ('automatic', 'confirmed', 'cancelled')),
            match_type TEXT NOT NULL CHECK(match_type IN ('automatic', 'manual')),
            score INTEGER CHECK(score IS NULL OR (score >= 0 AND score <= 100)),
            score_details_json TEXT,
            rules_snapshot_json TEXT,
            source_proposal_id INTEGER,
            legacy_occurrence_id INTEGER UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            confirmed_at TEXT,
            cancelled_at TEXT,
            cancel_reason TEXT,
            FOREIGN KEY(source_proposal_id) REFERENCES reconciliation_proposals(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS reconciliation_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reconciliation_id INTEGER NOT NULL,
            member_type TEXT NOT NULL CHECK(member_type IN ('transaction', 'occurrence')),
            transaction_id INTEGER,
            occurrence_id INTEGER,
            role TEXT NOT NULL DEFAULT 'member',
            amount_snapshot REAL,
            date_snapshot TEXT,
            label_snapshot TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK(
                (member_type = 'transaction' AND transaction_id IS NOT NULL AND occurrence_id IS NULL)
                OR
                (member_type = 'occurrence' AND occurrence_id IS NOT NULL AND transaction_id IS NULL)
            ),
            FOREIGN KEY(reconciliation_id) REFERENCES reconciliations(id) ON DELETE CASCADE,
            FOREIGN KEY(transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
            FOREIGN KEY(occurrence_id) REFERENCES forecast_occurrences(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS reconciliation_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL UNIQUE,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            reason TEXT,
            payload_json TEXT,
            actor_id TEXT,
            dedup_key TEXT UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_transaction_reconciliation_state_status
            ON transaction_reconciliation_state(status, transaction_id);

        CREATE INDEX IF NOT EXISTS idx_reconciliation_proposals_status
            ON reconciliation_proposals(status, created_at);

        CREATE INDEX IF NOT EXISTS idx_reconciliation_proposal_members_tx
            ON reconciliation_proposal_members(transaction_id)
            WHERE transaction_id IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_reconciliation_proposal_members_occ
            ON reconciliation_proposal_members(occurrence_id)
            WHERE occurrence_id IS NOT NULL;

        CREATE UNIQUE INDEX IF NOT EXISTS uq_reconciliation_proposal_tx_member
            ON reconciliation_proposal_members(proposal_id, transaction_id)
            WHERE transaction_id IS NOT NULL;

        CREATE UNIQUE INDEX IF NOT EXISTS uq_reconciliation_proposal_occ_member
            ON reconciliation_proposal_members(proposal_id, occurrence_id)
            WHERE occurrence_id IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_reconciliations_status
            ON reconciliations(status, created_at);

        CREATE INDEX IF NOT EXISTS idx_reconciliation_members_tx
            ON reconciliation_members(transaction_id)
            WHERE transaction_id IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_reconciliation_members_occ
            ON reconciliation_members(occurrence_id)
            WHERE occurrence_id IS NOT NULL;

        CREATE UNIQUE INDEX IF NOT EXISTS uq_reconciliation_tx_member
            ON reconciliation_members(reconciliation_id, transaction_id)
            WHERE transaction_id IS NOT NULL;

        CREATE UNIQUE INDEX IF NOT EXISTS uq_reconciliation_occ_member
            ON reconciliation_members(reconciliation_id, occurrence_id)
            WHERE occurrence_id IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_reconciliation_events_entity
            ON reconciliation_events(entity_type, entity_id, created_at);

        CREATE INDEX IF NOT EXISTS idx_reconciliation_events_type
            ON reconciliation_events(event_type, created_at);
        """
    )


def _ensure_transaction_states(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO transaction_reconciliation_state(transaction_id, status)
        SELECT id, 'unclassified'
        FROM transactions
        """
    )


def _migrate_legacy_confirmed_matches(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT o.id AS occurrence_id,
               o.status,
               o.actual_transaction_id AS transaction_id,
               o.expected_amount,
               o.expected_date,
               o.expected_label,
               o.actual_amount,
               o.actual_date,
               o.match_confidence,
               o.match_reason,
               o.match_type,
               o.created_at,
               o.updated_at,
               t.amount AS transaction_amount,
               t.tx_date AS transaction_date,
               t.label AS transaction_label
        FROM forecast_occurrences o
        JOIN transactions t ON t.id = o.actual_transaction_id
        WHERE o.deleted_at IS NULL
          AND o.actual_transaction_id IS NOT NULL
          AND o.status IN ('auto_matched', 'confirmed')
        ORDER BY o.id
        """
    ).fetchall()

    for row in rows:
        legacy_occurrence_id = int(row["occurrence_id"])
        status = "automatic" if row["status"] == "auto_matched" else "confirmed"
        match_type = "automatic" if status == "automatic" else "manual"
        score_details = json.dumps(
            {
                "migration_source": "r7.2",
                "legacy_match_reason": row["match_reason"],
            },
            ensure_ascii=False,
        )
        rules_snapshot = json.dumps({"source": "r7.2-legacy"}, ensure_ascii=False)

        conn.execute(
            """
            INSERT OR IGNORE INTO reconciliations(
                uuid, status, match_type, score, score_details_json,
                rules_snapshot_json, legacy_occurrence_id, created_at, confirmed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?)
            """,
            (
                str(uuid4()),
                status,
                match_type,
                row["match_confidence"],
                score_details,
                rules_snapshot,
                legacy_occurrence_id,
                row["created_at"],
                row["updated_at"] if status == "confirmed" else None,
            ),
        )
        reconciliation = conn.execute(
            "SELECT id FROM reconciliations WHERE legacy_occurrence_id = ?",
            (legacy_occurrence_id,),
        ).fetchone()
        if reconciliation is None:
            continue
        reconciliation_id = int(reconciliation["id"])

        conn.execute(
            """
            INSERT OR IGNORE INTO reconciliation_members(
                reconciliation_id, member_type, transaction_id, role,
                amount_snapshot, date_snapshot, label_snapshot
            )
            VALUES (?, 'transaction', ?, 'actual', ?, ?, ?)
            """,
            (
                reconciliation_id,
                int(row["transaction_id"]),
                row["transaction_amount"],
                row["transaction_date"],
                row["transaction_label"],
            ),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO reconciliation_members(
                reconciliation_id, member_type, occurrence_id, role,
                amount_snapshot, date_snapshot, label_snapshot
            )
            VALUES (?, 'occurrence', ?, 'forecast', ?, ?, ?)
            """,
            (
                reconciliation_id,
                legacy_occurrence_id,
                row["expected_amount"],
                row["expected_date"],
                row["expected_label"],
            ),
        )
        conn.execute(
            """
            UPDATE transaction_reconciliation_state
            SET status = 'reconciled',
                reason = 'Migration R7.2: rapprochement existant',
                last_evaluated_at = COALESCE(?, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            WHERE transaction_id = ?
            """,
            (row["updated_at"], int(row["transaction_id"])),
        )
        _insert_migration_event(
            conn,
            entity_type="reconciliation",
            entity_id=reconciliation_id,
            event_type="legacy_reconciliation_migrated",
            dedup_key=f"r8:legacy-reconciliation:{legacy_occurrence_id}",
            payload={
                "legacy_occurrence_id": legacy_occurrence_id,
                "transaction_id": int(row["transaction_id"]),
                "legacy_status": row["status"],
            },
        )


def _migrate_legacy_proposals(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT o.id AS occurrence_id,
               o.actual_transaction_id AS transaction_id,
               o.expected_amount,
               o.expected_date,
               o.expected_label,
               o.match_confidence,
               o.match_reason,
               o.created_at,
               o.updated_at,
               t.amount AS transaction_amount,
               t.tx_date AS transaction_date,
               t.label AS transaction_label
        FROM forecast_occurrences o
        JOIN transactions t ON t.id = o.actual_transaction_id
        WHERE o.deleted_at IS NULL
          AND o.actual_transaction_id IS NOT NULL
          AND o.status = 'to_review'
        ORDER BY o.id
        """
    ).fetchall()

    for row in rows:
        legacy_occurrence_id = int(row["occurrence_id"])
        score_details = json.dumps(
            {
                "migration_source": "r7.2",
                "legacy_match_reason": row["match_reason"],
            },
            ensure_ascii=False,
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO reconciliation_proposals(
                uuid, status, score, confidence_level, score_details_json,
                rules_snapshot_json, legacy_occurrence_id, created_at, updated_at
            )
            VALUES (?, 'proposed', ?, 'review', ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), COALESCE(?, CURRENT_TIMESTAMP))
            """,
            (
                str(uuid4()),
                row["match_confidence"],
                score_details,
                json.dumps({"source": "r7.2-legacy"}, ensure_ascii=False),
                legacy_occurrence_id,
                row["created_at"],
                row["updated_at"],
            ),
        )
        proposal = conn.execute(
            "SELECT id FROM reconciliation_proposals WHERE legacy_occurrence_id = ?",
            (legacy_occurrence_id,),
        ).fetchone()
        if proposal is None:
            continue
        proposal_id = int(proposal["id"])

        conn.execute(
            """
            INSERT OR IGNORE INTO reconciliation_proposal_members(
                proposal_id, member_type, transaction_id, role,
                amount_snapshot, date_snapshot, label_snapshot
            )
            VALUES (?, 'transaction', ?, 'actual', ?, ?, ?)
            """,
            (
                proposal_id,
                int(row["transaction_id"]),
                row["transaction_amount"],
                row["transaction_date"],
                row["transaction_label"],
            ),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO reconciliation_proposal_members(
                proposal_id, member_type, occurrence_id, role,
                amount_snapshot, date_snapshot, label_snapshot
            )
            VALUES (?, 'occurrence', ?, 'candidate', ?, ?, ?)
            """,
            (
                proposal_id,
                legacy_occurrence_id,
                row["expected_amount"],
                row["expected_date"],
                row["expected_label"],
            ),
        )
        conn.execute(
            """
            UPDATE transaction_reconciliation_state
            SET status = CASE WHEN status = 'reconciled' THEN status ELSE 'has_proposal' END,
                reason = CASE
                    WHEN status = 'reconciled' THEN reason
                    ELSE 'Migration R7.2: proposition existante'
                END,
                last_evaluated_at = COALESCE(?, CURRENT_TIMESTAMP),
                updated_at = CURRENT_TIMESTAMP
            WHERE transaction_id = ?
            """,
            (row["updated_at"], int(row["transaction_id"])),
        )
        _insert_migration_event(
            conn,
            entity_type="proposal",
            entity_id=proposal_id,
            event_type="legacy_proposal_migrated",
            dedup_key=f"r8:legacy-proposal:{legacy_occurrence_id}",
            payload={
                "legacy_occurrence_id": legacy_occurrence_id,
                "transaction_id": int(row["transaction_id"]),
                "legacy_status": "to_review",
            },
        )


def _insert_migration_event(
    conn: sqlite3.Connection,
    *,
    entity_type: str,
    entity_id: int,
    event_type: str,
    dedup_key: str,
    payload: dict,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO reconciliation_events(
            uuid, entity_type, entity_id, event_type, reason, payload_json, dedup_key
        )
        VALUES (?, ?, ?, ?, 'Migration non destructive R7.2 vers R8', ?, ?)
        """,
        (
            str(uuid4()),
            entity_type,
            entity_id,
            event_type,
            json.dumps(payload, ensure_ascii=False),
            dedup_key,
        ),
    )
