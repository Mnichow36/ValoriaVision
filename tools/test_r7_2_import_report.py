from __future__ import annotations

import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.r7_2.import_integrity import apply_r7_2_import_integrity_patch
from app.r7_2.import_report_patch import apply_r7_2_import_report_patch
from app.imports.import_models import ImportAnalysis, ImportRejectedLine, ImportDiagnostic
from app.database import Database


def main() -> int:
    apply_r7_2_import_integrity_patch()
    apply_r7_2_import_report_patch()

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "valoria_report_test.db"
        db = Database(db_path)
        db.initialize()

        accounts = db.list_accounts()
        account_id = int(accounts[0]["id"])
        batch_id = db.create_import_batch("test_report.csv", account_id, parser_profile="Test R7.2", header_line=3)

        # Simule le contexte d'analyse conservé par l'écran Transactions :
        # une ligne a été rejetée avant écriture et doit malgré tout apparaître
        # dans le rapport final du lot.
        analysis = ImportAnalysis(file_name="test_report.csv")
        analysis.diagnostic = ImportDiagnostic(profile_name="Test R7.2")
        analysis.rejected_lines.append(
            ImportRejectedLine(
                line_number=5,
                reason="Montant non interprétable",
                raw_payload={"Date": "21/08/2026", "Libellé": "LIGNE KO", "Montant": "abc"},
            )
        )
        db._r7_2_current_import_analysis = analysis

        inserted = db.insert_transaction(
            account_id,
            "2026-08-21",
            "CARTE X6425 TEST RAPPORT",
            None,
            -7.76,
            "Import bancaire",
            batch_id,
            source_line=4,
            source_profile="Test R7.2",
            raw_payload='{"reference":"SG-REPORT-0001","label":"CARTE X6425 TEST RAPPORT"}',
            source_identifier="SG-REPORT-0001",
        )
        if not inserted:
            print("Insertion import impossible")
            return 1

        db.update_import_batch(batch_id, 1, 0, 1)
        report_path = Path(db.export_import_report(batch_id))
        if not report_path.exists():
            print("Rapport non créé")
            return 1
        content = report_path.read_text(encoding="utf-8")
        required = [
            "Valoria Vision — Rapport d'import R7.2.3",
            "test_report.csv",
            "CARTE X6425 TEST RAPPORT",
            "SG-REPORT-0001",
            "Transaction écrite",
            "rejected",
            "Montant non interprétable",
            "LIGNE KO",
        ]
        missing = [text for text in required if text not in content]
        if missing:
            print("Contenu manquant:", missing)
            return 1
        print("Rapport import R7.2.3 généré avec ligne rejetée:", report_path)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
