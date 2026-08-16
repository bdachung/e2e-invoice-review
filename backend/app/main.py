"""FastAPI application factory for the local document-review API."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError

from app.accounting.routes import router as accounting_router
from app.auth import COOKIE_NAME, PUBLIC_API_PATHS, PasswordAuth, unauthorized_response
from app.auth_routes import router as auth_router
from app.config import get_app_config, get_settings
from app.database import build_database
from app.documents.models import DocumentRecord
from app.documents.progress_routes import router as progress_router
from app.documents.routes import router as document_router

logger = logging.getLogger(__name__)
SQLITE_SCHEMA_INITIALIZATION_ATTEMPTS = 12
SQLITE_SCHEMA_RETRY_DELAY_SECONDS = 2


def _migrate_sqlite(engine: Engine) -> None:
    """Apply the one additive local-schema change needed by existing demo databases."""
    with engine.begin() as connection:
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(documents)"))}
        if "document_review" not in columns:
            connection.execute(text("ALTER TABLE documents ADD COLUMN document_review JSON"))


def _initialize_sqlite_schema(engine: Engine) -> None:
    """Create or migrate the local schema, waiting for a previous revision's lock."""
    for attempt in range(1, SQLITE_SCHEMA_INITIALIZATION_ATTEMPTS + 1):
        try:
            DocumentRecord.metadata.create_all(engine)
            _migrate_sqlite(engine)
            return
        except OperationalError as error:
            engine.dispose()
            is_locked = "database is locked" in str(error).lower()
            if not is_locked or attempt == SQLITE_SCHEMA_INITIALIZATION_ATTEMPTS:
                raise
            logger.warning(
                "SQLite schema is locked; retrying startup in %s seconds (%s/%s).",
                SQLITE_SCHEMA_RETRY_DELAY_SECONDS,
                attempt,
                SQLITE_SCHEMA_INITIALIZATION_ATTEMPTS,
            )
            time.sleep(SQLITE_SCHEMA_RETRY_DELAY_SECONDS)


def create_app() -> FastAPI:
    settings = get_settings()
    config = get_app_config(settings)
    config.upload_dir.mkdir(parents=True, exist_ok=True)
    if config.database_url.startswith("sqlite:///"):
        Path(config.database_url.removeprefix("sqlite:///")).parent.mkdir(
            parents=True, exist_ok=True
        )
    engine, session_factory = build_database(config.database_url)
    if config.database_url.startswith("sqlite"):
        _initialize_sqlite_schema(engine)
    else:
        DocumentRecord.metadata.create_all(engine)
    password_auth = PasswordAuth(
        enabled=settings.auth_enabled,
        password=settings.app_password,
        session_secret=settings.session_secret,
        session_max_age_seconds=settings.session_max_age_seconds,
    )
    password_auth.validate_configuration()

    app = FastAPI(title="Invoice Review API", version="0.1.0")
    app.state.config, app.state.session_factory = config, session_factory
    app.state.password_auth = password_auth
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def require_password_for_api(request: Request, call_next):
        if (
            password_auth.enabled
            and request.url.path.startswith("/api")
            and request.url.path not in PUBLIC_API_PATHS
            and not password_auth.is_authenticated(request.cookies.get(COOKIE_NAME))
        ):
            return unauthorized_response()
        return await call_next(request)

    app.include_router(auth_router)
    app.include_router(document_router)
    app.include_router(progress_router)
    app.include_router(accounting_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if settings.frontend_dist_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=settings.frontend_dist_dir / "assets"),
            name="frontend-assets",
        )
        index_file = settings.frontend_dist_dir / "index.html"

        @app.get("/{path:path}", include_in_schema=False)
        def frontend(path: str) -> FileResponse:
            return FileResponse(index_file)

    return app


app = create_app()
