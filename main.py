from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from app.main_window import MainWindow
from app.database import Database
from app.r7_2.account_context_menu_patch import apply_r7_2_account_context_menu_patch
from app.r7_2.account_management_patch import apply_r7_2_account_management_patch
from app.r7_2.encrypted_backup_complete_patch import apply_r7_2_encrypted_backup_complete_patch
from app.r7_2.forecast_recurrences_patch import apply_r7_2_forecast_recurrences_patch
from app.r7_2.forecast_ux_simplification_patch import apply_r7_2_forecast_ux_simplification_patch
from app.r7_2.import_account_resolution_patch import apply_r7_2_import_account_resolution_patch
from app.r7_2.import_integrity import apply_r7_2_import_integrity_patch
from app.r7_2.import_lifecycle_patch import apply_r7_2_import_lifecycle_patch
from app.r7_2.import_report_patch import apply_r7_2_import_report_patch
from app.r7_2.import_progress_patch import apply_r7_2_import_progress_patch
from app.r7_2.import_ui_feedback_patch import apply_r7_2_import_ui_feedback_patch
from app.r7_2.settings_backup_ux_patch import apply_r7_2_settings_backup_ux_patch
from app.r7_2.ui_privacy_patch import apply_r7_2_ui_privacy_patch
from app.security.auth_service import AuthService
from app.ui.auth_dialog import MasterPasswordDialog
import sys


APP_VERSION = "V0.6.6-R7.2.4 Lot 5.3.2 UX Sauvegarde centralisée"


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Valoria Vision")
    app.setOrganizationName("Valoria Vision")

    # R7.2 CDC v1.1 — active les correctifs avant initialisation/migration
    # et avant création des écrans.
    apply_r7_2_import_integrity_patch()
    apply_r7_2_import_report_patch()
    apply_r7_2_import_progress_patch()
    apply_r7_2_import_ui_feedback_patch()
    apply_r7_2_import_lifecycle_patch()
    apply_r7_2_ui_privacy_patch()
    apply_r7_2_account_management_patch()
    apply_r7_2_import_account_resolution_patch()
    apply_r7_2_account_context_menu_patch()
    apply_r7_2_forecast_recurrences_patch()
    apply_r7_2_forecast_ux_simplification_patch()
    apply_r7_2_encrypted_backup_complete_patch()
    apply_r7_2_settings_backup_ux_patch()

    db = Database()
    db.initialize()

    auth = AuthService(db)
    mode = "unlock" if auth.is_configured() else "setup"
    dialog = MasterPasswordDialog(auth, mode=mode)
    if dialog.exec() != MasterPasswordDialog.Accepted:
        return 0

    window = MainWindow(db)
    window.setWindowTitle(f"Valoria Vision — {APP_VERSION}")
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
