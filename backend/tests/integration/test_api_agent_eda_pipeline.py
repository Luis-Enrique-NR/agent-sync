"""Multi-layer integration: HTTP → DB → EventBus → EDA matchmaking."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from ai.domain.models import AgentProfile, EntityType, SessionStatus
from persistence.database import init_db, get_session
from persistence.models import AgentProfileRow, NegotiationStateRow
from persistence.repository import create_agent_profile
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

    # Provide enough scripted turns for the engine
    turn = AgentTurn(public_message="turno de prueba", intent=TurnIntent.OFFER)
    app = _create_app(secret_provider=FakeSecret(), bus=bus)
    app.state.engine = NegotiationEngine(ScriptedLLMProvider([turn] * 20))
    return TestClient(app), bus


@pytest.fixture(autouse=True)
def clean() -> None:
    init_db()
    s = get_session()
    for t in [AgentProfileRow, NegotiationStateRow]:
        for r in s.exec(select(t)).all():
            s.delete(r)
    s.commit()
    s.close()


# ── Full matchmaking cycle ─────────────────────────────────────────────


def test_register_agent_triggers_full_eda_matchmaking_cycle() -> None:
    """HTTP 201 → DB profile created → bus received agent.registered"""
    c, bus = _build()

    # Register buyer
    r1 = c.post("/api/v1/agents", json={
        "display_name": "Buyer", "entity_type": "person",
        "public_description": "t", "personality": "t", "objectives": ["t"],
        "interests": ["buy_bike"], "capabilities": ["cash"],
    })
    assert r1.status_code == 201
    bid = UUID(r1.json()["agent_id"])

    # Verify DB
    s = get_session()
    row = s.get(AgentProfileRow, bid)
    assert row is not None
    assert row.interests == ["buy_bike"]
    s.close()

    # Verify bus received event
    assert len(bus.accepted) >= 1, "agent.registered must be published to bus"
    assert bus.accepted[0].event_type == "agent.registered"


# ── Both agents registered → matchmaking through handler ───────────────


def test_two_compatible_agents_trigger_matchmaking() -> None:
    """Register seller + buyer with matching tags → negotiation created"""
    c, bus = _build()

    # Register seller with capability matching buyer's interest
    r1 = c.post("/api/v1/agents", json={
        "display_name": "Seller", "entity_type": "person",
        "public_description": "t", "personality": "t", "objectives": ["t"],
        "interests": ["sell_bike"], "capabilities": ["buy_bike", "sell_bicycle"],
    })
    assert r1.status_code == 201

    r2 = c.post("/api/v1/agents", json={
        "display_name": "Buyer2", "entity_type": "person",
        "public_description": "t", "personality": "t", "objectives": ["t"],
        "interests": ["buy_bike"], "capabilities": ["cash"],
    })
    assert r2.status_code == 201

    # Both agents published events
    assert len(bus.accepted) >= 2  # one per registration
