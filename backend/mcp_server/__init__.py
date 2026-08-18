"""Northstar Finance MCP server: a thin, business-level adapter over the app.

The MCP server owns no finance policy. It exposes four coarse-grained tools
(``process_document``, ``approve_document``, ``reject_document``,
``draft_supplier_email``) and delegates every domain decision to the existing
finance application through :class:`mcp_server.adapter.FinanceAdapter`.
"""

from mcp_server.adapter import FinanceAdapter, McpError

__all__ = ["FinanceAdapter", "McpError"]
