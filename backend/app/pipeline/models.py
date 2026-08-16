"""Typed state and outputs shared by financial-document pipeline steps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.accounting import GeneralLedgerSuggestion
from app.document_review.schemas import DocumentReview, ExpenseCategory, ReviewLineItem
from app.pipeline.document_classification import DocumentClassification
from app.schemas.invoice import InvoiceExtraction
from app.schemas.receipt import ReceiptExtraction
from app.validation.models import ValidationReport


class FieldProvenance(StrEnum):
    DOCUMENT_INTELLIGENCE = "document_intelligence"
    HUMAN = "human"
    LLM_FALLBACK = "llm_fallback"


class FinancialDocumentReviewData(BaseModel):
    """Normalized values, provenance, confidence, and line items for Maya's review."""

    document_type: Literal["invoice", "receipt"]
    expense_category: ExpenseCategory | None = None
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
    amount_due: Decimal | None = None
    line_items: list[ReviewLineItem] = Field(default_factory=list)
    field_confidence: dict[str, float | None] = Field(default_factory=dict)
    field_provenance: dict[str, FieldProvenance] = Field(default_factory=dict)

    def mark_human_supplied(self, *fields: str) -> FinancialDocumentReviewData:
        provenance = dict(self.field_provenance)
        provenance.update({field: FieldProvenance.HUMAN for field in fields})
        return self.model_copy(update={"field_provenance": provenance})


FinancialDocumentView = FinancialDocumentReviewData


class FinancialDocumentMetadata(BaseModel):
    gl_suggestion: GeneralLedgerSuggestion


class FinancialDocumentPipelineResult(BaseModel):
    classification: DocumentClassification
    extraction: InvoiceExtraction | ReceiptExtraction
    review_data: FinancialDocumentReviewData
    document_review: DocumentReview
    validation: ValidationReport
    metadata: FinancialDocumentMetadata


@dataclass
class FinancialDocumentProcessingState:
    document_path: Path
    content_type: str | None = None
    document_text: str | None = None
    classification: DocumentClassification | None = None
    extraction: InvoiceExtraction | ReceiptExtraction | None = None
    review_data: FinancialDocumentReviewData | None = None
    document_review: DocumentReview | None = None
    validation: ValidationReport | None = None
    metadata: FinancialDocumentMetadata | None = None
