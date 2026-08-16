"""Run the chained financial-document pipeline on fictional source documents."""

import json
import logging

from _bootstrap import PROJECT_ROOT
from dotenv import load_dotenv

from app.pipeline import FinancialDocumentPipeline
from app.validation.models import CompanyIdentity

NORTHSTAR_IDENTITY = CompanyIdentity(
    legal_name="Northstar Facilities B.V.",
    vat_id="NL00449544B01",
)
SAMPLES = (
    PROJECT_ROOT / "samples" / "sample_invoice.pdf",
    PROJECT_ROOT / "samples" / "generated" / "13-nl-fuel-receipt.png",
)
OUTPUT_PATH = PROJECT_ROOT / "playground" / "financial_document_pipeline_results.json"


def no_duplicate_invoice(_supplier_name: str, _invoice_number: str) -> bool:
    """Placeholder until the SQLite repository provides duplicate detection."""
    return False


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    load_dotenv(PROJECT_ROOT / "backend" / ".env")
    pipeline = FinancialDocumentPipeline.from_environment(
        NORTHSTAR_IDENTITY,
        duplicate_check=no_duplicate_invoice,
    )
    results = []
    for sample_path in SAMPLES:
        logging.info("Processing %s", sample_path.name)
        result = pipeline.process(sample_path)
        serialized = result.model_dump(mode="json")
        results.append({"source": sample_path.name, "result": serialized})
        print(json.dumps(serialized, indent=2))

    OUTPUT_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    logging.info("Saved results to %s", OUTPUT_PATH)


if __name__ == "__main__":
    main()
