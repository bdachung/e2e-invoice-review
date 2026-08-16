"""HTTP request and response models for local document reviews."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.accounting.models import GeneralLedgerAccount, GeneralLedgerSuggestion
from app.document_review.schemas import DocumentReview
from app.pipeline.document_classification import DocumentClassification
from app.pipeline.models import FinancialDocumentReviewData
from app.schemas.invoice import InvoiceExtraction
from app.schemas.receipt import ReceiptExtraction
from app.validation.models import ValidationIssue, ValidationReport

DocumentDecision = Literal["approved", "rejected"]
DocumentStatus = Literal["processing", "ready", "needs_review", "approved", "rejected", "failed"]


class AccountingSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gl_account_code: str


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: DocumentDecision


class DocumentCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
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


class AccountingCoding(BaseModel):
    suggestion: GeneralLedgerSuggestion | None = None
    selected_account: GeneralLedgerAccount | None = None
    overridden: bool = False


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    original_filename: str
    content_type: str
    status: DocumentStatus
    classification: DocumentClassification | None = None
    extraction: InvoiceExtraction | ReceiptExtraction | None = None
    review_data: FinancialDocumentReviewData | None = None
    document_review: DocumentReview | None = None
    validation: ValidationReport | None = None
    metadata: dict[str, object] | None = None
    accounting: AccountingCoding | None = None
    issues: list[ValidationIssue] = Field(default_factory=list)
    supplier_action_required: bool = False
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
