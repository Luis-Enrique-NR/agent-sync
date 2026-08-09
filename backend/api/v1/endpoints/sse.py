"""SSE streaming endpoint for negotiation transcript events.

Exposes ``GET /api/v1/negotiations/{session_id}/stream`` for real-time
delivery of new turn events to frontend clients via Server-Sent Events.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from persistence.database import get_session
from persistence.models import NegotiationStateRow

logger = logging.getLogger(__name__)

KEEPALIVE_INTERVAL = 30.0  # seconds
IDLE_TIMEOUT = 300.0  # 5 minutes


class SessionQueueManager:
    """Manages per-session ``asyncio.Queue`` instances for SSE fan-out.

    The EDA handler calls ``notify()`` after generating a new turn.  The
    SSE endpoint reads from the queue and yields ``text/event-stream``
    frames to the waiting client.
    """

    def __init__(
        self,
        keepalive: float = KEEPALIVE_INTERVAL,
        idle_timeout: float = IDLE_TIMEOUT,
    ) -> None:
        self._queues: dict[str, asyncio.Queue[dict]] = {}
        self.keepalive = keepalive
        self.idle_timeout = idle_timeout

    def get_queue(self, session_id: str) -> asyncio.Queue[dict]:
        """Return (and create if missing) the queue for *session_id*."""
        if session_id not in self._queues:
            self._queues[session_id] = asyncio.Queue()
        return self._queues[session_id]

    def notify(self, session_id: str, event: dict) -> None:
        """Push *event* onto the session's queue (noop if no subscriber)."""
        queue = self._queues.get(session_id)
        if queue is not None:
            queue.put_nowait(event)

    def remove_queue(self, session_id: str) -> None:
        """Drop the queue for *session_id* (client disconnect or timeout)."""
        self._queues.pop(session_id, None)


router = APIRouter(prefix="/negotiations", tags=["sse"])


async def _event_generator(
    session_id: str,
    queue: asyncio.Queue[dict],
    manager: SessionQueueManager,
) -> AsyncGenerator[str, None]:
    """Yield SSE frames from the session queue.

    - Emits ``data: {json}\\n\\n`` for each event on the queue.
    - Sends ``: ping\\n\\n`` keepalive frames every *keepalive* seconds.
    - Closes the connection after *idle_timeout* seconds with no events.
    - Cleans up the queue on disconnect (:class:`asyncio.CancelledError`).
    """
    idle_count = 0
    max_idle = (
        int(manager.idle_timeout / manager.keepalive)
        if manager.keepalive > 0
        else 1
    )
    try:
        while True:
            try:
                event = await asyncio.wait_for(
                    queue.get(), timeout=manager.keepalive
                )
                yield f"data: {json.dumps(event)}\n\n"
                idle_count = 0
            except asyncio.TimeoutError:
                idle_count += 1
                if idle_count >= max_idle:
                    logger.info(
                        "SSE idle timeout session=%s", session_id
                    )
                    break
                yield ": ping\n\n"
    except asyncio.CancelledError:
        logger.info("SSE client disconnected session=%s", session_id)
    finally:
        manager.remove_queue(session_id)


@router.get("/{session_id}/stream")
async def stream_negotiation(
    session_id: UUID,
    request: Request,
) -> StreamingResponse:
    """Stream negotiation transcript events via Server-Sent Events.

    Returns 404 if *session_id* does not reference a known negotiation.
    Clients receive ``data:`` frames for each new turn and ``: ping``
    keepalives every 30 s.  The connection times out after 5 min idle.
    """
    session = get_session()
    try:
        row = session.get(NegotiationStateRow, session_id)
    finally:
        session.close()

    if row is None:
        raise HTTPException(status_code=404, detail="negotiation not found")

    manager: SessionQueueManager = request.app.state.sse_broadcaster
    queue = manager.get_queue(str(session_id))

    return StreamingResponse(
        _event_generator(str(session_id), queue, manager),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
