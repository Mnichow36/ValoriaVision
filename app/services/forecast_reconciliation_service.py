from __future__ import annotations

from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from uuid import uuid4


STATUS_LABELS = {
    "planned": "Prévue",
    "auto_matched": "Rapprochée automatiquement",
    "confirmed": "Rapprochée manuellement",
    "to_review": "À vérifier",
    "partially_matched": "Partiellement rapprochée",
    "overdue": "En retard",
    "ignored": "Ignorée",
    "cancelled": "Annulée",
}

ACTIVE_STATUSES = {"planned", "overdue", "to_review", "partially_matched"}
FINAL_STATUSES = {"auto_matched", "confirmed", "ignored", "cancelled"}
MANUAL_STATUS = "confirmed"
AUTO_STATUS = "auto_matched"


def _parse_date(value) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def _norm(value) -> str:
    return " ".join(str(value or "").lower().replace("—", " ").replace("-", " ").split())


class ForecastReconciliationService:
    """R7.2 forecast/reality reconciliation engine.

    The service builds an exhaustive dataset first (transactions + forecast
    occurrences), then applies screen filters. UI filters never decide what data
    exists in the engine.
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
            if item["account_id"] is None:
                continue
            source_id = int(item["id"])
            current = _parse_date(item["next_date"])
            item_end = _parse_date(item["end_date"]) if item["end_date"] else end

            while current <= end and current <= item_end:
                if current >= start:
                    amount = float(item["amount"] or 0)
                    payload = {
                        "uuid": str(uuid4()),
                        "source_type": "recurring",
                        "source_id": source_id,
                        "account_id": item["account_id"],
                        "expected_date": current.isoformat(),
                        "expected_amount": amount,
                        "expected_label": item["name"],
                        "expected_category": item["category"] or "Prévisionnel",
                        "direction": "credit" if amount >= 0 else "debit",
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

    def build_reconciliation_dataset(
        self,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
        account_id: int | None = None,
        status: str | None = "active",
        limit: int | None = None,
    ) -> dict:
        """Build complete eligible data first, then apply display filters."""
        start = _parse_date(start_date) if start_date else date.today() - timedelta(days=90)
        end = _parse_date(end_date) if end_date else date.today() + timedelta(days=180)

        # Display refreshes are read-only. Occurrence generation remains an explicit
        # action (or is triggered by an import), so page navigation never performs
        # hundreds of synchronous SQLite upserts.
        all_transactions = self._eligible_transactions(start, end, account_id)
        all_occurrences = self._eligible_occurrences(start, end, account_id)

        filtered_transactions = []
        for tx in all_transactions:
            # Active working list: hide transactions already consumed by an active/final link.
            if status in {None, "", "active", "planned", "overdue", "to_review"} and tx["linked_occurrence_id"]:
                continue
            if status in {None, "", "active", "planned", "overdue", "to_review"}:
                candidates = self.find_candidates(tx)
                if not candidates or candidates[0]["score"] < self.REVIEW_THRESHOLD:
                    continue
            filtered_transactions.append(tx)

        filtered_occurrences = []
        for occ in all_occurrences:
            if self._status_matches(str(occ["status"]), status):
                filtered_occurrences.append(occ)

        visible_transactions = filtered_transactions if limit is None else filtered_transactions[:limit]
        visible_occurrences = filtered_occurrences if limit is None else filtered_occurrences[:limit]
        proposals = self._eligible_proposals(start, end, account_id)
        summary = self._summary_from_occurrences(all_occurrences)
        return {
            "transactions": visible_transactions,
            "occurrences": visible_occurrences,
            "proposals": proposals,
            "summary": summary,
            "source_counts": {
                "transactions_loaded": len(all_transactions),
                "occurrences_loaded": len(all_occurrences),
                "transactions_displayed": len(visible_transactions),
                "occurrences_displayed": len(visible_occurrences),
                "proposals_loaded": len(proposals),
            },
        }

    def _status_matches(self, actual_status: str, requested_status: str | None) -> bool:
        if requested_status in {None, "", "active", "all_active"}:
            return actual_status in ACTIVE_STATUSES
        if requested_status == "all":
            return True
        if requested_status == "finalized":
            return actual_status in FINAL_STATUSES
        return actual_status == requested_status

    def _summary_from_occurrences(self, occurrences: list) -> dict:
        output = {status: 0 for status in STATUS_LABELS}
        output["active"] = 0
        output["finalized"] = 0
        output["all"] = len(occurrences)
        for occ in occurrences:
            status = occ["status"]
            if status not in output:
                output[status] = 0
            output[status] += 1
            if status in ACTIVE_STATUSES:
                output["active"] += 1
            if status in FINAL_STATUSES:
                output["finalized"] += 1
        return output

    def _eligible_transactions(self, start: date, end: date, account_id: int | None) -> list:
        with self.db.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT t.*,
                           a.name AS account_name,
                           a.bank AS bank,
                           (SELECT l.occurrence_id FROM forecast_reconciliation_links l
                            WHERE l.transaction_id = t.id AND l.deleted_at IS NULL
                            ORDER BY l.id LIMIT 1) AS linked_occurrence_id,
                           (SELECT o.expected_label FROM forecast_reconciliation_links l
                            JOIN forecast_occurrences o ON o.id = l.occurrence_id
                            WHERE l.transaction_id = t.id AND l.deleted_at IS NULL
                            ORDER BY l.id LIMIT 1) AS linked_expected_label,
                           (SELECT o.status FROM forecast_reconciliation_links l
                            JOIN forecast_occurrences o ON o.id = l.occurrence_id
                            WHERE l.transaction_id = t.id AND l.deleted_at IS NULL
                            ORDER BY l.id LIMIT 1) AS linked_status
                    FROM transactions t
                    JOIN accounts a ON a.id = t.account_id
                    WHERE t.source IN ('Import bancaire', 'Manuel')
                      AND a.status = 'Actif'
                      AND t.tx_date BETWEEN ? AND ?
                      AND (? IS NULL OR t.account_id = ?)
                    ORDER BY t.tx_date DESC, t.id DESC
                    """,
                    (start.isoformat(), end.isoformat(), account_id, account_id),
                )
            )

    def _eligible_occurrences(self, start: date, end: date, account_id: int | None) -> list:
        with self.db.connect() as conn:
            return list(
                conn.execute(
                    """
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
                    WHERE o.deleted_at IS NULL
                      AND o.expected_date BETWEEN ? AND ?
                      AND (? IS NULL OR o.account_id IS NULL OR o.account_id = ?)
                    ORDER BY o.expected_date DESC, o.id DESC
                    """,
                    (start.isoformat(), end.isoformat(), account_id, account_id),
                )
            )

    def _eligible_proposals(self, start: date, end: date, account_id: int | None) -> list:
        with self.db.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT p.*, o.expected_date, o.expected_label, o.expected_amount,
                           o.matched_amount, o.remaining_amount, o.overage_amount,
                           t.tx_date, t.label AS tx_label, t.amount AS tx_amount,
                           a.name AS account_name
                    FROM forecast_reconciliation_proposals p
                    JOIN forecast_occurrences o ON o.id = p.occurrence_id
                    JOIN transactions t ON t.id = p.transaction_id
                    LEFT JOIN accounts a ON a.id = o.account_id
                    WHERE p.deleted_at IS NULL
                      AND p.status = 'to_review'
                      AND o.deleted_at IS NULL
                      AND o.expected_date BETWEEN ? AND ?
                      AND (? IS NULL OR o.account_id = ?)
                    ORDER BY p.score DESC, o.expected_date, p.id
                    """,
                    (start.isoformat(), end.isoformat(), account_id, account_id),
                )
            )

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
                if self._link_occurrence(best["occurrence"]["id"], tx, best, AUTO_STATUS, "automatic"):
                    summary["auto"] += 1
                else:
                    summary["unmatched"] += 1
            elif best["score"] >= self.REVIEW_THRESHOLD:
                if self._save_proposal(best):
                    summary["to_review"] += 1
                else:
                    summary["unmatched"] += 1
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
                      AND o.status IN ('planned', 'overdue', 'to_review', 'partially_matched')
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

    def _save_proposal(self, scored: dict) -> bool:
        occurrence = scored["occurrence"]
        transaction = scored["transaction"]
        with self.db.connect() as conn:
            existing = conn.execute(
                """
                SELECT id FROM forecast_reconciliation_proposals
                WHERE occurrence_id = ? AND transaction_id = ?
                  AND deleted_at IS NULL AND status = 'to_review'
                """,
                (occurrence["id"], transaction["id"]),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE forecast_reconciliation_proposals SET score = ?, reason = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (int(scored["score"]), scored["reason"], existing["id"]),
                )
                return True
            conn.execute(
                """
                INSERT INTO forecast_reconciliation_proposals(
                    uuid, occurrence_id, transaction_id, score, reason
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid4()), occurrence["id"], transaction["id"], int(scored["score"]), scored["reason"]),
            )
            return True

    def compute_match_score(self, occurrence, transaction) -> tuple[int, str]:
        score = 0
        reasons = []

        if occurrence["account_id"] == transaction["account_id"]:
            score += 30
            reasons.append("compte identique +30")
        else:
            return 0, "compte différent"

        occ_direction = occurrence["direction"]
        tx_direction = "credit" if float(transaction["amount"] or 0) >= 0 else "debit"
        if occ_direction == tx_direction:
            score += 25
            reasons.append("sens identique +25")
        else:
            return 0, "sens différent"

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

    def _transaction_already_linked(self, conn, transaction_id: int, except_occurrence_id: int | None = None) -> bool:
        params = [transaction_id]
        extra = ""
        if except_occurrence_id:
            extra = " AND id <> ?"
            params.append(except_occurrence_id)
        row = conn.execute(
            f"""
            SELECT id FROM forecast_occurrences
            WHERE actual_transaction_id = ?
              AND deleted_at IS NULL
              AND status IN ('auto_matched', 'confirmed', 'to_review')
              {extra}
            LIMIT 1
            """,
            params,
        ).fetchone()
        return row is not None

    def _link_occurrence(self, occurrence_id: int, transaction, scored: dict, status: str, match_type: str) -> bool:
        linked, _ = self.add_reconciliation_link(
            occurrence_id,
            int(transaction["id"]),
            match_type=match_type,
            confidence=int(scored["score"]),
            reason=scored["reason"],
        )
        return linked

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

    def add_reconciliation_link(
        self,
        occurrence_id: int,
        transaction_id: int,
        applied_amount: float | None = None,
        match_type: str = "manual",
        confidence: int | None = None,
        reason: str = "",
    ) -> tuple[bool, str]:
        """Attach one transaction allocation and recalculate the occurrence rollup."""
        with self.db.connect() as conn:
            occurrence = conn.execute(
                "SELECT * FROM forecast_occurrences WHERE id = ? AND deleted_at IS NULL",
                (occurrence_id,),
            ).fetchone()
            transaction = conn.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
            if not occurrence or not transaction:
                return False, "Occurrence ou transaction introuvable."
            if occurrence["account_id"] is not None and int(occurrence["account_id"]) != int(transaction["account_id"]):
                return False, "Le compte de la transaction ne correspond pas à celui de la prévision."
            expected_direction = str(occurrence["direction"])
            transaction_direction = "credit" if float(transaction["amount"] or 0) >= 0 else "debit"
            if expected_direction != transaction_direction:
                return False, "Le sens de la transaction ne correspond pas à celui de la prévision."

            transaction_total = abs(float(transaction["amount"] or 0))
            already_allocated = float(
                conn.execute(
                    "SELECT COALESCE(SUM(applied_amount), 0) FROM forecast_reconciliation_links WHERE transaction_id = ? AND deleted_at IS NULL",
                    (transaction_id,),
                ).fetchone()[0]
            )
            transaction_remaining = max(transaction_total - already_allocated, 0.0)
            occurrence_realized = float(
                conn.execute(
                    "SELECT COALESCE(SUM(applied_amount), 0) FROM forecast_reconciliation_links WHERE occurrence_id = ? AND deleted_at IS NULL",
                    (occurrence_id,),
                ).fetchone()[0]
            )
            occurrence_remaining = max(abs(float(occurrence["expected_amount"] or 0)) - occurrence_realized, 0.0)
            allocation = min(transaction_remaining, occurrence_remaining) if applied_amount is None else abs(float(applied_amount))
            if allocation <= 0.005:
                return False, "Aucun montant restant ne peut être affecté."
            if allocation - transaction_remaining > 0.005:
                return False, "Le montant affecté dépasse le solde disponible de la transaction."

            conn.execute(
                """
                INSERT INTO forecast_reconciliation_links(
                    uuid, occurrence_id, transaction_id, applied_amount,
                    match_type, confidence, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (str(uuid4()), occurrence_id, transaction_id, round(allocation, 2), match_type, confidence, reason),
            )
            self._refresh_occurrence_rollup(conn, occurrence_id)
        return True, "Rapprochement ajouté et montants recalculés."

    def _refresh_occurrence_rollup(self, conn, occurrence_id: int) -> None:
        occurrence = conn.execute(
            "SELECT expected_amount, expected_date FROM forecast_occurrences WHERE id = ?",
            (occurrence_id,),
        ).fetchone()
        links = conn.execute(
            """
            SELECT l.transaction_id, l.applied_amount, l.match_type, t.tx_date
            FROM forecast_reconciliation_links l
            JOIN transactions t ON t.id = l.transaction_id
            WHERE l.occurrence_id = ? AND l.deleted_at IS NULL
            ORDER BY l.created_at, l.id
            """,
            (occurrence_id,),
        ).fetchall()
        expected = abs(float(occurrence["expected_amount"] or 0))
        realized = round(sum(float(link["applied_amount"] or 0) for link in links), 2)
        remaining = round(max(expected - realized, 0.0), 2)
        overage = round(max(realized - expected, 0.0), 2)
        tolerance = max(0.01, expected * 0.02)
        if not links:
            status = "overdue" if _parse_date(occurrence["expected_date"]) < date.today() else "planned"
        elif remaining > tolerance:
            status = "partially_matched"
        else:
            status = "auto_matched" if len(links) == 1 and links[0]["match_type"] == "automatic" else "confirmed"
        first = links[0] if links else None
        conn.execute(
            """
            UPDATE forecast_occurrences
            SET status = ?, actual_transaction_id = ?, actual_date = ?, actual_amount = ?,
                amount_delta = ?, matched_amount = ?, remaining_amount = ?, overage_amount = ?,
                match_type = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                status,
                first["transaction_id"] if first else None,
                first["tx_date"] if first else None,
                (-realized if occurrence["expected_amount"] < 0 else realized) if links else None,
                ((-realized if occurrence["expected_amount"] < 0 else realized) - float(occurrence["expected_amount"])) if links else None,
                realized,
                remaining,
                overage,
                "multi" if len(links) > 1 else (first["match_type"] if first else None),
                occurrence_id,
            ),
        )

    def cancel_reconciliation_link(self, occurrence_id: int, transaction_id: int) -> tuple[bool, str]:
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE forecast_reconciliation_links
                SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE occurrence_id = ? AND transaction_id = ? AND deleted_at IS NULL
                """,
                (occurrence_id, transaction_id),
            )
            if not cursor.rowcount:
                return False, "Rapprochement introuvable."
            self._refresh_occurrence_rollup(conn, occurrence_id)
        return True, "Rapprochement annulé et montants recalculés."

    def list_imported_transactions(self, start_date=None, end_date=None, account_id=None, limit: int | None = None) -> list:
        return self.build_reconciliation_dataset(start_date, end_date, account_id, "active", limit)["transactions"]

    def list_occurrences(self, status: str | None = "active", start_date=None, end_date=None, account_id=None, limit: int | None = None) -> list:
        return self.build_reconciliation_dataset(start_date, end_date, account_id, status, limit)["occurrences"]

    def summary(self, start_date=None, end_date=None, account_id=None) -> dict:
        return self.build_reconciliation_dataset(start_date, end_date, account_id, "all", 999999)["summary"]

    def confirm_manual_match(self, occurrence_id: int, transaction_id: int) -> tuple[int, str]:
        with self.db.connect() as conn:
            occurrence = conn.execute("SELECT * FROM forecast_occurrences WHERE id = ? AND deleted_at IS NULL", (occurrence_id,)).fetchone()
            transaction = conn.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
            if not occurrence or not transaction:
                return 0, "Occurrence ou transaction introuvable."

        score, reason = self.compute_match_score(occurrence, transaction)
        linked = self._link_occurrence(
            occurrence_id,
            transaction,
            {"occurrence": occurrence, "transaction": transaction, "score": max(score, 100 if score >= 60 else score), "reason": "Rapprochement manuel. " + reason},
            MANUAL_STATUS,
            "manual",
        )
        return (1, "Rapprochement manuel confirmé.") if linked else (0, "Rapprochement impossible : lien incompatible.")

    def confirm_match(self, occurrence_id: int) -> tuple[int, str]:
        """R7.2 safeguard: no finalization without a real linked transaction."""
        with self.db.connect() as conn:
            row = conn.execute("SELECT actual_transaction_id FROM forecast_occurrences WHERE id = ?", (occurrence_id,)).fetchone()
            if not row:
                return 0, "Occurrence introuvable."
            if row["actual_transaction_id"] is None:
                return 0, "R7.2 interdit de confirmer une occurrence sans transaction bancaire liée."
            conn.execute("UPDATE forecast_occurrences SET status = 'confirmed', match_type = 'manual', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (occurrence_id,))
        return 1, "Occurrence rapprochée manuellement."

    def cancel_match(self, occurrence_id: int) -> None:
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
                    match_type = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, occurrence_id),
            )

    def reject_match(self, occurrence_id: int) -> None:
        # Compatibility alias. UI R7.2 exposes this as “Annuler rapprochement”.
        self.cancel_match(occurrence_id)

    def ignore_occurrence(self, occurrence_id: int, reason: str = "") -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                UPDATE forecast_occurrences
                SET status = 'ignored', ignored_reason = ?, actual_transaction_id = NULL,
                    actual_date = NULL, actual_amount = NULL, amount_delta = NULL,
                    match_confidence = NULL, match_reason = NULL, match_type = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (reason, occurrence_id),
            )
