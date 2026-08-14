"""Document Intelligence extraction step selected by classification."""

from app.pipeline.models import FinancialDocumentProcessingState
from app.services.document_intelligence_service import DocumentIntelligenceService


class DocumentIntelligenceExtractionStep:
    def __init__(self, document_intelligence: DocumentIntelligenceService) -> None:
        self._document_intelligence = document_intelligence

    def run(self, state: FinancialDocumentProcessingState) -> FinancialDocumentProcessingState:
        if state.classification is None:
            raise RuntimeError("Classification must run before Document Intelligence extraction.")
        if state.classification.document_type == "invoice":
            state.extraction = self._document_intelligence.analyze_invoice(state.document_path)
        else:
            state.extraction = self._document_intelligence.analyze_receipt(state.document_path)
        return state
