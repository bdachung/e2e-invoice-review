"""Receipt schema and Azure result mapping."""

from .mapping import map_receipt_document, map_receipt_result, receipt_to_manifest_view
from .model import ReceiptExtraction, ReceiptLineItem

__all__ = [
    "ReceiptExtraction",
    "ReceiptLineItem",
    "map_receipt_document",
    "map_receipt_result",
    "receipt_to_manifest_view",
]
