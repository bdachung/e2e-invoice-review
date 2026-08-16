"""Thin deterministic validation step for normalized review data."""

from __future__ import annotations

from collections.abc import Callable

from app.pipeline.models import FinancialDocumentProcessingState
from app.validation.financial_documents import (
    DEFAULT_MINIMUM_CONFIDENCE,
    validate_invoice,
    validate_receipt,
)
from app.validation.models import CompanyIdentity


class ValidationStep:
    def __init__(
        self,
        company_identity: CompanyIdentity,
        duplicate_check: Callable[[str, str], bool],
        minimum_confidence: float = DEFAULT_MINIMUM_CONFIDENCE,
    ) -> None:
        self._company_identity = company_identity
        self._duplicate_check = duplicate_check
        self._minimum_confidence = minimum_confidence

    def run(self, state: FinancialDocumentProcessingState) -> FinancialDocumentProcessingState:
        if state.review_data is None:
            raise RuntimeError("Normalization must run before validation.")
        if state.review_data.document_type == "invoice":
            state.validation = validate_invoice(
                state.review_data,
                company_identity=self._company_identity,
                duplicate_check=self._duplicate_check,
                minimum_confidence=self._minimum_confidence,
            )
        else:
            state.validation = validate_receipt(
                state.review_data,
                minimum_confidence=self._minimum_confidence,
            )
        return state
