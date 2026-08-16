"""Pure determination of the validation findings a supplier can address."""

from app.validation.models import ValidationIssue

# Duplicate detection, low-confidence extraction, and account selection are
# Northstar-internal review concerns. The remaining codes identify facts Maya
# can reasonably ask the supplier or merchant to correct or clarify.
SUPPLIER_FIXABLE_CODES = {
    "supplier_name_required",
    "supplier_vat_id_required",
    "supplier_vat_id_invalid",
    "customer_name_mismatch",
    "customer_vat_id_mismatch",
    "document_number_required",
    "document_date_required",
    "currency_required",
    "total_required",
    "total_tax_required",
    "invoice_total_non_positive",
    "receipt_total_non_positive",
    "invoice_date_order_invalid",
    "invoice_total_mismatch",
    "receipt_total_mismatch",
}


def supplier_fixable_issues(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    """Return only findings appropriate to mention in an unsent supplier draft."""
    return [issue for issue in issues if issue.code in SUPPLIER_FIXABLE_CODES]
