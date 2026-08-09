"""TDD: AI engine reconciliation edge cases — B1 (DecisionKind), B2 (disclosures)."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from ai.domain.models import (
    AgentProfile, AgentTurn, DecisionKind, DecisionReason,
    DecisionRequest, EntityType, NegotiationState,
    SessionStatus, TurnIntent,
)
from api.app import create_app
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

    class FakeSecret:
        async def get_secret(self):
            return "t"

    from ai.providers.fake import ScriptedLLMProvider
    from ai.engine.graph import NegotiationEngine
    from ai.domain.models import AgentTurn, TurnIntent

    turn = AgentTurn(public_message="turno de prueba", intent=TurnIntent.OFFER)
    app = create_app(secret_provider=FakeSecret(), bus=bus)
    app.state.engine = NegotiationEngine(ScriptedLLMProvider([turn] * 20))
    return TestClient(app), bus


def _seed(session, kind=DecisionKind.OUTBOUND_TURN):
    a1 = UUID("d0000000-0000-0000-0000-000000000001")
    a2 = UUID("d0000000-0000-0000-0000-000000000002")
    sid = UUID("d0000000-0000-0000-0000-000000000100")
    p1 = AgentProfile(agent_id=a1, display_name="A", entity_type=EntityType.PERSON,
                      public_description="t", personality="t", objectives=["t"])
    p2 = AgentProfile(agent_id=a2, display_name="B", entity_type=EntityType.PERSON,
                      public_description="t", personality="t", objectives=["t"])
    create_agent_profile(p1, user_id=uuid4(), session=session)
    create_agent_profile(p2, user_id=uuid4(), session=session)
    turn = AgentTurn(public_message="oferta: 900 USD", intent=TurnIntent.OFFER)
    dec = DecisionRequest(
        session_id=sid, owner_agent_id=a1, requester_agent_id=a2,
        kind=kind, reasons=[DecisionReason.USER_RULE], candidate_turn=turn,
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
    session.add(row)
    session.commit()
    return sid


@pytest.fixture(autouse=True)
def clean():
    init_db()
    s = get_session()
    for t in [AgentProfileRow, NegotiationStateRow]:
        for r in s.exec(select(t)).all():
            s.delete(r)
    s.commit()
    s.close()


# ── B1: REPLACE with replacement_turn works ────────────────────────────


def test_approval_endpoint_handles_replacement_turn_as_agent_turn():
    """REPLACE with replacement_turn → 200, engine resumes."""
    c, _bus = _build()
    s = get_session()
    sid = _seed(s)
    s.close()

    resp = c.post(f"/api/v1/negotiations/{sid}/approval", json={
        "action": "REPLACE",
        "replacement_turn": "Ofrezco un mejor precio con envio incluido.",
    })
    assert resp.status_code == 200
    assert resp.json()["new_status"] in ("ACTIVE", "RESOLVED", "PENDING_HUMAN_APPROVAL")


# ── B1: APPROVE on OUTBOUND_TURN works ────────────────────────────────


def test_approval_endpoint_handles_outbound_turn_decision_kind():
    """APPROVE on OUTBOUND_TURN → 200, engine clears pending."""
    c, _bus = _build()
    s = get_session()
    sid = _seed(s, kind=DecisionKind.OUTBOUND_TURN)
    s.close()

    resp = c.post(f"/api/v1/negotiations/{sid}/approval", json={
        "action": "APPROVE", "reason": "looks good",
    })
    assert resp.status_code == 200


# ── B2: proposed_disclosures works ────────────────────────────────────


def test_escalation_evaluator_reads_proposed_disclosures():
    """EscalationEvaluator should handle AgentTurn with proposed_disclosures."""
    from ai.policies.escalation import EscalationEvaluator

    evaluator = EscalationEvaluator()
    profile = AgentProfile(
        display_name="Test", entity_type=EntityType.PERSON,
        public_description="t", personality="t", objectives=["t"],
    )
    turn = AgentTurn(
        public_message="mi telefono es 3001234567",
        intent=TurnIntent.OFFER,
        proposed_disclosures=[],  # no disclosure → no escalation
    )
    result = evaluator.evaluate(profile, turn)
    assert not result.required  # no PII → no escalation
