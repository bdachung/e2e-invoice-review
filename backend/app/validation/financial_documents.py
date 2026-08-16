"""Pure offline validation rules for normalized financial review data."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Literal

from stdnum.eu import vat

from app.pipeline.models import FieldProvenance, FinancialDocumentReviewData
from app.validation.models import (
    CompanyIdentity,
    ValidationIssue,
    ValidationReport,
    ValidationStatus,
)

DuplicateCheck = Callable[[str, str], bool]
TOTAL_TOLERANCE = Decimal("0.01")
DEFAULT_MINIMUM_CONFIDENCE = 0.80


def _issue(
    code: str, field: str | None, severity: Literal["error", "warning"], message: str
) -> ValidationIssue:
    return ValidationIssue(code=code, field=field, severity=severity, message=message)


def _normalized_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def _normalized_vat(value: str) -> str:
    return vat.compact(value)


def _totals_reconcile(
    subtotal: Decimal | None, tax: Decimal | None, total: Decimal | None
) -> bool | None:
    if subtotal is None or tax is None or total is None:
        return None
    return abs((subtotal + tax) - total) <= TOTAL_TOLERANCE


def _add_low_confidence_warnings(
    review_data: FinancialDocumentReviewData,
    fields: tuple[str, ...],
    minimum_confidence: float,
    issues: list[ValidationIssue],
) -> None:
    for field in fields:
        confidence = review_data.field_confidence.get(field)
        provenance = review_data.field_provenance.get(field, FieldProvenance.DOCUMENT_INTELLIGENCE)
        if (
            confidence is not None
            and confidence < minimum_confidence
            and provenance is not FieldProvenance.HUMAN
        ):
            issues.append(
                _issue(
                    f"{field}_low_confidence",
                    field,
                    "warning",
                    f"Extraction confidence is below {minimum_confidence:.2f}.",
                )
            )


def _report(
    issues: list[ValidationIssue],
    *,
    supplier_vat_valid: bool | None = None,
    customer_vat_valid: bool | None = None,
    totals_reconcile: bool | None = None,
) -> ValidationReport:
    status = (
        ValidationStatus.NEEDS_REVIEW
        if any(issue.severity == "error" for issue in issues)
        else ValidationStatus.READY
    )
    return ValidationReport(
        supplier_vat_valid=supplier_vat_valid,
        customer_vat_valid=customer_vat_valid,
        totals_reconcile=totals_reconcile,
        issues=issues,
        status=status,
    )


def validate_invoice(
    review_data: FinancialDocumentReviewData,
    company_identity: CompanyIdentity,
    duplicate_check: DuplicateCheck,
    minimum_confidence: float = DEFAULT_MINIMUM_CONFIDENCE,
) -> ValidationReport:
    """Apply invoice policy without provider, persistence, or HTTP dependencies."""
    issues: list[ValidationIssue] = []
    required_fields = {
        "supplier_name": review_data.supplier_name,
        "supplier_vat_id": review_data.supplier_vat_id,
        "customer_name": review_data.customer_name,
        "customer_vat_id": review_data.customer_vat_id,
        "document_number": review_data.document_number,
        "document_date": review_data.document_date,
        "total": review_data.total,
        "currency": review_data.currency,
    }
    for field, value in required_fields.items():
        if value is None or value == "":
            issues.append(
                _issue(
                    f"{field}_required",
                    field,
                    "error",
                    f"{field.replace('_', ' ').title()} is required.",
                )
            )

    supplier_vat_valid = None
    if review_data.supplier_vat_id:
        supplier_vat_valid = vat.is_valid(review_data.supplier_vat_id)
        if not supplier_vat_valid:
            issues.append(
                _issue(
                    "supplier_vat_id_invalid",
                    "supplier_vat_id",
                    "error",
                    "Supplier VAT ID has an invalid EU format or checksum.",
                )
            )

    customer_vat_valid = None
    if review_data.customer_vat_id:
        customer_vat_valid = vat.is_valid(review_data.customer_vat_id)
    if review_data.customer_name and _normalized_text(
        review_data.customer_name
    ) != _normalized_text(company_identity.legal_name):
        issues.append(
            _issue(
                "customer_name_mismatch",
                "customer_name",
                "error",
                "Customer name does not match the configured company identity.",
            )
        )
    if review_data.customer_vat_id and _normalized_vat(
        review_data.customer_vat_id
    ) != _normalized_vat(company_identity.vat_id):
        issues.append(
            _issue(
                "customer_vat_id_mismatch",
                "customer_vat_id",
                "error",
                "Customer VAT ID does not match the configured company identity.",
            )
        )

    if review_data.total is not None and review_data.total <= 0:
        issues.append(
            _issue(
                "invoice_total_non_positive", "total", "error", "Invoice total must be positive."
            )
        )
    if (
        review_data.document_date
        and review_data.due_date
        and review_data.due_date < review_data.document_date
    ):
        issues.append(
            _issue(
                "invoice_date_order_invalid",
                "due_date",
                "error",
                "Due date cannot precede invoice date.",
            )
        )

    totals_reconcile = _totals_reconcile(
        review_data.subtotal, review_data.total_tax, review_data.total
    )
    if totals_reconcile is False:
        issues.append(
            _issue(
                "invoice_total_mismatch",
                "total",
                "error",
                "Subtotal plus VAT does not equal the invoice total within EUR 0.01.",
            )
        )
    if (
        review_data.supplier_name
        and review_data.document_number
        and duplicate_check(
            _normalized_text(review_data.supplier_name),
            _normalized_text(review_data.document_number),
        )
    ):
        issues.append(
            _issue(
                "duplicate_invoice",
                "document_number",
                "error",
                "An invoice with this supplier and invoice number already exists.",
            )
        )
    if not review_data.purchase_order:
        issues.append(
            _issue(
                "purchase_order_missing", "purchase_order", "warning", "Purchase order is missing."
            )
        )

    _add_low_confidence_warnings(
        review_data,
        (
            "supplier_name",
            "supplier_vat_id",
            "customer_name",
            "customer_vat_id",
            "document_number",
            "document_date",
            "currency",
            "total",
        ),
        minimum_confidence,
        issues,
    )
    return _report(
        issues,
        supplier_vat_valid=supplier_vat_valid,
        customer_vat_valid=customer_vat_valid,
        totals_reconcile=totals_reconcile,
    )


def validate_receipt(
    review_data: FinancialDocumentReviewData,
    minimum_confidence: float = DEFAULT_MINIMUM_CONFIDENCE,
) -> ValidationReport:
    """Apply receipt policy without invoice-only requirements."""
    issues: list[ValidationIssue] = []
    required_fields = {
        "supplier_name": review_data.supplier_name,
        "document_date": review_data.document_date,
        "currency": review_data.currency,
        "total": review_data.total,
        "total_tax": review_data.total_tax,
    }
    labels = {
        "supplier_name": "Merchant name",
        "document_date": "Transaction date",
        "total_tax": "VAT total",
    }
    for field, value in required_fields.items():
        if value is None or value == "":
            label = labels.get(field, field.replace("_", " ").title())
            issues.append(_issue(f"{field}_required", field, "error", f"{label} is required."))
    if review_data.total is not None and review_data.total <= 0:
        issues.append(
            _issue(
                "receipt_total_non_positive", "total", "error", "Receipt total must be positive."
            )
        )

    totals_reconcile = _totals_reconcile(
        review_data.subtotal, review_data.total_tax, review_data.total
    )
    if totals_reconcile is False:
        issues.append(
            _issue(
                "receipt_total_mismatch",
                "total",
                "error",
                "Subtotal plus VAT does not equal the receipt total within EUR 0.01.",
            )
        )
    _add_low_confidence_warnings(
        review_data,
        ("supplier_name", "document_date", "total_tax", "total", "currency"),
        minimum_confidence,
        issues,
    )
    return _report(issues, totals_reconcile=totals_reconcile)
