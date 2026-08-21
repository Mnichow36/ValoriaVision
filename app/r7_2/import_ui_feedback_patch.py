from __future__ import annotations

_PATCHED = False


def apply_r7_2_import_ui_feedback_patch() -> None:
    """Show useful import feedback in the Transactions import UI.

    The business import remains handled by the existing TransactionsPage logic.
    This patch adds two user-visible behaviours:
    - after a successful import, show the generated report path;
    - when a re-import contains only duplicates, show a clear business message
      instead of the misleading "Aucune opération sélectionnée" message.
    """
    global _PATCHED
    if _PATCHED:
        return

    try:
        from PySide6.QtWidgets import QMessageBox
        from app.ui.transactions_page import TransactionsPage
    except Exception:
        return

    original_validate_import = TransactionsPage.validate_import
    original_validate_import_direct = TransactionsPage.validate_import_direct

    def _current_file_name(self) -> str:
        try:
            return self.current_import_path.name if self.current_import_path else "fichier sélectionné"
        except Exception:
            return "fichier sélectionné"

    def _show_all_duplicates_message(self, duplicate_count: int) -> None:
        file_name = _current_file_name(self)
        message = (
            "Aucune nouvelle opération à importer.\n\n"
            f"Le fichier {file_name} contient {duplicate_count} opération(s) déjà présentes.\n"
            "Elles ont été reconnues comme doublons et aucune transaction supplémentaire n'a été ajoutée."
        )
        try:
            if hasattr(self, "import_status"):
                self.import_status.setText(
                    f"Fichier déjà importé : {file_name}\n"
                    f"Nouvelles : 0\n"
                    f"Doublons reconnus : {duplicate_count}\n"
                    "Aucune transaction supplémentaire n'a été ajoutée."
                )
            if hasattr(self, "import_summary"):
                self.import_summary.setText(
                    "Nouvelles : 0\n"
                    f"Doublons : {duplicate_count}\n"
                    "Erreurs : 0\n"
                    "Statut : fichier déjà importé"
                )
            QMessageBox.information(self, "Fichier déjà importé", message)
        except Exception:
            pass

    def validate_import_direct_with_duplicate_feedback(self):
        try:
            rows = list(getattr(self, "preview_rows", []) or [])
            flags = list(self.duplicate_flags()) if rows else []
            duplicate_count = sum(1 for flag in flags if flag)
            new_count = len(rows) - duplicate_count
            if rows and new_count == 0 and duplicate_count > 0:
                _show_all_duplicates_message(self, duplicate_count)
                return
        except Exception:
            pass
        original_validate_import_direct(self)

    def validate_import_with_report_feedback(self, rows_to_import=None):
        # Defensive handling for callers that pass an empty selection because
        # every analysed line was already detected as a duplicate.
        try:
            rows = list(getattr(self, "preview_rows", []) or [])
            if rows_to_import is not None and not list(rows_to_import):
                flags = list(self.duplicate_flags()) if rows else []
                duplicate_count = sum(1 for flag in flags if flag)
                new_count = len(rows) - duplicate_count
                if rows and new_count == 0 and duplicate_count > 0:
                    _show_all_duplicates_message(self, duplicate_count)
                    return
        except Exception:
            pass

        original_validate_import(self, rows_to_import)
        report_path = ""
        try:
            if hasattr(self.db, "last_import_report_path"):
                report_path = self.db.last_import_report_path()
        except Exception:
            report_path = ""

        if not report_path:
            return

        message = (
            "Import validé.\n\n"
            "Un rapport d'import a été généré automatiquement :\n"
            f"{report_path}\n\n"
            "Ce rapport sert à contrôler les lignes importées, doublons et rejets."
        )
        try:
            if hasattr(self, "import_status"):
                self.import_status.setText(
                    "Import validé avec rapport d'audit.\n"
                    f"Rapport : {report_path}"
                )
            if hasattr(self, "import_summary"):
                previous = self.import_summary.text() or ""
                self.import_summary.setText(previous + "\nRapport : généré")
            QMessageBox.information(self, "Rapport d'import généré", message)
        except Exception:
            pass

    TransactionsPage.validate_import_direct = validate_import_direct_with_duplicate_feedback
    TransactionsPage.validate_import = validate_import_with_report_feedback
    _PATCHED = True
