"""Pure DI-primary reconciliation of normalized document values."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal, InvalidOperation

from app.document_review.schemas import DocumentReview, FieldComparison, LlmDocumentExtraction
from app.pipeline.models import FieldProvenance, FinancialDocumentReviewData

FIELDS = (
    ("supplier_name", "Supplier", "text"),
    ("supplier_vat_id", "Supplier VAT ID", "identifier"),
    ("customer_name", "Customer", "text"),
    ("customer_vat_id", "Customer VAT ID", "identifier"),
    ("document_number", "Document number", "identifier"),
    ("purchase_order", "Purchase order", "identifier"),
    ("document_date", "Document date", "date"),
    ("due_date", "Due date", "date"),
    ("currency", "Currency", "identifier"),
    ("subtotal", "Subtotal", "amount"),
    ("total_tax", "Tax", "amount"),
    ("total", "Total", "amount"),
    ("amount_due", "Amount due", "amount"),
)


def _shown(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value).strip() or None


def _text(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _identifier(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return value.strip().casefold()


def _amount(value: str) -> str:
    try:
        return str(Decimal(value.replace(",", ".")).normalize())
    except InvalidOperation:
        return value.strip().casefold()


NORMALIZERS: dict[str, Callable[[str], str]] = {
    "text": _text,
    "identifier": _identifier,
    "date": _date,
    "amount": _amount,
}


def merge_document_extractions(
    primary: FinancialDocumentReviewData, extraction: LlmDocumentExtraction
) -> tuple[FinancialDocumentReviewData, DocumentReview]:
    """Expose comparison evidence and fill only primary fields that are absent."""
    comparisons: list[FieldComparison] = []
    values = primary.model_dump()
    provenance = dict(primary.field_provenance)
    fallback_fields: list[FieldComparison] = []
    for field, label, normalizer_name in FIELDS:
        primary_value = _shown(getattr(primary, field))
        llm_value = _shown(getattr(extraction, field))
        if primary_value is None and llm_value is None:
            status = "missing_in_both"
        elif primary_value is None:
            status = "missing_in_document_intelligence"
        elif llm_value is None:
            status = "missing_in_llm"
        else:
            status = (
                "match"
                if NORMALIZERS[normalizer_name](primary_value)
                == NORMALIZERS[normalizer_name](llm_value)
                else "different"
            )
        comparison = FieldComparison(
            field=field,
            label=label,
            status=status,
            document_intelligence_value=primary_value,
            llm_value=llm_value,
        )
        comparisons.append(comparison)
        if primary_value is not None or llm_value is None:
            continue
        parsed = _parse_value(field, llm_value)
        if parsed is not None:
            values[field] = parsed
            provenance[field] = FieldProvenance.LLM_FALLBACK
            fallback_fields.append(comparison)
    if not primary.line_items and extraction.line_items:
        values["line_items"] = extraction.line_items
        provenance["line_items"] = FieldProvenance.LLM_FALLBACK
    if primary.document_type == "receipt" and primary.expense_category is None:
        values["expense_category"] = extraction.expense_category
    values["field_provenance"] = provenance
    review = DocumentReview(
        extraction=extraction, comparisons=comparisons, fallback_fields=fallback_fields
    )
    return FinancialDocumentReviewData.model_validate(values), review


def _parse_value(field: str, value: str) -> object | None:
    if field in {"document_date", "due_date"}:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    if field in {"subtotal", "total_tax", "total", "amount_due"}:
        try:
            return Decimal(value.replace(",", "."))
        except InvalidOperation:
            return None
    return value.strip() or None
