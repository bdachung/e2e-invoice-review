"""``approve_document`` and ``reject_document``: explicit human-gated actions."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.adapter import FinanceAdapter
from mcp_server.audit import run_tool


def register(mcp: FastMCP, finance: FinanceAdapter) -> None:
    @mcp.tool()
    async def approve_document(review_id: str, reviewer_id: str) -> dict[str, object]:
        """Approve an already processed finance review.

        Call this tool ONLY after an explicit reviewer approval action in the
        UI; the AI must never decide approval itself. reviewer_id must identify
        the trusted reviewer who clicked Approve.
        """
        return await run_tool(
            "approve_document",
            finance.approve_document,
            document_ref=review_id,
            actor=reviewer_id,
            review_id=review_id,
            reviewer_id=reviewer_id,
        )

    @mcp.tool()
    async def reject_document(review_id: str, reviewer_id: str, reason: str) -> dict[str, object]:
        """Reject an already processed finance review.

        Call this tool ONLY after an explicit reviewer rejection action with
        the reviewer's reason; the AI must never decide rejection itself. The
        reason is stored with the review.
        """
        return await run_tool(
            "reject_document",
            finance.reject_document,
            document_ref=review_id,
            actor=reviewer_id,
            review_id=review_id,
            reviewer_id=reviewer_id,
            reason=reason,
        )
