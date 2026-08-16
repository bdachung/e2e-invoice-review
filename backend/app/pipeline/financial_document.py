"""Assembly point for the financial-document processing pipeline."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.config import Settings
from app.document_review.base import DocumentReviewer
from app.pipeline.chain import FinancialDocumentChain, PipelineProgressCallback
from app.pipeline.document_classification import DocumentClassificationPipeline
from app.pipeline.general_ledger_classification import GeneralLedgerClassificationPipeline
from app.pipeline.models import (
    FinancialDocumentPipelineResult,
    FinancialDocumentProcessingState,
)
from app.pipeline.steps import (
    ClassificationStep,
    DocumentIntelligenceExtractionStep,
    GeneralLedgerClassificationStep,
    NormalizeDocumentStep,
    ValidationStep,
)
from app.pipeline.steps.document_review import DocumentReviewStep
from app.services.document_intelligence_service import DocumentIntelligenceService
from app.validation.financial_documents import DEFAULT_MINIMUM_CONFIDENCE
from app.validation.models import CompanyIdentity


def _no_duplicate_invoice(_supplier_name: str, _invoice_number: str) -> bool:
    return False


class FinancialDocumentPipeline:
    """Run Chat routing, DI extraction, review, policy, and GL suggestion."""

    def __init__(
        self,
        classifier: DocumentClassificationPipeline,
        document_intelligence: DocumentIntelligenceService,
        general_ledger_classifier: GeneralLedgerClassificationPipeline,
        company_identity: CompanyIdentity,
        duplicate_check: Callable[[str, str], bool] = _no_duplicate_invoice,
        minimum_confidence: float = DEFAULT_MINIMUM_CONFIDENCE,
        progress_callback: PipelineProgressCallback | None = None,
        document_reviewer: DocumentReviewer | None = None,
        content_type: str | None = None,
    ) -> None:
        self._content_type = content_type
        self._chain = FinancialDocumentChain(
            ClassificationStep(classifier),
            DocumentIntelligenceExtractionStep(document_intelligence),
            NormalizeDocumentStep(),
            DocumentReviewStep(document_reviewer),
            ValidationStep(company_identity, duplicate_check, minimum_confidence),
            GeneralLedgerClassificationStep(general_ledger_classifier),
            progress_callback=progress_callback,
        )

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        company_identity: CompanyIdentity,
        duplicate_check: Callable[[str, str], bool] = _no_duplicate_invoice,
        minimum_confidence: float = DEFAULT_MINIMUM_CONFIDENCE,
        progress_callback: PipelineProgressCallback | None = None,
        document_reviewer: DocumentReviewer | None = None,
        content_type: str | None = None,
    ) -> FinancialDocumentPipeline:
        if (
            not settings.azure_document_intelligence_endpoint
            or not settings.azure_document_intelligence_key
        ):
            raise RuntimeError(
                "Set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and "
                "AZURE_DOCUMENT_INTELLIGENCE_KEY in backend/.env."
            )
        document_intelligence = DocumentIntelligenceService(
            settings.azure_document_intelligence_endpoint,
            settings.azure_document_intelligence_key,
        )
        return cls(
            classifier=DocumentClassificationPipeline.from_settings(
                settings,
                text_extractor=document_intelligence.extract_text,
            ),
            document_intelligence=document_intelligence,
            general_ledger_classifier=GeneralLedgerClassificationPipeline.from_settings(settings),
            company_identity=company_identity,
            duplicate_check=duplicate_check,
            minimum_confidence=minimum_confidence,
            progress_callback=progress_callback,
            document_reviewer=document_reviewer,
            content_type=content_type,
        )

    def process(self, document_path: Path) -> FinancialDocumentPipelineResult:
        state = self._chain.run(
            FinancialDocumentProcessingState(
                document_path=document_path,
                content_type=self._content_type,
            )
        )
        if not all(
            (
                state.classification,
                state.extraction,
                state.review_data,
                state.document_review,
                state.validation,
                state.metadata,
            )
        ):
            raise RuntimeError("Financial document pipeline did not complete every required step.")
        return FinancialDocumentPipelineResult(
            classification=state.classification,
            extraction=state.extraction,
            review_data=state.review_data,
            document_review=state.document_review,
            validation=state.validation,
            metadata=state.metadata,
        )
