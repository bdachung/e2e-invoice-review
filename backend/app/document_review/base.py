"""Provider-independent independent-review interface."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.document_review.schemas import LlmDocumentExtraction


class DocumentReviewError(RuntimeError):
    """The independent reviewer could not return usable structured data."""


class DocumentReviewer(Protocol):
    def review(
        self,
        document_path: Path,
        content_type: str,
        document_text: str | None = None,
    ) -> LlmDocumentExtraction: ...
