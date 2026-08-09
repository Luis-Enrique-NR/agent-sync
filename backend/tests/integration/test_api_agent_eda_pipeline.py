"""Multi-layer integration: HTTP → DB → EventBus → EDA matchmaking.

Verifies that agent registration via the REST API triggers the full
matchmaking chain: DB persistence, bus publication, handler dispatch,
engine invocation, and state mutation (BUSY status, negotiation records).
"""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from ai.domain.models import (
    AgentProfile, AgentStatus, AuditAction, EntityType, SessionStatus,
)
from persistence.database import init_db, get_session
from persistence.models import (
    AgentProfileRow, AuditRecordRow, NegotiationStateRow,
)
from transport.models import TransportEnvelopeV1


@dataclass
class RecordingBus:
    accepted: list[TransportEnvelopeV1] = field(default_factory=list)
    async def accept(self, e): self.accepted.append(e)
    async def receive(self, c, l): return None
    async def ack(self, d): pass
    async def fail(self, d, c): pass


def _build():
    bus = RecordingBus()
    from api.app import create_app as _create_app
    from ai.providers.fake import ScriptedLLMProvider
    from ai.engine.graph import NegotiationEngine
    from ai.domain.models import AgentTurn, TurnIntent

    class FakeSecret:
        async def get_secret(self):
            return "t"

    turn = AgentTurn(public_message="turno de prueba", intent=TurnIntent.OFFER)
    app = _create_app(secret_provider=FakeSecret(), bus=bus)
    app.state.engine = NegotiationEngine(ScriptedLLMProvider([turn] * 20))
    return TestClient(app), bus


@pytest.fixture(autouse=True)
def clean() -> None:
    init_db()
    s = get_session()
    for t in [AgentProfileRow, NegotiationStateRow, AuditRecordRow]:
        for r in s.exec(select(t)).all():
            s.delete(r)
    s.commit()
    s.close()


# ── Agent registration → DB + bus ─────────────────────────────────────


def test_register_agent_triggers_full_eda_matchmaking_cycle() -> None:
    """HTTP 201 → DB profile created → bus received agent.registered"""
    c, bus = _build()

    r1 = c.post("/api/v1/agents", json={
        "display_name": "Buyer", "entity_type": "person",
        "public_description": "t", "personality": "t", "objectives": ["t"],
        "interests": ["buy_bike"], "capabilities": ["cash"],
    })
    assert r1.status_code == 201
    bid = UUID(r1.json()["agent_id"])

    s = get_session()
    row = s.get(AgentProfileRow, bid)
    assert row is not None
    assert row.interests == ["buy_bike"]
    s.close()

    assert len(bus.accepted) >= 1
    assert bus.accepted[0].event_type == "agent.registered"
    # Verify message carries agent_id for the handler
    assert bus.accepted[0].message is not None
    assert bus.accepted[0].message.author_id == str(bid)


# ── Two compatible agents → matchmaking triggered ──────────────────────


def test_two_compatible_agents_trigger_matchmaking() -> None:
    """Register compatible agents → handler dispatches → BUSY + negotiation."""
    c, bus = _build()

    # Register seller
    r1 = c.post("/api/v1/agents", json={
        "display_name": "Seller", "entity_type": "person",
        "public_description": "t", "personality": "t", "objectives": ["t"],
        "interests": ["sell_bike"], "capabilities": ["buy_bike", "sell_bicycle"],
    })
    assert r1.status_code == 201
    sid = UUID(r1.json()["agent_id"])

    # Register buyer
    r2 = c.post("/api/v1/agents", json={
        "display_name": "Buyer", "entity_type": "person",
        "public_description": "t", "personality": "t", "objectives": ["t"],
        "interests": ["buy_bike"], "capabilities": ["cash"],
    })
    assert r2.status_code == 201
    bid = UUID(r2.json()["agent_id"])

    assert len(bus.accepted) >= 2

    # Simulate consumer: dispatch each recorded envelope through the handler
    from eda.handlers import NegotiationHandler
    from ai.engine.graph import NegotiationEngine
    from ai.providers.fake import ScriptedLLMProvider
    from ai.domain.models import AgentTurn, TurnIntent
    from transport.bus import EventDelivery

    turn = AgentTurn(public_message="oferta inicial", intent=TurnIntent.OFFER)
    engine = NegotiationEngine(ScriptedLLMProvider([turn] * 20))
    handler = NegotiationHandler(engine=engine, portal=None)

    import asyncio
    async def _dispatch():
        for i, envelope in enumerate(bus.accepted):
            delivery = EventDelivery(message_id=f"msg_{i}", envelope=envelope)
            await handler.handle(delivery)

    asyncio.run(_dispatch())

    # Domain assertions
    s = get_session()

    # Both agents should be BUSY (matchmaking + engine invocation)
    buyer_row = s.get(AgentProfileRow, bid)
    seller_row = s.get(AgentProfileRow, sid)
    assert buyer_row.status == AgentStatus.BUSY.value, f"buyer status: {buyer_row.status}"
    assert seller_row.status == AgentStatus.BUSY.value, f"seller status: {seller_row.status}"

    # A negotiation record should exist
    sessions = s.exec(
        select(NegotiationStateRow).where(
            (NegotiationStateRow.agent_1_id == bid)
            | (NegotiationStateRow.agent_2_id == bid)
        )
    ).all()
    assert len(sessions) >= 1, "no negotiation session created"
    assert sessions[0].status in (
        SessionStatus.ACTIVE.value,
        SessionStatus.PENDING_HUMAN_APPROVAL.value,
    ), f"session status: {sessions[0].status}"

    # Audit should include SESSION_CREATED
    audits = s.exec(
        select(AuditRecordRow).where(
            AuditRecordRow.action == AuditAction.SESSION_CREATED.value,
            AuditRecordRow.session_id == sessions[0].session_id,
        )
    ).all()
    assert len(audits) >= 1, "no SESSION_CREATED audit"

    s.close()
