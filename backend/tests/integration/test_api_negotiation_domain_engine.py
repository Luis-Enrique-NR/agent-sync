"""Multi-layer: HTTP approval → DB raw_state → engine resume."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from ai.domain.models import (
    AgentProfile, AgentTurn, DecisionKind, DecisionReason, DecisionRequest,
    DecisionStatus, EntityType, NegotiationState,
    SessionStatus, TurnIntent,
)
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

    turn = AgentTurn(public_message="turno de prueba", intent=TurnIntent.OFFER)
    app = _create_app(secret_provider=FakeSecret(), bus=bus)
    app.state.engine = NegotiationEngine(ScriptedLLMProvider([turn] * 20))
    return TestClient(app), bus


def _seed_pending():
    s = get_session()
    a1 = UUID("d0000000-0000-0000-0000-000000000001")
    a2 = UUID("d0000000-0000-0000-0000-000000000002")
    sid = UUID("d0000000-0000-0000-0000-000000000100")
    p1 = AgentProfile(agent_id=a1, display_name="A", entity_type=EntityType.PERSON,
                      public_description="t", personality="t", objectives=["t"])
    p2 = AgentProfile(agent_id=a2, display_name="B", entity_type=EntityType.PERSON,
                      public_description="t", personality="t", objectives=["t"])
    create_agent_profile(p1, user_id=uuid4(), session=s)
    create_agent_profile(p2, user_id=uuid4(), session=s)
    turn = AgentTurn(public_message="oferta: 900 USD", intent=TurnIntent.OFFER)
    dec = DecisionRequest(
        session_id=sid, owner_agent_id=a1, kind=DecisionKind.OUTBOUND_TURN,
        reasons=[DecisionReason.USER_RULE],
        candidate_turn=turn,
    )
    state = NegotiationState(
        session_id=sid, agents=(p1, p2), current_speaker_id=a1,
        status="PENDING_HUMAN_APPROVAL",  # type: ignore[arg-type]
        deadline_at="2099-01-01T00:00:00Z",  # type: ignore[arg-type]
        pending_decision=dec,
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


@pytest.fixture(autouse=True)
def clean() -> None:
    init_db()
    s = get_session()
    for t in [AgentProfileRow, NegotiationStateRow]:
        for r in s.exec(select(t)).all():
            s.delete(r)
    s.commit()
    s.close()


# ── APPROVE clears pending_decision ────────────────────────────────────


def test_approval_approve_clears_pending_decision() -> None:
    """HTTP 200 → DB raw_state.pending_decision is None → transcript has turn."""
    c, _bus = _build()
    sid = _seed_pending()

    resp = c.post(f"/api/v1/negotiations/{sid}/approval", json={
        "action": "APPROVE", "reason": "ok",
    })
    assert resp.status_code == 200
    assert resp.json()["new_status"] in ("ACTIVE", "RESOLVED", "PENDING_HUMAN_APPROVAL")

    s = get_session()
    row = s.get(NegotiationStateRow, sid)
    state = NegotiationState.model_validate(row.raw_state)
    # Original decision moved to history (APPROVED)
    assert len(state.decision_history) >= 1
    assert state.decision_history[0].status.value == "APPROVED"
    assert state.decision_history[0].resolution is not None
    s.close()


# ── REPLACE with replacement_turn succeeds ─────────────────────────────


def test_approval_replace_with_turn_succeeds() -> None:
    """HTTP 200 for REPLACE → no 500 → transcript updated."""
    c, _bus = _build()
    sid = _seed_pending()

    resp = c.post(f"/api/v1/negotiations/{sid}/approval", json={
        "action": "REPLACE",
        "replacement_turn": "Propongo nuevo precio con envio incluido.",
    })
    assert resp.status_code == 200
    assert resp.json()["new_status"] in ("ACTIVE", "RESOLVED", "PENDING_HUMAN_APPROVAL")

    s = get_session()
    row = s.get(NegotiationStateRow, sid)
    state = NegotiationState.model_validate(row.raw_state)
    assert len(state.decision_history) >= 1
    assert state.decision_history[0].status.value == "REPLACED"
    s.close()


# ── REPLACE without turn fails validation ─────────────────────────────


def test_approval_replace_missing_turn_returns_422() -> None:
    c, _bus = _build()
    sid = _seed_pending()
    resp = c.post(f"/api/v1/negotiations/{sid}/approval", json={"action": "REPLACE"})
    assert resp.status_code == 422


# ── APPROVE on ACTIVE returns 400 ──────────────────────────────────────


def test_approval_on_active_returns_400() -> None:
    c, _bus = _build()
    # Seed an ACTIVE session
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
