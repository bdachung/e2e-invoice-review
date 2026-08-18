"""Probe the Northstar Finance MCP server over Streamable HTTP.

Starts the server itself (``python -m mcp_server.server --transport
streamable-http``) on a local port, waits until it is ready, then talks to it
with the official MCP HTTP client: initialize, tools/list, and an error-path
tools/call.

With ``--document-ref <id>`` it also runs the real ``process_document``
pipeline, which streams progress notifications over HTTP and consumes paid
Azure capacity (Document Intelligence + OpenAI for that one document).

    cd backend
    uv run --locked --no-sync python ../playground/mcp_http_probe.py
    uv run --locked --no-sync python ../playground/mcp_http_probe.py --port 9010 --document-ref <id>

Troubleshooting: if the run fails with a ``426 Upgrade Required`` error, the
chosen port is already held by another process (the MCP SDK never returns 426,
so the request reached a stale listener, not this server). Pick a free port
with ``--port NNNN`` or stop the process that owns the port:

    netstat -ano | findstr :9010
    taskkill /PID <pid> /F
"""

from __future__ import annotations

import argparse
import asyncio
import socket
import subprocess
import time
from typing import Any

from _bootstrap import BACKEND_ROOT
from _mcp_demo import server_environment, tool_result_text
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

DEFAULT_PORT = 9010
URL_TEMPLATE = "http://127.0.0.1:{port}/mcp"


def port_is_free(port: int) -> bool:
    """Return True when nothing is listening on the port yet."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def wait_for_server(port: int, process: subprocess.Popen[Any] | None = None) -> None:
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError(
                f"MCP server process exited early (code {process.returncode}). "
                f"Is port {port} already in use by another process?"
            )
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.25)
    raise RuntimeError(f"MCP server did not become ready on port {port}.")


async def probe(port: int, document_ref: str | None) -> None:
    url = URL_TEMPLATE.format(port=port)
    async with streamable_http_client(url) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Discovered tools:", [tool.name for tool in tools.tools])

            result = await session.call_tool(
                "process_document", {"document_ref": "doc-does-not-exist"}
            )
            print("\n### process_document(doc-does-not-exist)")
            print(tool_result_text(result))

            if document_ref:
                progress_events: list[str] = []

                async def on_progress(progress: float, total: float | None, message: str | None):
                    progress_events.append(f"{progress:.0f}/{total} {message}")
                    print(f"  [progress {progress:.0f}/{total}] {message}")

                result = await session.call_tool(
                    "process_document",
                    {"document_ref": document_ref},
                    progress_callback=on_progress,
                )
                print(f"\n### process_document({document_ref})")
                print(tool_result_text(result))
                print(f"  progress events: {len(progress_events)}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Northstar Finance MCP Streamable HTTP probe")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--document-ref", default=None, help="Optional real document id to process over HTTP."
    )
    args = parser.parse_args(argv)

    if not port_is_free(args.port):
        raise SystemExit(
            f"Port {args.port} is already in use by another process; the probe would "
            f"reach that process instead of the MCP server.\n"
            f"Find it with:   netstat -ano | findstr :{args.port}\n"
            f"Stop it with:   taskkill /PID <pid> /F\n"
            f"Or pick a free port:  --port NNNN"
        )

    command = [
        str(BACKEND_ROOT / ".venv" / "Scripts" / "python.exe"),
        "-m",
        "mcp_server.server",
        "--transport",
        "streamable-http",
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
    ]
    process = subprocess.Popen(command, cwd=str(BACKEND_ROOT), env=server_environment())
    try:
        wait_for_server(args.port, process)
        print(f"Server ready at {URL_TEMPLATE.format(port=args.port)}\n")
        asyncio.run(probe(args.port, args.document_ref))
    finally:
        process.terminate()
        process.wait(timeout=10)
        print("\n(server stopped)")


if __name__ == "__main__":
    main()
