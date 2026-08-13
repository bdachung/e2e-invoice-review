"""Map Azure Document Intelligence invoice results into Pydantic schemas."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.schemas.common import (
    TaxDetail,
    parse_address_field,
    parse_array_field,
    parse_currency_field,
    parse_date_field,
    parse_number_field,
    parse_object_fields,
    parse_string_field,
)
from app.schemas.invoice.model import Installment, InvoiceExtraction, InvoiceLineItem, PaymentDetail


def _map_tax_details(fields: dict[str, Any]) -> list[TaxDetail]:
    return [
        TaxDetail(
            amount=parse_currency_field(
                parse_object_fields(entry.get("valueObject")).get("Amount")
            ),
            rate=parse_string_field(parse_object_fields(entry.get("valueObject")).get("Rate")),
        )
        for entry in parse_array_field(fields.get("TaxDetails"))
    ]


def _map_invoice_items(fields: dict[str, Any]) -> list[InvoiceLineItem]:
    items: list[InvoiceLineItem] = []
    for entry in parse_array_field(fields.get("Items")):
        value_object = parse_object_fields(entry.get("valueObject"))
        items.append(
            InvoiceLineItem(
                description=parse_string_field(value_object.get("Description")),
                quantity=parse_number_field(value_object.get("Quantity")),
                unit=parse_string_field(value_object.get("Unit")),
                unit_price=parse_currency_field(value_object.get("UnitPrice")),
                amount=parse_currency_field(value_object.get("Amount")),
                tax=parse_currency_field(value_object.get("Tax")),
                tax_rate=parse_string_field(value_object.get("TaxRate")),
                product_code=parse_string_field(value_object.get("ProductCode")),
                date=parse_date_field(value_object.get("Date")),
            )
        )
    return items


def _map_payment_details(fields: dict[str, Any]) -> list[PaymentDetail]:
    payment_details: list[PaymentDetail] = []
    for entry in parse_array_field(fields.get("PaymentDetails")):
        value_object = parse_object_fields(entry.get("valueObject"))
        payment_details.append(
            PaymentDetail(
                iban=parse_string_field(value_object.get("IBAN")),
                swift=parse_string_field(value_object.get("SWIFT")),
                bank_account_number=parse_string_field(value_object.get("BankAccountNumber")),
                bpay_biller_code=parse_string_field(value_object.get("BPayBillerCode")),
                bpay_reference=parse_string_field(value_object.get("BPayReference")),
            )
        )
    return payment_details


def _map_installments(fields: dict[str, Any]) -> list[Installment]:
    installments: list[Installment] = []
    for entry in parse_array_field(fields.get("PaidInFourInstallements")):
        value_object = parse_object_fields(entry.get("valueObject"))
        installments.append(
            Installment(
                amount=parse_currency_field(value_object.get("Amount")),
                due_date=parse_date_field(value_object.get("DueDate")),
            )
        )
    return installments


def map_invoice_document(document: dict[str, Any]) -> InvoiceExtraction:
    fields = document.get("fields") or {}
    return InvoiceExtraction(
        model_id=document.get("docType") or document.get("documentType"),
        vendor_name=parse_string_field(fields.get("VendorName")),
        vendor_address=parse_address_field(fields.get("VendorAddress")),
        vendor_address_recipient=parse_string_field(fields.get("VendorAddressRecipient")),
        vendor_tax_id=parse_string_field(fields.get("VendorTaxId")),
        customer_name=parse_string_field(fields.get("CustomerName")),
        customer_id=parse_string_field(fields.get("CustomerId")),
        customer_address=parse_address_field(fields.get("CustomerAddress")),
        customer_address_recipient=parse_string_field(fields.get("CustomerAddressRecipient")),
        customer_tax_id=parse_string_field(fields.get("CustomerTaxId")),
        billing_address=parse_address_field(fields.get("BillingAddress")),
        billing_address_recipient=parse_string_field(fields.get("BillingAddressRecipient")),
        shipping_address=parse_address_field(fields.get("ShippingAddress")),
        shipping_address_recipient=parse_string_field(fields.get("ShippingAddressRecipient")),
        service_address=parse_address_field(fields.get("ServiceAddress")),
        service_address_recipient=parse_string_field(fields.get("ServiceAddressRecipient")),
        remittance_address=parse_address_field(fields.get("RemittanceAddress")),
        remittance_address_recipient=parse_string_field(fields.get("RemittanceAddressRecipient")),
        invoice_id=parse_string_field(fields.get("InvoiceId")),
        invoice_date=parse_date_field(fields.get("InvoiceDate")),
        due_date=parse_date_field(fields.get("DueDate")),
        purchase_order=parse_string_field(fields.get("PurchaseOrder")),
        payment_term=parse_string_field(fields.get("PaymentTerm")),
        kvk_number=parse_string_field(fields.get("KVKNumber")),
        subtotal=parse_currency_field(fields.get("SubTotal")),
        total_discount=parse_currency_field(fields.get("TotalDiscount")),
        total_tax=parse_currency_field(fields.get("TotalTax")),
        invoice_total=parse_currency_field(fields.get("InvoiceTotal")),
        amount_due=parse_currency_field(fields.get("AmountDue")),
        previous_unpaid_balance=parse_currency_field(fields.get("PreviousUnpaidBalance")),
        service_start_date=parse_date_field(fields.get("ServiceStartDate")),
        service_end_date=parse_date_field(fields.get("ServiceEndDate")),
        items=_map_invoice_items(fields),
        tax_details=_map_tax_details(fields),
        payment_details=_map_payment_details(fields),
        paid_in_four_installments=_map_installments(fields),
    )


def map_invoice_result(result_dict: dict[str, Any]) -> InvoiceExtraction:
    documents = result_dict.get("documents") or []
    if not documents:
        return InvoiceExtraction(model_id=result_dict.get("modelId"))
    extraction = map_invoice_document(documents[0])
    return (
        extraction.model_copy(update={"model_id": result_dict["modelId"]})
        if result_dict.get("modelId")
        else extraction
    )


def _format_money(amount: Decimal | None) -> str | None:
    return f"{amount:.2f}" if amount is not None else None


def invoice_to_manifest_view(extraction: InvoiceExtraction) -> dict[str, str | None]:
    currency = extraction.invoice_total or extraction.subtotal
    return {
        "document_type": extraction.document_type,
        "vendor_name": extraction.vendor_name.value if extraction.vendor_name else None,
        "vendor_vat_id": extraction.vendor_tax_id.value if extraction.vendor_tax_id else None,
        "customer_name": extraction.customer_name.value if extraction.customer_name else None,
        "customer_vat_id": extraction.customer_tax_id.value if extraction.customer_tax_id else None,
        "invoice_number": extraction.invoice_id.value if extraction.invoice_id else None,
        "invoice_date": extraction.invoice_date.value.isoformat()
        if extraction.invoice_date and extraction.invoice_date.value
        else None,
        "due_date": extraction.due_date.value.isoformat()
        if extraction.due_date and extraction.due_date.value
        else None,
        "purchase_order": extraction.purchase_order.value if extraction.purchase_order else None,
        "currency": currency.currency_code if currency else None,
        "subtotal": _format_money(extraction.subtotal.amount if extraction.subtotal else None),
        "total_tax": _format_money(extraction.total_tax.amount if extraction.total_tax else None),
        "invoice_total": _format_money(
            extraction.invoice_total.amount if extraction.invoice_total else None
        ),
    }
