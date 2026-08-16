"""In-memory progress events for the local document-processing pipeline."""

from __future__ import annotations

import asyncio
import threading
from collections import defaultdict
from typing import Literal

from fastapi import WebSocket
from pydantic import BaseModel

ProgressStatus = Literal["started", "completed", "failed"]


class DocumentProgressEvent(BaseModel):
    document_id: str
    step: str | None = None
    status: ProgressStatus
    message: str | None = None


class DocumentProgressBroker:
    """Broadcast best-effort, per-document progress to local WebSocket clients."""

    def __init__(self) -> None:
        self._events: dict[str, list[DocumentProgressEvent]] = defaultdict(list)
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    async def connect(self, document_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._loop = asyncio.get_running_loop()
        with self._lock:
            self._connections[document_id].add(websocket)
            events = list(self._events[document_id])
        for event in events:
            await websocket.send_json(event.model_dump(mode="json"))

    def disconnect(self, document_id: str, websocket: WebSocket) -> None:
        with self._lock:
            connections = self._connections.get(document_id)
            if not connections:
                return
            connections.discard(websocket)
            if not connections:
                self._connections.pop(document_id, None)

    def publish(
        self,
        document_id: str,
        status: ProgressStatus,
        step: str | None = None,
        message: str | None = None,
    ) -> None:
        event = DocumentProgressEvent(
            document_id=document_id, status=status, step=step, message=message
        )
        with self._lock:
            self._events[document_id].append(event)
            loop = self._loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(self._broadcast(event), loop)

    async def _broadcast(self, event: DocumentProgressEvent) -> None:
        with self._lock:
            connections = list(self._connections.get(event.document_id, set()))
        for websocket in connections:
            try:
                await websocket.send_json(event.model_dump(mode="json"))
            except RuntimeError:
                self.disconnect(event.document_id, websocket)


progress_broker = DocumentProgressBroker()
