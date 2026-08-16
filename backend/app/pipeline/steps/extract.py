"""Document Intelligence extraction selected by the structured classification."""

from app.pipeline.models import FinancialDocumentProcessingState
from app.services.document_intelligence_service import DocumentIntelligenceService


class DocumentIntelligenceExtractionStep:
    def __init__(self, document_intelligence: DocumentIntelligenceService) -> None:
        self._document_intelligence = document_intelligence

    def run(self, state: FinancialDocumentProcessingState) -> FinancialDocumentProcessingState:
        if state.classification is None:
            raise RuntimeError("Classification must run before Document Intelligence extraction.")
        if state.classification.document_type == "invoice":
            state.extraction, state.document_text = (
                self._document_intelligence.analyze_invoice_with_text(state.document_path)
            )
        else:
            state.extraction, state.document_text = (
                self._document_intelligence.analyze_receipt_with_text(state.document_path)
            )
        return state
