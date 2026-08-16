"""Azure Chat Completions adapter for independent structured document review."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from app.document_review.base import DocumentReviewer, DocumentReviewError
from app.document_review.schemas import LlmDocumentExtraction

INSTRUCTIONS = (
    "Independently review the supplied financial document. Classify it as an "
    "invoice, receipt, or unsupported, then extract the requested data directly "
    "from the supplied source text and image when available. Use null for "
    "unreadable values, ISO dates, plain decimal strings for money, and one "
    "concise factual summary. Do not assess validation, VAT validity, approval, "
    "or GL policy."
)


class AzureOpenAIDocumentReviewer(DocumentReviewer):
    """Return strict Pydantic extraction from Azure Chat Completions."""

    def __init__(self, client: Any, deployment: str) -> None:
        self._client = client
        self._deployment = deployment

    def review(
        self,
        document_path: Path,
        content_type: str,
        document_text: str | None = None,
    ) -> LlmDocumentExtraction:
        if not document_text:
            raise DocumentReviewError("Document Intelligence did not return readable text.")
        content: list[dict[str, object]] = [
            {
                "type": "text",
                "text": "Review this document. Its extracted source text follows:\n\n"
                + document_text,
            }
        ]
        if content_type in {"image/jpeg", "image/png"}:
            encoded = base64.b64encode(document_path.read_bytes()).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{content_type};base64,{encoded}",
                        "detail": "high",
                    },
                }
            )
        elif content_type != "application/pdf":
            raise DocumentReviewError("Independent review supports PDF, PNG, and JPEG files.")
        try:
            response = self._client.beta.chat.completions.parse(
                model=self._deployment,
                messages=[
                    {"role": "system", "content": INSTRUCTIONS},
                    {"role": "user", "content": content},
                ],
                response_format=LlmDocumentExtraction,
            )
            extraction = response.choices[0].message.parsed
            if extraction is None:
                raise ValueError("The completion did not contain structured output.")
            return extraction
        except (AttributeError, IndexError, TypeError, ValueError) as error:
            raise DocumentReviewError(
                "Azure OpenAI returned invalid independent-review output."
            ) from error
        except Exception as error:
            raise DocumentReviewError("Azure OpenAI independent document review failed.") from error
