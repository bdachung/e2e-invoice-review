"""Verify the Azure OpenAI service with local environment credentials."""

from dotenv import load_dotenv

from app.services.azure_openai_service import AzureOpenAIService

load_dotenv(".env")
response_text = AzureOpenAIService.from_environment().generate_text(
    "What is the capital of France? Answer in one short sentence."
)
print(f"answer: {response_text}")
