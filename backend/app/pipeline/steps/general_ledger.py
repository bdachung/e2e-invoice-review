"""Structured general-ledger suggestion step for all financial documents."""

from app.pipeline.general_ledger_classification import GeneralLedgerClassificationPipeline
from app.pipeline.models import FinancialDocumentMetadata, FinancialDocumentProcessingState


class GeneralLedgerClassificationStep:
    def __init__(self, classifier: GeneralLedgerClassificationPipeline) -> None:
        self._classifier = classifier

    def run(self, state: FinancialDocumentProcessingState) -> FinancialDocumentProcessingState:
        if state.document is None:
            raise RuntimeError("Normalization must run before general-ledger classification.")
        state.metadata = FinancialDocumentMetadata(
            gl_suggestion=self._classifier.classify(state.document)
        )
        return state
