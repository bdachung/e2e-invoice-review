"""Run a minimal Azure OpenAI Responses API experiment."""

import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / "backend" / ".env")
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.services.azure_openai_service import AzureOpenAIService  # noqa: E402


def main() -> None:
    service = AzureOpenAIService.from_environment()
    response_text = service.generate_text(
        "What is the capital of France? Answer in one short sentence."
    )
    print(response_text)


if __name__ == "__main__":
    main()
