from __future__ import annotations

import sqlite3
from datetime import date

from app.services.reconciliation.models import ForecastInput, TransactionInput
from app.services.reconciliation.persistence_service import (
    PersistedQualification,
    persist_qualification,
)
from app.services.reconciliation.qualification_service import qualify
from app.services.reconciliation.rules import ReconciliationRules


def _direction(value: str | None, amount: float) -> str:
    normalized = (value or "").strip().casefold()
    if normalized in {"debit", "débit", "depense", "dépense"}:
        return "debit"
    if normalized in {"credit", "crédit", "recette", "revenu"}:
        return "credit"
    return "debit" if amount < 0 else "credit"


def _load_transaction(conn: sqlite3.Connection, transaction_id: int) -> TransactionInput:
    row = conn.execute(
        """
        SELECT id, account_id, tx_date, amount, label, tx_type, category,
               source_identifier
        FROM transactions
        WHERE id = ?
        """,
        (transaction_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Transaction introuvable : {transaction_id}")
    amount = float(row["amount"])
    return TransactionInput(
        id=int(row["id"]),
        account_id=int(row["account_id"]),
        tx_date=date.fromisoformat(row["tx_date"]),
        amount=amount,
        label=row["label"] or "",
        direction=_direction(row["tx_type"], amount),
        category=row["category"],
        external_reference=row["source_identifier"],
    )


def _load_open_forecasts(
    conn: sqlite3.Connection,
    transaction: TransactionInput,
    rules: ReconciliationRules,
) -> tuple[ForecastInput, ...]:
    start = transaction.tx_date.fromordinal(
        transaction.tx_date.toordinal() - rules.date_tolerance_days
    ).isoformat()
    end = transaction.tx_date.fromordinal(
        transaction.tx_date.toordinal() + rules.date_tolerance_days
    ).isoformat()
    rows = conn.execute(
        """
        SELECT fo.id, fo.account_id, fo.expected_date, fo.expected_amount,
               fo.expected_label, fo.direction, fo.expected_category
        FROM forecast_occurrences fo
        WHERE fo.deleted_at IS NULL
          AND fo.status IN ('planned', 'overdue')
          AND fo.account_id = ?
          AND fo.expected_date BETWEEN ? AND ?
          AND NOT EXISTS (
              SELECT 1
              FROM reconciliation_members rm
              JOIN reconciliations r ON r.id = rm.reconciliation_id
              WHERE rm.occurrence_id = fo.id
                AND r.status IN ('automatic', 'confirmed')
          )
        ORDER BY fo.expected_date, fo.id
        """,
        (transaction.account_id, start, end),
    ).fetchall()
    return tuple(
        ForecastInput(
            id=int(row["id"]),
            account_id=int(row["account_id"]),
            expected_date=date.fromisoformat(row["expected_date"]),
            expected_amount=float(row["expected_amount"]),
            expected_label=row["expected_label"] or "",
            direction=_direction(row["direction"], float(row["expected_amount"])),
            category=row["expected_category"],
        )
        for row in rows
    )


def qualify_and_persist_transaction(
    conn: sqlite3.Connection,
    transaction_id: int,
    rules: ReconciliationRules | None = None,
) -> PersistedQualification:
    """Shared entry point for imported and manually-created transactions."""
    rules = rules or ReconciliationRules()
    transaction = _load_transaction(conn, transaction_id)
    forecasts = _load_open_forecasts(conn, transaction, rules)
    result = qualify(transaction, forecasts, rules)
    return persist_qualification(conn, transaction, result, rules)

