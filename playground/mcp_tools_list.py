"""Inspect the Northstar Finance MCP tool surface without starting a transport.

No Azure calls, no server process: builds the MCP server in-process and prints
the four business-level tools with their input schemas and descriptions.

    cd backend
    uv run --locked --no-sync python ../playground/mcp_tools_list.py
"""

import asyncio
import json

import _bootstrap  # noqa: F401  (puts the backend package on sys.path)

from mcp_server.server import build_server


async def main() -> None:
    server = build_server()
    tools = await server.list_tools()
    print(f"Northstar Finance exposes {len(tools)} MCP tools:\n")
    for tool in tools:
        print(f"- {tool.name}")
        print(f"  {(tool.description or '').strip()}")
        print(f"  input: {json.dumps(tool.inputSchema, indent=2)}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
