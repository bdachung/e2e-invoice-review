"""Map Azure Document Intelligence receipt results into Pydantic schemas."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.schemas.common import (
    ExtractedString,
    TaxDetail,
    parse_address_field,
    parse_array_field,
    parse_currency_field,
    parse_date_field,
    parse_number_field,
    parse_object_fields,
    parse_string_field,
    parse_time_field,
)
from app.schemas.receipt.model import ReceiptExtraction, ReceiptLineItem


def _map_tax_details(fields: dict[str, Any]) -> list[TaxDetail]:
    tax_details: list[TaxDetail] = []
    for entry in parse_array_field(fields.get("TaxDetails")):
        value_object = parse_object_fields(entry.get("valueObject"))
        tax_details.append(
            TaxDetail(
                amount=parse_currency_field(value_object.get("Amount")),
                rate=parse_string_field(value_object.get("Rate")),
            )
        )
    return tax_details


def _map_receipt_items(fields: dict[str, Any]) -> list[ReceiptLineItem]:
    items: list[ReceiptLineItem] = []
    for entry in parse_array_field(fields.get("Items")):
        value_object = parse_object_fields(entry.get("valueObject"))
        items.append(
            ReceiptLineItem(
                description=parse_string_field(value_object.get("Description")),
                quantity=parse_number_field(value_object.get("Quantity")),
                price=parse_currency_field(value_object.get("Price")),
                total_price=parse_currency_field(value_object.get("TotalPrice")),
                product_code=parse_string_field(value_object.get("ProductCode")),
                quantity_unit=parse_string_field(value_object.get("QuantityUnit")),
                date=parse_date_field(value_object.get("Date")),
                category=parse_string_field(value_object.get("Category")),
            )
        )
    return items


def _map_merchant_aliases(fields: dict[str, Any]) -> list[ExtractedString]:
    aliases: list[ExtractedString] = []
    for entry in parse_array_field(fields.get("MerchantAliases")):
        alias = parse_string_field(entry)
        if alias:
            aliases.append(alias)
    return aliases


def map_receipt_document(document: dict[str, Any]) -> ReceiptExtraction:
    fields = document.get("fields") or {}
    return ReceiptExtraction(
        model_id=document.get("docType") or document.get("documentType"),
        receipt_type=parse_string_field(fields.get("ReceiptType")),
        merchant_name=parse_string_field(fields.get("MerchantName")),
        merchant_phone_number=parse_string_field(fields.get("MerchantPhoneNumber")),
        merchant_address=parse_address_field(fields.get("MerchantAddress")),
        merchant_aliases=_map_merchant_aliases(fields),
        transaction_date=parse_date_field(fields.get("TransactionDate")),
        transaction_time=parse_time_field(fields.get("TransactionTime")),
        arrival_date=parse_date_field(fields.get("ArrivalDate")),
        departure_date=parse_date_field(fields.get("DepartureDate")),
        subtotal=parse_currency_field(fields.get("Subtotal")),
        total_tax=parse_currency_field(fields.get("TotalTax")),
        tip=parse_currency_field(fields.get("Tip")),
        total=parse_currency_field(fields.get("Total")),
        items=_map_receipt_items(fields),
        tax_details=_map_tax_details(fields),
    )


def map_receipt_result(result_dict: dict[str, Any]) -> ReceiptExtraction:
    documents = result_dict.get("documents") or []
    if not documents:
        return ReceiptExtraction(model_id=result_dict.get("modelId"))
    extraction = map_receipt_document(documents[0])
    if result_dict.get("modelId"):
        return extraction.model_copy(update={"model_id": result_dict["modelId"]})
    return extraction


def _format_money(amount: Decimal | None) -> str | None:
    return f"{amount:.2f}" if amount is not None else None


def receipt_to_manifest_view(extraction: ReceiptExtraction) -> dict[str, str | None]:
    currency = extraction.total or extraction.subtotal
    return {
        "document_type": extraction.document_type,
        "vendor_name": extraction.merchant_name.value if extraction.merchant_name else None,
        "vendor_vat_id": None,
        "customer_name": None,
        "customer_vat_id": None,
        "invoice_number": None,
        "invoice_date": (
            extraction.transaction_date.value.isoformat()
            if extraction.transaction_date and extraction.transaction_date.value
            else None
        ),
        "due_date": None,
        "purchase_order": None,
        "currency": currency.currency_code if currency else None,
        "subtotal": _format_money(extraction.subtotal.amount if extraction.subtotal else None),
        "total_tax": _format_money(extraction.total_tax.amount if extraction.total_tax else None),
        "invoice_total": _format_money(extraction.total.amount if extraction.total else None),
    }
