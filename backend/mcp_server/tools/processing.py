"""``process_document``: the primary long-running MCP tool with progress."""

from __future__ import annotations

import asyncio
import queue
from datetime import UTC, datetime

from mcp.server.fastmcp import Context, FastMCP

from mcp_server.adapter import FinanceAdapter, McpError
from mcp_server.audit import audit_logger, log_tool_call, new_request_id

# Ordered stages mirror the finance pipeline steps (see app.pipeline.chain).
STAGE_INDEX = {
    "classification": 1,
    "extraction": 2,
    "normalization": 3,
    "independent_review": 4,
    "validation": 5,
    "general_ledger": 6,
}
TOTAL_STAGES = len(STAGE_INDEX)
STARTED_MESSAGE = {
    1: "Classifying invoice or receipt",
    2: "Extracting document fields",
    3: "Normalizing fields and provenance",
    4: "Running independent document review",
    5: "Validating VAT, totals, duplicates, and PO",
    6: "Suggesting GL account",
}
COMPLETED_MESSAGE = {
    1: "Document classified",
    2: "Fields extracted",
    3: "Fields normalized",
    4: "Independent review complete",
    5: "Validation complete",
    6: "GL account suggested",
}


def register(mcp: FastMCP, finance: FinanceAdapter) -> None:
    @mcp.tool()
    async def process_document(document_ref: str, ctx: Context) -> dict[str, object]:
        """Process one already-uploaded invoice or receipt through the existing
        Northstar finance review workflow and return the complete review result.

        The host application uploads the file and supplies its document_ref;
        this tool runs classification, extraction, validation, duplicate and PO
        checks, and GL suggestion, streaming progress notifications while it
        works. Call the returned review_id with approve_document,
        reject_document, or draft_supplier_email afterwards.
        """
        request_id = new_request_id()
        started_at = datetime.now(UTC)
        events: queue.Queue[tuple[str, str, str | None]] = queue.Queue()

        def forward(step: str, status: str, message: str | None) -> None:
            events.put((step, status, message))

        def report(step: str, status: str, message: str | None) -> tuple[int, str]:
            index = STAGE_INDEX.get(step, TOTAL_STAGES)
            if status == "completed":
                label = COMPLETED_MESSAGE.get(index) or "Step complete"
            else:
                label = STARTED_MESSAGE.get(index) or message or "Processing document"
            return index, label

        try:
            task = asyncio.create_task(finance.process_document(document_ref, forward))
            while not task.done():
                try:
                    while True:
                        step, status, message = events.get_nowait()
                        index, label = report(step, status, message)
                        await ctx.report_progress(index, TOTAL_STAGES, label)
                except queue.Empty:
                    pass
                await asyncio.sleep(0.02)
            result = await task
        except McpError as error:
            log_tool_call(
                request_id=request_id,
                tool_name="process_document",
                document_ref=document_ref,
                status="error",
                error_code=error.code,
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )
            return {"error": error.code, "message": error.message}
        except Exception as error:  # noqa: BLE001 - intentionally surfaced to the agent
            audit_logger.exception("MCP tool process_document failed unexpectedly")
            log_tool_call(
                request_id=request_id,
                tool_name="process_document",
                document_ref=document_ref,
                status="error",
                error_code="INTERNAL_ERROR",
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )
            return {"error": "INTERNAL_ERROR", "message": str(error) or error.__class__.__name__}

        while True:
            try:
                step, status, message = events.get_nowait()
                index, label = report(step, status, message)
                await ctx.report_progress(index, TOTAL_STAGES, label)
            except queue.Empty:
                break
        await ctx.report_progress(TOTAL_STAGES, TOTAL_STAGES, "Review complete")
        log_tool_call(
            request_id=request_id,
            tool_name="process_document",
            document_ref=document_ref,
            status="ok",
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )
        return result
