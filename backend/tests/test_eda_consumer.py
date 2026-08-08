"""TDD suite for the EDA consumer — RED → GREEN phase.

Uses a FakeDurableEventBus that implements the transport Protocol without
Redis, making every test deterministic and side-effect-free.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, select

from ai.domain.models import AuditAction, AgentProfile, EntityType
from eda.consumer import EventHandler, consume_forever
from persistence.database import init_db, get_session
from persistence.models import AuditRecordRow, AgentProfileRow
from persistence.repository import (
    create_agent_profile,
    write_audit,
)
from transport.bus import EventDelivery
from transport.models import TransportEnvelopeV1, MessageSnapshot


# ── Fake durable bus (deterministic, no Redis) ──────────────────────────


@dataclass
class FakeDurableEventBus:
    """In-memory bus that implements the DurableEventBus Protocol."""

    deliveries: list[EventDelivery] = field(default_factory=list)
    acked: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    _cursor: int = 0

    async def accept(self, envelope: TransportEnvelopeV1) -> None:
        self.deliveries.append(
            EventDelivery(message_id=f"msg_{len(self.deliveries)}", envelope=envelope)
        )

    async def receive(self, consumer: str, lease_ms: int) -> EventDelivery | None:
        if self._cursor >= len(self.deliveries):
            return None
        delivery = self.deliveries[self._cursor]
        self._cursor += 1
        return delivery

    async def ack(self, delivery: EventDelivery) -> None:
        self.acked.append(delivery.message_id)

    async def fail(self, delivery: EventDelivery, code: str) -> None:
        self.failed.append((delivery.message_id, code))

    def remaining(self) -> int:
        return len(self.deliveries) - self._cursor


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def clean_db() -> None:
    """Clear DB state before each test."""
    init_db()
    session = get_session()
    for table in [AuditRecordRow, AgentProfileRow]:
        session.exec(table.__table__.delete())  # type: ignore[attr-defined]
    session.commit()
    session.close()


@pytest.fixture
def bus() -> FakeDurableEventBus:
    return FakeDurableEventBus()


def _envelope(
    channel: str = "channel_abc",
    text: str = "hello",
    author_id: str = "author_1",
    seq: int = 1,
) -> TransportEnvelopeV1:
    return TransportEnvelopeV1(
        event_id=f"evt_{uuid4().hex[:8]}",
        event_type="message.published",  # type: ignore[arg-type]
        event_time="2026-08-08T12:00:00Z",  # type: ignore[arg-type]
        environment="test",
        channel=channel,
        message=MessageSnapshot(id="msg_1", text=text, author_id=author_id, seq=seq),
        retracted=False,
    )


async def _run_until_empty(
    bus: FakeDurableEventBus,
    handler: EventHandler,
    *,
    poll_interval_seconds: float = 0.01,
) -> asyncio.Task[None]:
    """Run consumer as a background task until all deliveries are processed,
    then cancel it."""
    loop = asyncio.get_running_loop()
    task = loop.create_task(
        consume_forever(bus, "test-consumer", handler, lease_ms=5000, poll_interval_seconds=poll_interval_seconds)
    )
    # Wait for all deliveries to be consumed
    for _ in range(100):  # max 1s timeout
        if bus.remaining() == 0 and (bus.acked or bus.failed):
            break
        await asyncio.sleep(poll_interval_seconds)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    return task


# ── TDD CASE 1: valid event → deserialized → audit_records ──────────────


class RecordingHandler:
    """Handler that records every delivery for assertions and writes audit."""

    def __init__(self) -> None:
        self.received: list[EventDelivery] = []

    async def handle(self, delivery: EventDelivery) -> None:
        self.received.append(delivery)
        envelope = delivery.envelope
        write_audit(
            correlation_id=uuid4(),
            agent_id=None,
            user_id=None,
            actor_type="SYSTEM",
            actor_id="transport",
            action=AuditAction.TURN_PUBLISHED,
            severity="INFO",
            entity_type="TransportEnvelope",
            entity_id=None,
            reason=f"channel={envelope.channel} seq={envelope.message.seq if envelope.message else 'none'}",
            delivery_status="DELIVERED",
            payload=envelope.model_dump(mode="json"),
        )


@pytest.mark.asyncio
async def test_valid_event_writes_audit_record(bus: FakeDurableEventBus) -> None:
    """GREEN: a delivered message.published must produce an audit record and ack."""
    env = _envelope(channel="ch_session_1", text="oferta: 900 USD")
    await bus.accept(env)

    handler = RecordingHandler()
    await _run_until_empty(bus, handler)

    assert len(handler.received) == 1
    assert handler.received[0].envelope.channel == "ch_session_1"
    assert bus.acked == ["msg_0"]
    assert bus.failed == []

    session = get_session()
    records = session.exec(select(AuditRecordRow)).all()
    assert len(records) >= 1
    assert records[0].action == AuditAction.TURN_PUBLISHED
    assert records[0].severity == "INFO"
    session.close()


# ── TDD CASE 2: message.retracted → audit CRITICAL ─────────────────────


@pytest.mark.asyncio
async def test_retracted_event_writes_critical_audit(bus: FakeDurableEventBus) -> None:
    """GREEN: a message.retracted delivery must write an audit and ack."""
    env = TransportEnvelopeV1(
        event_id="evt_retracted_01",
        event_type="message.retracted",  # type: ignore[arg-type]
        event_time="2026-08-08T12:00:00Z",  # type: ignore[arg-type]
        environment="test",
        channel="ch_retracted",
        message=None,
        retracted=True,
    )
    await bus.accept(env)

    handler = RecordingHandler()
    await _run_until_empty(bus, handler)

    assert len(handler.received) == 1
    assert handler.received[0].envelope.event_type == "message.retracted"
    assert bus.acked == ["msg_0"]

    session = get_session()
    records = session.exec(select(AuditRecordRow)).all()
    assert len(records) >= 1
    assert records[0].action == AuditAction.TURN_PUBLISHED
    session.close()


# ── TDD CASE 3: handler fails → bus.fail() ─────────────────────────────


class FailingHandler:
    async def handle(self, delivery: EventDelivery) -> None:
        raise RuntimeError("simulated handler crash")


@pytest.mark.asyncio
async def test_handler_failure_calls_bus_fail(bus: FakeDurableEventBus) -> None:
    """GREEN: a failing handler must call bus.fail(), not bus.ack()."""
    env = _envelope()
    await bus.accept(env)

    await _run_until_empty(bus, FailingHandler())

    assert len(bus.acked) == 0
    assert len(bus.failed) == 1
    assert bus.failed[0][1] == "HANDLER_ERROR"


# ── TDD CASE 4: successful handler acks ────────────────────────────────


@pytest.mark.asyncio
async def test_successful_handler_acks_delivery(bus: FakeDurableEventBus) -> None:
    """GREEN: successful handler → bus.ack() called, no fail."""
    env = _envelope()
    await bus.accept(env)

    handler = RecordingHandler()
    await _run_until_empty(bus, handler)

    assert len(bus.acked) == 1
    assert len(bus.failed) == 0
    assert bus.acked[0] == "msg_0"
    assert len(handler.received) == 1


# ── TDD CASE 5: multiple deliveries, all consumed ──────────────────────


@pytest.mark.asyncio
async def test_multiple_deliveries_all_consumed(bus: FakeDurableEventBus) -> None:
    """GREEN: 5 deliveries → 5 audit records, all acked, none failed."""
    for i in range(5):
        await bus.accept(_envelope(channel=f"ch_{i}", text=f"message {i}"))

    handler = RecordingHandler()
    await _run_until_empty(bus, handler)

    assert len(handler.received) == 5
    assert len(bus.acked) == 5
    assert len(bus.failed) == 0

    session = get_session()
    records = session.exec(select(AuditRecordRow)).all()
    assert len(records) == 5
    session.close()
