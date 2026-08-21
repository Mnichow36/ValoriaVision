from __future__ import annotations

_PATCHED = False


def apply_r7_2_import_ui_feedback_patch() -> None:
    """Show the generated import report path in the Transactions import UI.

    The business import remains handled by the existing TransactionsPage logic.
    This patch only adds user-visible feedback after the import has succeeded:
    - the right panel mentions the generated report path;
    - a short information dialog confirms where the report can be found.
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

    def validate_import_with_report_feedback(self, rows_to_import=None):
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

    TransactionsPage.validate_import = validate_import_with_report_feedback
    _PATCHED = True
