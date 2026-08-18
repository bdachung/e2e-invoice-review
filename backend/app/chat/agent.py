"""pydantic-ai chat agent that drives the Finance MCP tools.

The agent is wired exactly like the existing classification pipeline
(``app.pipeline.document_classification``): the same Azure OpenAI deployment
through the same async client factory. Its only tools are the four MCP tools
exposed by the Northstar Finance MCP server via :class:`McpBridge`.

Tool progress and results are surfaced through a caller-supplied ``emit``
callback so the WebSocket route can forward them to the browser as they happen.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic_ai import Agent
from pydantic_ai._agent_graph import CallToolsNode, ModelRequestNode
from pydantic_ai.messages import ModelMessage, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.chat.bridge import McpBridge
from app.config import Settings
from app.providers.azure_openai import build_async_azure_openai_client

ChatEvent = Callable[[dict[str, object]], Awaitable[None]]

SYSTEM_PROMPT = (
    "You are the Northstar finance assistant embedded in the document-review app. "
    "Users ask you to review uploaded invoices and receipts. "
    "To review a document, call the MCP process_document tool with the document "
    "reference the user or the host provides; it returns the complete finance review. "
    "Report the outcome concisely: document type, supplier, totals, validation "
    "findings, and any suggested GL account. "
    "You may draft a supplier-correction email with draft_supplier_email, but only "
    "when the user asks for it. "
    "You must NEVER call approve_document or reject_document yourself: approval and "
    "rejection are explicit human decisions. Recommend the action instead, and the "
    "user will click the corresponding button."
)


class ChatAgent:
    """One pydantic-ai agent with the Finance MCP toolset and a chat event stream."""

    def __init__(self, settings: Settings, bridge: McpBridge) -> None:
        self._bridge = bridge
        deployment = settings.azure_openai_deployment
        if not deployment:
            raise RuntimeError("Set AZURE_OPENAI_DEPLOYMENT in backend/.env.")
        self._agent = Agent(
            OpenAIChatModel(
                deployment,
                provider=OpenAIProvider(
                    openai_client=build_async_azure_openai_client(settings)
                ),
            ),
            toolsets=[bridge.toolset],
            instructions=SYSTEM_PROMPT,
        )

    async def run_turn(
        self,
        text: str,
        *,
        document_ref: str | None,
        history: list[ModelMessage] | None,
        emit: ChatEvent,
    ) -> list[ModelMessage] | None:
        """Run one assistant turn, streaming events, and return new history."""
        prompt = text
        if document_ref:
            prompt = (
                f"{text}\n\n(current document reference supplied by the host: {document_ref})"
            )
        async with self._agent.iter(prompt, message_history=history) as run:
            async for node in run:
                if isinstance(node, CallToolsNode):
                    for part in node.model_response.parts:
                        if isinstance(part, ToolCallPart):
                            await emit(
                                {
                                    "type": "tool",
                                    "name": part.tool_name,
                                    "arguments": _parse_arguments(part.args),
                                }
                            )
                        elif isinstance(part, TextPart) and part.content:
                            await emit({"type": "text", "delta": part.content})
                elif isinstance(node, ModelRequestNode):
                    for part in node.request.parts:
                        if isinstance(part, ToolReturnPart):
                            await emit(
                                {
                                    "type": "tool_result",
                                    "name": part.tool_name,
                                    "content": _jsonable(part.content),
                                }
                            )
                            await _emit_review(part, emit)
            result = run.result
        history = result.new_messages() if result is not None else None
        await emit({"type": "done"})
        return history


async def _emit_review(part: ToolReturnPart, emit: ChatEvent) -> None:
    """Surface a process_document review so the UI can render action chips."""
    if part.tool_name != "process_document" or not isinstance(part.content, dict):
        return
    review = part.content
    if "review_id" not in review:
        return
    await emit(
        {
            "type": "review",
            "review_id": review.get("review_id"),
            "status": review.get("status"),
            "document_ref": review.get("document_ref"),
            "conclusion": review.get("conclusion"),
            "allowed_actions": review.get("allowed_actions") or [],
        }
    )


def _parse_arguments(args: Any) -> dict[str, object]:
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
        except ValueError:
            return {"raw": args}
        return parsed if isinstance(parsed, dict) else {"raw": args}
    return {}


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value
