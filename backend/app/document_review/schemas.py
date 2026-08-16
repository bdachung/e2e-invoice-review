"""Structured output and evidence exposed by the independent document review."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

DocumentKind = Literal["invoice", "receipt", "unsupported"]
ExpenseCategory = Literal["fuel", "meals", "travel", "supplies", "other"]


class ReviewLineItem(BaseModel):
    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None


class LlmDocumentExtraction(BaseModel):
    """Provider-neutral strict structured output from the source-document review."""

    document_type: DocumentKind
    expense_category: ExpenseCategory | None = None
    supplier_name: str | None = None
    supplier_vat_id: str | None = None
    customer_name: str | None = None
    customer_vat_id: str | None = None
    document_number: str | None = None
    purchase_order: str | None = None
    document_date: str | None = None
    due_date: str | None = None
    currency: str | None = None
    subtotal: str | None = None
    total_tax: str | None = None
    total: str | None = None
    amount_due: str | None = None
    line_items: list[ReviewLineItem] = Field(default_factory=list)
    summary: str | None = None


class FieldComparison(BaseModel):
    field: str
    label: str
    status: Literal[
        "match",
        "different",
        "missing_in_document_intelligence",
        "missing_in_llm",
        "missing_in_both",
    ]
    document_intelligence_value: str | None = None
    llm_value: str | None = None


class DocumentReview(BaseModel):
    extraction: LlmDocumentExtraction | None = None
    comparisons: list[FieldComparison] = Field(default_factory=list)
    fallback_fields: list[FieldComparison] = Field(default_factory=list)
    error_message: str | None = None
