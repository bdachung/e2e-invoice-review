"""Chat Completions general-ledger suggestion from normalized financial fields."""

from __future__ import annotations

from pydantic_ai import Agent, NativeOutput
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.accounting import GENERAL_LEDGER_CATALOG, GeneralLedgerSuggestion
from app.config import Settings
from app.pipeline.models import FinancialDocumentView
from app.providers.azure_openai import build_async_azure_openai_client

GENERAL_LEDGER_CLASSIFICATION_SYSTEM_PROMPT = (
    "You suggest one Northstar general-ledger account. Use only the supplied "
    "normalized financial-document data. Select exactly one account code from "
    "the fixed catalog below and give a short, factual rationale. This is a "
    "suggestion only; do not assess validation, approval, VAT, or payment status.\n\n"
    "Fixed catalog:\n"
    + "\n".join(
        f"- {account.code.value}: {account.name} — {account.description}"
        for account in GENERAL_LEDGER_CATALOG
    )
)


class GeneralLedgerClassificationPipeline:
    """Use OpenAI-compatible Chat Completions for a fixed-catalog suggestion."""

    def __init__(self, provider: OpenAIProvider, deployment: str) -> None:
        self._agent: Agent[None, GeneralLedgerSuggestion] = Agent(
            OpenAIChatModel(deployment, provider=provider),
            output_type=NativeOutput(GeneralLedgerSuggestion),
            instructions=GENERAL_LEDGER_CLASSIFICATION_SYSTEM_PROMPT,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> GeneralLedgerClassificationPipeline:
        if not settings.azure_openai_deployment:
            raise RuntimeError("Set AZURE_OPENAI_DEPLOYMENT in backend/.env.")
        return cls(
            provider=OpenAIProvider(openai_client=build_async_azure_openai_client(settings)),
            deployment=settings.azure_openai_deployment,
        )

    def classify(self, document: FinancialDocumentView) -> GeneralLedgerSuggestion:
        """Return one validated GL suggestion; Maya remains responsible for selection."""
        return self._agent.run_sync(
            "Suggest a GL account for this normalized financial document:\n"
            f"{document.model_dump_json()}"
        ).output
