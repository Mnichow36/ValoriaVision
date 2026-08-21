from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable
import json

_PATCHED = False


def _safe(value) -> str:
    if value is None:
        return ""
    return str(value)


def _money(value) -> str:
    try:
        return f"{float(value):,.2f} €".replace(",", "X").replace(".", ",").replace("X", " ")
    except Exception:
        return ""


def _report_dir() -> Path:
    root = Path(__file__).resolve().parents[2]
    path = root / "data" / "reports" / "imports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_file_stem(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)
    return cleaned.strip("_")[:120] or "import"


def _payload_to_text(payload) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(payload)


def _audit_rows(conn, batch_id: int) -> list:
    return list(
        conn.execute(
            """
            SELECT *
            FROM import_line_audit
            WHERE import_batch_id = ?
            ORDER BY COALESCE(source_line, id), id
            """,
            (batch_id,),
        )
    )


def _already_audited(conn, batch_id: int, source_line: int | None, decision: str, reason: str) -> bool:
    row = conn.execute(
        """
        SELECT id
        FROM import_line_audit
        WHERE import_batch_id = ?
          AND COALESCE(source_line, -1) = COALESCE(?, -1)
          AND decision = ?
          AND COALESCE(reason, '') = COALESCE(?, '')
        LIMIT 1
        """,
        (batch_id, source_line, decision, reason),
    ).fetchone()
    return row is not None


def _audit_rejected_lines(self, batch_id: int) -> None:
    """Attach pre-write rejected lines to the real import batch.

    The parser rejects invalid rows before transactions are written. Those rows
    do not pass through `insert_transaction`, so they need to be persisted here,
    just before the final report is generated.
    """
    analysis = getattr(self, "_r7_2_current_import_analysis", None)
    if not analysis:
        return

    diagnostic = getattr(analysis, "diagnostic", None)
    file_name = getattr(analysis, "file_name", None)
    profile = getattr(diagnostic, "profile_name", None) if diagnostic else None
    rejected = list(getattr(analysis, "rejected_lines", []) or [])

    with self.connect() as conn:
        batch = conn.execute("SELECT account_id, file_name FROM import_batches WHERE id = ?", (batch_id,)).fetchone()
        if not batch:
            return
        account_id = int(batch["account_id"])
        batch_file_name = batch["file_name"] or file_name

        for rejected_line in rejected:
            source_line = getattr(rejected_line, "line_number", None)
            reason = _safe(getattr(rejected_line, "reason", "Ligne rejetée")) or "Ligne rejetée"
            raw_payload = _payload_to_text(getattr(rejected_line, "raw_payload", None))
            if _already_audited(conn, batch_id, source_line, "rejected", reason):
                continue
            conn.execute(
                """
                INSERT INTO import_line_audit(
                    import_batch_id, file_name, account_id, source_line, decision, reason,
                    tx_date, label, amount, signature, source_identifier, source_profile, raw_payload
                )
                VALUES (?, ?, ?, ?, 'rejected', ?, NULL, NULL, NULL, NULL, NULL, ?, ?)
                """,
                (batch_id, batch_file_name, account_id, source_line, reason, profile, raw_payload),
            )


