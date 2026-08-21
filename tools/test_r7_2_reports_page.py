from __future__ import annotations

import tempfile
from pathlib import Path


def main() -> None:
    # Test non-UI : vérifie le parsing attendu par ReportsPage sans lancer Qt.
    from app.ui.reports_page import ReportsPage

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "import_batch_00001_00050384255_csv.txt"
        path.write_text(
            "Valoria Vision — Rapport d'import\n"
            "Généré le : 21/08/2026 17:56\n"
            "Fichier : 00050384255.csv\n"
            "Compte cible : SG CC 1 — SG\n"
            "Transactions importées : 314\n"
            "Doublons ignorés : 0\n"
            "Erreurs / rejets : 0\n"
            "Lignes auditées : 314\n",
            encoding="utf-8",
        )

        assert ReportsPage.extract_value(path.read_text(encoding="utf-8"), "Fichier") == "00050384255.csv"
        assert ReportsPage.extract_value(path.read_text(encoding="utf-8"), "Compte cible") == "SG CC 1 — SG"
        assert ReportsPage.extract_int(path.read_text(encoding="utf-8"), "Transactions importées") == 314
        assert ReportsPage.extract_int(path.read_text(encoding="utf-8"), "Doublons ignorés") == 0
        assert ReportsPage.extract_int(path.read_text(encoding="utf-8"), "Erreurs / rejets") == 0
        assert ReportsPage.extract_int(path.read_text(encoding="utf-8"), "Lignes auditées") == 314

    print("OK — ReportsPage import report parsing")


if __name__ == "__main__":
    main()
