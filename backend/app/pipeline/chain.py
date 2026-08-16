"""Small reusable chain abstraction for document-processing steps."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Literal, Protocol

from app.pipeline.models import FinancialDocumentProcessingState

logger = logging.getLogger(__name__)
PipelineProgressCallback = Callable[
    [str, Literal["started", "completed", "failed"], str | None], None
]

STEP_IDS = {
    "ClassificationStep": "classification",
    "DocumentIntelligenceExtractionStep": "extraction",
    "NormalizeDocumentStep": "normalization",
    "DocumentReviewStep": "independent_review",
    "ValidationStep": "validation",
    "GeneralLedgerClassificationStep": "general_ledger",
}


class FinancialDocumentStep(Protocol):
    """A step that enriches a financial-document processing state."""

    def run(self, state: FinancialDocumentProcessingState) -> FinancialDocumentProcessingState: ...


class FinancialDocumentChain:
    """Run ordered, replaceable document-processing steps."""

    def __init__(
        self,
        *steps: FinancialDocumentStep,
        progress_callback: PipelineProgressCallback | None = None,
    ) -> None:
        self._steps = steps
        self._progress_callback = progress_callback

    def run(self, state: FinancialDocumentProcessingState) -> FinancialDocumentProcessingState:
        for step in self._steps:
            step_name = step.__class__.__name__
            step_id = STEP_IDS.get(step_name, step_name)
            logger.info("Starting pipeline step: %s", step_name)
            self._publish(step_id, "started")
            try:
                state = step.run(state)
            except Exception as error:
                self._publish(step_id, "failed", str(error) or error.__class__.__name__)
                raise
            logger.info("Completed pipeline step: %s", step_name)
            self._publish(step_id, "completed")
        return state

    def _publish(
        self,
        step: str,
        status: Literal["started", "completed", "failed"],
        message: str | None = None,
    ) -> None:
        if self._progress_callback:
            self._progress_callback(step, status, message)
