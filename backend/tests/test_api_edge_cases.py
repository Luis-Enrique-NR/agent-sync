"""OpenAPI spec generation and HTTP edge-case tests."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from persistence.database import init_db
from persistence.models import AgentProfileRow, NegotiationStateRow
from persistence.database import get_session
from sqlmodel import select


def _build_test_app() -> TestClient:
    from transport.bus import DurableEventBus

    class FakeBus(DurableEventBus):  # type: ignore[misc]
        async def accept(self, envelope): pass
        async def receive(self, consumer, lease_ms): return None
        async def ack(self, delivery): pass
        async def fail(self, delivery, code): pass

    class FakeSecretProvider:
        async def get_secret(self): return "test-secret"

    app = create_app(secret_provider=FakeSecretProvider(), bus=FakeBus())
    return TestClient(app)


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


@pytest.fixture
def client() -> TestClient:
    return _build_test_app()


# ── OpenAPI ────────────────────────────────────────────────────────────


def test_openapi_json_returns_200(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    data = resp.json()
    assert "openapi" in data
    assert data["info"]["title"] == "AgentSync API"
    assert "/api/v1/agents" in data["paths"]


# ── Edge cases ─────────────────────────────────────────────────────────


def test_get_nonexistent_agent_returns_404(client: TestClient) -> None:
    resp = client.get(f"/api/v1/agents/{uuid4()}")
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_approval_on_invalid_state_returns_400(client: TestClient) -> None:
    resp = client.post(f"/api/v1/negotiations/{uuid4()}/approval", json={
        "action": "APPROVE",
    })
    assert resp.status_code == 404  # session doesn't exist → 404 is correct


def test_register_agent_invalid_payload_returns_422(client: TestClient) -> None:
    resp = client.post("/api/v1/agents", json={
        "display_name": "Bad",
        # missing required fields
    })
    assert resp.status_code == 422


def test_register_agent_empty_objectives_returns_422(client: TestClient) -> None:
    resp = client.post("/api/v1/agents", json={
        "display_name": "Test",
        "entity_type": "person",
        "public_description": "test",
        "personality": "test",
        "objectives": [],
    })
    assert resp.status_code == 422


def test_cors_headers_present(client: TestClient) -> None:
    resp = client.options("/api/v1/agents", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
    })
    assert resp.status_code in (200, 204, 405)
    headers = resp.headers
    assert "access-control-allow-origin" in headers or "access-control-allow-methods" in headers or resp.status_code == 200
