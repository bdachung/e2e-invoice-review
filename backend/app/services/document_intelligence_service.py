"""Azure AI Document Intelligence financial-document analysis surface."""

import os
from pathlib import Path

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

from app.schemas.invoice import InvoiceExtraction, map_invoice_result
from app.schemas.receipt import ReceiptExtraction, map_receipt_result

INVOICE_MODEL_ID = "prebuilt-invoice"
RECEIPT_MODEL_ID = "prebuilt-receipt"


class DocumentIntelligenceService:
    """Analyze local financial documents with Azure's prebuilt models."""

    def __init__(self, endpoint: str, api_key: str) -> None:
        self._client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key),
        )

    @classmethod
    def from_environment(cls) -> "DocumentIntelligenceService":
        """Create a service from the local Azure environment variables."""
        endpoint = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        api_key = os.environ.get("AZURE_DOCUMENT_INTELLIGENCE_KEY")
        if not endpoint or not api_key:
            message = (
                "Set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and "
                "AZURE_DOCUMENT_INTELLIGENCE_KEY before using this service."
            )
            raise RuntimeError(message)
        return cls(endpoint=endpoint, api_key=api_key)

    def analyze_invoice(self, invoice_path: Path) -> InvoiceExtraction:
        """Analyze one local invoice and preserve Azure extraction provenance."""
        return map_invoice_result(self._analyze_document(invoice_path, INVOICE_MODEL_ID))

    def analyze_receipt(self, receipt_path: Path) -> ReceiptExtraction:
        """Analyze one local receipt and preserve Azure extraction provenance."""
        return map_receipt_result(self._analyze_document(receipt_path, RECEIPT_MODEL_ID))

    def _analyze_document(self, document_path: Path, model_id: str) -> dict[str, object]:
        if not document_path.is_file():
            raise FileNotFoundError(f"Financial document was not found: {document_path}")

        with document_path.open("rb") as document_file:
            poller = self._client.begin_analyze_document(model_id, body=document_file)
            result = poller.result()

        return result.as_dict()
