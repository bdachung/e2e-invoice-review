"""Thin adapter that exposes existing finance-application capabilities to MCP.

``FinanceAdapter`` is the only bridge between the MCP tool layer and the
existing Northstar finance application. It owns no finance policy: it loads
documents, delegates processing and review actions to ``DocumentService``, and
translates application results and errors into the MCP-facing result models.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date
from typing import TypeVar

from app.accounting.catalog import get_gl_account
from app.config import AppConfig, get_app_config, get_settings
from app.database import build_database
from app.documents.models import DocumentRecord
from app.documents.repository import DocumentRepository
from app.documents.service import (
    DocumentConflictError,
    DocumentNotFoundError,
    DocumentService,
)
from app.pipeline.chain import PipelineProgressCallback
from app.pipeline.models import FinancialDocumentReviewData
from app.validation.models import ValidationReport
from mcp_server.schemas.results import (
    AllowedAction,
    CheckOutcome,
    GlSuggestion,
    ReviewFields,
    ReviewResult,
    ValidationSummary,
)

T = TypeVar("T")
SyncCall = Callable[[DocumentService], T]


class McpError(RuntimeError):
    """Structured error returned to the MCP client as a tool result."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _iso_date(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _tri_state(value: bool | None) -> CheckOutcome:
    if value is None:
        return "not_checked"
    return "pass" if value else "fail"


