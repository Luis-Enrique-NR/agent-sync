"""Integration tests for the Frontend REST API endpoints."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from api.app import create_app
from ai.domain.models import AgentProfile, AgentStatus, EntityType, SessionStatus
from persistence.database import get_session, init_db
from persistence.models import AgentProfileRow, NegotiationStateRow
from persistence.repository import create_agent_profile, save_negotiation_state
from transport.fake_portal import RecordingPortalAdmin


def _build_test_app() -> TestClient:
    """Build FastAPI TestClient with fake dependencies."""
    from transport.bus import DurableEventBus

    class FakeBus(DurableEventBus):  # type: ignore[misc]
        async def accept(self, envelope): pass
        async def receive(self, consumer, lease_ms): return None
        async def ack(self, delivery): pass
        async def fail(self, delivery, code): pass

    class FakeSecretProvider:
        async def get_secret(self): return "test-secret"

    app = create_app(
        secret_provider=FakeSecretProvider(),
        bus=FakeBus(),
    )
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_db() -> None:
    init_db()
    session = get_session()
    for table in [AgentProfileRow, NegotiationStateRow]:
        rows = session.exec(select(table)).all()
        for r in rows:
            session.delete(r)
    session.commit()
    session.close()


@pytest.fixture
def client() -> TestClient:
    init_db()
    return _build_test_app()


# ── Agent endpoints ────────────────────────────────────────────────────


def test_register_agent_returns_201(client: TestClient) -> None:
    resp = client.post("/api/v1/agents", json={
        "display_name": "TestAgent",
        "entity_type": "person",
        "public_description": "A test agent",
        "personality": "friendly",
        "objectives": ["test"],
        "interests": ["buy_bike"],
        "capabilities": ["cash"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["display_name"] == "TestAgent"
    assert data["status"] == "AVAILABLE"
    assert "agent_id" in data


def test_register_agent_invalid_entity_type_returns_422(client: TestClient) -> None:
    resp = client.post("/api/v1/agents", json={
        "display_name": "Bad",
        "entity_type": "corp",
        "public_description": "test",
        "personality": "test",
        "objectives": ["test"],
    })
    assert resp.status_code == 422


def test_get_agent_returns_200(client: TestClient) -> None:
    session = get_session()
    profile = AgentProfile(
        display_name="Existing", entity_type=EntityType.PERSON,
        public_description="t", personality="t", objectives=["t"],
    )
    row = create_agent_profile(profile, user_id=uuid4(), session=session)
    session.commit()
    aid = str(row.agent_id)
    session.close()

    resp = client.get(f"/api/v1/agents/{aid}")
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Existing"


def test_get_agent_not_found_returns_404(client: TestClient) -> None:
    resp = client.get(f"/api/v1/agents/{uuid4()}")
    assert resp.status_code == 404


def test_list_agents(client: TestClient) -> None:
    session = get_session()
    for i in range(3):
        p = AgentProfile(display_name=f"A{i}", entity_type=EntityType.PERSON,
                         public_description="t", personality="t", objectives=["t"])
        create_agent_profile(p, user_id=uuid4(), session=session)
    session.commit()
    session.close()

    resp = client.get("/api/v1/agents")
    assert resp.status_code == 200
    assert resp.json()["total"] == 3


# ── Negotiation endpoints ──────────────────────────────────────────────


def _seed_session() -> tuple[UUID, UUID, UUID]:
    session = get_session()
    a1 = UUID("b0000000-0000-0000-0000-000000000001")
    a2 = UUID("b0000000-0000-0000-0000-000000000002")
    sid = UUID("b0000000-0000-0000-0000-000000000100")

    p1 = AgentProfile(agent_id=a1, display_name="A1", entity_type=EntityType.PERSON,
                      public_description="t", personality="t", objectives=["t"])
    p2 = AgentProfile(agent_id=a2, display_name="A2", entity_type=EntityType.PERSON,
                      public_description="t", personality="t", objectives=["t"])
    create_agent_profile(p1, user_id=uuid4(), session=session)
    create_agent_profile(p2, user_id=uuid4(), session=session)
    session.flush()

    from ai.domain.models import NegotiationState
    state = NegotiationState(
        session_id=sid,
        agents=(p1, p2),
        current_speaker_id=a1,
        status="ACTIVE",  # type: ignore[arg-type]
        deadline_at="2099-01-01T00:00:00Z",  # type: ignore[arg-type]
    )
    row = NegotiationStateRow(
        session_id=sid,
        agent_1_id=a1, agent_2_id=a2, initiator_id=a1,
        current_speaker_id=a1,
        status="ACTIVE",
        raw_state=state.model_dump(mode="json"),
    )
    session.add(row)
    session.commit()
    session.close()
    return a1, a2, sid


def test_list_negotiations_by_agent(client: TestClient) -> None:
    a1, _a2, _sid = _seed_session()
    resp = client.get(f"/api/v1/negotiations?agent_id={a1}")
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_get_negotiation_detail(client: TestClient) -> None:
    _a1, _a2, sid = _seed_session()
    resp = client.get(f"/api/v1/negotiations/{sid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ACTIVE"
    assert "transcript" in data


def test_get_negotiation_not_found(client: TestClient) -> None:
    resp = client.get(f"/api/v1/negotiations/{uuid4()}")
    assert resp.status_code == 404


def test_submit_decision_on_active_fails(client: TestClient) -> None:
    _a1, _a2, sid = _seed_session()
    resp = client.post(f"/api/v1/negotiations/{sid}/approval", json={
        "action": "APPROVE",
    })
    assert resp.status_code == 400


def test_audit_trail(client: TestClient) -> None:
    _a1, _a2, sid = _seed_session()
    resp = client.get(f"/api/v1/negotiations/{sid}/audit")
    assert resp.status_code == 200
    assert "records" in resp.json()
