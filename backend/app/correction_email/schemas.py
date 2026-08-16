"""Structured correction-email draft returned to the reviewer."""

from pydantic import BaseModel


class CorrectionEmailDraft(BaseModel):
    recipient_name: str | None = None
    subject: str
    body: str
