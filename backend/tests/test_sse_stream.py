"""Tests for SSE negotiation transcript streaming."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import httpx
import pytest
from sqlmodel import select

from api.app import create_app
from api.v1.endpoints.sse import (
    SessionQueueManager,
    _event_generator,
)
from persistence.database import get_session, init_db
from persistence.models import NegotiationStateRow
from transport.bus import DurableEventBus
from transport.portal import WebhookSecretProvider


# ── Test infrastructure ────────────────────────────────────────────────────


class FakeBus(DurableEventBus):  # type: ignore[misc]
    async def accept(self, envelope): pass
    async def receive(self, consumer, lease_ms): return None
    async def ack(self, delivery): pass
    async def fail(self, delivery, code): pass


class FakeSecretProvider(WebhookSecretProvider):
    async def get_secret(self) -> str | None:
        return "test-secret"


def _build_test_app(
    sse_manager: SessionQueueManager | None = None,
) -> "FastAPI":  # noqa: F821
    app = create_app(
        secret_provider=FakeSecretProvider(),
        bus=FakeBus(),
        sse_broadcaster=sse_manager,
    )
    return app


def _create_session(session_id: UUID | None = None) -> UUID:
    """Create a minimal NegotiationStateRow for SSE tests."""
    sid = session_id or uuid4()
    row = NegotiationStateRow(
        session_id=sid,
        agent_1_id=uuid4(),
        agent_2_id=uuid4(),
        initiator_id=uuid4(),
        status="ACTIVE",
        raw_state={"agents": [], "transcript": []},
    )
    session = get_session()
    try:
        session.add(row)
        session.commit()
    finally:
        session.close()
    return sid


@pytest.fixture(autouse=True)
def _clean_db() -> None:
    init_db()
    s = get_session()
    try:
        for table in [NegotiationStateRow]:
            for r in s.exec(select(table)).all():
                s.delete(r)
        s.commit()
    finally:
        s.close()


# ── Task 3.5: SessionQueueManager unit tests ───────────────────────────────


class TestSessionQueueManager:
    """Unit tests for the queue lifecycle."""

    def test_get_queue_creates_new(self) -> None:
        manager = SessionQueueManager()
        q = manager.get_queue("session-1")
        assert isinstance(q, asyncio.Queue)

    def test_get_queue_returns_same_instance(self) -> None:
        manager = SessionQueueManager()
        q1 = manager.get_queue("session-1")
        q2 = manager.get_queue("session-1")
        assert q1 is q2

    def test_get_queue_creates_separate_instances_for_different_sessions(self) -> None:
        manager = SessionQueueManager()
        q1 = manager.get_queue("session-1")
        q2 = manager.get_queue("session-2")
        assert q1 is not q2

    def test_notify_pushes_event_to_queue(self) -> None:
        manager = SessionQueueManager()
        q = manager.get_queue("session-1")
        manager.notify("session-1", {"key": "value"})
        assert q.qsize() == 1

    def test_notify_is_noop_for_unknown_session(self) -> None:
        manager = SessionQueueManager()
        manager.notify("nonexistent", {"key": "value"})
        # No exception raised — verified by reaching this line

    def test_remove_queue_drops_session(self) -> None:
        manager = SessionQueueManager()
        manager.get_queue("session-1")
        manager.remove_queue("session-1")
        assert "session-1" not in manager._queues  # type: ignore[attr-defined]

    def test_remove_queue_is_noop_for_unknown_session(self) -> None:
        manager = SessionQueueManager()
        manager.remove_queue("nonexistent")
        # No exception raised


# ── Task 3.5: Event generator tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_event_generator_yields_queue_events() -> None:
    """_event_generator yields SSE 'data:' frame for each queued event."""
    manager = SessionQueueManager(keepalive=1.0, idle_timeout=10.0)
    queue: asyncio.Queue[dict] = asyncio.Queue()

    queue.put_nowait({"turn": 1, "public_message": "hello"})

    gen = _event_generator("test-sess", queue, manager)
    chunk = await gen.__anext__()
    assert chunk == 'data: {"turn": 1, "public_message": "hello"}\n\n'

    # Cleanup — close generator so remove_queue runs
    await gen.aclose()
    assert "test-sess" not in manager._queues


@pytest.mark.asyncio
async def test_event_generator_sends_keepalive_ping() -> None:
    """After keepalive_interval with no events, ': ping' is yielded."""
    manager = SessionQueueManager(keepalive=0.1, idle_timeout=10.0)
    queue: asyncio.Queue[dict] = asyncio.Queue()

    gen = _event_generator("test-sess", queue, manager)
    chunk = await gen.__anext__()
    assert chunk == ": ping\n\n"

    await gen.aclose()


@pytest.mark.asyncio
async def test_event_generator_idle_timeout_breaks_loop() -> None:
    """After idle_timeout elapses with no events, generator finishes cleanly."""
    manager = SessionQueueManager(keepalive=0.1, idle_timeout=0.25)
    queue: asyncio.Queue[dict] = asyncio.Queue()

    gen = _event_generator("test-sess", queue, manager)
    chunks: list[str] = []
    async for chunk in gen:
        chunks.append(chunk)

    # Should have pings before breaking out (0.1 * ceil(0.25/0.1) = 3 pings max)
    ping_count = sum(1 for c in chunks if c.strip() == ": ping")
    assert ping_count >= 1, f"Expected at least 1 ping, got: {chunks}"
    assert "test-sess" not in manager._queues


@pytest.mark.asyncio
async def test_event_generator_disconnect_cleans_up_queue() -> None:
    """CancelledError (client disconnect) triggers queue removal."""
    manager = SessionQueueManager(keepalive=1.0, idle_timeout=10.0)
    manager.get_queue("test-sess")  # pre-create
    queue = manager._queues["test-sess"]  # type: ignore[attr-defined]

    gen = _event_generator("test-sess", queue, manager)
    await gen.__anext__()  # Start iteration (will wait on queue.get with timeout)

    # Simulate client disconnect
    await gen.aclose()

    assert "test-sess" not in manager._queues


# ── Task 3.5: Endpoint integration test (non-streaming) ────────────────────


@pytest.mark.asyncio
async def test_sse_404_for_unknown_session() -> None:
    """GET /api/v1/negotiations/{unknown}/stream returns 404 JSON."""
    manager = SessionQueueManager()
    app = _build_test_app(manager)
    unknown_id = uuid4()

    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", timeout=2.0
    ) as client:
        resp = await client.get(f"/api/v1/negotiations/{unknown_id}/stream")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
