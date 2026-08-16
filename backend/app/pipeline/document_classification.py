"""Chat Completions invoice-versus-receipt classification before DI extraction."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent, NativeOutput
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.config import Settings
from app.providers.azure_openai import build_async_azure_openai_client

CLASSIFICATION_SYSTEM_PROMPT = (
    "Classify the supplied financial-document text for extraction routing. "
    "Return invoice for a supplier request for payment, and receipt "
    "for evidence of a completed payment. Do not extract fields."
)


class DocumentClassification(BaseModel):
    """The prebuilt Document Intelligence route selected for one document."""

    document_type: Literal["invoice", "receipt"]


class DocumentClassificationPipeline:
    """Use OpenAI-compatible Chat Completions with strict Pydantic routing output."""

    def __init__(
        self,
        provider: OpenAIProvider,
        deployment: str,
        text_extractor: Callable[[Path], str],
    ) -> None:
        self._agent: Agent[None, DocumentClassification] = Agent(
            OpenAIChatModel(deployment, provider=provider),
            output_type=NativeOutput(DocumentClassification),
            instructions=CLASSIFICATION_SYSTEM_PROMPT,
        )
        self._text_extractor = text_extractor

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        text_extractor: Callable[[Path], str],
    ) -> DocumentClassificationPipeline:
        if not settings.azure_openai_deployment:
            raise RuntimeError("Set AZURE_OPENAI_DEPLOYMENT in backend/.env.")
        return cls(
            provider=OpenAIProvider(openai_client=build_async_azure_openai_client(settings)),
            deployment=settings.azure_openai_deployment,
            text_extractor=text_extractor,
        )

    def classify(self, document_path: Path) -> DocumentClassification:
        """Classify layout text so PDFs work through Chat Completions too."""
        if not document_path.is_file():
            raise FileNotFoundError(f"Financial document was not found: {document_path}")
        document_text = self._text_extractor(document_path).strip()
        if not document_text:
            raise ValueError(
                "Document Intelligence did not return readable text for classification."
            )
        return self._agent.run_sync("Classify this financial document:\n\n" + document_text).output
