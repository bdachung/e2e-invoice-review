"""Full Northstar Finance MCP demo over the stdio transport.

Spawns the MCP server and drives it with the official MCP client:

1. tool discovery
2. error path for an unknown document reference (no Azure)
3. a clean invoice: process with live progress, host GL selection, approve
   (unknown reviewer and missing GL are shown as structured errors)
4. a defective invoice: process, reject with a reason, draft an unsent email

Azure cost: two document-processing runs (Document Intelligence + OpenAI) and
one correction-email draft. Created records persist in the local SQLite
database so the review UI can show them; delete them from the web UI or with
the helper ``_mcp_demo.delete_record`` when done.

    cd backend
    uv run --locked --no-sync python ../playground/mcp_stdio_client.py
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any

from _bootstrap import BACKEND_ROOT
from _mcp_demo import select_gl_account, server_environment, tool_result_text, upload_sample
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

VENV_PYTHON = BACKEND_ROOT / ".venv" / "Scripts" / "python.exe"
DEFAULT_SAMPLE_A = "01-en-happy-classic.pdf"
DEFAULT_SAMPLE_B = "08-en-total-mismatch.pdf"


async def call(session: ClientSession, name: str, arguments: dict[str, Any], on_progress=None):
    result = await session.call_tool(name, arguments, progress_callback=on_progress)
    print(f"\n### {name}({arguments})")
    print(tool_result_text(result))


async def demo(session: ClientSession, document_ref_a: str, sample_b: str) -> None:
    tools = await session.list_tools()
    print("Discovered tools:", [tool.name for tool in tools.tools])

    await call(session, "process_document", {"document_ref": "doc-does-not-exist"})

    progress_events: list[str] = []

    async def on_progress(progress: float, total: float | None, message: str | None) -> None:
        progress_events.append(f"{progress:.0f}/{total} {message}")
        print(f"  [progress {progress:.0f}/{total}] {message}")

    await call(
        session, "process_document", {"document_ref": document_ref_a}, on_progress=on_progress
    )
    print(f"  progress events: {len(progress_events)}")

    select_gl_account(document_ref_a, "6300")
    print("\n(host selected GL account 6300 in the finance app)")
    await call(session, "approve_document", {"review_id": document_ref_a, "reviewer_id": "admin"})
    await call(session, "approve_document", {"review_id": document_ref_a, "reviewer_id": "maya"})
    await call(session, "approve_document", {"review_id": document_ref_a, "reviewer_id": "maya"})

    document_ref_b = upload_sample(sample_b)
    print(f"\n(created unprocessed record {document_ref_b} from {sample_b})")
    await call(session, "process_document", {"document_ref": document_ref_b})
    await call(
        session,
        "reject_document",
        {
            "review_id": document_ref_b,
            "reviewer_id": "maya",
            "reason": "Invoice total does not match the referenced purchase order.",
        },
    )
    await call(
        session,
        "draft_supplier_email",
        {"review_id": document_ref_b, "reason": "Please issue a corrected invoice."},
    )


async def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Northstar Finance MCP stdio demo")
    parser.add_argument(
        "--document-ref",
        default=None,
        help="Use an existing document id for the first invoice instead of uploading a sample.",
    )
    parser.add_argument("--sample-a", default=DEFAULT_SAMPLE_A)
    parser.add_argument("--sample-b", default=DEFAULT_SAMPLE_B)
    args = parser.parse_args(argv)

    document_ref_a = args.document_ref or upload_sample(args.sample_a)
    if args.document_ref is None:
        print(f"(created unprocessed record {document_ref_a} from {args.sample_a})")

    params = StdioServerParameters(
        command=str(VENV_PYTHON),
        args=["-m", "mcp_server.server", "--transport", "stdio"],
        env=server_environment(),
        cwd=str(BACKEND_ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await demo(session, document_ref_a, args.sample_b)


if __name__ == "__main__":
    asyncio.run(main())
