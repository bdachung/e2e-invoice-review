"""WebSocket chat endpoint that streams the Finance MCP agent and human actions."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth import COOKIE_NAME
from app.chat.agent import ChatAgent
from app.chat.bridge import McpBridge
from app.config import AppConfig

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.websocket("/stream")
async def chat_stream(websocket: WebSocket) -> None:
    """Stream one chat conversation against the Northstar Finance MCP server."""
    auth = websocket.app.state.password_auth
    if not auth.is_authenticated(websocket.cookies.get(COOKIE_NAME)):
        await websocket.close(code=1008)
        return
    bridge: McpBridge = websocket.app.state.mcp_bridge
    agent: ChatAgent | None = websocket.app.state.chat_agent
    config: AppConfig = websocket.app.state.config
    reviewer_id = config.mcp_reviewer_ids[0] if config.mcp_reviewer_ids else "maya"
    send_lock = asyncio.Lock()

    async def emit(event: dict[str, object]) -> None:
        async with send_lock:
            await websocket.send_text(json.dumps(event))

    async def forward_progress(
        progress: float, total: float | None, message: str | None
    ) -> None:
        await emit(
            {
                "type": "progress",
                "progress": progress,
                "total": total,
                "message": message,
            }
        )

    await websocket.accept()
    bridge.progress_forwarder = forward_progress
    history: list[Any] | None = None
    try:
        tools = await bridge.list_tools()
        await emit({"type": "ready", "tools": tools})
        if agent is None:
            await emit(
                {
                    "type": "error",
                    "message": "The chat agent is not configured: set AZURE_OPENAI_ENDPOINT, "
                    "AZURE_OPENAI_API_KEY, and AZURE_OPENAI_DEPLOYMENT in backend/.env.",
                }
            )
        while True:
            payload = json.loads(await websocket.receive_text())
            kind = payload.get("type")
            if kind == "message" and agent is not None:
                text = str(payload.get("text", "")).strip()
                if not text:
                    continue
                await emit({"type": "user", "text": text})
                document_ref = payload.get("document_ref")
                try:
                    history = await agent.run_turn(
                        text,
                        document_ref=document_ref if isinstance(document_ref, str) else None,
                        history=history,
                        emit=emit,
                    )
                except Exception as error:  # noqa: BLE001 - surfaced to the chat user
                    await emit({"type": "error", "message": _error_message(error)})
            elif kind == "action" and agent is not None:
                action = payload.get("action")
                review_id = payload.get("review_id")
                if action in {"approve", "reject", "draft_email"} and isinstance(review_id, str):
                    result = await _human_action(
                        bridge, action, review_id, reviewer_id, payload.get("reason")
                    )
                    await emit({"type": "action_result", "action": action, "result": result})
    except WebSocketDisconnect:
        pass
    finally:
        bridge.progress_forwarder = None


async def _human_action(
    bridge: McpBridge,
    action: str,
    review_id: str,
    reviewer_id: str,
    reason: Any,
) -> dict[str, object]:
    """Run one explicit human-gated MCP action without the LLM."""
    if action == "approve":
        return await bridge.call_tool(
            "approve_document", {"review_id": review_id, "reviewer_id": reviewer_id}
        )
    if action == "reject":
        return await bridge.call_tool(
            "reject_document",
            {
                "review_id": review_id,
                "reviewer_id": reviewer_id,
                "reason": str(reason) if reason else "No reason provided.",
            },
        )
    arguments: dict[str, object] = {"review_id": review_id}
    if reason:
        arguments["reason"] = str(reason)
    return await bridge.call_tool("draft_supplier_email", arguments)


def _error_message(error: Exception) -> str:
    return str(error) or error.__class__.__name__
