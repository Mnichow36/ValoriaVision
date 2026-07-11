from __future__ import annotations

from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from uuid import uuid4


STATUS_LABELS = {
    "planned": "Prévue",
    "auto_matched": "Rapprochée automatiquement",
    "confirmed": "Rapprochée manuellement",
    "to_review": "À vérifier",
    "overdue": "En retard",
    "ignored": "Ignorée",
    "cancelled": "Annulée",
}


def _parse_date(value) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _norm(value) -> str:
    return " ".join(str(value or "").lower().replace("—", " ").replace("-", " ").split())


class ForecastReconciliationService:
    """Reconcile forecast occurrences with imported real transactions.

    The service implements the V0.6.6-R6 foundation:
    - occurrence generation from active recurring items;
    - automatic matching after bank import;
    - manual confirmation/rejection/ignore actions;
    - status tracking for overdue and uncertain occurrences.
    """

    AUTO_THRESHOLD = 90
    REVIEW_THRESHOLD = 60
    DATE_TOLERANCE_DAYS = 5

    def __init__(self, db) -> None:
        self.db = db

    def status_label(self, status: str) -> str:
        return STATUS_LABELS.get(status, status)

    def generate_occurrences(self, start_date: str | date, end_date: str | date) -> int:
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        generated = 0

        for item in self.db.list_recurring_items(active_only=True):
            source_id = int(item["id"])
            current = _parse_date(item["next_date"])
            item_end = _parse_date(item["end_date"]) if item["end_date"] else end

            while current <= end and current <= item_end:
                if current >= start:
                    amount = float(item["amount"] or 0)
                    direction = "credit" if amount >= 0 else "debit"
                    payload = {
                        "uuid": str(uuid4()),
                        "source_type": "recurring",
                        "source_id": source_id,
                        "account_id": item["account_id"],
                        "expected_date": current.isoformat(),
                        "expected_amount": amount,
                        "expected_label": item["name"],
                        "expected_category": item["category"] or "Prévisionnel",
                        "direction": direction,
                    }
                    if self._upsert_occurrence(payload):
                        generated += 1
                current = self.db.add_period(current, item["frequency"])

        return generated

    def _upsert_occurrence(self, payload: dict) -> bool:
        with self.db.connect() as conn:
            existing = conn.execute(
                """
                SELECT id, status, actual_transaction_id
                FROM forecast_occurrences
                WHERE source_type = ? AND source_id = ? AND expected_date = ? AND deleted_at IS NULL
                """,
                (payload["source_type"], payload["source_id"], payload["expected_date"]),
            ).fetchone()
            if existing:
                # Do not erase reconciliation decisions.
                if existing["status"] in {"auto_matched", "confirmed", "to_review", "ignored", "cancelled"}:
                    return False
                conn.execute(
                    """
                    UPDATE forecast_occurrences
                    SET account_id = ?, expected_amount = ?, expected_label = ?, expected_category = ?,
                        direction = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        payload["account_id"],
                        payload["expected_amount"],
                        payload["expected_label"],
                        payload["expected_category"],
                        payload["direction"],
                        existing["id"],
                    ),
                )
                return False

            conn.execute(
                """
                INSERT INTO forecast_occurrences(
                    uuid, source_type, source_id, account_id, expected_date, expected_amount,
                    expected_label, expected_category, direction, status, created_at, updated_at
                )
                VALUES (:uuid, :source_type, :source_id, :account_id, :expected_date, :expected_amount,
                        :expected_label, :expected_category, :direction, 'planned', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                payload,
            )
            return True

    def reconcile_import_batch(self, import_batch_id: int) -> dict:
        transactions = self._imported_transactions(import_batch_id)
        if not transactions:
            return {"auto": 0, "to_review": 0, "unmatched": 0, "generated": 0}

        min_day = min(_parse_date(tx["tx_date"]) for tx in transactions) - timedelta(days=self.DATE_TOLERANCE_DAYS)
        max_day = max(_parse_date(tx["tx_date"]) for tx in transactions) + timedelta(days=self.DATE_TOLERANCE_DAYS)
        generated = self.generate_occurrences(min_day, max_day)

        summary = {"auto": 0, "to_review": 0, "unmatched": 0, "generated": generated}
        for tx in transactions:
            candidates = self.find_candidates(tx)
            if not candidates:
                summary["unmatched"] += 1
                continue
            best = candidates[0]
            if best["score"] >= self.AUTO_THRESHOLD:
                self._link_occurrence(best["occurrence"]["id"], tx, best, "auto_matched")
                summary["auto"] += 1
            elif best["score"] >= self.REVIEW_THRESHOLD:
                self._link_occurrence(best["occurrence"]["id"], tx, best, "to_review")
                summary["to_review"] += 1
            else:
                summary["unmatched"] += 1

        self.mark_overdue(date.today())
        return summary

    def _imported_transactions(self, import_batch_id: int) -> list:
        with self.db.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT t.*, a.name AS account_name
                    FROM transactions t
                    JOIN accounts a ON a.id = t.account_id
                    WHERE t.import_batch_id = ?
                    ORDER BY t.tx_date, t.id
                    """,
                    (import_batch_id,),
                )
            )

    def find_candidates(self, transaction) -> list[dict]:
        tx_date = _parse_date(transaction["tx_date"])
        start = (tx_date - timedelta(days=self.DATE_TOLERANCE_DAYS)).isoformat()
        end = (tx_date + timedelta(days=self.DATE_TOLERANCE_DAYS)).isoformat()
        direction = "credit" if float(transaction["amount"] or 0) >= 0 else "debit"

        with self.db.connect() as conn:
            rows = list(
                conn.execute(
                    """
                    SELECT o.*, a.name AS account_name
                    FROM forecast_occurrences o
                    LEFT JOIN accounts a ON a.id = o.account_id
                    WHERE o.deleted_at IS NULL
                      AND o.status IN ('planned', 'overdue', 'to_review')
                      AND o.account_id = ?
                      AND o.direction = ?
                      AND o.expected_date BETWEEN ? AND ?
                      AND (o.actual_transaction_id IS NULL OR o.actual_transaction_id = ?)
                    ORDER BY o.expected_date, o.id
                    """,
                    (transaction["account_id"], direction, start, end, transaction["id"]),
                )
            )

        scored = []
        for occurrence in rows:
            score, reason = self.compute_match_score(occurrence, transaction)
            scored.append({"occurrence": occurrence, "transaction": transaction, "score": score, "reason": reason})
        return sorted(scored, key=lambda row: row["score"], reverse=True)

    def compute_match_score(self, occurrence, transaction) -> tuple[int, str]:
        score = 0
        reasons = []

        if occurrence["account_id"] == transaction["account_id"]:
            score += 30
            reasons.append("compte identique +30")
        else:
            reasons.append("compte différent")
            return 0, "; ".join(reasons)

        occ_direction = occurrence["direction"]
        tx_direction = "credit" if float(transaction["amount"] or 0) >= 0 else "debit"
        if occ_direction == tx_direction:
            score += 25
            reasons.append("sens identique +25")
        else:
            reasons.append("sens différent")
            return 0, "; ".join(reasons)

        expected = abs(float(occurrence["expected_amount"] or 0))
        actual = abs(float(transaction["amount"] or 0))
        delta = abs(actual - expected)
        tolerance = max(1.0, expected * 0.02)
        wider = max(5.0, expected * 0.05)
        if delta <= 0.01:
            score += 25
            reasons.append("montant exact +25")
        elif delta <= tolerance:
            score += 20
            reasons.append(f"montant proche +20, écart {delta:.2f}")
        elif delta <= wider:
            score += 12
            reasons.append(f"montant à vérifier +12, écart {delta:.2f}")
        else:
            reasons.append(f"montant hors tolérance, écart {delta:.2f}")

        days = abs((_parse_date(transaction["tx_date"]) - _parse_date(occurrence["expected_date"])).days)
        if days <= 1:
            score += 15
            reasons.append(f"date très proche +15 ({days} j)")
        elif days <= 3:
            score += 12
            reasons.append(f"date proche +12 ({days} j)")
        elif days <= self.DATE_TOLERANCE_DAYS:
            score += 8
            reasons.append(f"date tolérée +8 ({days} j)")
        else:
            reasons.append(f"date hors tolérance ({days} j)")

        expected_label = _norm(occurrence["expected_label"])
        tx_label = _norm(transaction["label"])
        if expected_label and tx_label:
            ratio = SequenceMatcher(None, expected_label, tx_label).ratio()
            token_hit = any(token and token in tx_label for token in expected_label.split() if len(token) >= 4)
            if token_hit or ratio >= 0.45:
                score += 5
                reasons.append("libellé compatible +5")

        occ_cat = _norm(occurrence["expected_category"])
        tx_cat = _norm(transaction["category"])
        if occ_cat and tx_cat and occ_cat == tx_cat:
            score += 5
            reasons.append("catégorie identique +5")

        return min(score, 100), "; ".join(reasons)

    def _link_occurrence(self, occurrence_id: int, transaction, scored: dict, status: str) -> None:
        expected_amount = float(scored["occurrence"]["expected_amount"] or 0)
        actual_amount = float(transaction["amount"] or 0)
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE forecast_occurrences
                SET status = ?,
                    actual_transaction_id = ?,
                    actual_date = ?,
                    actual_amount = ?,
                    amount_delta = ?,
                    match_confidence = ?,
                    match_reason = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    status,
                    transaction["id"],
                    transaction["tx_date"],
                    actual_amount,
                    round(actual_amount - expected_amount, 2),
                    int(scored["score"]),
                    scored["reason"],
                    occurrence_id,
                ),
            )

    def mark_overdue(self, reference_date: str | date) -> int:
        ref = _parse_date(reference_date).isoformat()
        with self.db.connect() as conn:
            cur = conn.execute(
                """
                UPDATE forecast_occurrences
                SET status = 'overdue', updated_at = CURRENT_TIMESTAMP
                WHERE deleted_at IS NULL
                  AND status = 'planned'
                  AND actual_transaction_id IS NULL
                  AND expected_date < ?
                """,
                (ref,),
            )
            return int(cur.rowcount or 0)


    def list_imported_transactions(
        self,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
        account_id: int | None = None,
        limit: int = 500,
    ) -> list:
        """List real bank transactions imported from statements."""
        clauses = ["t.source = 'Import bancaire'"]
        params: list = []
        if start_date:
            clauses.append("t.tx_date >= ?")
            params.append(_parse_date(start_date).isoformat())
        if end_date:
            clauses.append("t.tx_date <= ?")
            params.append(_parse_date(end_date).isoformat())
        if account_id:
            clauses.append("t.account_id = ?")
            params.append(account_id)

        where = " AND ".join(clauses)
        params.append(limit)
        with self.db.connect() as conn:
            return list(
                conn.execute(
                    f"""
                    SELECT t.*,
                           a.name AS account_name,
                           a.bank AS bank,
                           o.id AS linked_occurrence_id,
                           o.expected_label AS linked_expected_label,
                           o.status AS linked_status
                    FROM transactions t
                    JOIN accounts a ON a.id = t.account_id
                    LEFT JOIN forecast_occurrences o
                        ON o.actual_transaction_id = t.id
                       AND o.deleted_at IS NULL
                    WHERE {where}
                    ORDER BY t.tx_date DESC, t.id DESC
                    LIMIT ?
                    """,
                    params,
                )
            )

    def confirm_manual_match(self, occurrence_id: int, transaction_id: int) -> tuple[int, str]:
        """Manually link one occurrence and one real transaction."""
        with self.db.connect() as conn:
            occurrence = conn.execute(
                "SELECT * FROM forecast_occurrences WHERE id = ? AND deleted_at IS NULL",
                (occurrence_id,),
            ).fetchone()
            transaction = conn.execute(
                "SELECT * FROM transactions WHERE id = ?",
                (transaction_id,),
            ).fetchone()
            if not occurrence or not transaction:
                return 0, "Occurrence ou transaction introuvable."

            score, reason = self.compute_match_score(occurrence, transaction)
            expected_amount = float(occurrence["expected_amount"] or 0)
            actual_amount = float(transaction["amount"] or 0)

            conn.execute(
                """
                UPDATE forecast_occurrences
                SET status = 'confirmed',
                    actual_transaction_id = ?,
                    actual_date = ?,
                    actual_amount = ?,
                    amount_delta = ?,
                    match_confidence = ?,
                    match_reason = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    transaction_id,
                    transaction["tx_date"],
                    actual_amount,
                    round(actual_amount - expected_amount, 2),
                    max(score, 100 if score >= 60 else score),
                    "Rapprochement manuel. " + reason,
                    occurrence_id,
                ),
            )
            return 1, "Rapprochement manuel confirmé."


    def confirm_match(self, occurrence_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE forecast_occurrences
                SET status = 'confirmed', updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND actual_transaction_id IS NOT NULL
                """,
                (occurrence_id,),
            )

    def reject_match(self, occurrence_id: int) -> None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT expected_date FROM forecast_occurrences WHERE id = ?", (occurrence_id,)).fetchone()
            status = "overdue" if row and _parse_date(row["expected_date"]) < date.today() else "planned"
            conn.execute(
                """
                UPDATE forecast_occurrences
                SET status = ?,
                    actual_transaction_id = NULL,
                    actual_date = NULL,
                    actual_amount = NULL,
                    amount_delta = NULL,
                    match_confidence = NULL,
                    match_reason = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, occurrence_id),
            )

    def ignore_occurrence(self, occurrence_id: int, reason: str = "") -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE forecast_occurrences
                SET status = 'ignored', ignored_reason = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (reason, occurrence_id),
            )

    def list_occurrences(
        self,
        status: str | None = None,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
        account_id: int | None = None,
        limit: int = 500,
    ) -> list:
        clauses = ["o.deleted_at IS NULL"]
        params: list = []
        if status and status != "all":
            clauses.append("o.status = ?")
            params.append(status)
        if start_date:
            clauses.append("o.expected_date >= ?")
            params.append(_parse_date(start_date).isoformat())
        if end_date:
            clauses.append("o.expected_date <= ?")
            params.append(_parse_date(end_date).isoformat())
        if account_id:
            clauses.append("o.account_id = ?")
            params.append(account_id)

        where = " AND ".join(clauses)
        params.append(limit)
        with self.db.connect() as conn:
            return list(
                conn.execute(
                    f"""
                    SELECT o.*,
                           a.name AS account_name,
                           a.bank AS bank,
                           t.tx_date AS tx_date,
                           t.label AS tx_label,
                           t.amount AS tx_amount,
                           t.category AS tx_category
                    FROM forecast_occurrences o
                    LEFT JOIN accounts a ON a.id = o.account_id
                    LEFT JOIN transactions t ON t.id = o.actual_transaction_id
                    WHERE {where}
                    ORDER BY o.expected_date DESC, o.id DESC
                    LIMIT ?
                    """,
                    params,
                )
            )

    def summary(self) -> dict:
        with self.db.connect() as conn:
            rows = list(
                conn.execute(
                    """
                    SELECT status, COUNT(*) AS count
                    FROM forecast_occurrences
                    WHERE deleted_at IS NULL
                    GROUP BY status
                    """
                )
            )
        output = {status: 0 for status in STATUS_LABELS}
        for row in rows:
            output[row["status"]] = int(row["count"])
        return output
