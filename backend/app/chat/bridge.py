"""Persistent MCP client bridge from the FastAPI app to the Finance MCP server.

The Northstar Finance MCP server runs as a persistent ``stdio`` child process
spawned by the FastAPI application. This module owns that connection:

- the shared :class:`~pydantic_ai.mcp.MCPToolset` handed to the chat agent, and
- direct, serialized ``call_tool`` access for explicit human-gated actions
  (approve / reject / draft email) that must not go through the LLM.

The MCP server's ``process_document`` progress notifications are forwarded
through a swappable per-connection ``progress_forwarder``.
"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from typing import Any

from fastmcp.client import Client
from fastmcp.client.transports import StdioTransport
from mcp.types import TextContent
from pydantic_ai.mcp import MCPToolset

from app.config import BACKEND_ROOT

ProgressHandler = Callable[[float, float | None, str | None], Awaitable[None]]


class McpBridge:
    """Own the MCP server child process and serialize every MCP tool call."""

    def __init__(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(BACKEND_ROOT)
        self._transport = StdioTransport(
            command=sys.executable,
            args=["-m", "mcp_server.server", "--transport", "stdio"],
            env=env,
            cwd=str(BACKEND_ROOT),
        )
        self._progress_forwarder: ProgressHandler | None = None

        async def _forward_progress(
            progress: float, total: float | None, message: str | None
        ) -> None:
            if self._progress_forwarder is not None:
                await self._progress_forwarder(progress, total, message)

        self._client = Client(self._transport, progress_handler=_forward_progress)
        self.toolset = MCPToolset(self._client)
        self._lock = asyncio.Lock()

    @property
    def progress_forwarder(self) -> ProgressHandler | None:
        """Per-connection progress callback; set by the chat route before a run."""
        return self._progress_forwarder

    @progress_forwarder.setter
    def progress_forwarder(self, handler: ProgressHandler | None) -> None:
        self._progress_forwarder = handler

    async def list_tools(self) -> list[str]:
        """Return the names of the MCP tools exposed by the finance server."""
        async with self._lock:
            async with self.toolset:
                tools = await self._client.list_tools()
        return [tool.name for tool in tools]

    async def call_tool(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        """Call one MCP tool directly; used for explicit human-gated actions."""
        async with self._lock:
            async with self.toolset:
                result = await self._client.call_tool(name, arguments)
        return _simplify_tool_result(result)

    async def stop(self) -> None:
        """Close the MCP session and terminate the child server process."""
        async with self._lock:
            await self._client.close()


def _simplify_tool_result(result: Any) -> dict[str, object]:
    """Turn a FastMCP tool result into a JSON-serializable response dict."""
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured
    text = "".join(
        part.text for part in getattr(result, "content", []) if isinstance(part, TextContent)
    )
    return {"content": text, "is_error": bool(getattr(result, "is_error", False))}
