from __future__ import annotations

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.database import Database
from app.security.auth_service import AuthService
from app.services.feature_access_service import FeatureAccessService
from app.ui.auth_dialog import MasterPasswordDialog
from app.theme import APP_STYLESHEET
from app.ui.accounts_page import AccountsPage
from app.ui.assets_page import AssetsPage
from app.ui.dashboard_page import DashboardPage
from app.ui.transactions_page import TransactionsPage
from app.ui.forecast_page import ForecastPage
from app.ui.placeholder_page import PlaceholderPage
from app.ui.budgets_page import BudgetsPage
from app.ui.scenarios_page import ScenariosPage
from app.ui.premium_locked_page import PremiumLockedPage
from app.ui.reconciliation_page import ReconciliationPage
from app.ui.reports_page import ReportsPage
from app.ui.settings_page import SettingsPage


class MainWindow(QMainWindow):
    def __init__(self, db: Database) -> None:
        super().__init__()
        self.db = db
        self.auth = AuthService(db)
        self.features = FeatureAccessService(db)
        self.is_locked = False
        self.setWindowTitle("Valoria Vision — MVP V0.6.6-R7.2.2.1")
        self.resize(1600, 980)
        self.setMinimumSize(1280, 820)
        self.setStyleSheet(APP_STYLESHEET)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        self.sidebar = self.build_sidebar()
        root_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root_layout.addWidget(self.stack)

        self.pages = {
            "Dashboard": DashboardPage(db),
            "Comptes": AccountsPage(db),
            "Transactions": TransactionsPage(db),
            "Prévisionnel": ForecastPage(db),
            "Rapprochements": ReconciliationPage(db),
            "Scénarios": (
                ScenariosPage(db)
                if self.features.has_feature(FeatureAccessService.FEATURE_SCENARIOS)
                else PremiumLockedPage(
                    "Scénarios",
                    "Créez et comparez des simulations avancées sans modifier vos données réelles.",
                    [
                        "scénarios personnalisés par projet ou changement de situation",
                        "événements ponctuels ou récurrents propres à une simulation",
                        "comparaison avec le scénario de référence",
                        "projection de l'impact sur la trésorerie",
                    ],
                )
            ),
            "Patrimoine": AssetsPage(db),
            "Investissements": PlaceholderPage("Investissements", "Suivi PEA, CTO, assurance-vie, crypto et allocations."),
            "Budgets": BudgetsPage(db),
            "Rapports": ReportsPage(db),
            "Paramètres": SettingsPage(db),
        }
        # Cross-page callbacks
        self.pages["Comptes"].on_view_transactions = self.open_transactions_for_account
        self.pages["Comptes"].on_import_operations = self.open_transactions_for_account
        self.pages["Prévisionnel"].on_open_scenarios = lambda: self.select_page("Scénarios")

        for page in self.pages.values():
            self.stack.addWidget(page)

        self.nav_buttons: dict[str, QPushButton] = {}
        self.populate_nav()
        self.select_page("Dashboard")
        self.setup_session_lock()

    def build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(250)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 24, 18, 24)
        layout.setSpacing(8)

        title = QLabel("Valoria Vision")
        title.setObjectName("AppTitle")
        subtitle = QLabel("Trésorerie & Patrimoine")
        subtitle.setObjectName("AppSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(24)
        return sidebar

    def populate_nav(self) -> None:
        layout = self.sidebar.layout()
        entries = [
            ("Dashboard", "◎  Dashboard"),
            ("Comptes", "◉  Comptes"),
            ("Transactions", "▤  Transactions"),
            ("Prévisionnel", "⌁  Prévisionnel"),
            ("Rapprochements", "≋  Rapprochements"),
            ("Scénarios", "◇  Scénarios  PREMIUM"),
            ("Patrimoine", "◆  Patrimoine"),
            ("Investissements", "▲  Investissements"),
            ("Budgets", "◌  Budgets"),
            ("Rapports", "▣  Rapports"),
            ("Paramètres", "⚙  Paramètres"),
        ]
        for key, label in entries:
            button = QPushButton(label)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, page=key: self.select_page(page))
            self.nav_buttons[key] = button
            layout.addWidget(button)

        self.lock_btn = QPushButton("🔒  Verrouiller")
        self.lock_btn.setObjectName("NavButton")
        self.lock_btn.setCursor(Qt.PointingHandCursor)
        self.lock_btn.clicked.connect(self.lock_session)
        layout.addWidget(self.lock_btn)

        layout.addStretch(1)
        version = QLabel("Prototype V0.6.6-R7.2.3 — Lot 3 en cours")
        version.setStyleSheet("color: #8FAADC; font-size: 11px;")
        layout.addWidget(version)

    def select_page(self, name: str) -> None:
        if name == "Scénarios":
            should_have_access = self.features.has_feature(FeatureAccessService.FEATURE_SCENARIOS)
            has_real_page = isinstance(self.pages.get("Scénarios"), ScenariosPage)
            if should_have_access and not has_real_page:
                old_page = self.pages["Scénarios"]
                new_page = ScenariosPage(self.db)
                self.pages["Scénarios"] = new_page
                self.stack.addWidget(new_page)
                self.stack.removeWidget(old_page)
                old_page.deleteLater()
            elif not should_have_access and has_real_page:
                old_page = self.pages["Scénarios"]
                new_page = PremiumLockedPage(
                    "Scénarios",
                    "Créez et comparez des simulations avancées sans modifier vos données réelles.",
                    [
                        "scénarios personnalisés par projet ou changement de situation",
                        "événements ponctuels ou récurrents propres à une simulation",
                        "comparaison avec le scénario de référence",
                        "projection de l'impact sur la trésorerie",
                    ],
                )
                self.pages["Scénarios"] = new_page
                self.stack.addWidget(new_page)
                self.stack.removeWidget(old_page)
                old_page.deleteLater()
        page = self.pages[name]
        self.stack.setCurrentWidget(page)
        for key, button in self.nav_buttons.items():
            button.setChecked(key == name)
        if hasattr(page, "refresh"):
            page.refresh()

    def open_transactions_for_account(self, account_id: int) -> None:
        self.select_page("Transactions")
        transactions_page = self.pages["Transactions"]
        if hasattr(transactions_page, "select_account_filter"):
            transactions_page.select_account_filter(account_id)


    def setup_session_lock(self) -> None:
        self.session_timer = QTimer(self)
        self.session_timer.setInterval(self.auth.session_timeout_minutes() * 60 * 1000)
        self.session_timer.timeout.connect(self.lock_session)
        self.session_timer.start()
        self.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() in {
            QEvent.MouseButtonPress,
            QEvent.MouseButtonRelease,
            QEvent.MouseMove,
            QEvent.KeyPress,
            QEvent.Wheel,
        }:
            if hasattr(self, "session_timer") and not self.is_locked:
                self.session_timer.start()
        return super().eventFilter(obj, event)

    def lock_session(self) -> None:
        if self.is_locked:
            return
        self.is_locked = True
        self.hide()
        dialog = MasterPasswordDialog(self.auth, mode="unlock", parent=None)
        if dialog.exec() == MasterPasswordDialog.Accepted:
            self.is_locked = False
            self.show()
            self.raise_()
            self.activateWindow()
            if hasattr(self, "session_timer"):
                self.session_timer.start()
        else:
            self.close()
