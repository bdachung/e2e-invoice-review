"""WebSocket endpoint for live document-processing progress."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth import COOKIE_NAME, PasswordAuth
from app.documents.progress import progress_broker

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.websocket("/{document_id}/progress")
async def document_progress(document_id: str, websocket: WebSocket) -> None:
    """Stream best-effort progress events for one local document run."""
    auth: PasswordAuth = websocket.app.state.password_auth
    if not auth.is_authenticated(websocket.cookies.get(COOKIE_NAME)):
        await websocket.close(code=1008)
        return
    await progress_broker.connect(document_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        progress_broker.disconnect(document_id, websocket)

