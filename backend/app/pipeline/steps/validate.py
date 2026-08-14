"""Deterministic invoice and receipt validation step."""

from app.pipeline.models import FinancialDocumentProcessingState
from app.schemas.invoice import InvoiceExtraction
from app.schemas.receipt import ReceiptExtraction
from app.validation.financial_documents import validate_invoice, validate_receipt


class ValidationStep:
    def __init__(self, expected_customer_vat_id: str) -> None:
        self._expected_customer_vat_id = expected_customer_vat_id

    def run(self, state: FinancialDocumentProcessingState) -> FinancialDocumentProcessingState:
        if isinstance(state.extraction, InvoiceExtraction):
            state.validation = validate_invoice(state.extraction, self._expected_customer_vat_id)
        elif isinstance(state.extraction, ReceiptExtraction):
            state.validation = validate_receipt(state.extraction)
        else:
            raise RuntimeError("Extraction must run before validation.")
        return state
