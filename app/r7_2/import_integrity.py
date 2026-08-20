from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

_PATCHED = False


def _normalise_label(label: str | None) -> str:
    return " ".join(str(label or "").lower().strip().split())[:120]


def _safe_json_loads(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def _canonical_payload(raw_payload: Any) -> str:
    payload = _safe_json_loads(raw_payload)
    if payload is None:
        return ""
    if isinstance(payload, dict):
        cleaned = {
            str(k).strip(): str(v).strip()
            for k, v in payload.items()
            if k is not None and str(v or "").strip()
        }
        return json.dumps(cleaned, ensure_ascii=False, sort_keys=True)
    return str(payload).strip()


def _extract_reference_tokens(raw_payload: Any) -> list[str]:
    """Extract bank references likely to distinguish two legitimate rows.

    This deliberately keeps long alphanumeric or numeric references from the
    source payload. These values are not used for display; they only enrich the
    technical duplicate signature.
    """
    text = _canonical_payload(raw_payload)
    if not text:
        return []
    tokens = []
    # Long numeric references, card/backend IDs, technical references.
    for match in re.findall(r"[A-Z0-9]{8,}", text.upper()):
        if match not in tokens:
            tokens.append(match)
    return tokens[:8]


def import_discriminant(source_identifier: str | None = None, raw_payload: Any = None, source_line: int | None = None) -> str:
    """Build a stable discriminant for imported bank rows.

    Priority:
    1. explicit bank source identifier when available;
    2. discriminating references extracted from the raw payload;
    3. canonical raw payload hash;
    4. source line only as a last-resort local fallback.

    The canonical raw payload makes a re-import of the same bank line produce
    the same discriminant, while two legitimate similar bank operations can stay
    distinct when their source payload differs.
    """
    clean_source = re.sub(r"\s+", "", str(source_identifier or "")).strip()
    if clean_source:
        return f"src:{clean_source}"

    refs = _extract_reference_tokens(raw_payload)
    if refs:
        digest = hashlib.sha1("|".join(refs).encode("utf-8")).hexdigest()[:16]
        return f"refs:{digest}"

    canonical = _canonical_payload(raw_payload)
    if canonical:
        digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]
        return f"payload:{digest}"

    if source_line is not None:
        return f"line:{int(source_line)}"
    return ""


def r7_2_signature(
    account_id: int,
    tx_date: str,
    label: str,
    amount: float,
    *,
    source_identifier: str | None = None,
    raw_payload: Any = None,
    source_line: int | None = None,
) -> str:
    base = f"{account_id}|{tx_date}|{round(float(amount or 0), 2)}|{_normalise_label(label)}"
    discriminant = import_discriminant(source_identifier, raw_payload, source_line)
    return f"{base}|{discriminant}" if discriminant else base


def ensure_import_audit_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS import_line_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_batch_id INTEGER,
            file_name TEXT,
            account_id INTEGER,
            source_line INTEGER,
            decision TEXT NOT NULL,
            reason TEXT,
            tx_date TEXT,
            label TEXT,
            amount REAL,
            signature TEXT,
            source_identifier TEXT,
            source_profile TEXT,
            raw_payload TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(import_batch_id) REFERENCES import_batches(id) ON DELETE SET NULL,
            FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE SET NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_import_line_audit_batch ON import_line_audit(import_batch_id, source_line)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_import_line_audit_decision ON import_line_audit(decision)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_import_line_audit_signature ON import_line_audit(signature)")


