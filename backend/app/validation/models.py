"""Provider-independent models returned by deterministic validation."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ValidationIssue(BaseModel):
    """One deterministic policy finding for a financial document."""

    code: str
    severity: Literal["error", "warning"]
    message: str


class ValidationReport(BaseModel):
    """Offline financial-document validation outcome."""

    supplier_vat_valid: bool | None = None
    customer_vat_valid: bool | None = None
    totals_reconcile: bool | None = None
    issues: list[ValidationIssue] = []

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)
