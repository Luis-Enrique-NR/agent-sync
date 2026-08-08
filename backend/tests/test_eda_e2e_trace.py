"""E2E trace test — validates the full EDA flow with timestamped trace log.

Runs the complete admission → bus accept → worker poll → handler lookup →
audit write → bus ack chain, then compares against the expected behavioral
model and emits the trace log to console.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, select

from ai.domain.models import (
    AgentProfile,
    AgentStatus,
    AuditAction,
    EntityType,
    SessionStatus,
)
from eda.consumer import EventHandler, consume_forever
from eda.handlers import handle_message_published
from eda.trace import TRACE_LOG_PATH, trace
from persistence.database import init_db, get_session
from persistence.models import (
    AgentProfileRow,
    AuditRecordRow,
    NegotiationStateRow,
)
from persistence.repository import create_agent_profile, write_audit
from transport.bus import EventDelivery
from transport.models import TransportEnvelopeV1, MessageSnapshot

# ── Traced Fake Bus ────────────────────────────────────────────────────


@dataclass
class TracedFakeBus:
    deliveries: list[EventDelivery] = field(default_factory=list)
    acked: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    _cursor: int = 0

    async def accept(self, envelope: TransportEnvelopeV1) -> None:
        trace("BUS_ACCEPT", f"deduplicating event_id={envelope.event_id} channel={envelope.channel}")
        self.deliveries.append(
            EventDelivery(message_id=f"msg_{len(self.deliveries)}", envelope=envelope)
        )
        trace("BUS_ACCEPT", f"accepted — delivery_id=msg_{len(self.deliveries)-1}")

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


# ── Helpers ───────────────────────────────────────────────────────────


def _envelope(
    channel: str = "chan_test_123",
    text: str = "oferta: 900 USD",
) -> TransportEnvelopeV1:
    return TransportEnvelopeV1(
        event_id="evt_e2e_test_001",
        event_type="message.published",  # type: ignore[arg-type]
        event_time="2026-08-08T14:00:00Z",  # type: ignore[arg-type]
        environment="test",
        channel=channel,
        message=MessageSnapshot(id="msg_test", text=text, author_id="author_1", seq=1),
        retracted=False,
    )


def _agent_profile(agent_id: UUID, name: str, entity: EntityType) -> AgentProfile:
    return AgentProfile(
        agent_id=agent_id,
        display_name=name,
        entity_type=entity,
        public_description=f"test {name}",
        personality="test",
        objectives=["test"],
    )


async def _run_one_cycle(bus: TracedFakeBus, handler: EventHandler) -> None:
    """Run consumer for one processing cycle, then cancel."""
    loop = asyncio.get_running_loop()
    task = loop.create_task(
        consume_forever(bus, "e2e-consumer", handler, lease_ms=5000, poll_interval_seconds=0.05)
    )
    for _ in range(50):
        if bus.remaining() == 0 and (bus.acked or bus.failed):
            break
        await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ── Adapter: wraps a plain async function as EventHandler ──────────


class _HandlerAdapter:
    def __init__(self, fn) -> None:
        self._fn = fn

    async def handle(self, delivery: EventDelivery) -> None:
        await self._fn(delivery)


# ── E2E Test ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e2e_full_eda_trace_flow() -> None:
    """E2E: admission → bus accept → worker poll → handler lookup → audit write → bus ack."""
    # Clear trace log
    TRACE_LOG_PATH.write_text("", encoding="utf-8")
    trace("E2E_START", "initializing E2E trace test")

    # Init DB
    init_db()
    session = get_session()
    # Clean
    for table in [AuditRecordRow, NegotiationStateRow, AgentProfileRow]:
        session.exec(table.__table__.delete())  # type: ignore[attr-defined]
    session.commit()

    # Create agent profiles
    agent_a_id = UUID("e2e00000-0000-0000-0000-000000000001")
    agent_b_id = UUID("e2e00000-0000-0000-0000-000000000002")
    session_id = UUID("e2e00000-0000-0000-0000-000000000100")

    profile_a = _agent_profile(agent_a_id, "E2E_Seller", EntityType.COMPANY)
    profile_b = _agent_profile(agent_b_id, "E2E_Buyer", EntityType.COMPANY)

    create_agent_profile(profile_a, user_id=uuid4(), session=session)
    create_agent_profile(profile_b, user_id=uuid4(), session=session)

    # Create a negotiation_state with portal_channel_id = "chan_test_123"
    state_row = NegotiationStateRow(
        session_id=session_id,
        portal_channel_id="chan_test_123",
        agent_1_id=agent_a_id,
        agent_2_id=agent_b_id,
        initiator_id=agent_a_id,
        current_speaker_id=agent_b_id,
        status=SessionStatus.ACTIVE.value,
        turn_count=2,
        max_turns=8,
        raw_state={"session_id": str(session_id), "status": "ACTIVE", "turn_count": 2},
    )
    session.add(state_row)
    session.commit()
    session.close()

    trace("E2E_SETUP", f"session={session_id} channel=chan_test_123 status=ACTIVE")

    # STEP 1-2: Simulate admission + bus accept
    envelope = _envelope()
    trace("ADMISSION", f"simulated POST /webhooks/portal event_id={envelope.event_id}")

    bus = TracedFakeBus()
    await bus.accept(envelope)

    # STEP 3-6: Run consumer
    trace("WORKER_POLL", "starting consume_forever for one cycle")
    await _run_one_cycle(bus, _HandlerAdapter(handle_message_published))

    # Assertions
    assert len(bus.acked) == 1, f"expected 1 ack, got {len(bus.acked)}"
    assert len(bus.failed) == 0, f"expected 0 failures, got {bus.failed}"

    s = get_session()
    audits = s.exec(select(AuditRecordRow)).all()
    assert len(audits) == 1
    assert audits[0].action == AuditAction.TURN_PUBLISHED.value
    assert audits[0].session_id == session_id
    assert audits[0].severity == "INFO"
    s.close()

    trace("E2E_END", f"VERIFIED: 1 audit record, session={session_id}, action=TURN_PUBLISHED")

    # Print trace log
    print("\n" + "=" * 72)
    print("  E2E TRACE LOG — logs/eda_e2e_trace.log")
    print("=" * 72)
    raw = TRACE_LOG_PATH.read_text("utf-8")
    for line in raw.strip().split("\n"):
        print(f"  {line}")
    print("=" * 72)

    # Verify ALL 6 steps appear in trace
    steps_expected = ["ADMISSION", "BUS_ACCEPT", "WORKER_POLL", "HANDLER_LOOKUP", "AUDIT_WRITE", "BUS_ACK"]
    for step in steps_expected:
        assert step in raw, f"TRACE GAP: step '{step}' not found in trace log"

    print(f"\n  FLUX_VERIFIED_SUCCESS — all {len(steps_expected)} steps traced")
