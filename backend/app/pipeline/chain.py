"""Small reusable chain abstraction for document-processing steps."""

from __future__ import annotations

import logging
from typing import Protocol

from app.pipeline.models import FinancialDocumentProcessingState

logger = logging.getLogger(__name__)


class FinancialDocumentStep(Protocol):
    """A step that enriches a financial-document processing state."""

    def run(self, state: FinancialDocumentProcessingState) -> FinancialDocumentProcessingState: ...


class FinancialDocumentChain:
    """Run ordered, replaceable document-processing steps."""

    def __init__(self, *steps: FinancialDocumentStep) -> None:
        self._steps = steps

    def run(self, state: FinancialDocumentProcessingState) -> FinancialDocumentProcessingState:
        for step in self._steps:
            step_name = step.__class__.__name__
            logger.info("Starting pipeline step: %s", step_name)
            state = step.run(state)
            logger.info("Completed pipeline step: %s", step_name)
        return state
