"""Print and save the normalized invoice model for the fictional sample invoice."""

import json

from _bootstrap import PROJECT_ROOT
from dotenv import load_dotenv

from app.services.document_intelligence_service import DocumentIntelligenceService


RESULT_PATH = PROJECT_ROOT / "playground" / "sample_invoice_result.json"


def main() -> None:
    load_dotenv(PROJECT_ROOT / "backend" / ".env")
    invoice_path = PROJECT_ROOT / "samples" / "sample_invoice.pdf"
    result = DocumentIntelligenceService.from_environment().analyze_invoice(invoice_path)
    result_json = json.dumps(result.model_dump(mode="json"), indent=2)

    RESULT_PATH.write_text(result_json, encoding="utf-8")
    print(f"Saved result to {RESULT_PATH}")
    print(result_json)


if __name__ == "__main__":
    main()
