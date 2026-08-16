"""Provider-independent supplier correction-email contracts."""

from .base import CorrectionEmailDrafter, CorrectionEmailDraftingError
from .schemas import CorrectionEmailDraft

__all__ = ["CorrectionEmailDraft", "CorrectionEmailDrafter", "CorrectionEmailDraftingError"]
