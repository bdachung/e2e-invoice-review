"""Classify fictional financial documents with Azure Chat Completions."""

import json

from _bootstrap import PROJECT_ROOT

from app.config import get_settings
from app.pipeline.document_classification import DocumentClassificationPipeline
from app.services.document_intelligence_service import DocumentIntelligenceService

SAMPLES = (
    PROJECT_ROOT / "samples" / "sample_invoice.pdf",
    PROJECT_ROOT / "samples" / "generated" / "13-nl-fuel-receipt.png",
)


def main() -> None:
    settings = get_settings()
    if not settings.azure_document_intelligence_endpoint or not settings.azure_document_intelligence_key:
        raise RuntimeError("Set Document Intelligence endpoint and key in backend/.env.")
    document_intelligence = DocumentIntelligenceService(
        settings.azure_document_intelligence_endpoint,
        settings.azure_document_intelligence_key,
    )
    pipeline = DocumentClassificationPipeline.from_settings(
        settings,
        text_extractor=document_intelligence.extract_text,
    )
    for sample_path in SAMPLES:
        classification = pipeline.classify(sample_path)
        print(f"{sample_path.name}: {json.dumps(classification.model_dump())}")


if __name__ == "__main__":
    main()
