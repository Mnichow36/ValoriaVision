from __future__ import annotations

import hmac
import os
from contextvars import ContextVar
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, SecretStr

from app.database import Database
from app.security.api_session import ApiSessionStore
from app.security.auth_service import AuthService
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
    app = FastAPI(
        title="Valoria Vision Local API",
        version="0.1.0",
        description="Local-only boundary between the React UI and Python engines.",
    )

    legacy_database = database or Database()
    # Le registre ne sert plus qu'à retrouver le profil Démo (base séparée) et,
    # lors de la reprise d'une installation existante, le nom/l'avatar d'origine.
    profiles = ProfileManager(legacy_database.data_dir, legacy_database=legacy_database)
    users = UserStore(legacy_database)
    snapshots = ScopedSnapshots(legacy_database)
    active_database = ActiveDatabase()
    state: dict = {"ready": False, "demo_id": None}
    policy = AuthService(None)
    bank_imports = BankImportWorkflowService(active_database)
    sessions = ApiSessionStore(600)
    bootstrap_secret = os.environ.get("VALORIA_API_BOOTSTRAP_SECRET", "")

    # ------------------------------------------------------------------
    # Préparation de la base commune et reprise d'une installation existante
    # ------------------------------------------------------------------
    def ensure_ready() -> None:
        if state["ready"] or not users.db_exists():
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

    def public_profiles() -> list[dict]:
        ensure_ready()
        return users.list_users() + demo_profiles()

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
        has_users = users.count() > 0
        ident = sessions.identity(x_valoria_session, touch=False)
        active_id = None
        if ident is not None:
            active_id = state["demo_id"] if ident[1] == "demo" else f"u{ident[0]}"
        selected = active_id or (listing[0]["id"] if len(listing) == 1 else None)
        current = next((p for p in listing if p["id"] == selected), None)
        retry = 0
        user_id = UserStore.parse_public_id(current["id"]) if current else None
        if user_id is not None:
            retry = AuthService(users.settings_for(user_id)).lock_remaining_seconds()
        return {
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
        if users.count() > 0:
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
        if users.count() == 0:
            raise HTTPException(status_code=409, detail="Le mot de passe maître doit être configuré.")
        kind, target = resolve_target(payload.profile_id)
        if kind == "demo":
            # Profil de démonstration : données fictives, aucun mot de passe.
            state["demo_id"] = target
            token, expires_in = open_session(None, "demo")
            return {"token": token, "expiresIn": expires_in, "profileId": target}
        service = AuthService(users.settings_for(int(target)))
        if not service.is_configured():
            raise HTTPException(status_code=409, detail="Le mot de passe de ce profil doit être configuré.")
        refuse_if_throttled(service)
        if not service.verify_master_password(payload.password.get_secret_value()):
            fail_with_throttle("Mot de passe incorrect.", service, status_if_not_locked=401)
        service.reset_failures()
        token, expires_in = open_session(int(target), "family")
        service.record_event("auth.unlock_success", "Connexion réussie.")
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
        }

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
        service.reset_failures()
        service.record_event(
            "auth.recovery_key_created",
            "Clé de secours remplacée." if replaced else "Clé de secours créée.",
        )
        return {"recoveryKey": key, "createdAt": service.recovery_key_created_at()}

    @app.post("/api/v1/auth/recover")
    def recover(
        payload: RecoverPayload,
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        kind, target = resolve_target(payload.profile_id)
        if kind != "user":
            raise HTTPException(status_code=409, detail="Le profil Démo n’a pas de mot de passe.")
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
        return users.access_matrix()

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
