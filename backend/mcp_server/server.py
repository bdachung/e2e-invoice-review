"""Server construction and entry points for the Northstar Finance MCP server.

Run locally over stdio (default, works with MCP Inspector and desktop hosts):

    cd backend
    uv run --locked --no-sync python -m mcp_server.server --transport stdio

Or deploy over Streamable HTTP (stateless, progress-friendly):

    uv run --locked --no-sync python -m mcp_server.server \
        --transport streamable-http --host 127.0.0.1 --port 9000
"""

from __future__ import annotations

import argparse
import logging
from typing import Literal

from mcp.server.fastmcp import FastMCP

from mcp_server.adapter import FinanceAdapter
from mcp_server.tools.email import register as register_email_tools
from mcp_server.tools.processing import register as register_processing_tools
from mcp_server.tools.review import register as register_review_tools

INSTRUCTIONS = (
    "Northstar Finance MCP server. process_document runs the existing finance "
    "review workflow and streams progress. approve_document and "
    "reject_document are human-gated: call them only after an explicit "
    "reviewer action. draft_supplier_email returns an unsent correction draft."
)

DEFAULT_MCP_PORT = 9000


def build_server(
    *,
    stateless_http: bool = False,
    host: str = "127.0.0.1",
    port: int = DEFAULT_MCP_PORT,
) -> FastMCP:
    """Create the MCP server and register the four business-level tools."""
    mcp = FastMCP(
        "Northstar Finance",
        instructions=INSTRUCTIONS,
        host=host,
        port=port,
        stateless_http=stateless_http,
    )
    finance = FinanceAdapter()
    register_processing_tools(mcp, finance)
    register_review_tools(mcp, finance)
    register_email_tools(mcp, finance)
    return mcp


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Northstar Finance MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="MCP transport; stdio suits local MCP clients and the Inspector",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Streamable HTTP bind host")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_MCP_PORT, help="Streamable HTTP bind port"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    transport: Literal["stdio", "streamable-http"] = args.transport
    server = build_server(
        stateless_http=transport == "streamable-http",
        host=args.host,
        port=args.port,
    )
    server.run(transport=transport)


if __name__ == "__main__":
    main()
