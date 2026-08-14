"""Assembly point for the financial-document processing pipeline."""

from __future__ import annotations

from pathlib import Path

from app.pipeline.chain import FinancialDocumentChain
from app.pipeline.document_classification import DocumentClassificationPipeline
from app.pipeline.general_ledger_classification import GeneralLedgerClassificationPipeline
from app.pipeline.models import FinancialDocumentPipelineResult, FinancialDocumentProcessingState
from app.pipeline.steps import (
    ClassificationStep,
    DocumentIntelligenceExtractionStep,
    GeneralLedgerClassificationStep,
    NormalizeDocumentStep,
    ValidationStep,
)
from app.services.document_intelligence_service import DocumentIntelligenceService


class FinancialDocumentPipeline:
    """Classify, extract, normalize, validate, and categorize a local document."""

    def __init__(
        self,
        classifier: DocumentClassificationPipeline,
        document_intelligence: DocumentIntelligenceService,
        general_ledger_classifier: GeneralLedgerClassificationPipeline,
        expected_customer_vat_id: str,
    ) -> None:
        self._chain = FinancialDocumentChain(
            ClassificationStep(classifier),
            DocumentIntelligenceExtractionStep(document_intelligence),
            NormalizeDocumentStep(),
            ValidationStep(expected_customer_vat_id),
            GeneralLedgerClassificationStep(general_ledger_classifier),
        )

    @classmethod
    def from_environment(cls, expected_customer_vat_id: str) -> FinancialDocumentPipeline:
        """Build the Azure-backed pipeline with an explicit Northstar VAT ID."""
        return cls(
            classifier=DocumentClassificationPipeline.from_environment(),
            document_intelligence=DocumentIntelligenceService.from_environment(),
            general_ledger_classifier=GeneralLedgerClassificationPipeline.from_environment(),
            expected_customer_vat_id=expected_customer_vat_id,
        )

    def process(self, document_path: Path) -> FinancialDocumentPipelineResult:
        """Run every configured step and return its typed output."""
        state = self._chain.run(FinancialDocumentProcessingState(document_path=document_path))
        if state.classification is None:
            raise RuntimeError("Financial document pipeline did not classify the document.")
        if state.extraction is None:
            raise RuntimeError("Financial document pipeline did not extract the document.")
        if state.document is None:
            raise RuntimeError("Financial document pipeline did not normalize the document.")
        if state.validation is None:
            raise RuntimeError("Financial document pipeline did not validate the document.")
        if state.metadata is None:
            raise RuntimeError(
                "Financial document pipeline did not classify a general ledger account."
            )
        return FinancialDocumentPipelineResult(
            classification=state.classification,
            extraction=state.extraction,
            document=state.document,
            validation=state.validation,
            metadata=state.metadata,
        )
