"""OpenAPI, edge cases, and TDD bug-fix tests for the REST API."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from ai.domain.models import (
    AgentProfile,
    DecisionKind,
    DecisionReason,
    DecisionRequest,
    EntityType,
    NegotiationState,
    SessionStatus,
)
from api.app import create_app
from persistence.database import init_db, get_session
from persistence.models import AgentProfileRow, NegotiationStateRow
from persistence.repository import create_agent_profile, save_negotiation_state
from transport.models import TransportEnvelopeV1


@dataclass
class RecordingFakeBus:
    """Fake bus that records accepted envelopes for assertions."""
    accepted: list[TransportEnvelopeV1] = field(default_factory=list)

    async def accept(self, envelope): self.accepted.append(envelope)
    async def receive(self, consumer, lease_ms): return None
    async def ack(self, delivery): pass
    async def fail(self, delivery, code): pass


def _build_test_app(bus=None):
    if bus is None:
        bus = RecordingFakeBus()

    class FakeSecretProvider:
        async def get_secret(self): return "test-secret"

    app = create_app(secret_provider=FakeSecretProvider(), bus=bus)

    # Inject a fake engine so approval tests don't need OPENAI_API_KEY
    from ai.providers.fake import ScriptedLLMProvider
    from ai.engine.graph import NegotiationEngine
    app.state.engine = NegotiationEngine(ScriptedLLMProvider([]))

    return TestClient(app), bus


@pytest.fixture(autouse=True)
def clean() -> None:
    init_db()
    s = get_session()
    for t in [AgentProfileRow, NegotiationStateRow]:
        rows = s.exec(select(t)).all()
        for r in rows:
            s.delete(r)
    s.commit()
    s.close()


# ── Existing tests (kept) ──────────────────────────────────────────────


def test_openapi_json_returns_200():
    c, _ = _build_test_app()
    resp = c.get("/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "AgentSync API"


def test_get_nonexistent_agent_returns_404():
    c, _ = _build_test_app()
    resp = c.get(f"/api/v1/agents/{uuid4()}")
    assert resp.status_code == 404


def test_register_agent_invalid_payload_returns_422():
    c, _ = _build_test_app()
    resp = c.post("/api/v1/agents", json={"display_name": "Bad"})
    assert resp.status_code == 422


def test_register_agent_empty_objectives_returns_422():
    c, _ = _build_test_app()
    resp = c.post("/api/v1/agents", json={
        "display_name": "T", "entity_type": "person",
        "public_description": "t", "personality": "t", "objectives": [],
    })
    assert resp.status_code == 422


def test_cors_headers_present():
    c, _ = _build_test_app()
    resp = c.options("/api/v1/agents", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
    })
    assert resp.status_code in (200, 204, 405)


# ── TDD RED: agent registration publishes event to bus ─────────────────


def test_register_agent_publishes_event_to_bus() -> None:
    """RED: POST /agents must publish agent.registered to the bus."""
    bus = RecordingFakeBus()
    c, bus = _build_test_app(bus)
    resp = c.post("/api/v1/agents", json={
        "display_name": "MatchAgent", "entity_type": "person",
        "public_description": "test", "personality": "test",
        "objectives": ["test"], "interests": ["buy_bike"],
    })
    assert resp.status_code == 201
    # RED: should have published at least one envelope
    assert len(bus.accepted) >= 1, "agent registration must publish event to bus"
    assert bus.accepted[0].event_type == "agent.registered"


# ── TDD RED: approval uses engine, clears pending_decision ─────────────


def _seed_pending_session():
    from ai.domain.models import AgentTurn

    s = get_session()
    a1 = UUID("d0000000-0000-0000-0000-000000000001")
    a2 = UUID("d0000000-0000-0000-0000-000000000002")
    sid = UUID("d0000000-0000-0000-0000-000000000100")
    p1 = AgentProfile(agent_id=a1, display_name="A1", entity_type=EntityType.PERSON,
                      public_description="t", personality="t", objectives=["t"])
    p2 = AgentProfile(agent_id=a2, display_name="A2", entity_type=EntityType.PERSON,
                      public_description="t", personality="t", objectives=["t"])
    create_agent_profile(p1, user_id=uuid4(), session=s)
    create_agent_profile(p2, user_id=uuid4(), session=s)

    turn = AgentTurn(public_message="oferta: 900 USD", intent="OFFER")  # type: ignore[arg-type]
    decision = DecisionRequest(
        session_id=sid,
        owner_agent_id=a1,
        kind=DecisionKind.OUTBOUND_TURN,
        reasons=[DecisionReason.USER_RULE],  # type: ignore[arg-type]
        candidate_turn=turn,
    )
    state = NegotiationState(
        session_id=sid, agents=(p1, p2), current_speaker_id=a1,
        status="PENDING_HUMAN_APPROVAL",  # type: ignore[arg-type]
        deadline_at="2099-01-01T00:00:00Z",  # type: ignore[arg-type]
        pending_decision=decision,
    )
    row = NegotiationStateRow(
        session_id=sid, agent_1_id=a1, agent_2_id=a2, initiator_id=a1,
        current_speaker_id=a1, status=SessionStatus.PENDING_HUMAN_APPROVAL.value,
        raw_state=state.model_dump(mode="json"),
    )
    s.add(row)
    s.commit()
    s.close()
    return sid


def test_approval_approve_resumes_engine_and_clears_pending() -> None:
    """RED: APPROVE must clear pending_decision and update raw_state."""
    bus = RecordingFakeBus()
    c, _bus = _build_test_app(bus)
    sid = _seed_pending_session()

    resp = c.post(f"/api/v1/negotiations/{sid}/approval", json={
        "action": "APPROVE", "reason": "looks good",
    })
    assert resp.status_code == 200

    s = get_session()
    row = s.get(NegotiationStateRow, sid)
    state = NegotiationState.model_validate(row.raw_state)
    # RED: pending_decision should be cleared
    assert state.pending_decision is None, "pending_decision must be cleared after APPROVE"
    s.close()


def test_approval_replace_action_success() -> None:
    """RED: REPLACE with replacement_turn must return 200, not 500."""
    bus = RecordingFakeBus()
    c, _bus = _build_test_app(bus)
    sid = _seed_pending_session()

    resp = c.post(f"/api/v1/negotiations/{sid}/approval", json={
        "action": "REPLACE",
        "replacement_turn": "Nueva contraoferta. Propongo un mejor precio con envio incluido.",
    })
    assert resp.status_code == 200


def test_approval_replace_missing_turn_returns_422() -> None:
    """RED: REPLACE without replacement_turn must fail validation."""
    bus = RecordingFakeBus()
    c, _bus = _build_test_app(bus)
    sid = _seed_pending_session()

    resp = c.post(f"/api/v1/negotiations/{sid}/approval", json={
        "action": "REPLACE",
    })
    assert resp.status_code == 422


def test_approval_on_active_state_returns_400() -> None:
    """RED: APPROVE on ACTIVE session must return 400, not 404."""
    bus = RecordingFakeBus()
    c, _bus = _build_test_app(bus)
    # Create an ACTIVE session
    s = get_session()
    a1 = UUID("e0000000-0000-0000-0000-000000000001")
    a2 = UUID("e0000000-0000-0000-0000-000000000002")
    sid = UUID("e0000000-0000-0000-0000-000000000100")
    p1 = AgentProfile(agent_id=a1, display_name="X", entity_type=EntityType.PERSON,
                      public_description="t", personality="t", objectives=["t"])
    p2 = AgentProfile(agent_id=a2, display_name="Y", entity_type=EntityType.PERSON,
                      public_description="t", personality="t", objectives=["t"])
    create_agent_profile(p1, user_id=uuid4(), session=s)
    create_agent_profile(p2, user_id=uuid4(), session=s)
    state = NegotiationState(
        session_id=sid, agents=(p1, p2), current_speaker_id=a1,
        status="ACTIVE",  # type: ignore[arg-type]
        deadline_at="2099-01-01T00:00:00Z",  # type: ignore[arg-type]
    )
    row = NegotiationStateRow(
        session_id=sid, agent_1_id=a1, agent_2_id=a2, initiator_id=a1,
        current_speaker_id=a1, status="ACTIVE",
        raw_state=state.model_dump(mode="json"),
    )
    s.add(row)
    s.commit()
    s.close()

    resp = c.post(f"/api/v1/negotiations/{sid}/approval", json={"action": "APPROVE"})
    assert resp.status_code == 400
    assert "detail" in resp.json()
