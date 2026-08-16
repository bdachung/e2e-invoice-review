"""Azure AI Document Intelligence extraction at the provider boundary."""

from __future__ import annotations

import os
from pathlib import Path

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

from app.schemas.invoice import InvoiceExtraction, map_invoice_result
from app.schemas.receipt import ReceiptExtraction, map_receipt_result

INVOICE_MODEL_ID = "prebuilt-invoice"
RECEIPT_MODEL_ID = "prebuilt-receipt"
LAYOUT_MODEL_ID = "prebuilt-layout"


class DocumentIntelligenceService:
    """Analyze local financial documents and expose provider-independent values."""

    def __init__(self, endpoint: str, api_key: str) -> None:
        self._client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key),
        )

    @classmethod
    def from_environment(cls) -> DocumentIntelligenceService:
        """Create a playground service from the documented local environment."""
        endpoint = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        api_key = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY")
        if not endpoint or not api_key:
            raise RuntimeError(
                "Set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and "
                "AZURE_DOCUMENT_INTELLIGENCE_KEY before using this service."
            )
        return cls(endpoint=endpoint, api_key=api_key)

    def analyze_invoice(self, invoice_path: Path) -> InvoiceExtraction:
        """Analyze an invoice and retain only its typed financial extraction."""
        return self.analyze_invoice_with_text(invoice_path)[0]

    def analyze_invoice_with_text(self, invoice_path: Path) -> tuple[InvoiceExtraction, str]:
        """Analyze an invoice and return its source text for Chat Completions."""
        result = self._analyze_document(invoice_path, INVOICE_MODEL_ID)
        return map_invoice_result(result), self._content(result)

    def analyze_receipt(self, receipt_path: Path) -> ReceiptExtraction:
        """Analyze a receipt and retain only its typed financial extraction."""
        return self.analyze_receipt_with_text(receipt_path)[0]

    def analyze_receipt_with_text(self, receipt_path: Path) -> tuple[ReceiptExtraction, str]:
        """Analyze a receipt and return its source text for Chat Completions."""
        result = self._analyze_document(receipt_path, RECEIPT_MODEL_ID)
        return map_receipt_result(result), self._content(result)

    def extract_text(self, document_path: Path) -> str:
        """Read a document with the layout model for PDF-safe Chat classification."""
        return self._content(self._analyze_document(document_path, LAYOUT_MODEL_ID))

    def _analyze_document(self, document_path: Path, model_id: str) -> dict[str, object]:
        if not document_path.is_file():
            raise FileNotFoundError(f"Financial document was not found: {document_path}")
        with document_path.open("rb") as document_file:
            poller = self._client.begin_analyze_document(model_id, body=document_file)
            return poller.result().as_dict()

    @staticmethod
    def _content(result: dict[str, object]) -> str:
        return str(result.get("content") or "").strip()
