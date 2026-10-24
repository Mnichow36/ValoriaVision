from __future__ import annotations

from contextlib import asynccontextmanager

import base64
import binascii
import gc
import hmac
import os
import sqlite3
import time
from contextvars import ContextVar
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, SecretStr

from app.database import Database
from app.security.api_session import ApiSessionStore
from app.security.crypto_service import VaultLockedError
from app.security.protection import ProtectionError, ProtectionService
from app.security.auth_service import AuthService
from app.security import backup_location
from app.security.backup_service import BackupError, BackupService, WrongPassphrase, count_content
from app.security.profiles import LEGACY_PROFILE_ID, ProfileError, ProfileManager, ProfileNotFound
from app.security.users import (
    ROLE_ADMIN,
    ROLE_LABELS,
    UNRESTRICTED,
    Scope,
    ScopedSnapshots,
    UserError,
    UserNotFound,
    UserStore,
)
from app.services.accounts_read_service import AccountDeletionBlockedError, AccountsReadService
from app.services.assets_read_service import AssetsReadService
from app.services.bank_import_workflow_service import BankImportWorkflowService
from app.services.budgets_read_service import BudgetsReadService
from app.services.dashboard_read_service import DashboardReadService
from app.services.forecast_read_service import ForecastReadService
from app.services.recurrence_occurrences_service import RecurrenceOccurrencesService
from app.services.recurrence_write_service import RecurrenceWriteService
from app.services.reconciliation_read_service import ReconciliationReadService
from app.services.scenario_event_service import ScenarioEventService
from app.services.scenario_service import ScenarioService
from app.services.settings_read_service import SettingsReadService
from app.services.rule_suggestion_service import RuleSuggestionService
from app.services.transactions_read_service import TransactionsReadService


class BudgetRevisionPayload(BaseModel):
    category: str
    month: str
    scope: str = "from"
    new_amount: float
    reason: str = ""


class BudgetCategoryPayload(BaseModel):
    category: str
    month: str
    planned_amount: float | None = None
    alert_threshold: float | None = None
    mode: str | None = None
    notes: str | None = None
    active: bool | None = None


class BudgetCategoryRemovePayload(BaseModel):
    category: str
    month: str


class BudgetRulesPayload(BaseModel):
    default_alert_threshold: float


class PasswordPayload(BaseModel):
    password: SecretStr = SecretStr("")
    profile_id: str | None = None
    name: str | None = None


class ChangePasswordPayload(BaseModel):
    current_password: SecretStr
    new_password: SecretStr


class PinSetPayload(BaseModel):
    password: SecretStr
    pin: SecretStr


class PinUnlockPayload(BaseModel):
    profile_id: str | None = None
    pin: SecretStr


class RecoveryKeyRequestPayload(BaseModel):
    password: SecretStr


class RecoverPayload(BaseModel):
    recovery_key: SecretStr
    new_password: SecretStr
    profile_id: str | None = None


class ProfileCreatePayload(BaseModel):
    name: str
    color: str | None = None
    kind: str = "personal"
    role: str = "contributor"
    password: SecretStr | None = None
    avatar: str | None = None
    accounts: list[int] = []
    assets: list[int] = []


class ProfileUpdatePayload(BaseModel):
    name: str | None = None
    color: str | None = None
    role: str | None = None
    avatar: str | None = None
    clear_avatar: bool = False


class ProfileAccessPayload(BaseModel):
    accounts: list[int] = []
    assets: list[int] = []


class ProfileDeletePayload(BaseModel):
    password: SecretStr = SecretStr("")


class BackupCreatePayload(BaseModel):
    passphrase: SecretStr = SecretStr("")
    confirm: SecretStr = SecretStr("")


class BackupLocationPayload(BaseModel):
    """Dossier des sauvegardes ; vide = dossier par défaut."""

    directory: str | None = None


class ResetPayload(BaseModel):
    """Remise à zéro : mot de passe de l'administrateur, phrase de confirmation et phrase de la copie de sécurité."""

    password: SecretStr = SecretStr("")
    confirmation: str = ""
    passphrase: SecretStr = SecretStr("")


RESET_CONFIRMATION = "REMETTRE À ZÉRO"


class BackupSourcePayload(BaseModel):
    """Sauvegarde désignée soit par son nom (copie locale), soit par son contenu (base64)."""

    name: str | None = None
    data: str | None = None
    passphrase: SecretStr = SecretStr("")
    password: SecretStr = SecretStr("")


class ReconciliationManualMatchPayload(BaseModel):
    occurrence_id: int
    transaction_id: int
    include_overage: bool = False


class ReconciliationCancelPayload(BaseModel):
    occurrence_id: int
    transaction_id: int | None = None


class ReconciliationRulesPayload(BaseModel):
    date_tolerance_days: int | None = None
    amount_tolerance_abs: float | None = None
    amount_tolerance_percent: float | None = None
    manual_window_days: int | None = None
    manual_amount_tolerance_percent: float | None = None


class SettingsGeneralPayload(BaseModel):
    currency: str = "EUR"
    current_month: str = ""
    session_timeout_minutes: int = 10


class SettingsCategoryPayload(BaseModel):
    name: str
    kind: str = "Dépense"
    direction: str = "Dépense"
    color: str = "#64748B"
    budget_enabled: bool = True


class SettingsRulePayload(BaseModel):
    name: str
    description: str = ""
    is_active: bool = True
    priority: int = 100
    match_field: str = "label"
    match_operator: str = "contains"
    match_value: str = ""
    transaction_type: str | None = None
    account_id: int | None = None
    min_amount: float | None = None
    max_amount: float | None = None
    target_category_id: int
    confidence: int = 100


class SettingsRuleActivePayload(BaseModel):
    active: bool


class SettingsRulePendingPayload(BaseModel):
    rule_id: int | None = None


class SettingsRuleApplyPayload(BaseModel):
    transaction_ids: list[int]
    rule_id: int | None = None


class BankImportPreviewPayload(BaseModel):
    file_name: str
    content_base64: str
    account_id: int | None = None


class BankImportCommitPayload(BaseModel):
    preview_id: str
    account_id: int | None = None


class AccountPayload(BaseModel):
    name: str
    bank: str
    account_type: str
    identifier: str = ""
    initial_balance: float = 0
    initial_date: str
    currency: str = "EUR"
    status: str = "Actif"


class AccountReferencePayload(BaseModel):
    initial_balance: float
    initial_date: str


class AccountStatusPayload(BaseModel):
    status: str


class AssetPayload(BaseModel):
    name: str
    category: str
    asset_type: str
    value: float
    valuation_date: str
    valuation_mode: str = "Manuelle"
    comment: str = ""
    details: dict[str, str] = {}
    status: str = "Actif"


class TransactionPayload(BaseModel):
    account_id: int
    tx_date: str
    label: str
    category: str | None = None
    direction: str
    amount: float
    status: str


class TransactionCreatePayload(BaseModel):
    account_id: int
    tx_date: str
    label: str
    beneficiary: str | None = None
    category: str | None = None
    direction: str
    amount: float


class TransactionBulkPayload(BaseModel):
    transaction_ids: list[int]
    action: str
    category: str | None = None


class TransactionCategorizationRulePayload(BaseModel):
    target_category_id: int
    match_value: str | None = None


class RuleSuggestionItemPayload(BaseModel):
    match_value: str
    target_category_id: int
    transaction_type: str | None = None
    transaction_ids: list[int] = []


class RuleSuggestionApplyPayload(BaseModel):
    items: list[RuleSuggestionItemPayload]


class RuleSuggestionDismissPayload(BaseModel):
    match_value: str


class RecurrencePayload(BaseModel):
    account_id: int
    name: str
    category: str
    direction: str
    amount: float
    frequency: str = "Mensuel"
    next_date: str
    end_date: str | None = None
    scenario: str = "Réaliste"
    kind: str | None = None


class SafetyThresholdPayload(BaseModel):
    amount: float


class ForecastSimulationPayload(BaseModel):
    kind: str = "Dépense"
    date: str
    amount: float
    account_id: int | None = None
    label: str = ""
    scenario: str = "Réaliste"


class OccurrenceUpdatePayload(BaseModel):
    date: str
    amount: float
    label: str
    category: str = ""
    apply_to_rule: bool = False


class OccurrenceIdsPayload(BaseModel):
    occurrence_ids: list[int]


class OccurrenceShiftPayload(BaseModel):
    occurrence_ids: list[int]
    target_date: str


class OccurrenceReschedulePayload(BaseModel):
    occurrence_ids: list[int]
    target_date: str


class ScenarioPayload(BaseModel):
    name: str
    description: str = ""
    scenario_type: str = "Projet libre"
    start_date: str
    end_date: str | None = None
    horizon_months: int = 12
    currency_code: str = "EUR"
    is_active: bool = True


class ScenarioPresetPayload(BaseModel):
    income_percent: float
    expense_percent: float


class ScenarioEventPayload(BaseModel):
    event_type: str = "cash_out"
    label: str
    description: str = ""
    event_date: str
    end_date: str | None = None
    amount: float
    currency_code: str = "EUR"
    frequency: str = "once"
    duration_months: int | None = None
    account_id: int | None = None
    is_active: bool = True


