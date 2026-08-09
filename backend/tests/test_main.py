"""Tests for backend main entry point and health endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from transport.bus import DurableEventBus
from transport.portal import WebhookSecretProvider


class FakeBus(DurableEventBus):  # type: ignore[misc]
    async def accept(self, envelope): pass
    async def receive(self, consumer, lease_ms): return None
    async def ack(self, delivery): pass
    async def fail(self, delivery, code): pass


class FakeSecretProvider(WebhookSecretProvider):
    async def get_secret(self) -> str | None:
        return "test-secret"


def _build_test_app() -> TestClient:
    app = create_app(
        secret_provider=FakeSecretProvider(),
        bus=FakeBus(),
    )
    return TestClient(app)


def test_health_endpoint_returns_200_with_status_and_version() -> None:
    """GET /health returns 200 with { status: ok, version: 0.1.0 }."""
    client = _build_test_app()
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"status": "ok", "version": "0.1.0"}


def test_main_app_imports_without_error(monkeypatch) -> None:
    """GREEN: main.py exports a FastAPI 'app' without import errors."""
    monkeypatch.setenv("PORTAL_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-dummy-for-tests")
    monkeypatch.setenv("AGENTSYNC_LLM_PROVIDER", "fake")

    with (
        patch("redis.asyncio.from_url", return_value=AsyncMock()),
    ):
        from main import app  # noqa: F811
        assert app is not None
        assert app.title == "AgentSync API"
