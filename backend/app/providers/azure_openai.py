"""OpenAI-compatible Azure Chat Completions clients using an API key."""

from __future__ import annotations

from openai import AsyncOpenAI, OpenAI

from app.config import Settings


def _require_openai_settings(settings: Settings) -> tuple[str, str, str]:
    """Resolve the OpenAI-compatible base URL, API key, and deployment name."""
    if not (
        settings.azure_openai_endpoint
        and settings.azure_openai_api_key
        and settings.azure_openai_deployment
    ):
        raise RuntimeError(
            "Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and "
            "AZURE_OPENAI_DEPLOYMENT in backend/.env."
        )
    return (
        settings.azure_openai_endpoint,
        settings.azure_openai_api_key,
        settings.azure_openai_deployment,
    )


def build_azure_openai_client(settings: Settings) -> OpenAI:
    """Create a standard OpenAI client against Azure's OpenAI-compatible URL."""
    base_url, api_key, _deployment = _require_openai_settings(settings)
    return OpenAI(base_url=base_url, api_key=api_key)


def build_async_azure_openai_client(settings: Settings) -> AsyncOpenAI:
    """Create the standard async client used by Pydantic AI Chat Completions."""
    base_url, api_key, _deployment = _require_openai_settings(settings)
    return AsyncOpenAI(base_url=base_url, api_key=api_key)
