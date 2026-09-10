from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from app.migrations.r8_reconciliation import apply_r8_reconciliation_foundation


R8_TABLES = {
    "transaction_reconciliation_state",
    "reconciliation_proposals",
    "reconciliation_proposal_members",
    "reconciliations",
    "reconciliation_members",
    "reconciliation_events",
}


def _tables(conn: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in conn.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
    ]


def _fingerprint_table(conn: sqlite3.Connection, table: str) -> dict[str, Any]:
    quoted = '"' + table.replace('"', '""') + '"'
    columns = [row[1] for row in conn.execute(f"PRAGMA table_info({quoted})")]
    digest = hashlib.sha256()
    row_count = 0
    for row in conn.execute(f"SELECT * FROM {quoted} ORDER BY rowid"):
        digest.update(
            json.dumps(
                list(row),
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        )
        digest.update(b"\n")
        row_count += 1
    return {"columns": columns, "row_count": row_count, "sha256": digest.hexdigest()}


def _legacy_snapshot(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    return {
        table: _fingerprint_table(conn, table)
        for table in _tables(conn)
        if table not in R8_TABLES
    }


def _r8_counts(conn: sqlite3.Connection) -> dict[str, int]:
    existing = set(_tables(conn))
    return {
        table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in sorted(R8_TABLES)
        if table in existing
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_database(source: Path) -> dict[str, Any]:
    """Validate migration, verified backup and rollback on temporary copies only."""
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Base introuvable : {source}")

    if source.read_bytes()[:16] != b"SQLite format 3\x00":
        raise ValueError(
            "Le fichier n'est pas une base SQLite lisible. "
            "Un coffre .vvdb chiffré ne peut pas être validé directement."
        )

    source_sha256 = _file_sha256(source)
    with tempfile.TemporaryDirectory(prefix="valoria-r8-validation-") as temp_dir:
        temp_path = Path(temp_dir)
        verified_backup = temp_path / "r7_2_verified_backup.db"
        working_copy = temp_path / "r7_2_validation_copy.db"
        rollback_copy = temp_path / "r7_2_rollback_copy.db"

        # The source is never opened for writing. Backup creation and byte-level
        # verification happen before the migration copy is touched.
        shutil.copy2(source, verified_backup)
        backup_sha256 = _file_sha256(verified_backup)
        backup_sha256_verified = backup_sha256 == source_sha256
        if not backup_sha256_verified:
            raise IOError("La sauvegarde préalable ne correspond pas à la source")

        with sqlite3.connect(verified_backup) as backup_conn:
            backup_integrity = backup_conn.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]
        if backup_integrity != "ok":
            raise sqlite3.DatabaseError(
                f"Sauvegarde préalable invalide : {backup_integrity}"
            )

        shutil.copy2(verified_backup, working_copy)
        conn = sqlite3.connect(working_copy)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            integrity_before = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity_before != "ok":
                raise sqlite3.DatabaseError(
                    f"Intégrité invalide avant migration : {integrity_before}"
                )

            tables_before = set(_tables(conn))
            missing = sorted({"transactions", "forecast_occurrences"} - tables_before)
            if missing:
                raise ValueError(
                    "Schéma R7.2 incompatible : tables manquantes " + ", ".join(missing)
                )

            legacy_before = _legacy_snapshot(conn)
            source_counts = {
                "transactions": conn.execute(
                    "SELECT COUNT(*) FROM transactions"
                ).fetchone()[0],
                "occurrences": conn.execute(
                    "SELECT COUNT(*) FROM forecast_occurrences"
                ).fetchone()[0],
                "legacy_auto": conn.execute(
                    "SELECT COUNT(*) FROM forecast_occurrences "
                    "WHERE status = 'auto_matched' AND actual_transaction_id IS NOT NULL"
                ).fetchone()[0],
                "legacy_confirmed": conn.execute(
                    "SELECT COUNT(*) FROM forecast_occurrences "
                    "WHERE status = 'confirmed' AND actual_transaction_id IS NOT NULL"
                ).fetchone()[0],
                "legacy_to_review": conn.execute(
                    "SELECT COUNT(*) FROM forecast_occurrences "
                    "WHERE status = 'to_review' AND actual_transaction_id IS NOT NULL"
                ).fetchone()[0],
            }

            apply_r8_reconciliation_foundation(conn)
            conn.commit()
            legacy_after_first = _legacy_snapshot(conn)
            counts_after_first = _r8_counts(conn)

            apply_r8_reconciliation_foundation(conn)
            conn.commit()
            legacy_after_second = _legacy_snapshot(conn)
            counts_after_second = _r8_counts(conn)
            integrity_after = conn.execute("PRAGMA integrity_check").fetchone()[0]

            migrated_counts = {
                "transaction_states": conn.execute(
                    "SELECT COUNT(*) FROM transaction_reconciliation_state"
                ).fetchone()[0],
                "reconciliations": conn.execute(
                    "SELECT COUNT(*) FROM reconciliations"
                ).fetchone()[0],
                "proposals": conn.execute(
                    "SELECT COUNT(*) FROM reconciliation_proposals"
                ).fetchone()[0],
                "orphan_reconciliation_members": conn.execute(
                    """
                    SELECT COUNT(*) FROM reconciliation_members rm
                    LEFT JOIN reconciliations r ON r.id = rm.reconciliation_id
                    WHERE r.id IS NULL
                    """
                ).fetchone()[0],
                "orphan_proposal_members": conn.execute(
                    """
                    SELECT COUNT(*) FROM reconciliation_proposal_members rpm
                    LEFT JOIN reconciliation_proposals rp ON rp.id = rpm.proposal_id
                    WHERE rp.id IS NULL
                    """
                ).fetchone()[0],
            }
        finally:
            conn.close()

        changed_legacy_tables = sorted(
            table
            for table, before in legacy_before.items()
            if legacy_after_first.get(table) != before
            or legacy_after_second.get(table) != before
        )
        idempotent = counts_after_first == counts_after_second
        all_r8_tables_created = R8_TABLES.issubset(
            set(legacy_after_second) | set(counts_after_second)
        )
        counts_reconciled = (
            migrated_counts["transaction_states"] == source_counts["transactions"]
            and migrated_counts["reconciliations"]
            == source_counts["legacy_auto"] + source_counts["legacy_confirmed"]
            and migrated_counts["proposals"] == source_counts["legacy_to_review"]
        )
        no_orphans = (
            migrated_counts["orphan_reconciliation_members"] == 0
            and migrated_counts["orphan_proposal_members"] == 0
        )

        # Restore to another temporary file and compare both bytes and integrity.
        shutil.copy2(verified_backup, rollback_copy)
        rollback_sha256 = _file_sha256(rollback_copy)
        with sqlite3.connect(rollback_copy) as rollback_conn:
            rollback_integrity = rollback_conn.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]
        rollback_matches_source = rollback_sha256 == source_sha256
        rollback_tested = rollback_integrity == "ok" and rollback_matches_source

        success = (
            integrity_after == "ok"
            and not changed_legacy_tables
            and idempotent
            and all_r8_tables_created
            and counts_reconciled
            and no_orphans
            and backup_sha256_verified
            and rollback_tested
        )
        return {
            "success": success,
            "source_identifier": f"sha256:{source_sha256[:12]}",
            "source_size_bytes": source.stat().st_size,
            "legacy_table_count": len(legacy_before),
            "integrity_before": integrity_before,
            "integrity_after": integrity_after,
            "backup_created_before_migration": True,
            "backup_integrity": backup_integrity,
            "backup_sha256_verified": backup_sha256_verified,
            "rollback_tested": rollback_tested,
            "rollback_integrity": rollback_integrity,
            "rollback_matches_source": rollback_matches_source,
            "all_r8_tables_created": all_r8_tables_created,
            "changed_legacy_tables": changed_legacy_tables,
            "idempotent": idempotent,
            "counts_reconciled": counts_reconciled,
            "no_orphan_members": no_orphans,
            "source_counts": source_counts,
            "migrated_counts": migrated_counts,
            "r8_counts": counts_after_second,
            "temporary_copies_deleted_after_validation": True,
        }

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valide la migration R8 sur une copie temporaire d'une base R7.2."
    )
    parser.add_argument("database", type=Path, help="Chemin de la base SQLite R7.2")
    parser.add_argument("--report", type=Path, help="Fichier JSON de sortie facultatif")
    args = parser.parse_args()
    try:
        report = validate_database(args.database)
    except Exception as exc:
        report = {
            "success": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    output = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(output)
    if args.report:
        args.report.write_text(output + "\n", encoding="utf-8")
    return 0 if report.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