def apply_r7_2_import_integrity_patch() -> None:
    """Patch the existing R7.2.2.1 data layer without changing main branch.

    This is intentionally scoped to Lot 1 / beginning of Lot 2:
    - stronger import signatures for false duplicate #53;
    - persistent import-line audit table;
    - preview duplicate detection using the same signature logic as final write.
    """
    global _PATCHED
    if _PATCHED:
        return

    from app.database import Database

    original_apply_migrations = Database.apply_migrations

    def apply_migrations_with_r7_2_import_integrity(self, conn):
        original_apply_migrations(self, conn)
        ensure_import_audit_schema(conn)

    def make_signature_with_discriminant(
        self,
        account_id: int,
        tx_date: str,
        label: str,
        amount: float,
        source_identifier: str | None = None,
        raw_payload: Any = None,
        source_line: int | None = None,
    ) -> str:
        return r7_2_signature(
            account_id,
            tx_date,
            label,
            amount,
            source_identifier=source_identifier,
            raw_payload=raw_payload,
            source_line=source_line,
        )

    def audit_import_line(
        self,
        *,
        import_batch_id: int | None,
        file_name: str | None,
        account_id: int | None,
        source_line: int | None,
        decision: str,
        reason: str | None,
        tx_date: str | None,
        label: str | None,
        amount: float | None,
        signature: str | None,
        source_identifier: str | None,
        source_profile: str | None,
        raw_payload: str | None,
    ) -> None:
        with self.connect() as conn:
            ensure_import_audit_schema(conn)
            conn.execute(
                """
                INSERT INTO import_line_audit(
                    import_batch_id, file_name, account_id, source_line, decision, reason,
                    tx_date, label, amount, signature, source_identifier, source_profile, raw_payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    import_batch_id,
                    file_name,
                    account_id,
                    source_line,
                    decision,
                    reason,
                    tx_date,
                    label,
                    amount,
                    signature,
                    source_identifier,
                    source_profile,
                    raw_payload,
                ),
            )

    def insert_transaction_with_import_discriminant(
        self,
        account_id: int,
        tx_date: str,
        label: str,
        category: str | None,
        amount: float,
        source: str,
        import_batch_id: int | None = None,
        *,
        currency: str = "EUR",
        source_line: int | None = None,
        source_profile: str | None = None,
        raw_payload: str | None = None,
        source_identifier: str | None = None,
    ) -> bool:
        if source == "Manuel":
            amount = self.normalize_amount_for_category(category, amount)
        tx_type = "Crédit" if amount >= 0 else "Débit"
        status = "Validée" if category else "À catégoriser"
        if source == "Manuel":
            categorization_status = "manual" if category else "to_categorize"
            categorized_by = "manual" if category else None
            categorized_at = datetime.now().isoformat(timespec="seconds") if category else None
            signature = r7_2_signature(account_id, tx_date, label, amount)
        else:
            categorization_status = "to_categorize"
            categorized_by = "import_default" if category else None
            categorized_at = None
            signature = r7_2_signature(
                account_id,
                tx_date,
                label,
                amount,
                source_identifier=source_identifier,
                raw_payload=raw_payload,
                source_line=source_line,
            )

        with self.connect() as conn:
            ensure_import_audit_schema(conn)
            exists = conn.execute("SELECT id FROM transactions WHERE signature = ?", (signature,)).fetchone()
            if exists:
                if import_batch_id is not None:
                    conn.execute(
                        """
                        INSERT INTO import_line_audit(
                            import_batch_id, account_id, source_line, decision, reason,
                            tx_date, label, amount, signature, source_identifier, source_profile, raw_payload
                        )
                        VALUES (?, ?, ?, 'duplicate', 'Signature R7.2 déjà présente', ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (import_batch_id, account_id, source_line, tx_date, label, amount, signature, source_identifier, source_profile, raw_payload),
                    )
                return False

            conn.execute(
                """
                INSERT INTO transactions(account_id, tx_date, label, category, amount, tx_type, status, source, import_batch_id, signature,
                                         categorization_status, categorized_by, categorization_rule_id, categorized_at,
                                         currency, source_line, source_profile, raw_payload, source_identifier)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    tx_date,
                    label,
                    category,
                    amount,
                    tx_type,
                    status,
                    source,
                    import_batch_id,
                    signature,
                    categorization_status,
                    categorized_by,
                    categorized_at,
                    currency or "EUR",
                    source_line,
                    source_profile,
                    raw_payload,
                    source_identifier,
                ),
            )
            if import_batch_id is not None:
                conn.execute(
                    """
                    INSERT INTO import_line_audit(
                        import_batch_id, account_id, source_line, decision, reason,
                        tx_date, label, amount, signature, source_identifier, source_profile, raw_payload
                    )
                    VALUES (?, ?, ?, 'imported', 'Transaction écrite', ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (import_batch_id, account_id, source_line, tx_date, label, amount, signature, source_identifier, source_profile, raw_payload),
                )
            return True

    def transaction_exists_imported_tx(self, account_id: int, tx) -> bool:
        signature = r7_2_signature(
            account_id,
            tx.tx_date,
            tx.label,
            tx.amount,
            source_identifier=getattr(tx, "source_identifier", None),
            raw_payload=json.dumps(getattr(tx, "raw_payload", {}) or {}, ensure_ascii=False, sort_keys=True),
            source_line=getattr(tx, "source_line", None),
        )
        with self.connect() as conn:
            row = conn.execute("SELECT id FROM transactions WHERE signature = ?", (signature,)).fetchone()
            return row is not None

    def transaction_exists_legacy(self, account_id: int, tx_date: str, label: str, amount: float) -> bool:
        signature = r7_2_signature(account_id, tx_date, label, amount)
        with self.connect() as conn:
            row = conn.execute("SELECT id FROM transactions WHERE signature = ?", (signature,)).fetchone()
            return row is not None

    Database.apply_migrations = apply_migrations_with_r7_2_import_integrity
    Database.make_signature = make_signature_with_discriminant
    Database.audit_import_line = audit_import_line
    Database.insert_transaction = insert_transaction_with_import_discriminant
    Database.transaction_exists_imported_tx = transaction_exists_imported_tx
    Database.transaction_exists = transaction_exists_legacy

    # UI preview must use the same duplicate signature as final insertion.
    try:
        from app.ui.transactions_page import TransactionsPage

        def duplicate_flags_r7_2(self) -> list[bool]:
            account_id = self.import_account_combo.currentData()
            if not account_id:
                return [False for _ in self.preview_rows]
            return [self.db.transaction_exists_imported_tx(account_id, tx) for tx in self.preview_rows]

        TransactionsPage.duplicate_flags = duplicate_flags_r7_2
    except Exception:
        # UI may not be imported yet in some technical tests.
        pass

    _PATCHED = True
