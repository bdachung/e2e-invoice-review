"""Structured financial-document classification step."""

from app.pipeline.document_classification import DocumentClassificationPipeline
from app.pipeline.models import FinancialDocumentProcessingState


class ClassificationStep:
    def __init__(self, classifier: DocumentClassificationPipeline) -> None:
        self._classifier = classifier

    def run(self, state: FinancialDocumentProcessingState) -> FinancialDocumentProcessingState:
        state.classification = self._classifier.classify(state.document_path)
        return state
