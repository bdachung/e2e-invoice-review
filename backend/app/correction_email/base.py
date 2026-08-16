"""Correction-email drafting interface."""

from typing import Protocol

from app.correction_email.schemas import CorrectionEmailDraft
from app.pipeline.models import FinancialDocumentReviewData
from app.validation.models import ValidationIssue


class CorrectionEmailDraftingError(RuntimeError):
    pass


class CorrectionEmailDrafter(Protocol):
    def draft(
        self, data: FinancialDocumentReviewData, issues: list[ValidationIssue]
    ) -> CorrectionEmailDraft: ...
