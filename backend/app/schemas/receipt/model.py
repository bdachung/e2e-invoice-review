"""Rich provider-independent receipt extraction schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, computed_field

from app.schemas.common import (
    ExtractedAddress,
    ExtractedDate,
    ExtractedMoney,
    ExtractedNumber,
    ExtractedString,
    ExtractedTime,
    TaxDetail,
    average_confidence,
    minimum_confidence,
)


class ReceiptLineItem(BaseModel):
    description: ExtractedString | None = None
    quantity: ExtractedNumber | None = None
    price: ExtractedMoney | None = None
    total_price: ExtractedMoney | None = None
    product_code: ExtractedString | None = None
    quantity_unit: ExtractedString | None = None
    date: ExtractedDate | None = None
    category: ExtractedString | None = None


class ReceiptExtraction(BaseModel):
    document_type: Literal["receipt"] = "receipt"
    model_id: str | None = None
    receipt_type: ExtractedString | None = None
    merchant_name: ExtractedString | None = None
    merchant_phone_number: ExtractedString | None = None
    merchant_address: ExtractedAddress | None = None
    merchant_aliases: list[ExtractedString] = []
    transaction_date: ExtractedDate | None = None
    transaction_time: ExtractedTime | None = None
    arrival_date: ExtractedDate | None = None
    departure_date: ExtractedDate | None = None
    subtotal: ExtractedMoney | None = None
    total_tax: ExtractedMoney | None = None
    tip: ExtractedMoney | None = None
    total: ExtractedMoney | None = None
    items: list[ReceiptLineItem] = []
    tax_details: list[TaxDetail] = []

    @computed_field
    @property
    def average_confidence(self) -> float | None:
        return average_confidence(self)

    @computed_field
    @property
    def minimum_confidence(self) -> float | None:
        return minimum_confidence(self)
