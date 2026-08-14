"""Structured invoice-versus-receipt document classification."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from pydantic_ai import Agent, BinaryContent, NativeOutput
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.azure import AzureProvider

CLASSIFICATION_SYSTEM_PROMPT = (
    "Classify the supplied financial document for extraction routing. "
    "Return invoice for a supplier request for payment, and receipt "
    "for evidence of a completed payment. Do not extract invoice fields."
)

class DocumentClassification(BaseModel):
    """The extraction route selected for one financial document."""

    document_type: Literal["invoice", "receipt"]


class DocumentClassificationPipeline:
    """Classify a financial document before selecting its extraction model."""

    def __init__(self, endpoint: str, api_key: str, deployment: str) -> None:
        model = OpenAIResponsesModel(
            deployment,
            provider=AzureProvider(azure_endpoint=endpoint, api_key=api_key),
        )
        self._agent: Agent[None, DocumentClassification] = Agent(
            model,
            output_type=NativeOutput(DocumentClassification),
            instructions=CLASSIFICATION_SYSTEM_PROMPT,
        )

    @classmethod
    def from_environment(cls) -> DocumentClassificationPipeline:
        """Create the pipeline from the local Azure OpenAI environment variables."""
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
        if not endpoint or not api_key or not deployment:
            message = (
                "Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and "
                "AZURE_OPENAI_DEPLOYMENT before using this pipeline."
            )
            raise RuntimeError(message)
        return cls(endpoint=endpoint, api_key=api_key, deployment=deployment)

    def classify(self, document_path: Path) -> DocumentClassification:
        """Return the structured extraction route for a local PDF or image."""
        if not document_path.is_file():
            raise FileNotFoundError(f"Financial document was not found: {document_path}")

        media_type = mimetypes.guess_type(document_path.name)[0]
        if media_type not in {"application/pdf", "image/jpeg", "image/png"}:
            raise ValueError("Only PDF, PNG, and JPEG documents can be classified.")

        result = self._agent.run_sync(
            [
                "Classify this financial document.",
                BinaryContent(data=document_path.read_bytes(), media_type=media_type),
            ]
        )
        return result.output