def _build_report(batch, rows: Iterable) -> str:
    rows = list(rows)
    decisions = Counter(_safe(row["decision"]) for row in rows)
    total_amount = sum(float(row["amount"] or 0) for row in rows if row["decision"] == "imported")
    debits = sum(float(row["amount"] or 0) for row in rows if row["decision"] == "imported" and float(row["amount"] or 0) < 0)
    credits = sum(float(row["amount"] or 0) for row in rows if row["decision"] == "imported" and float(row["amount"] or 0) > 0)

    lines: list[str] = []
    lines.append("Valoria Vision — Rapport d'import R7.2.3")
    lines.append("=" * 48)
    lines.append("")
    lines.append(f"Lot d'import        : {batch['id']}")
    lines.append(f"Fichier             : {batch['file_name']}")
    lines.append(f"Compte Valoria      : {batch['account_name']} — {batch['bank']}")
    lines.append(f"Identifiant compte  : {batch['account_identifier'] or ''}")
    lines.append(f"Profil parseur      : {batch['parser_profile'] or ''}")
    lines.append(f"En-tête ligne       : {batch['header_line'] or ''}")
    lines.append(f"Statut              : {batch['status']}")
    lines.append(f"Créé le             : {batch['created_at']}")
    lines.append("")
    lines.append("Synthèse")
    lines.append("-" * 48)
    lines.append(f"Transactions importées : {batch['imported_count']}")
    lines.append(f"Doublons ignorés       : {batch['duplicate_count']}")
    lines.append(f"Erreurs / rejets       : {batch['error_count']}")
    lines.append(f"Lignes auditées        : {len(rows)}")
    lines.append(f"Décisions              : {dict(decisions)}")
    lines.append(f"Crédits importés       : {_money(credits)}")
    lines.append(f"Débits importés        : {_money(abs(debits))}")
    lines.append(f"Solde net importé      : {_money(total_amount)}")
    lines.append("")
    lines.append("Détail des lignes auditées")
    lines.append("-" * 48)
    lines.append("Ligne | Décision | Date | Montant | Libellé | Motif | Signature")
    lines.append("-" * 120)
    if rows:
        for row in rows:
            lines.append(
                " | ".join(
                    [
                        _safe(row["source_line"]),
                        _safe(row["decision"]),
                        _safe(row["tx_date"]),
                        _money(row["amount"]),
                        _safe(row["label"])[:80],
                        _safe(row["reason"])[:100],
                        _safe(row["signature"])[:120],
                    ]
                )
            )
    else:
        lines.append("Aucune ligne d'audit n'a été associée à ce lot.")
    lines.append("")
    lines.append("Note")
    lines.append("-" * 48)
    lines.append("Ce rapport est généré automatiquement après validation d'un import.")
    lines.append("Il sert de preuve de cohérence entre l'aperçu, l'écriture réelle et les décisions de doublons/rejets.")
    lines.append("")
    return "\n".join(lines)


def apply_r7_2_import_report_patch() -> None:
    """Generate a readable import report after each validated import batch."""
    global _PATCHED
    if _PATCHED:
        return

    from app.database import Database

    original_update_import_batch = Database.update_import_batch

    def export_import_report(self, batch_id: int) -> str:
        with self.connect() as conn:
            batch = conn.execute(
                """
                SELECT b.*, a.name AS account_name, a.bank AS bank, a.identifier AS account_identifier
                FROM import_batches b
                JOIN accounts a ON a.id = b.account_id
                WHERE b.id = ?
                """,
                (batch_id,),
            ).fetchone()
            if not batch:
                raise ValueError("Lot d'import introuvable.")
            rows = _audit_rows(conn, batch_id)
            report = _build_report(batch, rows)

        target = _report_dir() / f"import_batch_{int(batch_id):05d}_{_safe_file_stem(batch['file_name'])}.txt"
        target.write_text(report, encoding="utf-8")
        return str(target)

    def update_import_batch_with_report(self, batch_id: int, imported: int, duplicates: int, errors: int) -> None:
        original_update_import_batch(self, batch_id, imported, duplicates, errors)
        try:
            _audit_rejected_lines(self, batch_id)
            export_import_report(self, batch_id)
        except Exception:
            # Never block a valid import because report generation failed.
            pass

    def list_import_audit_rows(self, batch_id: int) -> list:
        with self.connect() as conn:
            return _audit_rows(conn, batch_id)

    Database.export_import_report = export_import_report
    Database.update_import_batch = update_import_batch_with_report
    Database.list_import_audit_rows = list_import_audit_rows

    try:
        from app.ui.transactions_page import TransactionsPage

        original_validate_import = TransactionsPage.validate_import

        def validate_import_with_report_context(self, rows_to_import=None):
            self.db._r7_2_current_import_analysis = getattr(self.import_service, "last_analysis", None)
            try:
                return original_validate_import(self, rows_to_import)
            finally:
                if hasattr(self.db, "_r7_2_current_import_analysis"):
                    delattr(self.db, "_r7_2_current_import_analysis")

        TransactionsPage.validate_import = validate_import_with_report_context
    except Exception:
        # UI may not be imported in technical scripts.
        pass

    _PATCHED = True
