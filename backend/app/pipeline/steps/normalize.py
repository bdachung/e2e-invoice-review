"""Normalize rich extraction models into review data for downstream processing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.document_review.schemas import ReviewLineItem
from app.pipeline.models import (
    FieldProvenance,
    FinancialDocumentProcessingState,
    FinancialDocumentReviewData,
)
from app.schemas.invoice import InvoiceExtraction


class NormalizeDocumentStep:
    def run(self, state: FinancialDocumentProcessingState) -> FinancialDocumentProcessingState:
        extraction = state.extraction
        if extraction is None:
            raise RuntimeError("Extraction must run before normalization.")
        if isinstance(extraction, InvoiceExtraction):
            state.review_data = FinancialDocumentReviewData(
                document_type="invoice",
                supplier_name=_string(extraction.vendor_name),
                supplier_vat_id=_string(extraction.vendor_tax_id),
                customer_name=_string(extraction.customer_name),
                customer_vat_id=_string(extraction.customer_tax_id),
                document_number=_string(extraction.invoice_id),
                document_date=_date(extraction.invoice_date),
                due_date=_date(extraction.due_date),
                purchase_order=_string(extraction.purchase_order),
                currency=_currency(extraction.invoice_total) or _currency(extraction.subtotal),
                subtotal=_money(extraction.subtotal),
                total_tax=_money(extraction.total_tax),
                total=_money(extraction.invoice_total),
                amount_due=_money(extraction.amount_due),
                line_items=[
                    ReviewLineItem(
                        description=_string(item.description),
                        quantity=_number(item.quantity),
                        unit_price=_money(item.unit_price),
                        amount=_money(item.amount),
                    )
                    for item in extraction.items
                ],
                field_confidence=_invoice_confidence(extraction),
                field_provenance=_di_provenance(),
            )
        else:
            state.review_data = FinancialDocumentReviewData(
                document_type="receipt",
                supplier_name=_string(extraction.merchant_name),
                document_date=_date(extraction.transaction_date),
                currency=_currency(extraction.total) or _currency(extraction.subtotal),
                subtotal=_money(extraction.subtotal),
                total_tax=_money(extraction.total_tax),
                total=_money(extraction.total),
                amount_due=_money(extraction.total),
                line_items=[
                    ReviewLineItem(
                        description=_string(item.description),
                        quantity=_number(item.quantity),
                        unit_price=_money(item.price),
                        amount=_money(item.total_price),
                    )
                    for item in extraction.items
                ],
                field_confidence={
                    "supplier_name": _confidence(extraction.merchant_name),
                    "document_date": _confidence(extraction.transaction_date),
                    "currency": _confidence(extraction.total) or _confidence(extraction.subtotal),
                    "total_tax": _confidence(extraction.total_tax),
                    "total": _confidence(extraction.total),
                },
                field_provenance=_di_provenance(),
            )
        return state


def _di_provenance() -> dict[str, FieldProvenance]:
    return {
        field: FieldProvenance.DOCUMENT_INTELLIGENCE
        for field in FinancialDocumentReviewData.model_fields
    }


def _invoice_confidence(extraction: InvoiceExtraction) -> dict[str, float | None]:
    return {
        "supplier_name": _confidence(extraction.vendor_name),
        "supplier_vat_id": _confidence(extraction.vendor_tax_id),
        "customer_name": _confidence(extraction.customer_name),
        "customer_vat_id": _confidence(extraction.customer_tax_id),
        "document_number": _confidence(extraction.invoice_id),
        "document_date": _confidence(extraction.invoice_date),
        "currency": _confidence(extraction.invoice_total) or _confidence(extraction.subtotal),
        "total": _confidence(extraction.invoice_total),
    }


def _string(field: object) -> str | None:
    return getattr(field, "value", None) if field else None


def _date(field: object) -> date | None:
    return getattr(field, "value", None) if field else None


def _money(field: object) -> Decimal | None:
    return getattr(field, "amount", None) if field else None


def _number(field: object) -> Decimal | None:
    return getattr(field, "value", None) if field else None


def _currency(field: object) -> str | None:
    return getattr(field, "currency_code", None) if field else None


def _confidence(field: object) -> float | None:
    return getattr(field, "confidence", None) if field else None