class FinanceAdapter:
    """Bridge between MCP tools and the existing finance application."""

    def __init__(self, config: AppConfig | None = None) -> None:
        self._config = config or get_app_config(get_settings())
        _, self._session_factory = build_database(self._config.database_url)

    # -- document processing -------------------------------------------------

    async def process_document(
        self,
        document_ref: str,
        progress_callback: PipelineProgressCallback | None = None,
    ) -> dict[str, object]:
        """Run or reuse the existing finance review for a document reference."""
        return await asyncio.to_thread(
            self._process_document_sync, document_ref, progress_callback
        )

    def _process_document_sync(
        self, document_ref: str, progress_callback: PipelineProgressCallback | None
    ) -> dict[str, object]:
        def run(service: DocumentService) -> DocumentRecord:
            try:
                record = service.get(document_ref)
            except DocumentNotFoundError as error:
                raise McpError("DOCUMENT_NOT_FOUND", str(error)) from error
            if record.status == "failed":
                raise McpError(
                    "DOCUMENT_PROCESSING_FAILED",
                    record.error_message or "The document could not be processed.",
                )
            if record.status == "processing":
                record = service.process_existing(
                    document_ref, progress_callback=progress_callback
                )
                if record.status == "failed":
                    raise McpError(
                        "DOCUMENT_PROCESSING_FAILED",
                        record.error_message or "The document could not be processed.",
                    )
            return record

        record = self._call_service(run)
        return self._to_review_result(record, document_ref).model_dump(mode="json")

    # -- human-gated review actions ------------------------------------------

    async def approve_document(self, review_id: str, reviewer_id: str) -> dict[str, object]:
        """Approve an existing review after an explicit human action."""
        return await asyncio.to_thread(self._approve_document_sync, review_id, reviewer_id)

    def _approve_document_sync(self, review_id: str, reviewer_id: str) -> dict[str, object]:
        self._authorize_reviewer(reviewer_id)
        record = self._call_service(
            lambda service: self._guarded(service.decide, review_id, "approved")
        )
        return {"review_id": review_id, "status": record.status, "reviewer_id": reviewer_id}

    async def reject_document(
        self, review_id: str, reviewer_id: str, reason: str
    ) -> dict[str, object]:
        """Reject an existing review with a reason after an explicit human action."""
        return await asyncio.to_thread(self._reject_document_sync, review_id, reviewer_id, reason)

    def _reject_document_sync(
        self, review_id: str, reviewer_id: str, reason: str
    ) -> dict[str, object]:
        self._authorize_reviewer(reviewer_id)
        record = self._call_service(
            lambda service: self._guarded(service.decide, review_id, "rejected", reason)
        )
        return {"review_id": review_id, "status": record.status, "reason": reason}

    # -- supplier-correction email -------------------------------------------

    async def draft_supplier_email(
        self, review_id: str, reason: str | None = None
    ) -> dict[str, object]:
        """Draft, but never send, a supplier-correction email."""
        return await asyncio.to_thread(self._draft_supplier_email_sync, review_id, reason)

    def _draft_supplier_email_sync(
        self, review_id: str, reason: str | None
    ) -> dict[str, object]:
        draft = self._call_service(
            lambda service: self._guarded(service.draft_correction_email, review_id, reason)
        )
        return {
            "review_id": review_id,
            "recipient_name": draft.recipient_name,
            "subject": draft.subject,
            "body": draft.body,
            "reason": reason,
        }

    # -- internal helpers -----------------------------------------------------

    def _call_service(self, fn: SyncCall[T]) -> T:
        session = self._session_factory()
        try:
            service = DocumentService(DocumentRepository(session), self._config)
            return fn(service)
        finally:
            session.close()

    @staticmethod
    def _guarded(fn: Callable[..., T], *args: object) -> T:
        try:
            return fn(*args)
        except DocumentNotFoundError as error:
            raise McpError("DOCUMENT_NOT_FOUND", str(error)) from error
        except DocumentConflictError as error:
            raise McpError("INVALID_REVIEW_STATE", str(error)) from error

    def _authorize_reviewer(self, reviewer_id: str) -> None:
        if not reviewer_id or reviewer_id not in self._config.mcp_reviewer_ids:
            raise McpError(
                "UNKNOWN_REVIEWER",
                f"Reviewer {reviewer_id!r} is not authorized for human review actions.",
            )

    def _to_review_result(self, record: DocumentRecord, document_ref: str) -> ReviewResult:
        data = FinancialDocumentReviewData.model_validate(record.review_data or {})
        report = ValidationReport.model_validate(record.validation or {})
        metadata = record.metadata_json or {}
        raw_suggestion = metadata.get("gl_suggestion")
        suggestion = raw_suggestion if isinstance(raw_suggestion, dict) else {}
        code = suggestion.get("account_code")
        account = get_gl_account(code) if isinstance(code, str) else None
        return ReviewResult(
            review_id=record.id,
            document_ref=document_ref,
            document_type=data.document_type,
            status=record.status,
            fields=self._review_fields(data),
            validation=self._validation_summary(data, report),
            gl_suggestion=(
                GlSuggestion(code=account.code.value, name=account.name) if account else None
            ),
            conclusion=self._conclusion(record.status, report),
            allowed_actions=self._allowed_actions(record.status),
            error_message=record.error_message,
        )

    @staticmethod
    def _review_fields(data: FinancialDocumentReviewData) -> ReviewFields:
        return ReviewFields(
            document_type=data.document_type,
            expense_category=data.expense_category,
            supplier_name=data.supplier_name,
            supplier_vat_id=data.supplier_vat_id,
            customer_name=data.customer_name,
            customer_vat_id=data.customer_vat_id,
            document_number=data.document_number,
            document_date=_iso_date(data.document_date),
            due_date=_iso_date(data.due_date),
            purchase_order=data.purchase_order,
            currency=data.currency,
            subtotal=data.subtotal,
            total_tax=data.total_tax,
            total=data.total,
            amount_due=data.amount_due,
        )

    @staticmethod
    def _validation_summary(
        data: FinancialDocumentReviewData, report: ValidationReport
    ) -> ValidationSummary:
        issue_codes = {issue.code for issue in report.issues}
        if data.document_type == "receipt":
            po_match = "not_required"
        elif data.purchase_order:
            po_match = "pass"
        else:
            po_match = "not_available"
        return ValidationSummary(
            vat_format=_tri_state(report.supplier_vat_valid),
            totals=_tri_state(report.totals_reconcile),
            duplicate="fail" if "duplicate_invoice" in issue_codes else "pass",
            po_match=po_match,
        )

    @staticmethod
    def _conclusion(status: str, report: ValidationReport) -> str:
        if status == "needs_review":
            first_error = next(
                (issue.message for issue in report.issues if issue.severity == "error"), None
            )
            return (
                f"The document requires review: {first_error}"
                if first_error
                else "The document requires review."
            )
        if status == "ready":
            first_warning = next(
                (issue.message for issue in report.issues if issue.severity == "warning"), None
            )
            return (
                f"The document is ready but has warnings: {first_warning}"
                if first_warning
                else "The document passed all validations."
            )
        if status == "approved":
            return "The document is approved."
        if status == "rejected":
            return "The document is rejected."
        if status == "processing":
            return "The document is still being processed."
        return "The document could not be processed."

    @staticmethod
    def _allowed_actions(status: str) -> list[AllowedAction]:
        if status in {"ready", "needs_review"}:
            return ["approve", "reject", "draft_email"]
        if status == "rejected":
            return ["draft_email"]
        return []
