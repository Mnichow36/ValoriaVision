from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.database import Database
from app.services.dashboard_read_service import DashboardReadService


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
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type", "X-Valoria-Session"],
    )

    active_database = database or Database()

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "valoria-local-api",
            "apiVersion": "0.1.0",
        }

    @app.get("/api/v1/dashboard")
    def dashboard() -> dict:
        database_path = Path(active_database.path)
        if not database_path.exists():
            raise HTTPException(
                status_code=503,
                detail=(
                    "Aucune base utilisateur active n’a été trouvée. "
                    "Le prototype n’initialise jamais de données de démonstration automatiquement."
                ),
            )
        return DashboardReadService(active_database).snapshot()

    return app


app = create_app()
