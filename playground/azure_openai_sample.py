"""Run a minimal Azure OpenAI Responses API experiment."""

from _bootstrap import PROJECT_ROOT
from dotenv import load_dotenv

from app.services.azure_openai_service import AzureOpenAIService


def main() -> None:
    load_dotenv(PROJECT_ROOT / "backend" / ".env")
    service = AzureOpenAIService.from_environment()
    response_text = service.generate_text(
        "What is the capital of France? Answer in one short sentence."
    )
    print(response_text)


if __name__ == "__main__":
    main()
