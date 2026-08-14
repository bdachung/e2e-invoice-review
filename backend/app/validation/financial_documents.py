"""Pure offline validation rules for extracted financial documents."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from stdnum.eu import vat

from app.schemas.invoice import InvoiceExtraction
from app.schemas.receipt import ReceiptExtraction
from app.validation.models import ValidationIssue, ValidationReport

TOTAL_TOLERANCE = Decimal("0.01")
MINIMUM_PRIMARY_CONFIDENCE = 0.80


def _value(field: object) -> object | None:
    return getattr(field, "value", None) if field else None


def _amount(field: object) -> Decimal | None:
    return getattr(field, "amount", None) if field else None


def _currency(field: object) -> str | None:
    return getattr(field, "currency_code", None) if field else None


def _issue(code: str, severity: Literal["error", "warning"], message: str) -> ValidationIssue:
    return ValidationIssue(code=code, severity=severity, message=message)


def _validate_vat(
    value: str | None,
    required_code: str,
    invalid_code: str,
    label: str,
    issues: list[ValidationIssue],
) -> bool | None:
    if not value:
        issues.append(_issue(required_code, "error", f"{label} VAT ID is required."))
        return None
    if not vat.is_valid(value):
        issues.append(
            _issue(invalid_code, "error", f"{label} VAT ID has an invalid EU format or checksum.")
        )
        return False
    return True


def _totals_reconcile(
    subtotal: Decimal | None, tax: Decimal | None, total: Decimal | None
) -> bool | None:
    if subtotal is None or tax is None or total is None:
        return None
    return abs((subtotal + tax) - total) <= TOTAL_TOLERANCE


def _add_confidence_warning(
    average_confidence: float | None, issues: list[ValidationIssue]
) -> None:
    if average_confidence is not None and average_confidence < MINIMUM_PRIMARY_CONFIDENCE:
        issues.append(
            _issue(
                "primary_confidence_low",
                "warning",
                f"Primary extraction confidence is below {MINIMUM_PRIMARY_CONFIDENCE:.2f}.",
            )
        )


def validate_invoice(
    extraction: InvoiceExtraction, expected_customer_vat_id: str
) -> ValidationReport:
    """Apply the non-storage Northstar invoice rules without network calls."""
    issues: list[ValidationIssue] = []
    vendor_name = _value(extraction.vendor_name)
    customer_name = _value(extraction.customer_name)
    vendor_vat = _value(extraction.vendor_tax_id)
    customer_vat = _value(extraction.customer_tax_id)
    invoice_id = _value(extraction.invoice_id)
    invoice_date = _value(extraction.invoice_date)
    due_date = _value(extraction.due_date)

    if not vendor_name:
        issues.append(_issue("vendor_name_required", "error", "Supplier name is required."))
    if not customer_name:
        issues.append(_issue("customer_name_required", "error", "Customer name is required."))

    supplier_vat_valid = _validate_vat(
        vendor_vat if isinstance(vendor_vat, str) else None,
        "vendor_vat_id_required",
        "vendor_vat_id_invalid",
        "Supplier",
        issues,
    )
    customer_vat_valid = _validate_vat(
        customer_vat if isinstance(customer_vat, str) else None,
        "customer_vat_id_required",
        "customer_vat_id_invalid",
        "Customer",
        issues,
    )
    if (
        isinstance(customer_vat, str)
        and vat.is_valid(customer_vat)
        and vat.compact(customer_vat) != vat.compact(expected_customer_vat_id)
    ):
        issues.append(
            _issue(
                "customer_vat_id_mismatch",
                "error",
                "Customer VAT ID does not match Northstar's configured VAT ID.",
            )
        )

    if not invoice_id:
        issues.append(_issue("invoice_number_required", "error", "Invoice number is required."))
    if not invoice_date:
        issues.append(_issue("invoice_date_required", "error", "Invoice date is required."))
    if invoice_date and due_date and due_date < invoice_date:
        issues.append(
            _issue("invoice_date_order_invalid", "error", "Due date cannot precede invoice date.")
        )

    total = _amount(extraction.invoice_total)
    if total is None:
        issues.append(_issue("invoice_total_required", "error", "Invoice total is required."))
    elif total <= 0:
        issues.append(
            _issue("invoice_total_non_positive", "error", "Invoice total must be positive.")
        )
    if not _currency(extraction.invoice_total) and not _currency(extraction.subtotal):
        issues.append(_issue("currency_required", "error", "Invoice currency is required."))

    totals_reconcile = _totals_reconcile(
        _amount(extraction.subtotal), _amount(extraction.total_tax), total
    )
    if totals_reconcile is False:
        issues.append(
            _issue(
                "invoice_total_mismatch",
                "error",
                "Subtotal plus VAT does not equal the invoice total within EUR 0.01.",
            )
        )
    if not _value(extraction.purchase_order):
        issues.append(_issue("purchase_order_missing", "warning", "Purchase order is missing."))
    _add_confidence_warning(extraction.average_confidence, issues)

    return ValidationReport(
        supplier_vat_valid=supplier_vat_valid,
        customer_vat_valid=customer_vat_valid,
        totals_reconcile=totals_reconcile,
        issues=issues,
    )


def validate_receipt(extraction: ReceiptExtraction) -> ValidationReport:
    """Apply the non-storage Northstar receipt rules without network calls."""
    issues: list[ValidationIssue] = []
    if not _value(extraction.merchant_name):
        issues.append(_issue("merchant_name_required", "error", "Merchant name is required."))
    if not _value(extraction.transaction_date):
        issues.append(_issue("transaction_date_required", "error", "Transaction date is required."))

    total = _amount(extraction.total)
    if total is None:
        issues.append(_issue("receipt_total_required", "error", "Receipt total is required."))
    elif total <= 0:
        issues.append(
            _issue("receipt_total_non_positive", "error", "Receipt total must be positive.")
        )
    if not _currency(extraction.total) and not _currency(extraction.subtotal):
        issues.append(_issue("currency_required", "error", "Receipt currency is required."))
    if _amount(extraction.total_tax) is None:
        issues.append(_issue("total_tax_required", "error", "Receipt VAT total is required."))

    totals_reconcile = _totals_reconcile(
        _amount(extraction.subtotal), _amount(extraction.total_tax), total
    )
    if totals_reconcile is False:
        issues.append(
            _issue(
                "receipt_total_mismatch",
                "error",
                "Subtotal plus VAT does not equal the receipt total within EUR 0.01.",
            )
        )
    _add_confidence_warning(extraction.average_confidence, issues)
    return ValidationReport(totals_reconcile=totals_reconcile, issues=issues)
