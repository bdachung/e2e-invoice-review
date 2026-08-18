"""``draft_supplier_email``: an unsent supplier-correction draft."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.adapter import FinanceAdapter
from mcp_server.audit import run_tool


def register(mcp: FastMCP, finance: FinanceAdapter) -> None:
    @mcp.tool()
    async def draft_supplier_email(
        review_id: str, reason: str | None = None
    ) -> dict[str, object]:
        """Draft, but never send, a supplier-correction email for an already
        reviewed document.

        Optionally include the reviewer's reason for the correction request.
        The returned text is editable and the app has no send-email capability.
        """
        return await run_tool(
            "draft_supplier_email",
            finance.draft_supplier_email,
            document_ref=review_id,
            review_id=review_id,
            reason=reason,
        )
