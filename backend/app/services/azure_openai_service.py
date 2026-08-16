"""Small Azure Chat Completions surface used by the playground experiment."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.providers.azure_openai import build_azure_openai_client


class AzureOpenAIService:
    """Generate plain text through an Azure Chat Completions deployment."""

    def __init__(self, client: Any, deployment: str) -> None:
        self._client = client
        self._deployment = deployment

    @classmethod
    def from_settings(cls, settings: Settings) -> AzureOpenAIService:
        if not settings.azure_openai_deployment:
            raise RuntimeError("Set AZURE_OPENAI_DEPLOYMENT in backend/.env.")
        return cls(build_azure_openai_client(settings), settings.azure_openai_deployment)

    @classmethod
    def from_environment(cls) -> AzureOpenAIService:
        """Convenience constructor for the local playground command."""
        return cls.from_settings(get_settings())

    def generate_text(self, prompt: str, *, instructions: str | None = None) -> str:
        """Generate one text completion with an optional system instruction."""
        messages: list[dict[str, str]] = []
        if instructions:
            messages.append({"role": "system", "content": instructions})
        messages.append({"role": "user", "content": prompt})
        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=messages,
        )
        return response.choices[0].message.content or ""
