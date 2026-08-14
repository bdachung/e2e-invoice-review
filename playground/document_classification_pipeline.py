"""Classify fictional financial documents with the Azure OpenAI pipeline."""

import json

from _bootstrap import PROJECT_ROOT
from dotenv import load_dotenv

from app.pipeline import DocumentClassificationPipeline


SAMPLES = (
    PROJECT_ROOT / "samples" / "sample_invoice.pdf",
    PROJECT_ROOT / "samples" / "generated" / "13-nl-fuel-receipt.png",
)


def main() -> None:
    load_dotenv(PROJECT_ROOT / "backend" / ".env")
    pipeline = DocumentClassificationPipeline.from_environment()
    for sample_path in SAMPLES:
        classification = pipeline.classify(sample_path)
        print(f"{sample_path.name}: {json.dumps(classification.model_dump())}")


if __name__ == "__main__":
    main()
