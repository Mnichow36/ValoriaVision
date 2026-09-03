from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Iterable, Any

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


def _raw_payload_text(value: Any) -> str:
    text = _safe(value).replace("\n", " ").replace("\r", " ").strip()
    return text[:180]


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
                        _safe(row["reason"])[:80],
                        _safe(row["signature"])[:120],
                    ]
                )
            )
    else:
        lines.append("Aucune ligne d'audit n'a été associée à ce lot.")

    rejected_rows = [row for row in rows if row["decision"] == "rejected"]
    if rejected_rows:
        lines.append("")
        lines.append("Lignes rejetées — détail brut")
        lines.append("-" * 48)
        for row in rejected_rows:
            lines.append(
                f"Ligne {row['source_line']} — {row['reason']} — {_raw_payload_text(row['raw_payload'])}"
            )

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
            analysis = getattr(self, "_r7_2_current_import_analysis", None)
            for rejected in list(getattr(analysis, "rejected_lines", []) or []):
                exists = conn.execute(
                    "SELECT 1 FROM import_line_audit WHERE import_batch_id = ? AND source_line = ? AND decision = 'rejected' LIMIT 1",
                    (batch_id, rejected.line_number),
                ).fetchone()
                if not exists:
                    conn.execute(
                        """
                        INSERT INTO import_line_audit(
                            import_batch_id, file_name, account_id, source_line,
                            decision, reason, raw_payload, source_profile
                        ) VALUES (?, ?, ?, ?, 'rejected', ?, ?, ?)
                        """,
                        (
                            batch_id, batch["file_name"], batch["account_id"], rejected.line_number,
                            rejected.reason, json.dumps(rejected.raw_payload, ensure_ascii=False),
                            batch["parser_profile"],
                        ),
                    )
            rows = _audit_rows(conn, batch_id)
            report = _build_report(batch, rows)

        target = _report_dir() / f"import_batch_{int(batch_id):05d}_{_safe_file_stem(batch['file_name'])}.txt"
        target.write_text(report, encoding="utf-8")
        self._last_import_report_path = str(target)
        self._last_import_report_batch_id = int(batch_id)
        return str(target)

    def update_import_batch_with_report(self, batch_id: int, imported: int, duplicates: int, errors: int) -> None:
        original_update_import_batch(self, batch_id, imported, duplicates, errors)
        try:
            export_import_report(self, batch_id)
        except Exception:
            # Never block a valid import because report generation failed.
            self._last_import_report_path = ""
            self._last_import_report_batch_id = int(batch_id)

    def list_import_audit_rows(self, batch_id: int) -> list:
        with self.connect() as conn:
            return _audit_rows(conn, batch_id)

    def last_import_report_path(self) -> str:
        return str(getattr(self, "_last_import_report_path", "") or "")

    def last_import_report_batch_id(self) -> int | None:
        value = getattr(self, "_last_import_report_batch_id", None)
        return int(value) if value is not None else None

    Database.export_import_report = export_import_report
    Database.update_import_batch = update_import_batch_with_report
    Database.list_import_audit_rows = list_import_audit_rows
    Database.last_import_report_path = last_import_report_path
    Database.last_import_report_batch_id = last_import_report_batch_id

    _PATCHED = True
