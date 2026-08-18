"""Structured results returned by the Northstar Finance MCP tools.

These models translate the finance application's review state into the
agent-readable shape described in ``docs/mcp-design.md``. They contain no
business policy: every value is copied from the authoritative application
models.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

DocumentKind = Literal["invoice", "receipt"]
CheckOutcome = Literal["pass", "fail", "not_checked", "not_required", "not_available"]
AllowedAction = Literal["approve", "reject", "draft_email"]


class ReviewFields(BaseModel):
    """Curated normalized fields for one reviewed financial document."""

    document_type: DocumentKind
    expense_category: str | None = None
    supplier_name: str | None = None
    supplier_vat_id: str | None = None
    customer_name: str | None = None
    customer_vat_id: str | None = None
    document_number: str | None = None
    document_date: str | None = None
    due_date: str | None = None
    purchase_order: str | None = None
    currency: str | None = None
    subtotal: Decimal | None = None
    total_tax: Decimal | None = None
    total: Decimal | None = None
    amount_due: Decimal | None = None


class ValidationSummary(BaseModel):
    """Agent-readable summary of the deterministic finance policy findings."""

    vat_format: CheckOutcome
    totals: CheckOutcome
    duplicate: CheckOutcome
    po_match: CheckOutcome


class GlSuggestion(BaseModel):
    """Suggested GL account from the fixed Northstar catalog."""

    code: str
    name: str


class ReviewResult(BaseModel):
    """Final review result returned by ``process_document``."""

    review_id: str
    document_ref: str
    document_type: DocumentKind
    status: str
    fields: ReviewFields
    validation: ValidationSummary
    gl_suggestion: GlSuggestion | None = None
    conclusion: str
    allowed_actions: list[AllowedAction]
    error_message: str | None = None
