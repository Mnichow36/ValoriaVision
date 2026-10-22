from __future__ import annotations

import hmac
import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, SecretStr

from app.database import Database
from app.security.api_session import ApiSessionStore
from app.security.auth_service import AuthService
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
    password: SecretStr


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


def create_app(database: Database | None = None) -> FastAPI:
    app = FastAPI(
        title="Valoria Vision Local API",
        version="0.1.0",
        description="Local-only boundary between the React UI and Python engines.",
    )
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

    active_database = database or Database()
    auth = AuthService(active_database)
    bank_imports = BankImportWorkflowService(active_database)
    database_path = Path(active_database.path)
    timeout_seconds = 600
    if database_path.exists():
        try:
            timeout_seconds = auth.session_timeout_minutes() * 60
        except Exception:
            # A damaged or incomplete database is reported by the first real
            # request; importing the API must never create or repair it.
            timeout_seconds = 600
    sessions = ApiSessionStore(timeout_seconds)
    bootstrap_secret = os.environ.get("VALORIA_API_BOOTSTRAP_SECRET", "")

    def ensure_database_exists() -> None:
        if not database_path.exists():
            raise HTTPException(
                status_code=503,
                detail=(
                    "Aucune base utilisateur active n’a été trouvée. "
                    "Le prototype n’initialise jamais de données de démonstration automatiquement."
                ),
            )

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
        ensure_database_exists()
        return {
            "configured": auth.is_configured(),
            "authenticated": sessions.validate(x_valoria_session, touch=False),
            "timeoutSeconds": sessions.timeout_seconds,
        }

    @app.post("/api/v1/auth/setup")
    def setup(
        payload: PasswordPayload,
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        if auth.is_configured():
            raise HTTPException(status_code=409, detail="Le mot de passe maître est déjà configuré.")
        try:
            auth.set_master_password(payload.password.get_secret_value())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        token, expires_in = sessions.create()
        return {"token": token, "expiresIn": expires_in}

    @app.post("/api/v1/auth/unlock")
    def unlock(
        payload: PasswordPayload,
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        if not auth.is_configured():
            raise HTTPException(status_code=409, detail="Le mot de passe maître doit être configuré.")
        if not auth.verify_master_password(payload.password.get_secret_value()):
            raise HTTPException(status_code=401, detail="Mot de passe incorrect.")
        token, expires_in = sessions.create()
        return {"token": token, "expiresIn": expires_in}

    @app.post("/api/v1/auth/lock")
    def lock(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict[str, bool]:
        require_bootstrap(x_valoria_bootstrap)
        sessions.revoke(x_valoria_session)
        return {"locked": True}

    @app.get("/api/v1/dashboard")
    def dashboard(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return DashboardReadService(active_database).snapshot()

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
            return AccountsReadService(active_database).create(payload.model_dump())
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
