from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from app.main_window import MainWindow
from app.database import Database
from app.r7_2.import_integrity import apply_r7_2_import_integrity_patch
from app.security.auth_service import AuthService
from app.ui.auth_dialog import MasterPasswordDialog
import sys


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Valoria Vision")
    app.setOrganizationName("Valoria Vision")

    # R7.2 CDC v1.1 — active les correctifs d’intégrité import avant
    # initialisation/migration de la base SQLite.
    apply_r7_2_import_integrity_patch()

    db = Database()
    db.initialize()

    auth = AuthService(db)
    mode = "unlock" if auth.is_configured() else "setup"
    dialog = MasterPasswordDialog(auth, mode=mode)
    if dialog.exec() != MasterPasswordDialog.Accepted:
        return 0

    window = MainWindow(db)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
