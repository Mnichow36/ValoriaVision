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
from app.services.dashboard_read_service import DashboardReadService


class PasswordPayload(BaseModel):
    password: SecretStr


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

    return app


app = create_app()
