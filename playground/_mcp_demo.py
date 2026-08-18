"""Shared helpers for the Northstar Finance MCP playground demos.

Run the playground scripts from the repository root:

    cd backend
    uv run --locked --no-sync python ../playground/mcp_tools_list.py

The helpers create unprocessed document records through the real finance
application service so that ``process_document`` runs the pipeline live, and
resolve storage paths to the backend folder so the demos work from any cwd.
"""

from __future__ import annotations

import os
from dataclasses import replace

from _bootstrap import BACKEND_ROOT, PROJECT_ROOT
from mcp.types import CallToolResult, TextContent

from app.config import AppConfig, get_app_config, get_settings
from app.database import build_database
from app.documents.repository import DocumentRepository
from app.documents.service import DocumentService

SAMPLES_DIR = PROJECT_ROOT / "samples" / "generated"
VENV_PYTHON = BACKEND_ROOT / ".venv" / "Scripts" / "python.exe"


def tool_result_text(result: CallToolResult) -> str:
    """Extract the text from an MCP tool result, ignoring non-text content."""
    parts = [item.text for item in result.content if isinstance(item, TextContent)]
    return "\n".join(parts) or "<no text content>"


def demo_config() -> AppConfig:
    """App config with absolute storage paths, valid from any working directory."""
    config = get_app_config(get_settings())
    database_url = config.database_url
    if database_url.startswith("sqlite:///./"):
        database_url = f"sqlite:///{(BACKEND_ROOT / database_url.removeprefix('sqlite:///./')).as_posix()}"
    upload_dir = config.upload_dir
    if not upload_dir.is_absolute():
        upload_dir = BACKEND_ROOT / upload_dir
    return replace(config, database_url=database_url, upload_dir=upload_dir)


def upload_sample(filename: str) -> str:
    """Store a fictional sample as an unprocessed document; return its id."""
    config = demo_config()
    path = SAMPLES_DIR / filename
    _, session_factory = build_database(config.database_url)
    with session_factory() as session:
        service = DocumentService(DocumentRepository(session), config)
        return service.create(path.name, "application/pdf", path.read_bytes(), ".pdf").id


def select_gl_account(record_id: str, code: str = "6300") -> None:
    """Host-side GL selection; the finance app requires it before approval."""
    config = demo_config()
    _, session_factory = build_database(config.database_url)
    with session_factory() as session:
        DocumentService(DocumentRepository(session), config).select_gl_account(record_id, code)


def delete_record(record_id: str) -> None:
    """Remove a demo document record and its stored file."""
    config = demo_config()
    _, session_factory = build_database(config.database_url)
    with session_factory() as session:
        DocumentService(DocumentRepository(session), config).delete(record_id)


def server_environment() -> dict[str, str]:
    """Environment for the spawned MCP server process."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(BACKEND_ROOT)
    return env
