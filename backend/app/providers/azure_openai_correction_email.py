"""Azure Chat Completions adapter for structured, unsent email drafts."""

from __future__ import annotations

import json
from typing import Any

from app.correction_email.base import CorrectionEmailDrafter, CorrectionEmailDraftingError
from app.correction_email.schemas import CorrectionEmailDraft
from app.pipeline.models import FinancialDocumentReviewData
from app.validation.models import ValidationIssue

INSTRUCTIONS = (
    "Draft a concise professional correction request from Maya in Finance "
    "Administration at Northstar Facilities B.V. Mention only supplied document "
    "facts and business findings. Ask for a corrected document or clarification. "
    "Do not mention AI, confidence, internal systems, or invent an email address. "
    "The app will never send this email."
)


class AzureOpenAICorrectionEmailDrafter(CorrectionEmailDrafter):
    """Create an unsent, strongly typed correction draft via Chat Completions."""

    def __init__(self, client: Any, deployment: str) -> None:
        self._client = client
        self._deployment = deployment

    def draft(
        self,
        data: FinancialDocumentReviewData,
        issues: list[ValidationIssue],
        reason: str | None = None,
    ) -> CorrectionEmailDraft:
        prompt: dict[str, object] = {
            "document": data.model_dump(mode="json"),
            "issues": [issue.model_dump() for issue in issues],
        }
        if reason:
            prompt["reviewer_reason"] = reason
        try:
            response = self._client.beta.chat.completions.parse(
                model=self._deployment,
                messages=[
                    {"role": "system", "content": INSTRUCTIONS},
                    {"role": "user", "content": json.dumps(prompt)},
                ],
                response_format=CorrectionEmailDraft,
            )
            draft = response.choices[0].message.parsed
            if draft is None:
                raise ValueError("The completion did not contain structured output.")
            return draft
        except (AttributeError, IndexError, TypeError, ValueError) as error:
            raise CorrectionEmailDraftingError(
                "Azure OpenAI returned an invalid correction-email draft."
            ) from error
        except Exception as error:
            raise CorrectionEmailDraftingError(
                "Azure OpenAI could not draft the correction email."
            ) from error
