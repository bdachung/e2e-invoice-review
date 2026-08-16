"""SQLite model for one locally stored financial document."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class DocumentRecord(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index(
            "ix_documents_duplicate_key", "normalized_supplier_name", "normalized_document_number"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), index=True)
    normalized_supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    normalized_document_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    classification: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    extraction: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    document_review: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    validation: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    review_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    selected_gl_account_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
