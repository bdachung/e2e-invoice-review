"""Print and save the normalized invoice model for the fictional sample invoice."""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = PROJECT_ROOT / "playground" / "sample_invoice_result.json"
load_dotenv(PROJECT_ROOT / "backend" / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.services.document_intelligence_service import DocumentIntelligenceService  # noqa: E402


def main() -> None:
    invoice_path = PROJECT_ROOT / "samples" / "sample_invoice.pdf"
    result = DocumentIntelligenceService.from_environment().analyze_invoice(invoice_path)
    result_json = json.dumps(result.model_dump(mode="json"), indent=2)

    RESULT_PATH.write_text(result_json, encoding="utf-8")
    print(f"Saved result to {RESULT_PATH}")
    print(result_json)


if __name__ == "__main__":
    main()
