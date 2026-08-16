"""Independent review and Document-Intelligence-primary reconciliation step."""

from __future__ import annotations

from app.document_review.base import DocumentReviewer, DocumentReviewError
from app.document_review.reconciliation import merge_document_extractions
from app.document_review.schemas import DocumentReview
from app.pipeline.models import FinancialDocumentProcessingState


class DocumentReviewStep:
    """Add independent structured review without allowing it to override DI values."""

    def __init__(self, reviewer: DocumentReviewer | None = None) -> None:
        self._reviewer = reviewer

    def run(self, state: FinancialDocumentProcessingState) -> FinancialDocumentProcessingState:
        if state.review_data is None:
            raise RuntimeError("Normalization must run before independent document review.")
        if self._reviewer is None or state.content_type is None:
            state.document_review = DocumentReview(
                error_message="Independent review is unavailable."
            )
            return state
        try:
            reviewed = self._reviewer.review(
                state.document_path,
                state.content_type,
                state.document_text,
            )
        except DocumentReviewError as error:
            state.document_review = DocumentReview(error_message=str(error))
            return state
        if reviewed.document_type == "unsupported":
            state.document_review = DocumentReview(
                extraction=reviewed,
                error_message="Independent review marked this document unsupported.",
            )
            return state
        merged, evidence = merge_document_extractions(state.review_data, reviewed)
        state.review_data = merged
        state.document_review = evidence
        return state
