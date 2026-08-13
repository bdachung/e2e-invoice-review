"""Rich provider-independent invoice extraction schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, computed_field

from app.schemas.common import (
    ExtractedAddress,
    ExtractedDate,
    ExtractedMoney,
    ExtractedNumber,
    ExtractedString,
    TaxDetail,
    average_confidence,
    minimum_confidence,
)


class InvoiceLineItem(BaseModel):
    description: ExtractedString | None = None
    quantity: ExtractedNumber | None = None
    unit: ExtractedString | None = None
    unit_price: ExtractedMoney | None = None
    amount: ExtractedMoney | None = None
    tax: ExtractedMoney | None = None
    tax_rate: ExtractedString | None = None
    product_code: ExtractedString | None = None
    date: ExtractedDate | None = None


class PaymentDetail(BaseModel):
    iban: ExtractedString | None = None
    swift: ExtractedString | None = None
    bank_account_number: ExtractedString | None = None
    bpay_biller_code: ExtractedString | None = None
    bpay_reference: ExtractedString | None = None


class Installment(BaseModel):
    amount: ExtractedMoney | None = None
    due_date: ExtractedDate | None = None


class InvoiceExtraction(BaseModel):
    document_type: Literal["invoice"] = "invoice"
    model_id: str | None = None
    vendor_name: ExtractedString | None = None
    vendor_address: ExtractedAddress | None = None
    vendor_address_recipient: ExtractedString | None = None
    vendor_tax_id: ExtractedString | None = None
    customer_name: ExtractedString | None = None
    customer_id: ExtractedString | None = None
    customer_address: ExtractedAddress | None = None
    customer_address_recipient: ExtractedString | None = None
    customer_tax_id: ExtractedString | None = None
    billing_address: ExtractedAddress | None = None
    billing_address_recipient: ExtractedString | None = None
    shipping_address: ExtractedAddress | None = None
    shipping_address_recipient: ExtractedString | None = None
    service_address: ExtractedAddress | None = None
    service_address_recipient: ExtractedString | None = None
    remittance_address: ExtractedAddress | None = None
    remittance_address_recipient: ExtractedString | None = None
    invoice_id: ExtractedString | None = None
    invoice_date: ExtractedDate | None = None
    due_date: ExtractedDate | None = None
    purchase_order: ExtractedString | None = None
    payment_term: ExtractedString | None = None
    kvk_number: ExtractedString | None = None
    subtotal: ExtractedMoney | None = None
    total_discount: ExtractedMoney | None = None
    total_tax: ExtractedMoney | None = None
    invoice_total: ExtractedMoney | None = None
    amount_due: ExtractedMoney | None = None
    previous_unpaid_balance: ExtractedMoney | None = None
    service_start_date: ExtractedDate | None = None
    service_end_date: ExtractedDate | None = None
    items: list[InvoiceLineItem] = []
    tax_details: list[TaxDetail] = []
    payment_details: list[PaymentDetail] = []
    paid_in_four_installments: list[Installment] = []

    @computed_field
    @property
    def average_confidence(self) -> float | None:
        return average_confidence(self)

    @computed_field
    @property
    def minimum_confidence(self) -> float | None:
        return minimum_confidence(self)
