"""Provider-independent models returned by deterministic validation."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from app.accounting import GeneralLedgerAccountCode


class CompanyIdentity(BaseModel):
    """Configured legal identity that invoices must name as their customer."""

    legal_name: str
    vat_id: str


class ValidationStatus(StrEnum):
    NEEDS_REVIEW = "needs_review"
    READY = "ready"


class ValidationIssue(BaseModel):
    """One deterministic policy finding for a financial document."""

    code: str
    field: str | None = None
    severity: Literal["error", "warning"]
    message: str


class ValidationReport(BaseModel):
    """Offline financial-document validation outcome."""

    supplier_vat_valid: bool | None = None
    customer_vat_valid: bool | None = None
    totals_reconcile: bool | None = None
    issues: list[ValidationIssue] = []
    status: ValidationStatus

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    def can_approve(self, selected_account_code: str | None) -> bool:
        """Require a clean validation report and an account from the fixed catalog."""
        if self.has_errors or selected_account_code is None:
            return False
        return selected_account_code in {account.value for account in GeneralLedgerAccountCode}
