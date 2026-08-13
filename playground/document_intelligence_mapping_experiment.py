"""Run and save rich invoice and receipt extraction mapping experiments."""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / "backend" / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.schemas.invoice import invoice_to_manifest_view  # noqa: E402
from app.schemas.receipt import receipt_to_manifest_view  # noqa: E402
from app.services.document_intelligence_service import DocumentIntelligenceService  # noqa: E402

EXPERIMENTS = (
    (
        "sample_invoice_model.json",
        PROJECT_ROOT / "samples" / "sample_invoice.pdf",
        "analyze_invoice",
        invoice_to_manifest_view,
    ),
    (
        "sample_receipt_model.json",
        PROJECT_ROOT / "samples" / "generated" / "13-nl-fuel-receipt.png",
        "analyze_receipt",
        receipt_to_manifest_view,
    ),
)


def save_result(output_name: str, result: BaseModel) -> None:
    output_path = PROJECT_ROOT / "playground" / output_name
    output_path.write_text(json.dumps(result.model_dump(mode="json"), indent=2), encoding="utf-8")
    print(f"Saved result to {output_path}")


def main() -> None:
    service = DocumentIntelligenceService.from_environment()
    for output_name, sample_path, method_name, manifest_mapper in EXPERIMENTS:
        analyzer = getattr(service, method_name)
        result = analyzer(sample_path)
        save_result(output_name, result)
        print(json.dumps(manifest_mapper(result), indent=2))


if __name__ == "__main__":
    main()
