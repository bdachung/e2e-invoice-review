"""Backend configuration and fixed Northstar policy defaults."""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ALLOWED_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
DEFAULT_FRONTEND_DIST_DIR = BACKEND_ROOT.parent / "frontend" / "dist"


@dataclass(frozen=True)
class AppConfig:
    expected_customer_name: str = "Northstar Facilities B.V."
    expected_customer_vat_id: str = "NL00449544B01"
    database_url: str = "sqlite:///./data/documents.db"
    upload_dir: Path = Path("./data/uploads")
    max_upload_bytes: int = 4 * 1024 * 1024
    min_field_confidence: float = 0.80
    # Trusted reviewer identities for human-gated MCP review actions. The MCP
    # host passes reviewer_id; the server rejects anything outside this list.
    mcp_reviewer_ids: tuple[str, ...] = ("maya",)


APP_CONFIG = AppConfig()


class Settings(BaseSettings):
    """Environment-only settings used at application and provider boundaries."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    allowed_origins: str = DEFAULT_ALLOWED_ORIGINS
    database_url: str = APP_CONFIG.database_url
    upload_dir: Path = APP_CONFIG.upload_dir
    frontend_dist_dir: Path = DEFAULT_FRONTEND_DIST_DIR
    auth_enabled: bool = False
    app_password: str | None = None
    session_secret: str | None = None
    session_max_age_seconds: int = 12 * 60 * 60

    azure_openai_endpoint: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str = "2025-04-01-preview"
    azure_openai_api_key: str | None = None
    azure_document_intelligence_endpoint: str | None = None
    azure_document_intelligence_key: str | None = None

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_app_config(settings: Settings) -> AppConfig:
    """Combine fixed tutorial policy with deployable storage locations."""
    return replace(
        APP_CONFIG,
        database_url=settings.database_url,
        upload_dir=settings.upload_dir,
    )

