"""SQLite persistence for the document-review lifecycle."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.documents.models import DocumentRecord


def normalize_comparison(value: str) -> str:
    return " ".join(value.casefold().split())


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_processing(
        self, record_id: str, original_filename: str, stored_filename: str, content_type: str
    ) -> DocumentRecord:
        return self._commit(
            DocumentRecord(
                id=record_id,
                original_filename=original_filename,
                stored_filename=stored_filename,
                content_type=content_type,
                status="processing",
                issues=[],
            )
        )

    def get(self, record_id: str) -> DocumentRecord | None:
        return self._session.get(DocumentRecord, record_id)

    def list(self) -> list[DocumentRecord]:
        return list(
            self._session.scalars(select(DocumentRecord).order_by(DocumentRecord.created_at.desc()))
        )

    def duplicate_exists(
        self, supplier_name: str, document_number: str, *, exclude_id: str | None = None
    ) -> bool:
        query = select(DocumentRecord).where(
            DocumentRecord.normalized_supplier_name == normalize_comparison(supplier_name),
            DocumentRecord.normalized_document_number == normalize_comparison(document_number),
            DocumentRecord.status != "rejected",
        )
        if exclude_id:
            query = query.where(DocumentRecord.id != exclude_id)
        return self._session.scalar(query.limit(1)) is not None

    def save_failure(self, record_id: str, message: str) -> DocumentRecord:
        record = self._require(record_id)
        record.status = "failed"
        record.error_message = message
        return self._commit(record)

    def save_result(
        self,
        record_id: str,
        *,
        status: str,
        classification: dict[str, object],
        extraction: dict[str, object],
        document_review: dict[str, object],
        review_data: dict[str, object],
        validation: dict[str, object],
        metadata: dict[str, object],
        issues: list[dict[str, object]],
    ) -> DocumentRecord:
        record = self._require(record_id)
        record.status = status
        record.classification = classification
        record.extraction = extraction
        record.document_review = document_review
        record.review_data = review_data
        record.validation = validation
        record.metadata_json = metadata
        record.issues = issues
        record.error_message = None
        self._set_duplicate_key(record, review_data)
        return self._commit(record)

    def save_review(
        self,
        record_id: str,
        *,
        review_data: dict[str, object],
        validation: dict[str, object],
        issues: list[dict[str, object]],
        status: str,
    ) -> DocumentRecord:
        record = self._require(record_id)
        record.review_data = review_data
        record.validation = validation
        record.issues = issues
        record.status = status
        self._set_duplicate_key(record, review_data)
        return self._commit(record)

    def select_gl_account(self, record_id: str, account_code: str) -> DocumentRecord:
        record = self._require(record_id)
        record.selected_gl_account_code = account_code
        return self._commit(record)

    def set_status(self, record_id: str, status: str) -> DocumentRecord:
        record = self._require(record_id)
        record.status = status
        return self._commit(record)

    def delete(self, record_id: str) -> None:
        self._session.delete(self._require(record_id))
        self._session.commit()

    def _set_duplicate_key(self, record: DocumentRecord, data: dict[str, object]) -> None:
        supplier, number = data.get("supplier_name"), data.get("document_number")
        record.normalized_supplier_name = (
            normalize_comparison(supplier) if isinstance(supplier, str) else None
        )
        record.normalized_document_number = (
            normalize_comparison(number) if isinstance(number, str) else None
        )

    def _require(self, record_id: str) -> DocumentRecord:
        record = self.get(record_id)
        if record is None:
            raise KeyError(record_id)
        return record

    def _commit(self, record: DocumentRecord) -> DocumentRecord:
        self._session.add(record)
        self._session.commit()
        self._session.refresh(record)
        return record
