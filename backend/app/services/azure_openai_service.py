"""Azure OpenAI Responses API surface."""

import os

from openai import OpenAI


class AzureOpenAIService:
    """Generate text through an Azure OpenAI deployment."""

    def __init__(self, endpoint: str, api_key: str, deployment: str) -> None:
        self._client = OpenAI(base_url=endpoint, api_key=api_key)
        self._deployment = deployment

    @classmethod
    def from_environment(cls) -> "AzureOpenAIService":
        """Create the service from local Azure OpenAI environment variables."""
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
        if not endpoint or not api_key or not deployment:
            message = (
                "Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and "
                "AZURE_OPENAI_DEPLOYMENT before using this service."
            )
            raise RuntimeError(message)
        return cls(endpoint=endpoint, api_key=api_key, deployment=deployment)

    def generate_text(self, prompt: str, *, instructions: str | None = None) -> str:
        """Generate text from the configured Azure OpenAI deployment."""
        response = self._client.responses.create(
            model=self._deployment,
            input=prompt,
            instructions=instructions,
        )
        return response.output_text
