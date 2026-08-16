"""Public pipeline API with lazy imports to keep step dependencies acyclic."""

from __future__ import annotations

from typing import Any

__all__ = [
    "DocumentClassification",
    "DocumentClassificationPipeline",
    "FinancialDocumentMetadata",
    "FinancialDocumentPipeline",
    "FinancialDocumentPipelineResult",
    "FinancialDocumentView",
    "GeneralLedgerClassificationPipeline",
]


def __getattr__(name: str) -> Any:
    """Load expensive pipeline assemblies only when a caller asks for them."""
    if name in {"DocumentClassification", "DocumentClassificationPipeline"}:
        from .document_classification import (
            DocumentClassification,
            DocumentClassificationPipeline,
        )

        return {
            "DocumentClassification": DocumentClassification,
            "DocumentClassificationPipeline": DocumentClassificationPipeline,
        }[name]
    if name == "FinancialDocumentPipeline":
        from .financial_document import FinancialDocumentPipeline

        return FinancialDocumentPipeline
    if name == "GeneralLedgerClassificationPipeline":
        from .general_ledger_classification import GeneralLedgerClassificationPipeline

        return GeneralLedgerClassificationPipeline
    if name in {
        "FinancialDocumentMetadata",
        "FinancialDocumentPipelineResult",
        "FinancialDocumentView",
    }:
        from .models import (
            FinancialDocumentMetadata,
            FinancialDocumentPipelineResult,
            FinancialDocumentView,
        )

        return {
            "FinancialDocumentMetadata": FinancialDocumentMetadata,
            "FinancialDocumentPipelineResult": FinancialDocumentPipelineResult,
            "FinancialDocumentView": FinancialDocumentView,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
