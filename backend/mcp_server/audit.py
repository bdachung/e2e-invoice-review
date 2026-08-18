"""Observability: structured audit logging for every MCP tool call.

Each tool call logs request id, tool name, document reference, actor, timings,
latency, status, and error code so MCP activity is traceable (see
``docs/mcp-design.md`` section 18).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from mcp_server.adapter import McpError

audit_logger = logging.getLogger("invoice_review.mcp.audit")


def new_request_id() -> str:
    """Return a fresh short request identifier for one MCP tool call."""
    return uuid.uuid4().hex[:12]


def log_tool_call(
    *,
    request_id: str,
    tool_name: str,
    document_ref: str | None = None,
    actor: str | None = None,
    status: str,
    error_code: str | None = None,
    started_at: datetime,
    finished_at: datetime,
) -> None:
    """Write one structured audit line for a finished MCP tool call."""
    record: dict[str, Any] = {
        "request_id": request_id,
        "tool_name": tool_name,
        "document_ref": document_ref,
        "actor": actor,
        "status": status,
        "error_code": error_code,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "latency_ms": round((finished_at - started_at).total_seconds() * 1000, 1),
    }
    if error_code:
        audit_logger.warning("mcp_tool_call %s", record)
    else:
        audit_logger.info("mcp_tool_call %s", record)


async def run_tool(
    tool_name: str,
    fn: Any,
    *,
    document_ref: str | None = None,
    actor: str | None = None,
    **kwargs: Any,
) -> dict[str, object]:
    """Await a simple adapter call, audit it, and map domain errors to results.

    Domain errors (``McpError``) are returned as structured ``{"error",
    "message"}`` tool results so the agent can read them. Unexpected failures
    become ``INTERNAL_ERROR`` results while the full traceback is logged.
    """
    request_id = new_request_id()
    started_at = datetime.now(UTC)
    try:
        result = await fn(**kwargs)
    except McpError as error:
        log_tool_call(
            request_id=request_id,
            tool_name=tool_name,
            document_ref=document_ref,
            actor=actor,
            status="error",
            error_code=error.code,
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )
        return {"error": error.code, "message": error.message}
    except Exception as error:  # noqa: BLE001 - intentionally surfaced to the agent
        audit_logger.exception("MCP tool %s failed unexpectedly", tool_name)
        log_tool_call(
            request_id=request_id,
            tool_name=tool_name,
            document_ref=document_ref,
            actor=actor,
            status="error",
            error_code="INTERNAL_ERROR",
            started_at=started_at,
            finished_at=datetime.now(UTC),
        )
        return {
            "error": "INTERNAL_ERROR",
            "message": str(error) or error.__class__.__name__,
        }
    log_tool_call(
        request_id=request_id,
        tool_name=tool_name,
        document_ref=document_ref,
        actor=actor,
        status="ok",
        started_at=started_at,
        finished_at=datetime.now(UTC),
    )
    return result
