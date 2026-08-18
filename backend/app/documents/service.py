"""Orchestrate storage, combined review, validation, and reviewer actions."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.accounting.catalog import get_gl_account
from app.config import AppConfig, get_settings
from app.correction_email.eligibility import supplier_fixable_issues
from app.correction_email.schemas import CorrectionEmailDraft
from app.documents.models import DocumentRecord
from app.documents.progress import progress_broker
from app.documents.repository import DocumentRepository
from app.documents.schemas import DocumentCorrectionRequest
from app.pipeline import FinancialDocumentPipeline
from app.pipeline.chain import PipelineProgressCallback
from app.pipeline.models import FinancialDocumentReviewData
from app.providers.azure_openai import build_azure_openai_client
from app.providers.azure_openai_correction_email import AzureOpenAICorrectionEmailDrafter
from app.providers.azure_openai_document_review import AzureOpenAIDocumentReviewer
from app.validation.financial_documents import validate_invoice, validate_receipt
from app.validation.models import CompanyIdentity, ValidationReport


class DocumentNotFoundError(RuntimeError):
    pass


class DocumentContentError(RuntimeError):
    pass


class DocumentConflictError(RuntimeError):
    pass


class DocumentService:
    def __init__(self, repository: DocumentRepository, config: AppConfig) -> None:
        self._repository, self._config = repository, config
        self._identity = CompanyIdentity(
            legal_name=config.expected_customer_name, vat_id=config.expected_customer_vat_id
        )

    def create(
        self, original_filename: str, content_type: str, content: bytes, suffix: str
    ) -> DocumentRecord:
        record_id = str(uuid4())
        stored_filename = f"{record_id}{suffix}"
        path = self._config.upload_dir / stored_filename
        self._config.upload_dir.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        record = self._repository.create_processing(
            record_id, original_filename, stored_filename, content_type
        )
        progress_broker.publish(record_id, "started", "upload", "Document uploaded.")
        return record

    def process_existing(
        self, record_id: str, progress_callback: PipelineProgressCallback | None = None
    ) -> DocumentRecord:
        record = self.get(record_id)
        path = self._config.upload_dir / Path(record.stored_filename).name
        settings = get_settings()

        def forward(step: str, status: str, message: str | None) -> None:
            progress_broker.publish(record_id, status, step, message)
            if progress_callback:
                progress_callback(step, status, message)

        try:
            reviewer = None
            if settings.azure_openai_endpoint and settings.azure_openai_deployment:
                reviewer = AzureOpenAIDocumentReviewer(
                    build_azure_openai_client(settings), settings.azure_openai_deployment
                )
            pipeline = FinancialDocumentPipeline.from_settings(
                settings,
                self._identity,
                duplicate_check=lambda supplier, number: self._repository.duplicate_exists(
                    supplier, number, exclude_id=record_id
                ),
                minimum_confidence=self._config.min_field_confidence,
                progress_callback=forward,
                document_reviewer=reviewer,
                content_type=record.content_type,
            )
            result = pipeline.process(path)
        except Exception as error:
            message = str(error) or error.__class__.__name__
            progress_broker.publish(record_id, "failed", message=message)
            return self._repository.save_failure(record_id, message)
        progress_broker.publish(record_id, "completed", message="Document processing completed.")
        return self._repository.save_result(
            record_id,
            status=result.validation.status.value,
            classification=result.classification.model_dump(mode="json"),
            extraction=result.extraction.model_dump(mode="json"),
            review_data=result.review_data.model_dump(mode="json"),
            document_review=result.document_review.model_dump(mode="json"),
            validation=result.validation.model_dump(mode="json"),
            metadata=result.metadata.model_dump(mode="json"),
            issues=[issue.model_dump(mode="json") for issue in result.validation.issues],
        )

    def get(self, record_id: str) -> DocumentRecord:
        record = self._repository.get(record_id)
        if record is None:
            raise DocumentNotFoundError("Document not found.")
        return record

    def file_path(self, record_id: str) -> Path:
        record = self.get(record_id)
        path = self._config.upload_dir / Path(record.stored_filename).name
        if not path.is_file():
            raise DocumentNotFoundError("Stored document file was not found.")
        return path

    def revalidate(self, record_id: str, corrections: DocumentCorrectionRequest) -> DocumentRecord:
        record = self.get(record_id)
        self._ensure_editable(record)
        if record.review_data is None:
            raise DocumentConflictError("The document has no completed review data.")
        review_data = FinancialDocumentReviewData.model_validate(record.review_data)
        changes = corrections.model_dump(exclude_unset=True)
        changed_fields = [
            field for field, value in changes.items() if value != getattr(review_data, field)
        ]
        updated = review_data.model_copy(update=changes).mark_human_supplied(*changed_fields)
        report = self._validate(updated, record_id)
        return self._repository.save_review(
            record_id,
            review_data=updated.model_dump(mode="json"),
            validation=report.model_dump(mode="json"),
            issues=[issue.model_dump(mode="json") for issue in report.issues],
            status=report.status.value,
        )

    def select_gl_account(self, record_id: str, account_code: str) -> DocumentRecord:
        record = self.get(record_id)
        self._ensure_editable(record)
        if get_gl_account(account_code) is None:
            raise ValueError(f"Unknown GL account: {account_code}")
        return self._repository.select_gl_account(record_id, account_code)

    def decide(self, record_id: str, decision: str, reason: str | None = None) -> DocumentRecord:
        record = self.get(record_id)
        self._ensure_editable(record)
        if record.status in {"processing", "failed"}:
            raise DocumentConflictError("Only a completed review can receive a decision.")
        if decision == "approved":
            report = ValidationReport.model_validate(record.validation or {})
            if report.has_errors:
                raise DocumentConflictError("Resolve all validation errors before approval.")
            if not report.can_approve(record.selected_gl_account_code):
                raise DocumentConflictError("Select a valid GL account before approval.")
        return self._repository.set_status(record_id, decision, reason=reason)

    def draft_correction_email(
        self, record_id: str, reason: str | None = None
    ) -> CorrectionEmailDraft:
        record = self.get(record_id)
        if record.status in {"processing", "failed"} or record.review_data is None:
            raise DocumentConflictError("Only a completed review can draft a correction email.")
        data = FinancialDocumentReviewData.model_validate(record.review_data)
        issues = [self._issue(value) for value in record.issues]
        eligible = supplier_fixable_issues(issues)
        if not eligible:
            raise DocumentConflictError("This review has no supplier-fixable business issues.")
        settings = get_settings()
        if not settings.azure_openai_endpoint or not settings.azure_openai_deployment:
            raise DocumentConflictError("Correction-email drafting is not configured.")
        drafter = AzureOpenAICorrectionEmailDrafter(
            build_azure_openai_client(settings), settings.azure_openai_deployment
        )
        return drafter.draft(data, eligible, reason=reason)

    def delete(self, record_id: str) -> None:
        path = self.file_path(record_id)
        self._repository.delete(record_id)
        path.unlink(missing_ok=True)

    def _validate(self, data: FinancialDocumentReviewData, record_id: str) -> ValidationReport:
        def duplicate(supplier, number):
            return self._repository.duplicate_exists(supplier, number, exclude_id=record_id)

        if data.document_type == "invoice":
            return validate_invoice(
                data, self._identity, duplicate, self._config.min_field_confidence
            )
        return validate_receipt(data, self._config.min_field_confidence)

    @staticmethod
    def _issue(value: dict[str, object]):
        from app.validation.models import ValidationIssue

        return ValidationIssue.model_validate(value)

    @staticmethod
    def _ensure_editable(record: DocumentRecord) -> None:
        if record.status in {"approved", "rejected"}:
            raise DocumentConflictError("A decided document cannot be changed.")
