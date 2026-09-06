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


def validate_database(source: Path) -> dict[str, Any]:
    source = source.resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Base introuvable : {source}")

    if source.read_bytes()[:16] != b"SQLite format 3\x00":
        raise ValueError(
            "Le fichier n'est pas une base SQLite lisible. "
            "Un coffre .vvdb chiffré ne peut pas être validé directement."
        )

    with tempfile.TemporaryDirectory(prefix="valoria-r8-validation-") as temp_dir:
        working_copy = Path(temp_dir) / "r7_2_validation_copy.db"
        shutil.copy2(source, working_copy)

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
            apply_r8_reconciliation_foundation(conn)
            conn.commit()
            legacy_after_first = _legacy_snapshot(conn)
            counts_after_first = _r8_counts(conn)

            apply_r8_reconciliation_foundation(conn)
            conn.commit()
            legacy_after_second = _legacy_snapshot(conn)
            counts_after_second = _r8_counts(conn)
            integrity_after = conn.execute("PRAGMA integrity_check").fetchone()[0]

            changed_legacy_tables = sorted(
                table
                for table, before in legacy_before.items()
                if legacy_after_first.get(table) != before
                or legacy_after_second.get(table) != before
            )
            idempotent = counts_after_first == counts_after_second
            all_r8_tables_created = R8_TABLES.issubset(set(_tables(conn)))
            success = (
                integrity_after == "ok"
                and not changed_legacy_tables
                and idempotent
                and all_r8_tables_created
            )
            return {
                "success": success,
                "source_file": source.name,
                "source_size_bytes": source.stat().st_size,
                "legacy_table_count": len(legacy_before),
                "integrity_before": integrity_before,
                "integrity_after": integrity_after,
                "all_r8_tables_created": all_r8_tables_created,
                "changed_legacy_tables": changed_legacy_tables,
                "idempotent": idempotent,
                "r8_counts": counts_after_second,
                "working_copy_deleted_after_validation": True,
            }
        finally:
            conn.close()


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
