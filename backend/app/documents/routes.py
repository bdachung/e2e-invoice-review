"""HTTP routes for upload, review, correction, decision, and correction drafting."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.accounting.catalog import get_gl_account
from app.config import AppConfig
from app.correction_email.eligibility import supplier_fixable_issues
from app.correction_email.schemas import CorrectionEmailDraft
from app.document_review.schemas import DocumentReview
from app.documents.models import DocumentRecord
from app.documents.repository import DocumentRepository
from app.documents.schemas import (
    AccountingCoding,
    AccountingSelectionRequest,
    DecisionRequest,
    DocumentCorrectionRequest,
    DocumentResponse,
)
from app.documents.service import DocumentConflictError, DocumentNotFoundError, DocumentService
from app.pipeline.document_classification import DocumentClassification
from app.pipeline.models import FinancialDocumentReviewData
from app.schemas.invoice import InvoiceExtraction
from app.schemas.receipt import ReceiptExtraction
from app.validation.models import ValidationIssue, ValidationReport

router = APIRouter(prefix="/api/documents", tags=["documents"])
ALLOWED_CONTENT_TYPES = {"application/pdf": ".pdf", "image/jpeg": ".jpg", "image/png": ".png"}


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def get_repository(session: Annotated[Session, Depends(get_session)]) -> DocumentRepository:
    return DocumentRepository(session)


def get_service(
    request: Request, repository: Annotated[DocumentRepository, Depends(get_repository)]
) -> DocumentService:
    return DocumentService(repository, request.app.state.config)


def process_document_in_background(
    session_factory: object, config: AppConfig, record_id: str
) -> None:
    with session_factory() as session:
        DocumentService(DocumentRepository(session), config).process_existing(record_id)  # type: ignore[operator]


def to_response(record: DocumentRecord) -> DocumentResponse:
    metadata = record.metadata_json or {}
    suggestion = metadata.get("gl_suggestion") if isinstance(metadata, dict) else None
    selected = get_gl_account(record.selected_gl_account_code or "")
    issues = [ValidationIssue.model_validate(value) for value in record.issues]
    return DocumentResponse(
        id=record.id,
        original_filename=record.original_filename,
        content_type=record.content_type,
        status=record.status,
        classification=DocumentClassification.model_validate(record.classification)
        if record.classification
        else None,
        extraction=InvoiceExtraction.model_validate(record.extraction)
        if record.extraction and record.extraction.get("document_type") == "invoice"
        else ReceiptExtraction.model_validate(record.extraction)
        if record.extraction
        else None,
        review_data=FinancialDocumentReviewData.model_validate(record.review_data)
        if record.review_data
        else None,
        document_review=DocumentReview.model_validate(record.document_review)
        if record.document_review
        else None,
        validation=ValidationReport.model_validate(record.validation)
        if record.validation
        else None,
        metadata=metadata,
        accounting=AccountingCoding(
            suggestion=suggestion,
            selected_account=selected,
            overridden=bool(
                selected and suggestion and selected.code.value != suggestion.get("account_code")
            ),
        ),
        issues=issues,
        supplier_action_required=bool(supplier_fixable_issues(issues)),
        error_message=record.error_message,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    service: Annotated[DocumentService, Depends(get_service)],
    auto_process: Annotated[bool, Query()] = True,
) -> DocumentResponse:
    config: AppConfig = request.app.state.config
    content_type = file.content_type or "application/octet-stream"
    suffix = ALLOWED_CONTENT_TYPES.get(content_type)
    if suffix is None:
        raise HTTPException(status_code=415, detail="Use a PDF, JPEG, or PNG document.")
    payload = file.file.read(config.max_upload_bytes + 1)
    if not payload:
        raise HTTPException(status_code=422, detail="Uploaded document is empty.")
    if len(payload) > config.max_upload_bytes:
        raise HTTPException(status_code=413, detail="A document may not exceed 4 MB.")
    record = service.create(
        Path(file.filename or "document").name[:255], content_type, payload, suffix
    )
    if auto_process:
        background_tasks.add_task(
            process_document_in_background, request.app.state.session_factory, config, record.id
        )
    return to_response(record)


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    repository: Annotated[DocumentRepository, Depends(get_repository)],
) -> list[DocumentResponse]:
    return [to_response(record) for record in repository.list()]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str, service: Annotated[DocumentService, Depends(get_service)]
) -> DocumentResponse:
    try:
        return to_response(service.get(document_id))
    except DocumentNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/{document_id}/file")
def get_document_file(
    document_id: str, service: Annotated[DocumentService, Depends(get_service)]
) -> FileResponse:
    try:
        record = service.get(document_id)
        return FileResponse(
            service.file_path(document_id),
            media_type=record.content_type,
            headers={"Content-Disposition": "inline"},
        )
    except DocumentNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.put("/{document_id}", response_model=DocumentResponse)
def correct_document(
    document_id: str,
    corrections: DocumentCorrectionRequest,
    service: Annotated[DocumentService, Depends(get_service)],
) -> DocumentResponse:
    try:
        return to_response(service.revalidate(document_id, corrections))
    except DocumentNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except DocumentConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.put("/{document_id}/accounting", response_model=DocumentResponse)
def select_gl_account(
    document_id: str,
    body: AccountingSelectionRequest,
    service: Annotated[DocumentService, Depends(get_service)],
) -> DocumentResponse:
    try:
        return to_response(service.select_gl_account(document_id, body.gl_account_code))
    except DocumentNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except DocumentConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/{document_id}/decision", response_model=DocumentResponse)
def decide_document(
    document_id: str,
    body: DecisionRequest,
    service: Annotated[DocumentService, Depends(get_service)],
) -> DocumentResponse:
    try:
        return to_response(service.decide(document_id, body.decision))
    except DocumentNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except DocumentConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/{document_id}/correction-email", response_model=CorrectionEmailDraft)
def draft_correction_email(
    document_id: str, service: Annotated[DocumentService, Depends(get_service)]
) -> CorrectionEmailDraft:
    try:
        return service.draft_correction_email(document_id)
    except DocumentNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except DocumentConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str, service: Annotated[DocumentService, Depends(get_service)]
) -> Response:
    try:
        service.delete(document_id)
    except DocumentNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