def _scenario_snapshot(database: Database) -> dict:
    scenario_service = ScenarioService(database)
    event_service = ScenarioEventService(database)
    scenarios = []
    for row in scenario_service.list_scenarios():
        events = []
        for event in event_service.list_events(int(row["id"])):
            event_type = str(event["event_type"] or "custom")
            frequency = str(event["frequency"] or "once")
            events.append({
                "id": int(event["id"]),
                "scenarioId": int(event["scenario_id"]),
                "eventType": event_type,
                "eventTypeLabel": event_service.EVENT_TYPES.get(event_type, event_type),
                "label": str(event["label"] or ""),
                "description": str(event["description"] or ""),
                "eventDate": str(event["event_date"] or ""),
                "endDate": str(event["end_date"] or ""),
                "amount": float(event["amount"] or 0),
                "currencyCode": str(event["currency_code"] or "EUR"),
                "frequency": frequency,
                "frequencyLabel": event_service.FREQUENCIES.get(frequency, frequency),
                "durationMonths": int(event["duration_months"] or 0),
                "accountId": int(event["account_id"]) if event["account_id"] is not None else None,
                "accountName": str(event["account_name"] or "Tous les comptes"),
                "isActive": bool(event["is_active"]),
                "nature": event_service.event_nature(event_type),
                "sense": event_service.event_sense_label(event_type),
            })
        scenarios.append({
            "id": int(row["id"]),
            "name": str(row["name"] or ""),
            "description": str(row["description"] or ""),
            "scenarioType": str(row["scenario_type"] or "Projet libre"),
            "startDate": str(row["start_date"] or ""),
            "endDate": str(row["end_date"] or ""),
            "horizonMonths": int(row["horizon_months"] or 12),
            "currencyCode": str(row["currency_code"] or "EUR"),
            "isReference": bool(row["is_reference"]),
            "isActive": bool(row["is_active"]),
            "eventCount": int(row["event_count"] or 0),
            "events": events,
        })

    return {
        "scenarioTypes": list(scenario_service.TYPES),
        "eventTypes": [
            {
                "id": event_type,
                "label": label,
                "nature": event_service.event_nature(event_type),
                "sense": event_service.event_sense_label(event_type),
            }
            for event_type, label in event_service.EVENT_TYPES.items()
        ],
        "frequencies": [
            {"id": frequency, "label": label}
            for frequency, label in event_service.FREQUENCIES.items()
        ],
        "accounts": [
            {
                "id": int(account["id"]),
                "name": str(account["name"] or "Compte"),
                "bank": str(account["bank"] or ""),
                "type": str(account["account_type"] or ""),
            }
            for account in database.list_accounts()
            if str(account["status"] or "") == "Actif"
        ],
        "presets": database.forecast_scenario_presets(),
        "scenarios": scenarios,
    }


_scope_view: ContextVar = ContextVar("valoria_scope_view", default=None)

# Requêtes POST qui ne modifient rien : elles restent permises aux profils en
# consultation et travaillent, comme les lectures, sur le périmètre visible.
READ_ONLY_POSTS = frozenset(
    {
        "/api/v1/transactions/imports/preview",
        "/api/v1/forecast/simulate",
        "/api/v1/settings/rules-preview",
        "/api/v1/settings/rules-pending-preview",
    }
)
SELF_SERVICE_PREFIXES = ("/api/v1/auth/", "/api/v1/security/")


class ActiveDatabase:
    """Base actuellement ouverte.

    Les services reçoivent cet objet une fois pour toutes ; il redirige chaque
    appel vers la base ouverte. Pour un profil au périmètre limité, les lectures
    sont redirigées vers une copie filtrée de la base (voir ``ScopedSnapshots``).
    """

    _REAL_ATTRIBUTES = frozenset({"path", "data_dir"})

    def __init__(self) -> None:
        object.__setattr__(self, "_target", None)

    def use(self, database: Database) -> None:
        object.__setattr__(self, "_target", database)

    def release(self) -> None:
        object.__setattr__(self, "_target", None)

    def is_active(self) -> bool:
        return object.__getattribute__(self, "_target") is not None

    def real(self) -> Database:
        target = object.__getattribute__(self, "_target")
        if target is None:
            raise RuntimeError("Aucun profil n’est ouvert.")
        return target

    def __getattr__(self, name: str):
        target = self.real()
        if name not in ActiveDatabase._REAL_ATTRIBUTES:
            view = _scope_view.get()
            if view is not None:
                return getattr(view(), name)
        return getattr(target, name)


