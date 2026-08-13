"""Classify fictional financial documents with the Azure OpenAI pipeline."""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / "backend" / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.pipeline import DocumentClassificationPipeline  # noqa: E402

SAMPLES = (
    PROJECT_ROOT / "samples" / "sample_invoice.pdf",
    PROJECT_ROOT / "samples" / "generated" / "13-nl-fuel-receipt.png",
)


def main() -> None:
    pipeline = DocumentClassificationPipeline.from_environment()
    for sample_path in SAMPLES:
        classification = pipeline.classify(sample_path)
        print(f"{sample_path.name}: {json.dumps(classification.model_dump())}")


if __name__ == "__main__":
    main()
