from __future__ import annotations

import json
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

    DEFAULT_RULES = {
        "require_same_account": True,
        "require_same_direction": True,
        "date_tolerance_days": 5,
        "amount_tolerance_abs": 1.0,
        "amount_tolerance_percent": 2.0,
        "label_similarity_min": 45,
        "auto_threshold": 90,
        "review_threshold": 60,
        "ambiguity_min_delta": 10,
    }

    def __init__(self, db) -> None:
        self.db = db
        self._rules_cache: dict | None = None

    @staticmethod
    def _setting_number(value: str, default: int | float, *, integer: bool = False) -> int | float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return int(default) if integer else float(default)
        return int(number) if integer else number

    def rules_config(self, refresh: bool = False) -> dict:
        if self._rules_cache is not None and not refresh:
            return dict(self._rules_cache)
        defaults = self.DEFAULT_RULES
        config = {
            # Issue #57: these are safeguards, not optional scoring bonuses.
            # Even a manually altered settings row must never bypass them.
            "require_same_account": True,
            "require_same_direction": True,
            "date_tolerance_days": self._setting_number(
                self.db.get_setting("reconciliation.date_tolerance_days", str(defaults["date_tolerance_days"])),
                defaults["date_tolerance_days"], integer=True,
            ),
            "amount_tolerance_abs": self._setting_number(
                self.db.get_setting("reconciliation.amount_tolerance_abs", str(defaults["amount_tolerance_abs"])),
                defaults["amount_tolerance_abs"],
            ),
            "amount_tolerance_percent": self._setting_number(
                self.db.get_setting("reconciliation.amount_tolerance_percent", str(defaults["amount_tolerance_percent"])),
                defaults["amount_tolerance_percent"],
            ),
            "label_similarity_min": self._setting_number(
                self.db.get_setting("reconciliation.label_similarity_min", str(defaults["label_similarity_min"])),
                defaults["label_similarity_min"], integer=True,
            ),
            "auto_threshold": self._setting_number(
                self.db.get_setting("reconciliation.auto_threshold", str(defaults["auto_threshold"])),
                defaults["auto_threshold"], integer=True,
            ),
            "review_threshold": self._setting_number(
                self.db.get_setting("reconciliation.review_threshold", str(defaults["review_threshold"])),
                defaults["review_threshold"], integer=True,
            ),
            "ambiguity_min_delta": self._setting_number(
                self.db.get_setting("reconciliation.ambiguity_min_delta", str(defaults["ambiguity_min_delta"])),
                defaults["ambiguity_min_delta"], integer=True,
            ),
        }
        config["date_tolerance_days"] = max(0, min(config["date_tolerance_days"], 60))
        config["amount_tolerance_abs"] = max(0.0, config["amount_tolerance_abs"])
        config["amount_tolerance_percent"] = max(0.0, min(config["amount_tolerance_percent"], 100.0))
        config["label_similarity_min"] = max(0, min(config["label_similarity_min"], 100))
        config["auto_threshold"] = max(1, min(config["auto_threshold"], 100))
        config["review_threshold"] = max(0, min(config["review_threshold"], 99))
        config["ambiguity_min_delta"] = max(0, min(config["ambiguity_min_delta"], 100))
        if config["review_threshold"] >= config["auto_threshold"]:
            config["review_threshold"] = max(0, config["auto_threshold"] - 1)
        self._rules_cache = config
        return dict(config)

    def save_rules_config(self, config: dict) -> dict:
        merged = {**self.DEFAULT_RULES, **dict(config or {})}
        auto_threshold = int(self._setting_number(merged["auto_threshold"], self.DEFAULT_RULES["auto_threshold"], integer=True))
        review_threshold = int(self._setting_number(merged["review_threshold"], self.DEFAULT_RULES["review_threshold"], integer=True))
        if review_threshold >= auto_threshold:
            raise ValueError("Le seuil À vérifier doit être inférieur au seuil Rapprochée auto.")
        keys = {
            "require_same_account": "true",
            "require_same_direction": "true",
            "date_tolerance_days": str(self._setting_number(merged["date_tolerance_days"], self.DEFAULT_RULES["date_tolerance_days"], integer=True)),
            "amount_tolerance_abs": str(self._setting_number(merged["amount_tolerance_abs"], self.DEFAULT_RULES["amount_tolerance_abs"])),
            "amount_tolerance_percent": str(self._setting_number(merged["amount_tolerance_percent"], self.DEFAULT_RULES["amount_tolerance_percent"])),
            "label_similarity_min": str(self._setting_number(merged["label_similarity_min"], self.DEFAULT_RULES["label_similarity_min"], integer=True)),
            "auto_threshold": str(auto_threshold),
            "review_threshold": str(review_threshold),
            "ambiguity_min_delta": str(self._setting_number(merged["ambiguity_min_delta"], self.DEFAULT_RULES["ambiguity_min_delta"], integer=True)),
        }
        for key, value in keys.items():
            self.db.set_setting(f"reconciliation.{key}", value)
        self._rules_cache = None
        return self.rules_config(refresh=True)

    def decision_for_score(self, score: int) -> str:
        rules = self.rules_config()
        if int(score) >= int(rules["auto_threshold"]):
            return "automatic"
        if int(score) >= int(rules["review_threshold"]):
            return "to_review"
        return "unmatched"

    def decision_for_candidates(self, candidates: list[dict]) -> str:
        """Apply thresholds and the mandatory ambiguity guard to a ranking."""
        if not candidates:
            return "unmatched"
        decision = self.decision_for_score(int(candidates[0]["score"]))
        if decision == "automatic" and len(candidates) > 1:
            delta = int(candidates[0]["score"]) - int(candidates[1]["score"])
            if delta < int(self.rules_config()["ambiguity_min_delta"]):
                return "to_review"
        return decision

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
            fully_allocated = float(tx["allocated_amount"] or 0) >= abs(float(tx["amount"] or 0)) - 0.005
            if status in {None, "", "active", "all_active"}:
                if tx["linked_occurrence_id"] and fully_allocated:
                    continue
                candidates = self.find_candidates(tx)
                if not candidates or self.decision_for_candidates(candidates) == "unmatched":
                    continue
                filtered_transactions.append(tx)
            elif status == "all":
                filtered_transactions.append(tx)
            elif status == "finalized":
                if tx["linked_status"] in FINAL_STATUSES:
                    filtered_transactions.append(tx)
            elif status in {"auto_matched", "confirmed", "partially_matched"}:
                if tx["linked_status"] == status:
                    filtered_transactions.append(tx)
            elif status == "to_review":
                if tx["linked_status"] == "to_review" or tx["proposal_occurrence_id"] is not None:
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
                            ORDER BY l.id LIMIT 1) AS linked_status,
                           (SELECT COALESCE(SUM(l.applied_amount), 0)
                            FROM forecast_reconciliation_links l
                            WHERE l.transaction_id = t.id AND l.deleted_at IS NULL) AS allocated_amount
                           ,(SELECT p.occurrence_id
                             FROM forecast_reconciliation_proposals p
                             JOIN forecast_occurrences po ON po.id = p.occurrence_id
                             WHERE p.transaction_id = t.id AND p.deleted_at IS NULL AND p.status = 'to_review'
                               AND po.deleted_at IS NULL AND po.status = 'to_review'
                             ORDER BY p.score DESC, p.id LIMIT 1) AS proposal_occurrence_id
                    FROM transactions t
                    JOIN accounts a ON a.id = t.account_id
                    WHERE a.status = 'Actif'
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
                      AND o.status = 'to_review'
                      AND o.expected_date BETWEEN ? AND ?
                      AND (? IS NULL OR o.account_id = ?)
                    ORDER BY p.score DESC, o.expected_date, p.id
                    """,
                    (start.isoformat(), end.isoformat(), account_id, account_id),
                )
            )

    def prepare_best_proposals(
        self,
        start_date: str | date,
        end_date: str | date,
        account_id: int | None = None,
        transactions: list | None = None,
        reconsider_rejected: bool = False,
    ) -> list:
        """Materialize the best review proposal for each eligible transaction.

        Proposals are produced by the engine before any UI selection. A rejected
        pair is not silently recreated; the next eligible candidate may then be
        proposed instead.
        """
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        candidates_transactions = transactions if transactions is not None else self._eligible_transactions(start, end, account_id)

        for transaction in candidates_transactions:
            transaction_id = int(transaction["id"])
            fully_allocated = float(transaction["allocated_amount"] or 0) >= abs(float(transaction["amount"] or 0)) - 0.005
            if fully_allocated:
                continue
            with self.db.connect() as conn:
                pending = conn.execute(
                    """
                    SELECT id, occurrence_id FROM forecast_reconciliation_proposals
                    WHERE transaction_id = ? AND deleted_at IS NULL AND status = 'to_review'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (transaction_id,),
                ).fetchone()

            ranked = self.find_candidates(transaction)
            decision = self.decision_for_candidates(ranked)
            if decision == "unmatched":
                continue
            scored = ranked[0]
            if decision == "automatic":
                occurrence_id = int(scored["occurrence"]["id"])
                if self._link_occurrence(
                    occurrence_id,
                    transaction,
                    scored,
                    AUTO_STATUS,
                    "automatic",
                ):
                    # A proposal may already exist in an upgraded user
                    # database. Close it atomically from the UI perspective
                    # so a 100% candidate is not left in "À vérifier".
                    with self.db.connect() as conn:
                        conn.execute(
                            """
                            UPDATE forecast_reconciliation_proposals
                            SET status = 'accepted', updated_at = CURRENT_TIMESTAMP
                            WHERE transaction_id = ?
                              AND occurrence_id = ?
                              AND deleted_at IS NULL
                              AND status = 'to_review'
                            """,
                            (transaction_id, occurrence_id),
                        )
                continue
            if pending:
                continue
            self._save_proposal(scored, reconsider_rejected=reconsider_rejected)

        return self._eligible_proposals(start, end, account_id)

    def reconcile_import_batch(self, import_batch_id: int) -> dict:
        transactions = self._imported_transactions(import_batch_id)
        if not transactions:
            return {"auto": 0, "to_review": 0, "unmatched": 0, "generated": 0}

        date_tolerance = int(self.rules_config()["date_tolerance_days"])
        min_day = min(_parse_date(tx["tx_date"]) for tx in transactions) - timedelta(days=date_tolerance)
        max_day = max(_parse_date(tx["tx_date"]) for tx in transactions) + timedelta(days=date_tolerance)
        generated = self.generate_occurrences(min_day, max_day)

        summary = {"auto": 0, "to_review": 0, "unmatched": 0, "generated": generated}
        for tx in transactions:
            candidates = self.find_candidates(tx)
            if not candidates:
                summary["unmatched"] += 1
                continue
            best = candidates[0]
            decision = self.decision_for_candidates(candidates)
            if decision == "automatic":
                if self._link_occurrence(best["occurrence"]["id"], tx, best, AUTO_STATUS, "automatic"):
                    summary["auto"] += 1
                else:
                    summary["unmatched"] += 1
            elif decision == "to_review":
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
        rules = self.rules_config()
        tx_date = _parse_date(transaction["tx_date"])
        date_tolerance = int(rules["date_tolerance_days"])
        start = (tx_date - timedelta(days=date_tolerance)).isoformat()
        end = (tx_date + timedelta(days=date_tolerance)).isoformat()
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
                      AND (? = 0 OR o.account_id = ?)
                      AND (? = 0 OR o.direction = ?)
                      AND o.expected_date BETWEEN ? AND ?
                      AND (o.actual_transaction_id IS NULL OR o.actual_transaction_id = ?)
                    ORDER BY o.expected_date, o.id
                    """,
                    (
                        1 if rules["require_same_account"] else 0,
                        transaction["account_id"],
                        1 if rules["require_same_direction"] else 0,
                        direction,
                        start,
                        end,
                        transaction["id"],
                    ),
                )
            )

        scored = []
        for occurrence in rows:
            score, reason = self.compute_match_score(occurrence, transaction)
            scored.append({"occurrence": occurrence, "transaction": transaction, "score": score, "reason": reason})
        return sorted(
            scored,
            key=lambda row: (
                -int(row["score"]),
                abs(abs(float(row["transaction"]["amount"] or 0)) - abs(float(row["occurrence"]["expected_amount"] or 0))),
                abs((_parse_date(row["transaction"]["tx_date"]) - _parse_date(row["occurrence"]["expected_date"])).days),
                int(row["occurrence"]["id"]),
            ),
        )

    def _save_proposal(self, scored: dict, *, reconsider_rejected: bool = False) -> bool:
        occurrence = scored["occurrence"]
        transaction = scored["transaction"]
        with self.db.connect() as conn:
            existing = conn.execute(
                """
                SELECT id, status FROM forecast_reconciliation_proposals
                WHERE occurrence_id = ? AND transaction_id = ?
                  AND deleted_at IS NULL
                ORDER BY id DESC LIMIT 1
                """,
                (occurrence["id"], transaction["id"]),
            ).fetchone()
            if existing:
                if existing["status"] != "to_review" and not reconsider_rejected:
                    return False
                conn.execute(
                    """
                    UPDATE forecast_reconciliation_proposals
                    SET status = 'to_review', score = ?, reason = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (int(scored["score"]), scored["reason"], existing["id"]),
                )
                conn.execute(
                    "UPDATE forecast_occurrences SET status = 'to_review', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status IN ('planned', 'overdue')",
                    (occurrence["id"],),
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
            conn.execute(
                "UPDATE forecast_occurrences SET status = 'to_review', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status IN ('planned', 'overdue')",
                (occurrence["id"],),
            )
            self.db.audit_event(
                conn,
                "reconciliation_proposed",
                "forecast_occurrence",
                str(occurrence["id"]),
                "Proposition de rapprochement créée automatiquement.",
                {"transaction_id": int(transaction["id"]), "score": int(scored["score"]), "reason": scored["reason"]},
            )
            return True

    def confirm_proposal(self, proposal_id: int) -> tuple[bool, str]:
        with self.db.connect() as conn:
            proposal = conn.execute(
                "SELECT * FROM forecast_reconciliation_proposals WHERE id = ? AND deleted_at IS NULL AND status = 'to_review'",
                (proposal_id,),
            ).fetchone()
        if not proposal:
            return False, "Proposition introuvable ou déjà traitée."
        linked, message = self.add_reconciliation_link(
            int(proposal["occurrence_id"]),
            int(proposal["transaction_id"]),
            match_type="manual",
            confidence=int(proposal["score"]),
            reason="Proposition validée manuellement. " + str(proposal["reason"] or ""),
        )
        if not linked:
            return False, message
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE forecast_reconciliation_proposals SET status = 'accepted', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (proposal_id,),
            )
        return True, "Proposition validée et rapprochement recalculé."

    def reject_proposal(self, proposal_id: int) -> tuple[bool, str]:
        with self.db.connect() as conn:
            proposal = conn.execute(
                "SELECT occurrence_id, transaction_id FROM forecast_reconciliation_proposals WHERE id = ? AND deleted_at IS NULL AND status = 'to_review'",
                (proposal_id,),
            ).fetchone()
            if not proposal:
                return False, "Proposition introuvable ou déjà traitée."
            cursor = conn.execute(
                """
                UPDATE forecast_reconciliation_proposals
                SET status = 'rejected', updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND deleted_at IS NULL AND status = 'to_review'
                """,
                (proposal_id,),
            )
            remaining = conn.execute(
                "SELECT COUNT(*) FROM forecast_reconciliation_proposals WHERE occurrence_id = ? AND deleted_at IS NULL AND status = 'to_review'",
                (proposal["occurrence_id"],),
            ).fetchone()[0]
            if not remaining:
                occurrence = conn.execute(
                    "SELECT expected_date FROM forecast_occurrences WHERE id = ?",
                    (proposal["occurrence_id"],),
                ).fetchone()
                restored = "overdue" if occurrence and _parse_date(occurrence["expected_date"]) < date.today() else "planned"
                conn.execute(
                    "UPDATE forecast_occurrences SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'to_review'",
                    (restored, proposal["occurrence_id"]),
                )
            self.db.audit_event(
                conn,
                "reconciliation_proposal_rejected",
                "forecast_occurrence",
                str(proposal["occurrence_id"]),
                "Proposition de rapprochement rejetée.",
                {"transaction_id": int(proposal["transaction_id"])},
            )
        return (True, "Proposition rejetée.") if cursor.rowcount else (False, "Proposition introuvable ou déjà traitée.")

    def compute_match_score(self, occurrence, transaction) -> tuple[int, str]:
        rules = self.rules_config()
        score = 0
        reasons = []

        if occurrence["account_id"] == transaction["account_id"]:
            score += 30
            reasons.append("compte identique +30")
        elif rules["require_same_account"]:
            return 0, "compte différent"
        else:
            reasons.append("compte différent autorisé")

        occ_direction = occurrence["direction"]
        tx_direction = "credit" if float(transaction["amount"] or 0) >= 0 else "debit"
        if occ_direction == tx_direction:
            score += 25
            reasons.append("sens identique +25")
        elif rules["require_same_direction"]:
            return 0, "sens différent"
        else:
            reasons.append("sens différent autorisé")

        expected = abs(float(occurrence["expected_amount"] or 0))
        actual = abs(float(transaction["amount"] or 0))
        delta = abs(actual - expected)
        tolerance = max(
            float(rules["amount_tolerance_abs"]),
            expected * float(rules["amount_tolerance_percent"]) / 100.0,
        )
        # The configured amount interval is a hard eligibility rule. A close
        # date or label must never compensate for an amount outside tolerance.
        if delta > tolerance:
            return 0, (
                f"montant hors tolérance, écart {delta:.2f}, "
                f"tolérance {tolerance:.2f}"
            )
        if delta <= 0.01:
            score += 25
            reasons.append("montant exact +25")
        else:
            score += 20
            reasons.append(
                f"montant dans la tolérance +20, écart {delta:.2f}, "
                f"tolérance {tolerance:.2f}"
            )

        days = abs((_parse_date(transaction["tx_date"]) - _parse_date(occurrence["expected_date"])).days)
        if days <= 1:
            score += 15
            reasons.append(f"date très proche +15 ({days} j)")
        elif days <= 3:
            score += 12
            reasons.append(f"date proche +12 ({days} j)")
        elif days <= int(rules["date_tolerance_days"]):
            score += 8
            reasons.append(f"date tolérée +8 ({days} j)")
        else:
            reasons.append(f"date hors tolérance ({days} j)")

        expected_label = _norm(occurrence["expected_label"])
        tx_label = _norm(transaction["label"])
        if expected_label and tx_label:
            ratio = SequenceMatcher(None, expected_label, tx_label).ratio()
            token_hit = any(token and token in tx_label for token in expected_label.split() if len(token) >= 4)
            if token_hit or ratio * 100 >= int(rules["label_similarity_min"]):
                score += 5
                reasons.append("libellé compatible +5")

        occ_cat = _norm(occurrence["expected_category"])
        tx_cat = _norm(transaction["category"])
        if occ_cat and tx_cat and occ_cat == tx_cat:
            score += 5
            reasons.append("catégorie identique +5")

        source_identifier = _norm(transaction["source_identifier"] if "source_identifier" in transaction.keys() else "")
        if source_identifier and expected_label and source_identifier in expected_label:
            score += 5
            reasons.append("référence bancaire compatible +5")

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
            self.db.audit_event(
                conn,
                "reconciliation_linked",
                "forecast_occurrence",
                str(occurrence_id),
                "Transaction rapprochée avec l’occurrence.",
                {
                    "transaction_id": int(transaction_id),
                    "match_type": match_type,
                    "confidence": confidence,
                    "applied_amount": round(allocation, 2),
                    "reason": reason,
                },
            )
        return True, "Rapprochement ajouté et montants recalculés."

    def _refresh_occurrence_rollup(self, conn, occurrence_id: int) -> None:
        occurrence = conn.execute(
            "SELECT expected_amount, expected_date FROM forecast_occurrences WHERE id = ?",
            (occurrence_id,),
        ).fetchone()
        links = conn.execute(
            """
            SELECT l.transaction_id, l.applied_amount, l.match_type,
                   l.confidence, l.reason, t.tx_date
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
        rules = self.rules_config()
        tolerance = max(
            0.01,
            float(rules["amount_tolerance_abs"]),
            expected * float(rules["amount_tolerance_percent"]) / 100.0,
        )
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
                match_type = ?, match_confidence = ?, match_reason = ?,
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
                first["confidence"] if first else None,
                first["reason"] if first else None,
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
            self.db.audit_event(
                conn,
                "reconciliation_unlinked",
                "forecast_occurrence",
                str(occurrence_id),
                "Rapprochement annulé.",
                {"transaction_id": int(transaction_id)},
            )
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

    def cancel_match(self, occurrence_id: int) -> tuple[bool, str]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT expected_date FROM forecast_occurrences WHERE id = ? AND deleted_at IS NULL", (occurrence_id,)).fetchone()
            if not row:
                return False, "Occurrence introuvable."
            cursor = conn.execute(
                "UPDATE forecast_reconciliation_links SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE occurrence_id = ? AND deleted_at IS NULL",
                (occurrence_id,),
            )
            if not cursor.rowcount:
                return False, "Aucun rapprochement actif à annuler."
            status = "overdue" if _parse_date(row["expected_date"]) < date.today() else "planned"
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
                    matched_amount = 0,
                    remaining_amount = ABS(expected_amount),
                    overage_amount = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, occurrence_id),
            )
            self.db.audit_event(
                conn,
                "reconciliation_cancelled",
                "forecast_occurrence",
                str(occurrence_id),
                "Tous les rapprochements actifs ont été annulés.",
                {"restored_status": status},
            )
        return True, "Rapprochement annulé ; la transaction et l’occurrence sont de nouveau disponibles."

    def reject_match(self, occurrence_id: int) -> None:
        # Compatibility alias. UI R7.2 exposes this as “Annuler rapprochement”.
        self.cancel_match(occurrence_id)

    def ignore_occurrence(self, occurrence_id: int, reason: str = "") -> tuple[bool, str]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT status FROM forecast_occurrences WHERE id = ? AND deleted_at IS NULL", (occurrence_id,)).fetchone()
            if not row:
                return False, "Occurrence introuvable."
            active_links = conn.execute(
                "SELECT COUNT(*) FROM forecast_reconciliation_links WHERE occurrence_id = ? AND deleted_at IS NULL",
                (occurrence_id,),
            ).fetchone()[0]
            if active_links:
                return False, "Annule d’abord le rapprochement actif de cette occurrence."
            conn.execute(
                "UPDATE forecast_reconciliation_proposals SET status = 'rejected', updated_at = CURRENT_TIMESTAMP WHERE occurrence_id = ? AND deleted_at IS NULL AND status = 'to_review'",
                (occurrence_id,),
            )
            conn.execute(
                """
                UPDATE forecast_occurrences
                SET status = 'ignored', ignored_reason = ?, actual_transaction_id = NULL,
                    actual_date = NULL, actual_amount = NULL, amount_delta = NULL,
                    match_confidence = NULL, match_reason = NULL, match_type = NULL,
                    matched_amount = 0, remaining_amount = ABS(expected_amount), overage_amount = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (reason, occurrence_id),
            )
            self.db.audit_event(
                conn,
                "occurrence_ignored",
                "forecast_occurrence",
                str(occurrence_id),
                "Occurrence ignorée.",
                {"previous_status": row["status"], "reason": reason},
            )
        return True, "Occurrence ignorée et conservée dans l’historique."

    def restore_occurrence(self, occurrence_id: int, reference_date: str | date | None = None) -> tuple[bool, str]:
        reference = _parse_date(reference_date) if reference_date else date.today()
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT expected_date, status, ignored_reason FROM forecast_occurrences WHERE id = ? AND deleted_at IS NULL",
                (occurrence_id,),
            ).fetchone()
            if not row or row["status"] != "ignored":
                return False, "Cette occurrence n’est pas au statut Ignorée."
            status = "overdue" if _parse_date(row["expected_date"]) < reference else "planned"
            conn.execute(
                "UPDATE forecast_occurrences SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, occurrence_id),
            )
            self.db.audit_event(
                conn,
                "occurrence_restored",
                "forecast_occurrence",
                str(occurrence_id),
                "Occurrence remise à traiter.",
                {"restored_status": status, "original_ignored_reason": row["ignored_reason"] or ""},
            )
        return True, "Occurrence remise à traiter avec son historique conservé."

    def cancel_occurrence(self, occurrence_id: int, reason: str = "") -> tuple[bool, str]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT status FROM forecast_occurrences WHERE id = ? AND deleted_at IS NULL",
                (occurrence_id,),
            ).fetchone()
            if not row:
                return False, "Occurrence introuvable."
            active_links = conn.execute(
                "SELECT COUNT(*) FROM forecast_reconciliation_links WHERE occurrence_id = ? AND deleted_at IS NULL",
                (occurrence_id,),
            ).fetchone()[0]
            if active_links:
                return False, "Annule d’abord le rapprochement actif de cette occurrence."
            if row["status"] not in ACTIVE_STATUSES:
                return False, "Seule une occurrence à traiter peut être annulée."
            conn.execute(
                "UPDATE forecast_reconciliation_proposals SET status = 'rejected', updated_at = CURRENT_TIMESTAMP WHERE occurrence_id = ? AND deleted_at IS NULL AND status = 'to_review'",
                (occurrence_id,),
            )
            conn.execute(
                """
                UPDATE forecast_occurrences
                SET status = 'cancelled', cancelled_reason = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (reason, occurrence_id),
            )
            self.db.audit_event(
                conn,
                "occurrence_cancelled",
                "forecast_occurrence",
                str(occurrence_id),
                "Occurrence annulée.",
                {"previous_status": row["status"], "reason": reason},
            )
        return True, "Occurrence annulée et conservée dans l’historique."

    def occurrence_details(self, occurrence_id: int) -> dict | None:
        with self.db.connect() as conn:
            occurrence = conn.execute(
                """
                SELECT o.*, a.name AS account_name, a.bank AS bank,
                       r.name AS recurring_name, r.frequency AS recurring_frequency
                FROM forecast_occurrences o
                LEFT JOIN accounts a ON a.id = o.account_id
                LEFT JOIN recurring_items r ON o.source_type = 'recurring' AND r.id = o.source_id
                WHERE o.id = ? AND o.deleted_at IS NULL
                """,
                (occurrence_id,),
            ).fetchone()
            if not occurrence:
                return None
            links = list(conn.execute(
                """
                SELECT l.*, t.tx_date, t.label AS tx_label, t.amount AS tx_amount,
                       CASE WHEN l.deleted_at IS NULL THEN 1 ELSE 0 END AS active
                FROM forecast_reconciliation_links l
                JOIN transactions t ON t.id = l.transaction_id
                WHERE l.occurrence_id = ?
                ORDER BY l.created_at, l.id
                """,
                (occurrence_id,),
            ))
            history_rows = list(conn.execute(
                """
                SELECT event_type, message, metadata_json, created_at
                FROM audit_log
                WHERE entity = 'forecast_occurrence' AND entity_id = ?
                ORDER BY created_at, id
                """,
                (str(occurrence_id),),
            ))
        history = []
        for row in history_rows:
            try:
                metadata = json.loads(row["metadata_json"] or "{}")
            except Exception:
                metadata = {}
            history.append({"event_type": row["event_type"], "message": row["message"], "created_at": row["created_at"], "metadata": metadata})
        return {"occurrence": dict(occurrence), "links": [dict(row) for row in links], "history": history}
