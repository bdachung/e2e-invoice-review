"""Structured general-ledger suggestion from normalized document fields."""

from __future__ import annotations

import os

from pydantic_ai import Agent, NativeOutput
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.azure import AzureProvider

from app.accounting import GENERAL_LEDGER_CATALOG, GeneralLedgerSuggestion
from app.pipeline.models import FinancialDocumentView

GENERAL_LEDGER_CLASSIFICATION_SYSTEM_PROMPT = """You suggest one Northstar general-ledger account.
Use only the supplied normalized financial-document data. Select exactly one account code
from the fixed catalog below and give a short, factual rationale. This is a suggestion only;
do not assess validation, approval, VAT, or payment status.

Fixed catalog:
""" + "\n".join(
    f"- {account.code.value}: {account.name} — {account.description}"
    for account in GENERAL_LEDGER_CATALOG
)


class GeneralLedgerClassificationPipeline:
    """Suggest a fixed GL account for an invoice or receipt."""

    def __init__(self, endpoint: str, api_key: str, deployment: str) -> None:
        model = OpenAIResponsesModel(
            deployment,
            provider=AzureProvider(azure_endpoint=endpoint, api_key=api_key),
        )
        self._agent: Agent[None, GeneralLedgerSuggestion] = Agent(
            model,
            output_type=NativeOutput(GeneralLedgerSuggestion),
            instructions=GENERAL_LEDGER_CLASSIFICATION_SYSTEM_PROMPT,
        )

    @classmethod
    def from_environment(cls) -> GeneralLedgerClassificationPipeline:
        """Create the classifier from the local Azure OpenAI environment variables."""
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

    def classify(self, document: FinancialDocumentView) -> GeneralLedgerSuggestion:
        """Return a validated suggestion using only normalized document fields."""
        result = self._agent.run_sync(
            "Suggest a GL account for this normalized financial document:\n"
            f"{document.model_dump_json()}"
        )
        return result.output
