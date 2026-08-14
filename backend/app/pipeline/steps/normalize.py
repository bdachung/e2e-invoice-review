"""Normalize rich extraction models for downstream financial processing."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.pipeline.models import FinancialDocumentProcessingState, FinancialDocumentView
from app.schemas.invoice import InvoiceExtraction


class NormalizeDocumentStep:
    def run(self, state: FinancialDocumentProcessingState) -> FinancialDocumentProcessingState:
        extraction = state.extraction
        if extraction is None:
            raise RuntimeError("Extraction must run before normalization.")
        if isinstance(extraction, InvoiceExtraction):
            state.document = FinancialDocumentView(
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
                line_item_count=len(extraction.items),
            )
        else:
            state.document = FinancialDocumentView(
                document_type="receipt",
                supplier_name=_string(extraction.merchant_name),
                document_date=_date(extraction.transaction_date),
                currency=_currency(extraction.total) or _currency(extraction.subtotal),
                subtotal=_money(extraction.subtotal),
                total_tax=_money(extraction.total_tax),
                total=_money(extraction.total),
                line_item_count=len(extraction.items),
            )
        return state


def _string(field: object) -> str | None:
    return getattr(field, "value", None) if field else None


def _date(field: object) -> date | None:
    return getattr(field, "value", None) if field else None


def _money(field: object) -> Decimal | None:
    return getattr(field, "amount", None) if field else None


def _currency(field: object) -> str | None:
    return getattr(field, "currency_code", None) if field else None
