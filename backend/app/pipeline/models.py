"""Typed state and outputs shared by financial-document pipeline steps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.accounting import GeneralLedgerSuggestion
from app.pipeline.document_classification import DocumentClassification
from app.schemas.invoice import InvoiceExtraction
from app.schemas.receipt import ReceiptExtraction
from app.validation.models import ValidationReport


class FinancialDocumentView(BaseModel):
    """Scalar financial fields supplied to downstream processing."""

    document_type: Literal["invoice", "receipt"]
    supplier_name: str | None = None
    supplier_vat_id: str | None = None
    customer_name: str | None = None
    customer_vat_id: str | None = None
    document_number: str | None = None
    document_date: date | None = None
    due_date: date | None = None
    purchase_order: str | None = None
    currency: str | None = None
    subtotal: Decimal | None = None
    total_tax: Decimal | None = None
    total: Decimal | None = None
    line_item_count: int


class FinancialDocumentMetadata(BaseModel):
    """Derived model metadata produced by the processing pipeline."""

    gl_suggestion: GeneralLedgerSuggestion


class FinancialDocumentPipelineResult(BaseModel):
    """The typed result of all financial-document pipeline steps."""

    classification: DocumentClassification
    extraction: InvoiceExtraction | ReceiptExtraction
    document: FinancialDocumentView
    validation: ValidationReport
    metadata: FinancialDocumentMetadata


@dataclass
class FinancialDocumentProcessingState:
    """Mutable state passed through each composable pipeline step."""

    document_path: Path
    classification: DocumentClassification | None = None
    extraction: InvoiceExtraction | ReceiptExtraction | None = None
    document: FinancialDocumentView | None = None
    validation: ValidationReport | None = None
    metadata: FinancialDocumentMetadata | None = None