def create_app(database: Database | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        # Arrêt normal de l'application : si les données sont protégées, on referme le coffre
        # (base en clair effacée, clé oubliée). Un arrêt brutal est repris au déverrouillage suivant.
        try:
            protection.lock()
        except Exception:
            pass

    app = FastAPI(
        title="Valoria Vision Local API",
        version="0.1.0",
        description="Local-only boundary between the React UI and Python engines.",
        lifespan=lifespan,
    )

    legacy_database = database or Database()
    # Le registre ne sert plus qu'à retrouver le profil Démo (base séparée) et,
    # lors de la reprise d'une installation existante, le nom/l'avatar d'origine.
    profiles = ProfileManager(legacy_database.data_dir, legacy_database=legacy_database)
    users = UserStore(legacy_database)
    protection = ProtectionService(legacy_database)
    snapshots = ScopedSnapshots(legacy_database)
    active_database = ActiveDatabase()
    # pin_ready : profils ayant ouvert une session par mot de passe depuis le lancement de
    # l'application. Le PIN ne sert qu'à rouvrir une session verrouillée ensuite.
    state: dict = {"ready": False, "demo_id": None, "pin_ready": set()}
    policy = AuthService(None)
    bank_imports = BankImportWorkflowService(active_database)
    sessions = ApiSessionStore(600)
    bootstrap_secret = os.environ.get("VALORIA_API_BOOTSTRAP_SECRET", "")

    # ------------------------------------------------------------------
    # Préparation de la base commune et reprise d'une installation existante
    # ------------------------------------------------------------------
    def ensure_ready() -> None:
        if protection.locked or state["ready"] or not users.db_exists():
            return
        legacy_database.prepare_existing_database()
        users.ensure_schema()
        if users.count() == 0:
            name, avatar = "Administrateur", None
            if profiles.exists(LEGACY_PROFILE_ID):
                entry = profiles.get(LEGACY_PROFILE_ID)
                if entry["name"] and entry["name"] != "Profil principal":
                    name = entry["name"]
                avatar = entry["avatar"]
            users.migrate_legacy_password(name, avatar)
        state["ready"] = True

    def demo_profiles() -> list[dict]:
        result = []
        for entry in profiles.list_profiles():
            if entry["kind"] != "demo":
                continue
            result.append(
                {
                    **entry,
                    "role": ROLE_ADMIN,
                    "roleLabel": "Démonstration",
                    "scopeAccounts": 0,
                    "scopeAssets": 0,
                    "totalAccounts": 0,
                    "totalAssets": 0,
                    "removable": True,
                }
            )
        return result

    def with_pin_flags(listing: list[dict]) -> list[dict]:
        """Ajoute à chaque profil : a-t-il un PIN, et est-il utilisable maintenant."""
        for item in listing:
            user_id = UserStore.parse_public_id(item["id"])
            has_pin = bool(user_id and AuthService(users.settings_for(user_id)).has_pin())
            item["pinConfigured"] = has_pin
            item["pinAvailable"] = bool(has_pin and user_id in state["pin_ready"])
        return listing

    def public_profiles() -> list[dict]:
        ensure_ready()
        if protection.locked:
            # Données verrouillées : l'annuaire en clair suffit à choisir un profil.
            return protection.read_directory() + demo_profiles()
        return with_pin_flags(users.list_users()) + demo_profiles()

    def user_count() -> int:
        return len(protection.read_directory()) if protection.locked else users.count()

    def refresh_directory() -> None:
        """Garde l'annuaire à jour pour l'écran de choix de profil quand tout est verrouillé."""
        if protection.protected and not protection.locked:
            try:
                protection.write_directory(users.list_users())
            except Exception:
                pass

    def timeout_seconds_for(db: Database) -> int:
        try:
            minutes = max(1, int(db.get_setting("security.session_timeout_minutes", "10")))
        except (ValueError, Exception):
            minutes = 10
        return max(60, minutes * 60)

    def open_session(user_id: int | None, mode: str):
        """Ouvre l'espace d'un profil : un seul profil actif à la fois."""
        sessions.clear()
        snapshots.clear()
        if mode == "demo":
            db = profiles.database_for(state["demo_id"])
            db.prepare_existing_database()
        else:
            db = legacy_database
            users.touch_login(int(user_id))
            refresh_directory()
        active_database.use(db)
        sessions.timeout_seconds = timeout_seconds_for(db)
        return sessions.create(user_id=user_id, mode=mode)

    # ------------------------------------------------------------------
    # Identité et périmètre
    # ------------------------------------------------------------------
    def scope_of(token: str | None) -> Scope:
        ident = sessions.identity(token)
        if ident is None or ident[1] == "demo" or ident[0] is None:
            return UNRESTRICTED
        try:
            return users.scope_for(ident[0])
        except UserNotFound:
            raise HTTPException(status_code=401, detail="Session locale absente ou expirée.") from None

    def require_admin(token: str | None) -> Scope:
        scope = scope_of(token)
        if not scope.is_admin:
            raise HTTPException(status_code=403, detail="Réservé à l’administrateur.")
        return scope

    def auth_for(token: str | None) -> AuthService:
        ident = sessions.identity(token)
        if ident is None or ident[0] is None:
            raise HTTPException(status_code=409, detail="Cette fonction n’existe pas pour le profil Démo.")
        return AuthService(users.settings_for(ident[0]))

    def hidden() -> HTTPException:
        return HTTPException(status_code=404, detail="Élément introuvable.")

    def guard_account(token: str | None, account_id: int | None) -> None:
        if not scope_of(token).sees_account(account_id):
            raise hidden()

    def guard_asset(token: str | None, asset_id: int | None) -> None:
        if not scope_of(token).sees_asset(asset_id):
            raise hidden()

    def guard_rows(token: str | None, sql: str, ids: list[int]) -> None:
        """Refuse une écriture si l'une des lignes ciblées dépend d'un compte hors périmètre."""
        scope = scope_of(token)
        if scope.accounts is None or not ids:
            return
        marks = ",".join("?" * len(ids))
        with active_database.real().connect() as conn:
            rows = conn.execute(sql.format(marks=marks), [int(i) for i in ids]).fetchall()
        if any(not scope.sees_account(r[0]) for r in rows):
            raise hidden()

    def guard_transactions(token: str | None, ids: list[int]) -> None:
        guard_rows(token, "SELECT DISTINCT account_id FROM transactions WHERE id IN ({marks})", ids)

    def guard_occurrences(token: str | None, ids: list[int]) -> None:
        guard_rows(token, "SELECT DISTINCT account_id FROM forecast_occurrences WHERE id IN ({marks})", ids)

    def guard_recurrences(token: str | None, ids: list[int]) -> None:
        guard_rows(token, "SELECT DISTINCT account_id FROM recurring_items WHERE id IN ({marks})", ids)

    def guard_proposal(token: str | None, proposal_id: int) -> None:
        guard_rows(
            token,
            "SELECT DISTINCT t.account_id FROM reconciliation_proposal_members m "
            "JOIN transactions t ON t.id = m.transaction_id WHERE m.proposal_id IN ({marks})",
            [proposal_id],
        )

    def grant_creator(token: str | None, resource_type: str, resource_id: int) -> None:
        """Un contributeur voit ce qu'il crée."""
        ident = sessions.identity(token)
        if ident is None or ident[0] is None or not resource_id:
            return
        scope = scope_of(token)
        if scope.restricted:
            users.grant(ident[0], resource_type, int(resource_id))

    def me_payload(token: str | None) -> dict | None:
        ident = sessions.identity(token)
        if ident is None:
            return None
        user_id, mode = ident
        if mode == "demo" or user_id is None:
            return {
                "id": state["demo_id"], "name": "Démo", "role": ROLE_ADMIN, "roleLabel": "Démonstration",
                "canWrite": True, "restricted": False,
                "visibleAccounts": 0, "totalAccounts": 0, "visibleAssets": 0, "totalAssets": 0,
            }
        row = users.get_row(user_id)
        scope = users.scope_for(user_id)
        totals = users.totals()
        return {
            "id": f"u{user_id}",
            "name": row["name"],
            "role": row["role"],
            "roleLabel": ROLE_LABELS.get(row["role"], row["role"]),
            "canWrite": scope.can_write,
            "restricted": scope.restricted,
            "visibleAccounts": len(scope.accounts) if scope.accounts is not None else totals["accounts"],
            "totalAccounts": totals["accounts"],
            "visibleAssets": len(scope.assets) if scope.assets is not None else totals["assets"],
            "totalAssets": totals["assets"],
        }

    @app.middleware("http")
    async def access_control(request: Request, call_next):
        token = request.headers.get("x-valoria-session")
        reset = None
        ident = sessions.identity(token) if token else None
        if ident is not None and ident[1] == "family" and ident[0] is not None:
            try:
                scope = users.scope_for(ident[0])
            except UserNotFound:
                return JSONResponse({"detail": "Session locale absente ou expirée."}, status_code=401)
            method, path = request.method, request.url.path
            is_read = method in ("GET", "HEAD", "OPTIONS") or path in READ_ONLY_POSTS
            self_service = path.startswith(SELF_SERVICE_PREFIXES) or (
                method == "PUT" and path.startswith("/api/v1/profiles/")
            )
            if not is_read and not self_service and not scope.can_write:
                return JSONResponse(
                    {"detail": "Votre profil est en consultation seulement."}, status_code=403
                )
            if scope.restricted and is_read:
                reset = _scope_view.set(lambda s=scope: snapshots.view(s))
        try:
            return await call_next(request)
        finally:
            if reset is not None:
                _scope_view.reset(reset)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "tauri://localhost",
            "https://tauri.localhost",
        ],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=[
            "Accept",
            "Content-Type",
            "X-Valoria-Bootstrap",
            "X-Valoria-Session",
        ],
    )

    def ensure_database_exists() -> None:
        if not active_database.is_active():
            raise HTTPException(
                status_code=401,
                detail="Session locale absente ou expirée.",
                headers={"WWW-Authenticate": "ValoriaSession"},
            )
        if not Path(active_database.path).exists():
            raise HTTPException(
                status_code=503,
                detail=(
                    "Aucune base utilisateur active n’a été trouvée. "
                    "Le prototype n’initialise jamais de données de démonstration automatiquement."
                ),
            )

    def resolve_target(requested: str | None) -> tuple[str, int | str]:
        """Retourne ("user", id) ou ("demo", id_du_profil_démo)."""
        ensure_ready()
        if protection.locked:
            directory = {item["id"] for item in protection.read_directory()}
            if requested:
                user_id = UserStore.parse_public_id(requested)
                if user_id is not None and requested in directory:
                    return "user", user_id
                if profiles.exists(requested) and profiles.get(requested)["kind"] == "demo":
                    return "demo", requested
                raise HTTPException(status_code=404, detail="Profil introuvable.")
            if len(directory) == 1:
                return "user", UserStore.parse_public_id(next(iter(directory)))
            raise HTTPException(status_code=409, detail="Choisissez un profil.")
        if requested:
            user_id = UserStore.parse_public_id(requested)
            if user_id is not None and users.exists(user_id):
                return "user", user_id
            if profiles.exists(requested) and profiles.get(requested)["kind"] == "demo":
                return "demo", requested
            raise HTTPException(status_code=404, detail="Profil introuvable.")
        only = users.only_user_id()
        if only:
            return "user", only
        raise HTTPException(status_code=409, detail="Choisissez un profil.")

    def require_session(token: str | None) -> None:
        if not sessions.validate(token):
            raise HTTPException(
                status_code=401,
                detail="Session locale absente ou expirée.",
                headers={"WWW-Authenticate": "ValoriaSession"},
            )

    def require_bootstrap(secret: str | None) -> None:
        if bootstrap_secret and not hmac.compare_digest(secret or "", bootstrap_secret):
            raise HTTPException(status_code=403, detail="Client local non autorisé.")

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "valoria-local-api",
            "apiVersion": "0.1.0",
        }

    @app.get("/api/v1/auth/status")
    def auth_status(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        listing = public_profiles()
        has_users = user_count() > 0
        ident = sessions.identity(x_valoria_session, touch=False)
        active_id = None
        if ident is not None:
            active_id = state["demo_id"] if ident[1] == "demo" else f"u{ident[0]}"
        selected = active_id or (listing[0]["id"] if len(listing) == 1 else None)
        current = next((p for p in listing if p["id"] == selected), None)
        retry = 0
        user_id = UserStore.parse_public_id(current["id"]) if current else None
        if user_id is not None:
            retry = (
                protection.throttle_seconds(user_id)
                if protection.locked
                else AuthService(users.settings_for(user_id)).lock_remaining_seconds()
            )
        return {
            "dataLocked": protection.locked,
            "configured": bool(has_users and current and (current["configured"] or current["kind"] == "demo")),
            "authenticated": ident is not None,
            "timeoutSeconds": sessions.timeout_seconds,
            "retryAfterSeconds": retry,
            "recoveryKeyConfigured": bool(current and current["recoveryKeyConfigured"]),
            "profiles": listing,
            "activeProfileId": active_id,
            "profileRequired": has_users and current is None and len(listing) > 1,
            "me": me_payload(x_valoria_session),
        }

    @app.get("/api/v1/me")
    def me(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        require_session(x_valoria_session)
        return {"me": me_payload(x_valoria_session)}

    @app.post("/api/v1/auth/setup")
    def setup(
        payload: PasswordPayload,
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        """Première installation : crée le premier administrateur."""
        require_bootstrap(x_valoria_bootstrap)
        ensure_ready()
        if protection.locked or users.count() > 0:
            raise HTTPException(status_code=409, detail="Le mot de passe maître est déjà configuré.")
        password = payload.password.get_secret_value()
        check = policy.password_policy(password)
        if not check.ok:
            raise HTTPException(status_code=422, detail=check.message)
        if not users.db_exists():
            users.initialize_family_database()
            state["ready"] = True
        try:
            created = users.create(payload.name or "Administrateur", ROLE_ADMIN)
        except UserError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        user_id = int(created["id"][1:])
        service = AuthService(users.settings_for(user_id))
        service.set_master_password(password)
        recovery_key = service.generate_recovery_key()
        service.record_event("auth.recovery_key_created", "Clé de secours créée.")
        token, expires_in = open_session(user_id, "family")
        return {"token": token, "expiresIn": expires_in, "profileId": created["id"], "recoveryKey": recovery_key}

    @app.post("/api/v1/auth/unlock")
    def unlock(
        payload: PasswordPayload,
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_ready()
        if user_count() == 0:
            raise HTTPException(status_code=409, detail="Le mot de passe maître doit être configuré.")
        kind, target = resolve_target(payload.profile_id)
        if kind == "demo":
            # Profil de démonstration : données fictives, aucun mot de passe.
            state["demo_id"] = target
            token, expires_in = open_session(None, "demo")
            return {"token": token, "expiresIn": expires_in, "profileId": target}
        if protection.locked:
            open_vault_with_password(int(target), payload.password.get_secret_value())
        service = AuthService(users.settings_for(int(target)))
        if not service.is_configured():
            raise HTTPException(status_code=409, detail="Le mot de passe de ce profil doit être configuré.")
        refuse_if_throttled(service)
        if not service.verify_master_password(payload.password.get_secret_value()):
            fail_with_throttle("Mot de passe incorrect.", service, status_if_not_locked=401)
        service.reset_failures()
        if protection.protected:
            # Chaque connexion réussie remet la serrure de ce profil d'équerre (nouveau profil,
            # mot de passe changé par un autre chemin, restauration d'une sauvegarde…).
            protection.set_password(int(target), payload.password.get_secret_value())
        token, expires_in = open_session(int(target), "family")
        state["pin_ready"].add(int(target))
        service.record_event("auth.unlock_success", "Connexion réussie.")
        return {"token": token, "expiresIn": expires_in, "profileId": f"u{target}"}

    def open_vault_with_password(user_id: int, password: str) -> None:
        """Données verrouillées : le mot de passe doit d'abord ouvrir la serrure du coffre."""
        wait = protection.throttle_seconds(user_id)
        if wait:
            raise HTTPException(
                status_code=429,
                detail=f"Trop d’essais. Réessayez dans {wait} s.",
                headers={"Retry-After": str(wait)},
            )
        if not protection.has_password_slot(user_id):
            raise HTTPException(
                status_code=409,
                detail="Les données sont verrouillées : ouvrez-les d’abord avec le profil administrateur.",
                headers={"X-Valoria-Vault": "admin-first"},
            )
        if not protection.unlock_with_password(user_id, password):
            delay = protection.register_failure(user_id)
            if delay:
                raise HTTPException(
                    status_code=429,
                    detail=f"Mot de passe incorrect. Trop d’essais : réessayez dans {delay} s.",
                    headers={"Retry-After": str(delay)},
                )
            raise HTTPException(status_code=401, detail="Mot de passe incorrect.")
        ensure_ready()

    @app.post("/api/v1/auth/unlock-pin")
    def unlock_pin(
        payload: PinUnlockPayload,
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        """Rouvre une session verrouillée avec le PIN (jamais au lancement de l'application)."""
        require_bootstrap(x_valoria_bootstrap)
        ensure_ready()
        kind, target = resolve_target(payload.profile_id)
        if kind != "user" or int(target) not in state["pin_ready"]:
            raise HTTPException(status_code=409, detail="Le PIN n’est pas disponible : utilisez le mot de passe.")
        service = AuthService(users.settings_for(int(target)))
        if not service.has_pin():
            raise HTTPException(status_code=409, detail="Aucun PIN n’est actif pour ce profil : utilisez le mot de passe.")
        refuse_if_throttled(service)
        if not service.verify_pin(payload.pin.get_secret_value()):
            remaining = service.register_pin_failure()
            service.record_event(
                "auth.pin_failure", "PIN incorrect.", {"remaining": remaining}
            )
            if remaining == 0:
                raise HTTPException(
                    status_code=403,
                    detail="PIN désactivé après 5 erreurs : connectez-vous avec votre mot de passe.",
                    headers={"X-Valoria-Pin": "disabled"},
                )
            raise HTTPException(
                status_code=403,
                detail=f"PIN incorrect · {remaining} essai{'s' if remaining > 1 else ''} restant{'s' if remaining > 1 else ''}",
                headers={"X-Valoria-Pin": "wrong"},
            )
        service.record_pin_success()
        token, expires_in = open_session(int(target), "family")
        service.record_event("auth.unlock_pin", "Session rouverte avec le PIN.")
        return {"token": token, "expiresIn": expires_in, "profileId": f"u{target}"}

    @app.post("/api/v1/auth/lock")
    def lock(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict[str, bool]:
        require_bootstrap(x_valoria_bootstrap)
        ident = sessions.identity(x_valoria_session)
        if ident is not None and ident[0] is not None:
            AuthService(users.settings_for(ident[0])).record_event("auth.lock", "Espace verrouillé.")
        sessions.revoke(x_valoria_session)
        snapshots.clear()
        return {"locked": True}

    def refuse_if_throttled(service: AuthService) -> None:
        wait = service.lock_remaining_seconds()
        if wait:
            raise HTTPException(
                status_code=429,
                detail=f"Trop d’essais. Réessayez dans {wait} s.",
                headers={"Retry-After": str(wait)},
            )

    def fail_with_throttle(
        message: str, service: AuthService, status_if_not_locked: int = 403
    ) -> None:
        delay = service.register_failure()
        service.record_event(
            "auth.unlock_failure",
            f"{message}" + (f" Verrouillage de {delay} s." if delay else ""),
            {"attempts": service.failed_attempts(), "lock_seconds": delay},
        )
        if delay:
            raise HTTPException(
                status_code=429,
                detail=f"{message} Trop d’essais : réessayez dans {delay} s.",
                headers={"Retry-After": str(delay)},
            )
        raise HTTPException(status_code=status_if_not_locked, detail=message)

    @app.get("/api/v1/security/status")
    def security_status(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        service = auth_for(x_valoria_session)
        return {
            "recoveryKeyConfigured": service.has_recovery_key(),
            "recoveryKeyCreatedAt": service.recovery_key_created_at() or None,
            "passwordChangedAt": service.db.get_setting("security.master_password_changed_at", "") or None,
            "pinConfigured": service.has_pin(),
            "pinCreatedAt": service.pin_created_at() or None,
            "pinLastUsedAt": service.pin_last_used_at() or None,
            "protectionEnabled": protection.protected,
            "protectionProfilesWithAccess": len(protection.owners()),
        }

    @app.post("/api/v1/security/protection/enable")
    def enable_protection(
        payload: RecoveryKeyRequestPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        """Verrouille les données par le mot de passe de l'administrateur connecté."""
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_family_admin(x_valoria_session)
        if protection.protected:
            raise HTTPException(status_code=409, detail="La protection par mot de passe est déjà active.")
        admin = auth_for(x_valoria_session)
        refuse_if_throttled(admin)
        password = payload.password.get_secret_value()
        if not admin.verify_master_password(password):
            fail_with_throttle("Mot de passe incorrect.", admin)
        admin.reset_failures()
        user_id = int(sessions.identity(x_valoria_session)[0])
        # Nouvelle clé de secours (montrée une seule fois) : elle ouvre aussi le coffre.
        keep = {k: admin.db.get_setting(f"security.recovery_{k}", "") for k in ("hash", "salt", "iterations", "created_at")}
        recovery_key = admin.generate_recovery_key()
        try:
            safety = protection.enable(user_id, password, recovery_key, users.list_users())
        except Exception as exc:
            for name, value in keep.items():
                admin.db.set_setting(f"security.recovery_{name}", value)
            raise HTTPException(status_code=500, detail=f"Activation annulée, rien n’a été modifié : {exc}") from exc
        admin.record_event("auth.protection_enabled", "Protection des données par mot de passe activée.")
        return {
            "enabled": True,
            "recoveryKey": recovery_key,
            "safetyCopy": Path(safety).name,
        }

    @app.post("/api/v1/security/protection/lock")
    def lock_vault(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        """Referme complètement les données : base en clair effacée, clé oubliée."""
        require_bootstrap(x_valoria_bootstrap)
        require_session(x_valoria_session)
        if not protection.protected:
            raise HTTPException(status_code=409, detail="La protection par mot de passe n’est pas active.")
        ident = sessions.identity(x_valoria_session)
        if ident is not None and ident[0] is not None:
            AuthService(users.settings_for(ident[0])).record_event("auth.vault_locked", "Données verrouillées.")
        sessions.clear()
        snapshots.clear()
        active_database.release()
        state["ready"] = False
        state["pin_ready"].clear()
        removed = protection.lock()
        return {"locked": True, "plaintextRemoved": removed}

    @app.post("/api/v1/security/pin")
    def set_pin(
        payload: PinSetPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        """Crée ou remplace le PIN du profil connecté (mot de passe exigé)."""
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        service = auth_for(x_valoria_session)
        refuse_if_throttled(service)
        try:
            service.set_pin(payload.password.get_secret_value(), payload.pin.get_secret_value())
        except PermissionError:
            fail_with_throttle("Mot de passe incorrect.", service)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        service.reset_failures()
        return {"pinConfigured": True, "pinCreatedAt": service.pin_created_at()}

    @app.post("/api/v1/security/pin/delete")
    def delete_pin(
        payload: RecoveryKeyRequestPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        service = auth_for(x_valoria_session)
        refuse_if_throttled(service)
        if not service.verify_master_password(payload.password.get_secret_value()):
            fail_with_throttle("Mot de passe incorrect.", service)
        service.reset_failures()
        service.remove_pin()
        return {"pinConfigured": False}

    @app.post("/api/v1/security/change-password")
    def change_password(
        payload: ChangePasswordPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict[str, bool]:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        service = auth_for(x_valoria_session)
        refuse_if_throttled(service)
        try:
            service.change_master_password(
                payload.current_password.get_secret_value(), payload.new_password.get_secret_value()
            )
        except PermissionError:
            fail_with_throttle("Mot de passe actuel incorrect.", service)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        ident = sessions.identity(x_valoria_session)
        if ident is not None and ident[0] is not None:
            protection.set_password(int(ident[0]), payload.new_password.get_secret_value())
        return {"changed": True}

    @app.post("/api/v1/security/recovery-key")
    def create_recovery_key(
        payload: RecoveryKeyRequestPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        service = auth_for(x_valoria_session)
        refuse_if_throttled(service)
        if not service.verify_master_password(payload.password.get_secret_value()):
            fail_with_throttle("Mot de passe incorrect.", service)
        replaced = service.has_recovery_key()
        key = service.generate_recovery_key()
        ident = sessions.identity(x_valoria_session)
        if ident is not None and ident[0] is not None:
            protection.set_recovery(int(ident[0]), key)
        service.reset_failures()
        service.record_event(
            "auth.recovery_key_created",
            "Clé de secours remplacée." if replaced else "Clé de secours créée.",
        )
        return {"recoveryKey": key, "createdAt": service.recovery_key_created_at()}

    def open_vault_with_recovery_key(user_id: int, recovery_key: str) -> None:
        wait = protection.throttle_seconds(f"r{user_id}")
        if wait:
            raise HTTPException(
                status_code=429,
                detail=f"Trop d’essais. Réessayez dans {wait} s.",
                headers={"Retry-After": str(wait)},
            )
        owner = protection.unlock_with_recovery(recovery_key)
        if owner != user_id:
            if owner is not None:
                protection.lock()  # la clé de secours d'un autre profil n'ouvre pas cet espace
            delay = protection.register_failure(f"r{user_id}")
            if delay:
                raise HTTPException(status_code=429, detail=f"Clé de secours incorrecte. Réessayez dans {delay} s.", headers={"Retry-After": str(delay)})
            raise HTTPException(status_code=403, detail="Clé de secours incorrecte.")
        ensure_ready()

    @app.post("/api/v1/auth/recover")
    def recover(
        payload: RecoverPayload,
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        kind, target = resolve_target(payload.profile_id)
        if kind != "user":
            raise HTTPException(status_code=409, detail="Le profil Démo n’a pas de mot de passe.")
        if protection.locked:
            open_vault_with_recovery_key(int(target), payload.recovery_key.get_secret_value())
        service = AuthService(users.settings_for(int(target)))
        if not service.has_recovery_key():
            raise HTTPException(status_code=409, detail="Aucune clé de secours n’a été créée.")
        refuse_if_throttled(service)
        try:
            new_key = service.reset_with_recovery_key(
                payload.recovery_key.get_secret_value(), payload.new_password.get_secret_value()
            )
        except PermissionError:
            fail_with_throttle("Clé de secours incorrecte.", service)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if protection.protected:
            protection.set_password(int(target), payload.new_password.get_secret_value())
            protection.set_recovery(int(target), new_key)
        token, expires_in = open_session(int(target), "family")
        return {"token": token, "expiresIn": expires_in, "recoveryKey": new_key, "profileId": f"u{target}"}

    # ------------------------------------------------------------------
    # Profils et accès
    # ------------------------------------------------------------------
    def user_error(exc: Exception) -> HTTPException:
        if isinstance(exc, (UserNotFound, ProfileNotFound)):
            return HTTPException(status_code=404, detail="Profil introuvable.")
        return HTTPException(status_code=422, detail=str(exc))

    @app.get("/api/v1/profiles")
    def list_profiles(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ident = sessions.identity(x_valoria_session, touch=False)
        active_id = None
        if ident is not None:
            active_id = state["demo_id"] if ident[1] == "demo" else f"u{ident[0]}"
        return {"profiles": public_profiles(), "activeProfileId": active_id}

    @app.post("/api/v1/profiles")
    def create_profile(
        payload: ProfileCreatePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        require_session(x_valoria_session)
        require_admin(x_valoria_session)
        try:
            if payload.kind == "demo":
                entry = profiles.create(payload.name, payload.color, "demo")
                return {"profile": entry, "recoveryKey": None}
            password = payload.password.get_secret_value() if payload.password else ""
            check = policy.password_policy(password)
            if not check.ok:
                raise HTTPException(status_code=422, detail=check.message)
            created = users.create(
                payload.name,
                payload.role,
                payload.color,
                payload.avatar,
                payload.accounts,
                payload.assets,
            )
        except (UserError, ProfileError) as exc:
            raise user_error(exc) from exc
        user_id = int(created["id"][1:])
        service = AuthService(users.settings_for(user_id))
        service.set_master_password(password)
        recovery_key = service.generate_recovery_key()
        service.record_event("auth.recovery_key_created", "Clé de secours créée.")
        if protection.protected:
            protection.set_password(user_id, password)
            protection.set_recovery(user_id, recovery_key)
            refresh_directory()
        return {"profile": users.get(user_id), "recoveryKey": recovery_key}

    @app.put("/api/v1/profiles/{profile_id}")
    def update_profile(
        profile_id: str,
        payload: ProfileUpdatePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        require_session(x_valoria_session)
        user_id = UserStore.parse_public_id(profile_id)
        if user_id is None:
            raise HTTPException(status_code=404, detail="Profil introuvable.")
        ident = sessions.identity(x_valoria_session)
        is_self = ident is not None and ident[0] == user_id
        if not is_self:
            require_admin(x_valoria_session)
        if payload.role is not None:
            require_admin(x_valoria_session)
        try:
            profile = users.update(
                user_id, payload.name, payload.color, payload.role, payload.avatar, payload.clear_avatar
            )
        except (UserError, UserNotFound) as exc:
            raise user_error(exc) from exc
        refresh_directory()
        return {"profile": profile}

    @app.put("/api/v1/profiles/{profile_id}/access")
    def update_profile_access(
        profile_id: str,
        payload: ProfileAccessPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        require_session(x_valoria_session)
        require_admin(x_valoria_session)
        user_id = UserStore.parse_public_id(profile_id)
        if user_id is None:
            raise HTTPException(status_code=404, detail="Profil introuvable.")
        try:
            users.set_grants(user_id, payload.accounts, payload.assets)
        except UserNotFound as exc:
            raise user_error(exc) from exc
        return {"profile": users.get(user_id)}

    @app.get("/api/v1/access")
    def access_matrix(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        require_session(x_valoria_session)
        require_admin(x_valoria_session)
        matrix = users.access_matrix()
        with_pin_flags(matrix.get("users", []))
        return matrix

    @app.post("/api/v1/profiles/{profile_id}/pin/delete")
    def admin_remove_pin(
        profile_id: str,
        payload: ProfileDeletePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        """L'administrateur retire le PIN d'un profil (oubli) ; le mot de passe du profil reste."""
        require_bootstrap(x_valoria_bootstrap)
        require_session(x_valoria_session)
        require_admin(x_valoria_session)
        admin = auth_for(x_valoria_session)
        refuse_if_throttled(admin)
        if not admin.verify_master_password(payload.password.get_secret_value()):
            fail_with_throttle("Mot de passe incorrect.", admin)
        admin.reset_failures()
        user_id = UserStore.parse_public_id(profile_id)
        if user_id is None or not users.exists(user_id):
            raise HTTPException(status_code=404, detail="Profil introuvable.")
        AuthService(users.settings_for(user_id)).remove_pin(
            "PIN retiré par l’administrateur.", "auth.pin_removed_by_admin"
        )
        return {"pinConfigured": False}

    @app.post("/api/v1/profiles/{profile_id}/delete")
    def delete_profile(
        profile_id: str,
        payload: ProfileDeletePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        """Suppression d'un profil : confirmée par le mot de passe de l'administrateur connecté."""
        require_bootstrap(x_valoria_bootstrap)
        require_session(x_valoria_session)
        require_admin(x_valoria_session)
        admin = auth_for(x_valoria_session)
        refuse_if_throttled(admin)
        if not admin.verify_master_password(payload.password.get_secret_value()):
            fail_with_throttle("Mot de passe incorrect.", admin)
        admin.reset_failures()
        user_id = UserStore.parse_public_id(profile_id)
        try:
            if user_id is None:
                if not profiles.exists(profile_id) or profiles.get(profile_id)["kind"] != "demo":
                    raise HTTPException(status_code=404, detail="Profil introuvable.")
                profiles.delete(profile_id)
            else:
                ident = sessions.identity(x_valoria_session)
                if ident is not None and ident[0] == user_id:
                    raise HTTPException(status_code=409, detail="Vous ne pouvez pas supprimer le profil ouvert.")
                users.delete(user_id)
                protection.remove_profile(user_id)
                refresh_directory()
        except (UserError, UserNotFound, ProfileError, ProfileNotFound) as exc:
            raise user_error(exc) from exc
        return {"deleted": True}

    @app.get("/api/v1/security/journal")
    def security_journal(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        require_admin(x_valoria_session)
        return {"events": AuthService(active_database.real()).recent_events(30)}

    # ------------------------------------------------------------------
    # Sauvegardes chiffrées (phrase secrète) — administrateur, base familiale
    # ------------------------------------------------------------------
    BACKUP_MAX_BYTES = 256 * 1024 * 1024

    def backup_service() -> BackupService:
        return BackupService(
            legacy_database.path,
            backup_location.effective_directory(legacy_database.data_dir, legacy_database.backup_dir),
            legacy_decrypt=legacy_database.crypto.decrypt_bytes,
        )

    def require_family_admin(token: str | None) -> None:
        require_session(token)
        ident = sessions.identity(token)
        if ident is None or ident[1] != "family":
            raise HTTPException(
                status_code=409,
                detail="Les sauvegardes concernent la base familiale ; elles ne sont pas disponibles en mode Démo.",
            )
        require_admin(token)

    def backup_failure(exc: BackupError) -> HTTPException:
        return HTTPException(status_code=422 if not isinstance(exc, WrongPassphrase) else 403, detail=str(exc))

    def load_backup_blob(payload: BackupSourcePayload, service: BackupService) -> bytes:
        try:
            if payload.name:
                return service.resolve(payload.name).read_bytes()
            if payload.data:
                if len(payload.data) > BACKUP_MAX_BYTES * 4 // 3 + 16:
                    raise BackupError("Fichier trop volumineux pour être une sauvegarde Valoria.")
                return base64.b64decode(payload.data, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise BackupError("Fichier de sauvegarde illisible.") from exc
        raise BackupError("Aucune sauvegarde indiquée.")

    @app.get("/api/v1/backups")
    def list_backups(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        require_family_admin(x_valoria_session)
        rows = backup_service().list_local()
        manual = [row for row in rows if row.get("kind") == "manual" and row.get("createdAt")]
        recorded = legacy_database.get_setting("backup.last_at", "")
        candidates = [row["createdAt"] for row in manual] + ([recorded] if recorded else [])
        return {
            "backups": rows,
            "lastBackupAt": max(candidates) if candidates else None,
            "reminderDays": 30,
            "directory": str(backup_service().backup_dir),
        }

    def location_info() -> dict:
        configured = backup_location.configured_directory(legacy_database.data_dir)
        current = backup_location.effective_directory(legacy_database.data_dir, legacy_database.backup_dir)
        return {
            "directory": str(current),
            "default": str(legacy_database.backup_dir),
            "isDefault": configured is None,
            "exists": current.is_dir(),
            "count": backup_location.count_backups(current),
        }

    @app.get("/api/v1/backups/location")
    def backup_location_get(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        require_family_admin(x_valoria_session)
        return location_info()

    @app.post("/api/v1/backups/location/test")
    def backup_location_test(
        payload: BackupLocationPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        require_family_admin(x_valoria_session)
        try:
            return backup_location.check_directory(payload.directory)
        except backup_location.BackupLocationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/backups/location/browse")
    def backup_location_browse(
        payload: BackupLocationPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        require_family_admin(x_valoria_session)
        try:
            return {"directory": backup_location.browse_directory(payload.directory)}
        except backup_location.BackupLocationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.put("/api/v1/backups/location")
    def backup_location_set(
        payload: BackupLocationPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        require_family_admin(x_valoria_session)
        try:
            backup_location.save_directory(legacy_database.data_dir, payload.directory)
        except backup_location.BackupLocationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        info = location_info()
        auth_for(x_valoria_session).record_event(
            "backup.location", f"Dossier des sauvegardes : {info['directory']}.", {}
        )
        return info

    @app.post("/api/v1/backups")
    def create_backup(
        payload: BackupCreatePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        require_family_admin(x_valoria_session)
        phrase = payload.passphrase.get_secret_value()
        if phrase != payload.confirm.get_secret_value():
            raise HTTPException(status_code=422, detail="Les deux phrases secrètes ne sont pas identiques.")
        service = backup_service()
        try:
            blob, info = service.build(phrase)
        except BackupError as exc:
            raise backup_failure(exc) from exc
        path = service.save_local(blob)
        legacy_database.set_setting("backup.last_at", info["createdAt"])
        auth_for(x_valoria_session).record_event("backup.created", f"Sauvegarde chiffrée créée ({path.name}).", {})
        return {"name": path.name, "data": base64.b64encode(blob).decode("ascii"), "info": info}

    @app.post("/api/v1/backups/download")
    def download_backup(
        payload: BackupSourcePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        require_family_admin(x_valoria_session)
        service = backup_service()
        try:
            path = service.resolve(payload.name or "")
        except BackupError as exc:
            raise backup_failure(exc) from exc
        return {"name": path.name, "data": base64.b64encode(path.read_bytes()).decode("ascii")}

    @app.post("/api/v1/backups/delete")
    def delete_backup(
        payload: BackupSourcePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        require_family_admin(x_valoria_session)
        try:
            backup_service().delete_local(payload.name or "")
        except BackupError as exc:
            raise backup_failure(exc) from exc
        return {"deleted": True}

    @app.post("/api/v1/backups/inspect")
    def inspect_backup(
        payload: BackupSourcePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        require_family_admin(x_valoria_session)
        service = backup_service()
        try:
            blob = load_backup_blob(payload, service)
            info = service.inspect(blob, payload.passphrase.get_secret_value())
        except BackupError as exc:
            raise backup_failure(exc) from exc
        return {"backup": info, "current": count_content(legacy_database.path)}

    @app.post("/api/v1/backups/restore")
    def restore_backup(
        payload: BackupSourcePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        """Remplace la base familiale ; confirmée par le mot de passe de l'administrateur connecté."""
        require_bootstrap(x_valoria_bootstrap)
        require_family_admin(x_valoria_session)
        admin = auth_for(x_valoria_session)
        refuse_if_throttled(admin)
        if not admin.verify_master_password(payload.password.get_secret_value()):
            fail_with_throttle("Mot de passe incorrect.", admin)
        admin.reset_failures()
        service = backup_service()
        try:
            blob = load_backup_blob(payload, service)
            safety = service.restore(blob, payload.passphrase.get_secret_value())
        except BackupError as exc:
            raise backup_failure(exc) from exc
        # La base a changé sous les pieds de l'application : on repart d'un état propre.
        sessions.clear()
        snapshots.clear()
        active_database.release()
        state["ready"] = False
        legacy_database.prepare_existing_database()
        ensure_ready()
        legacy_database.seal_database_to_encrypted_vault()
        refresh_directory()
        return {"restored": True, "safetyCopy": safety.name}

    def wipe_family_database() -> None:
        """Supprime la base familiale (et son coffre) ; sous Windows, un fichier peut rester
        verrouillé un instant : on libère les connexions, on réessaie, puis on vide la base en place."""
        protection.reset()  # plus rien à protéger : serrures et annuaire disparaissent avec les données
        database_path = Path(legacy_database.path)
        vault = Path(legacy_database.encrypted_db_path)
        # Le coffre d'abord : s'il restait seul, la base serait recréée depuis lui au prochain démarrage.
        ordered = [vault] + [database_path.with_name(database_path.name + suffix) for suffix in ("-wal", "-shm")] + [database_path]
        for target in ordered:
            for attempt in range(8):
                gc.collect()
                try:
                    target.unlink(missing_ok=True)
                    break
                except PermissionError:
                    if attempt == 7:
                        if target != database_path:
                            raise
                        wipe_in_place(database_path)
                    else:
                        time.sleep(0.25)
        users._schema_for = None

    def wipe_in_place(database_path: Path) -> None:
        """Dernier recours : remplace le contenu par une base vide en passant par SQLite lui-même."""
        empty = sqlite3.connect(":memory:")
        target = sqlite3.connect(database_path)
        try:
            empty.backup(target)
        finally:
            target.close()
            empty.close()
        users._schema_for = None
        users.initialize_family_database()

    @app.post("/api/v1/system/reset")
    def reset_everything(
        payload: ResetPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        """Remise à zéro complète : copie de sécurité chiffrée, puis suppression de la base familiale.

        Après l'opération, l'application repart comme à la première installation
        (création de l'administrateur). Le profil Démo, séparé, n'est pas touché.
        """
        require_bootstrap(x_valoria_bootstrap)
        require_family_admin(x_valoria_session)
        admin = auth_for(x_valoria_session)
        refuse_if_throttled(admin)
        if not admin.verify_master_password(payload.password.get_secret_value()):
            fail_with_throttle("Mot de passe incorrect.", admin)
        admin.reset_failures()
        if payload.confirmation.strip().upper() != RESET_CONFIRMATION:
            raise HTTPException(status_code=422, detail=f"Tapez exactement « {RESET_CONFIRMATION} » pour confirmer.")
        service = backup_service()
        try:
            blob, _ = service.build(payload.passphrase.get_secret_value(), kind="pre-reset")
        except BackupError as exc:
            raise backup_failure(exc) from exc
        # La copie est écrite avant toute suppression : si elle échoue, rien n'est touché.
        safety = service.save_local(blob, kind="pre-reset")
        sessions.clear()
        snapshots.clear()
        active_database.release()
        state["ready"] = False
        try:
            wipe_family_database()
        except OSError as exc:
            raise HTTPException(
                status_code=409,
                detail="Impossible de supprimer certains fichiers (utilisés par un autre programme). Fermez les autres fenêtres Valoria puis réessayez ; une copie de sécurité a été créée.",
            ) from exc
        return {"reset": True, "safetyCopy": safety.name}

    @app.get("/api/v1/dashboard")
    def dashboard(
        account_id: int | None = None,
        month: str | None = None,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            return DashboardReadService(active_database).snapshot(account_id, month)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/accounts")
    def accounts(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return AccountsReadService(active_database).snapshot()

    @app.post("/api/v1/accounts")
    def create_account(
        payload: AccountPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            result = AccountsReadService(active_database).create(payload.model_dump())
            grant_creator(x_valoria_session, "account", result.get("accountId", 0))
            return result
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/accounts/{account_id}")
    def update_account(
        account_id: int,
        payload: AccountPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_account(x_valoria_session, account_id)
        try:
            return AccountsReadService(active_database).update(account_id, payload.model_dump())
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/accounts/{account_id}/status")
    def update_account_status(
        account_id: int,
        payload: AccountStatusPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_account(x_valoria_session, account_id)
        try:
            return AccountsReadService(active_database).change_status(account_id, payload.status)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/accounts/{account_id}/delete")
    def delete_account(
        account_id: int,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_account(x_valoria_session, account_id)
        try:
            return AccountsReadService(active_database).delete(account_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
        except AccountDeletionBlockedError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/accounts/{account_id}/reference")
    def update_account_reference(
        account_id: int,
        payload: AccountReferencePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_account(x_valoria_session, account_id)
        try:
            return AccountsReadService(active_database).update_reference(
                account_id,
                payload.initial_balance,
                payload.initial_date,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/transactions")
    def transactions(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return TransactionsReadService(active_database).snapshot()

    @app.post("/api/v1/transactions")
    def create_transaction(
        payload: TransactionCreatePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_account(x_valoria_session, payload.account_id)
        try:
            return TransactionsReadService(active_database).create(payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/transactions/{transaction_id}")
    def update_transaction(
        transaction_id: int,
        payload: TransactionPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_transactions(x_valoria_session, [transaction_id])
        guard_account(x_valoria_session, payload.account_id)
        try:
            return TransactionsReadService(active_database).update(transaction_id, payload.model_dump())
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/transactions/{transaction_id}/categorization-rule")
    def create_transaction_categorization_rule(
        transaction_id: int,
        payload: TransactionCategorizationRulePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_transactions(x_valoria_session, [transaction_id])
        try:
            return SettingsReadService(active_database).create_rule_from_transaction(
                transaction_id,
                payload.target_category_id,
                payload.match_value,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/rule-suggestions")
    def rule_suggestions(
        min_reliability: float = 0.9,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return RuleSuggestionService(active_database).suggestions(min(max(min_reliability, 0.5), 1.0))

    @app.get("/api/v1/rule-suggestions/preview")
    def rule_suggestion_preview(
        match_value: str,
        transaction_type: str | None = None,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return {"transactions": RuleSuggestionService(active_database).preview(match_value, transaction_type)}

    @app.post("/api/v1/rule-suggestions/apply")
    def apply_rule_suggestions(
        payload: RuleSuggestionApplyPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            return RuleSuggestionService(active_database).apply([item.model_dump() for item in payload.items])
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/rule-suggestions/dismiss")
    def dismiss_rule_suggestion(
        payload: RuleSuggestionDismissPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            return RuleSuggestionService(active_database).dismiss(payload.match_value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/transactions/actions/bulk")
    def bulk_update_transactions(
        payload: TransactionBulkPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_transactions(x_valoria_session, payload.transaction_ids)
        try:
            return TransactionsReadService(active_database).bulk_update(
                payload.transaction_ids,
                payload.action,
                payload.category,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/transactions/imports/preview")
    def preview_bank_import(
        payload: BankImportPreviewPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            return bank_imports.preview(
                x_valoria_session or "",
                payload.file_name,
                payload.content_base64,
                payload.account_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/transactions/imports/commit")
    def commit_bank_import(
        payload: BankImportCommitPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_account(x_valoria_session, payload.account_id)
        try:
            return bank_imports.commit(
                x_valoria_session or "",
                payload.preview_id,
                payload.account_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/transactions/imports")
    def bank_import_history(
        limit: int = 20,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return bank_imports.history(limit)

    @app.post("/api/v1/transactions/imports/{batch_id}/cancel")
    def cancel_bank_import(
        batch_id: int,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_rows(x_valoria_session, "SELECT DISTINCT account_id FROM import_batches WHERE id IN ({marks})", [batch_id])
        try:
            return bank_imports.cancel(batch_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc.args[0])) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/forecast")
    def forecast(
        account_id: int | None = None,
        horizon_days: int = 15,
        scenario: str = "Réaliste",
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return ForecastReadService(active_database).snapshot(account_id, horizon_days, scenario)

    @app.put("/api/v1/forecast/safety-threshold")
    def update_safety_threshold(
        payload: SafetyThresholdPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            return ForecastReadService(active_database).update_safety_threshold(payload.amount)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/forecast/simulate")
    def simulate_forecast(
        payload: ForecastSimulationPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            return ForecastReadService(active_database).simulate(payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/forecast/reschedulable-occurrences")
    def reschedulable_forecast_occurrences(
        account_id: int | None = None,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return ReconciliationReadService(active_database).reschedulable_occurrences(account_id)

    @app.post("/api/v1/forecast/occurrences/reschedule")
    def reschedule_forecast_occurrences(
        payload: OccurrenceReschedulePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_occurrences(x_valoria_session, payload.occurrence_ids)
        result = ReconciliationReadService(active_database).reschedule_occurrences(
            payload.occurrence_ids,
            payload.target_date,
        )
        if not result["success"]:
            raise HTTPException(status_code=409, detail=result["message"])
        return result

    @app.get("/api/v1/recurrences/occurrences")
    def recurrence_occurrences(
        account_id: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return RecurrenceOccurrencesService(active_database).snapshot(account_id, start_date, end_date)

    def _occurrence_action(result: dict) -> dict:
        if not result["success"]:
            raise HTTPException(status_code=409, detail=result["message"])
        return result

    @app.put("/api/v1/recurrences/occurrences/{occurrence_id}")
    def update_recurrence_occurrence(
        occurrence_id: int,
        payload: OccurrenceUpdatePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_occurrences(x_valoria_session, [occurrence_id])
        return _occurrence_action(RecurrenceOccurrencesService(active_database).update(occurrence_id, payload.model_dump()))

    @app.post("/api/v1/recurrences/occurrences/shift")
    def shift_recurrence_occurrences(
        payload: OccurrenceShiftPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_occurrences(x_valoria_session, payload.occurrence_ids)
        return _occurrence_action(
            RecurrenceOccurrencesService(active_database).shift(payload.occurrence_ids, payload.target_date)
        )

    @app.post("/api/v1/recurrences/occurrences/postpone")
    def postpone_recurrence_occurrences(
        payload: OccurrenceIdsPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_occurrences(x_valoria_session, payload.occurrence_ids)
        return _occurrence_action(RecurrenceOccurrencesService(active_database).postpone(payload.occurrence_ids))

    @app.post("/api/v1/recurrences/occurrences/delete")
    def delete_recurrence_occurrences(
        payload: OccurrenceIdsPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_occurrences(x_valoria_session, payload.occurrence_ids)
        return _occurrence_action(RecurrenceOccurrencesService(active_database).delete(payload.occurrence_ids))

    @app.post("/api/v1/recurrences/occurrences/{occurrence_id}/restore")
    def restore_recurrence_occurrence(
        occurrence_id: int,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_occurrences(x_valoria_session, [occurrence_id])
        return _occurrence_action(RecurrenceOccurrencesService(active_database).restore(occurrence_id))

    @app.post("/api/v1/recurrences")
    def create_recurrence(
        payload: RecurrencePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_account(x_valoria_session, payload.account_id)
        try:
            return RecurrenceWriteService(active_database).create(payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.put("/api/v1/recurrences/{item_id}")
    def update_recurrence(
        item_id: int,
        payload: RecurrencePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_recurrences(x_valoria_session, [item_id])
        guard_account(x_valoria_session, payload.account_id)
        try:
            return RecurrenceWriteService(active_database).update(item_id, payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.delete("/api/v1/recurrences/{item_id}")
    def delete_recurrence(
        item_id: int,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_recurrences(x_valoria_session, [item_id])
        try:
            return RecurrenceWriteService(active_database).delete(item_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/scenarios")
    def scenarios(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return _scenario_snapshot(active_database)

    @app.post("/api/v1/scenario-presets/{scenario_name}")
    def update_scenario_preset(
        scenario_name: str,
        payload: ScenarioPresetPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            preset = active_database.update_forecast_scenario_preset(
                scenario_name,
                payload.income_percent,
                payload.expense_percent,
            )
            return {
                "success": True,
                "message": f"Paramètres du scénario {scenario_name} appliqués à la courbe.",
                "preset": preset,
            }
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/scenarios")
    def create_scenario(
        payload: ScenarioPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            scenario_id = ScenarioService(active_database).create_scenario(payload.model_dump())
            return {"success": True, "message": "Scénario créé.", "scenarioId": scenario_id}
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/scenarios/{scenario_id}")
    def update_scenario(
        scenario_id: int,
        payload: ScenarioPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            ScenarioService(active_database).update_scenario(scenario_id, payload.model_dump())
            return {"success": True, "message": "Scénario mis à jour.", "scenarioId": scenario_id}
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/scenarios/{scenario_id}/duplicate")
    def duplicate_scenario(
        scenario_id: int,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            duplicate_id = ScenarioService(active_database).duplicate_scenario(scenario_id)
            return {"success": True, "message": "Scénario dupliqué.", "scenarioId": duplicate_id}
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/scenarios/{scenario_id}/delete")
    def delete_scenario(
        scenario_id: int,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            ScenarioService(active_database).delete_scenario(scenario_id)
            return {"success": True, "message": "Scénario supprimé.", "scenarioId": scenario_id}
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/scenarios/{scenario_id}/events")
    def create_scenario_event(
        scenario_id: int,
        payload: ScenarioEventPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_account(x_valoria_session, payload.account_id)
        try:
            event_id = ScenarioEventService(active_database).add_event(scenario_id, payload.model_dump())
            return {"success": True, "message": "Hypothèse ajoutée.", "eventId": event_id, "scenarioId": scenario_id}
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/scenario-events/{event_id}")
    def update_scenario_event(
        event_id: int,
        payload: ScenarioEventPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_rows(x_valoria_session, "SELECT DISTINCT account_id FROM scenario_events WHERE id IN ({marks})", [event_id])
        guard_account(x_valoria_session, payload.account_id)
        try:
            ScenarioEventService(active_database).update_event(event_id, payload.model_dump())
            return {"success": True, "message": "Hypothèse mise à jour.", "eventId": event_id}
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/scenario-events/{event_id}/delete")
    def delete_scenario_event(
        event_id: int,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_rows(x_valoria_session, "SELECT DISTINCT account_id FROM scenario_events WHERE id IN ({marks})", [event_id])
        ScenarioEventService(active_database).delete_event(event_id)
        return {"success": True, "message": "Hypothèse supprimée.", "eventId": event_id}

    @app.get("/api/v1/budgets")
    def budgets(
        month: str | None = None,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return BudgetsReadService(active_database).snapshot(month)

    def _budget_write(action):
        try:
            return action()
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/budgets/revise")
    def revise_budget(
        payload: BudgetRevisionPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        result = _budget_write(lambda: active_database.revise_budget(payload.category, payload.new_amount, payload.scope, payload.month, payload.reason))
        return {"success": True, "message": "Budget révisé.", **result}

    @app.post("/api/v1/budgets/category")
    def save_budget_category(
        payload: BudgetCategoryPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        result = _budget_write(lambda: active_database.save_budget_category(
            payload.category, payload.month, payload.planned_amount, payload.alert_threshold, payload.mode, payload.notes, payload.active,
        ))
        return {"success": True, "message": "Catégorie budgétée enregistrée.", **result}

    @app.post("/api/v1/budgets/category/remove")
    def remove_budget_category(
        payload: BudgetCategoryRemovePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        removed = _budget_write(lambda: active_database.remove_budget_category(payload.category, payload.month))
        return {"success": True, "message": "Catégorie retirée du budget.", "removed": removed}

    @app.post("/api/v1/budgets/rules")
    def save_budget_rules(
        payload: BudgetRulesPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        value = _budget_write(lambda: active_database.set_budget_default_threshold(payload.default_alert_threshold))
        return {"success": True, "message": "Règles du budget enregistrées.", "defaultAlertThreshold": value}

    @app.get("/api/v1/assets")
    def assets(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return AssetsReadService(active_database).snapshot()

    @app.post("/api/v1/assets")
    def create_asset(
        payload: AssetPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        if not payload.name.strip():
            raise HTTPException(status_code=422, detail="Le nom de l’élément est obligatoire.")
        data = payload.model_dump()
        data["details_json"] = data.pop("details")
        asset_id = active_database.add_asset(data)
        grant_creator(x_valoria_session, "asset", asset_id)
        return {"success": True, "message": "Élément patrimonial ajouté.", "assetId": asset_id}

    @app.post("/api/v1/assets/{asset_id}")
    def update_asset(
        asset_id: int,
        payload: AssetPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_asset(x_valoria_session, asset_id)
        if not payload.name.strip():
            raise HTTPException(status_code=422, detail="Le nom de l’élément est obligatoire.")
        data = payload.model_dump()
        data["details_json"] = data.pop("details")
        try:
            active_database.update_asset(asset_id, data)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"success": True, "message": "Élément patrimonial mis à jour.", "assetId": asset_id}

    @app.post("/api/v1/assets/{asset_id}/delete")
    def delete_asset(
        asset_id: int,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_asset(x_valoria_session, asset_id)
        if active_database.get_asset(asset_id) is None:
            raise HTTPException(status_code=404, detail="Élément patrimonial introuvable.")
        active_database.delete_asset(asset_id)
        return {"success": True, "message": "Élément patrimonial supprimé.", "assetId": asset_id}

    @app.get("/api/v1/settings")
    def settings(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return SettingsReadService(active_database).snapshot()

    @app.post("/api/v1/settings/general")
    def update_settings_general(
        payload: SettingsGeneralPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        require_admin(x_valoria_session)
        try:
            return SettingsReadService(active_database).update_general(payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/settings/categories")
    def create_settings_category(
        payload: SettingsCategoryPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            return SettingsReadService(active_database).save_category(payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/settings/categories/{category_id}")
    def update_settings_category(
        category_id: int,
        payload: SettingsCategoryPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            return SettingsReadService(active_database).save_category(payload.model_dump(), category_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/settings/categories/{category_id}/delete")
    def delete_settings_category(
        category_id: int,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            return SettingsReadService(active_database).delete_category(category_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/settings/rules")
    def create_settings_rule(
        payload: SettingsRulePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            return SettingsReadService(active_database).save_rule(payload.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/settings/rules/{rule_id}")
    def update_settings_rule(
        rule_id: int,
        payload: SettingsRulePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            return SettingsReadService(active_database).save_rule(payload.model_dump(), rule_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/settings/rules/{rule_id}/active")
    def set_settings_rule_active(
        rule_id: int,
        payload: SettingsRuleActivePayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return SettingsReadService(active_database).set_rule_active(rule_id, payload.active)

    @app.post("/api/v1/settings/rules-pending-preview")
    def preview_pending_rules(
        payload: SettingsRulePendingPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            return SettingsReadService(active_database).pending_preview(payload.rule_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/settings/rules-apply")
    def apply_pending_rules(
        payload: SettingsRuleApplyPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            return SettingsReadService(active_database).apply_pending(payload.transaction_ids, payload.rule_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/settings/rules/{rule_id}/delete")
    def delete_settings_rule(
        rule_id: int,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        try:
            return SettingsReadService(active_database).delete_rule(rule_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/v1/settings/rules-preview")
    def preview_settings_rules(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return SettingsReadService(active_database).preview_rules()

    @app.get("/api/v1/reconciliation")
    def reconciliation(
        account_id: int | None = None,
        status: str = "active",
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return ReconciliationReadService(active_database).snapshot(account_id, status)

    def reconciliation_action(result: dict) -> dict:
        if not result["success"]:
            raise HTTPException(status_code=409, detail=result["message"])
        return result

    @app.post("/api/v1/reconciliation/proposals/{proposal_id}/confirm")
    def confirm_reconciliation_proposal(
        proposal_id: int,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_proposal(x_valoria_session, proposal_id)
        return reconciliation_action(ReconciliationReadService(active_database).confirm_proposal(proposal_id))

    @app.post("/api/v1/reconciliation/proposals/{proposal_id}/reject")
    def reject_reconciliation_proposal(
        proposal_id: int,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_proposal(x_valoria_session, proposal_id)
        return reconciliation_action(ReconciliationReadService(active_database).reject_proposal(proposal_id))

    @app.post("/api/v1/reconciliation/manual-match")
    def confirm_manual_reconciliation(
        payload: ReconciliationManualMatchPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_transactions(x_valoria_session, [payload.transaction_id])
        guard_occurrences(x_valoria_session, [payload.occurrence_id])
        return reconciliation_action(
            ReconciliationReadService(active_database).confirm_manual_match(
                payload.occurrence_id,
                payload.transaction_id,
                include_overage=payload.include_overage,
            )
        )

    @app.put("/api/v1/reconciliation/rules")
    def update_reconciliation_rules(
        payload: ReconciliationRulesPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        service = ReconciliationReadService(active_database)
        return reconciliation_action(service.update_rules({
            "dateToleranceDays": payload.date_tolerance_days,
            "amountToleranceAbs": payload.amount_tolerance_abs,
            "amountTolerancePercent": payload.amount_tolerance_percent,
            "manualWindowDays": payload.manual_window_days,
            "manualAmountTolerancePercent": payload.manual_amount_tolerance_percent,
        }))

    @app.post("/api/v1/reconciliation/links/cancel")
    def cancel_reconciliation_link(
        payload: ReconciliationCancelPayload,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        guard_occurrences(x_valoria_session, [payload.occurrence_id])
        guard_transactions(x_valoria_session, [payload.transaction_id] if payload.transaction_id else [])
        return reconciliation_action(
            ReconciliationReadService(active_database).cancel_reconciliation(
                payload.occurrence_id,
                payload.transaction_id,
            )
        )

    @app.get("/api/v1/reconciliation/history")
    def reconciliation_history(
        transaction_id: int | None = None,
        occurrence_id: int | None = None,
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        if transaction_id is None and occurrence_id is None:
            raise HTTPException(status_code=422, detail="Indiquez une transaction ou une prévision.")
        return ReconciliationReadService(active_database).history(transaction_id, occurrence_id)

    return app


app = create_app()
