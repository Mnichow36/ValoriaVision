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
from app.services.accounts_read_service import AccountsReadService
from app.services.assets_read_service import AssetsReadService
from app.services.bank_import_workflow_service import BankImportWorkflowService
from app.services.budgets_read_service import BudgetsReadService
from app.services.dashboard_read_service import DashboardReadService
from app.services.forecast_read_service import ForecastReadService
from app.services.reconciliation_read_service import ReconciliationReadService
from app.services.settings_read_service import SettingsReadService
from app.services.transactions_read_service import TransactionsReadService


class PasswordPayload(BaseModel):
    password: SecretStr


class ReconciliationManualMatchPayload(BaseModel):
    occurrence_id: int
    transaction_id: int
    include_overage: bool = False


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
        allow_methods=["GET", "POST"],
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
        horizon_days: int = 90,
        scenario: str = "Réaliste",
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return ForecastReadService(active_database).snapshot(account_id, horizon_days, scenario)

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

    @app.get("/api/v1/assets")
    def assets(
        x_valoria_session: str | None = Header(default=None, alias="X-Valoria-Session"),
        x_valoria_bootstrap: str | None = Header(default=None, alias="X-Valoria-Bootstrap"),
    ) -> dict:
        require_bootstrap(x_valoria_bootstrap)
        ensure_database_exists()
        require_session(x_valoria_session)
        return AssetsReadService(active_database).snapshot()

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

    return app


app = create_app()
