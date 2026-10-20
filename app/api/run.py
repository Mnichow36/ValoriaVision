from __future__ import annotations

import os

import uvicorn

from app.database import Database


def main() -> None:
    database = Database()
    database.prepare_existing_database()
    port = int(os.environ.get("VALORIA_API_PORT", "8765"))
    uvicorn.run(
        "app.api.main:app",
        host="127.0.0.1",
        port=port,
        reload=os.environ.get("VALORIA_API_RELOAD") == "1",
    )


if __name__ == "__main__":
    main()
