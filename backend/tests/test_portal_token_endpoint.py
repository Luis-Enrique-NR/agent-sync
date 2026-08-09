"""Tests for GET /api/portal-token endpoint — RED phase (tests written first)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from transport.bus import DurableEventBus
from transport.portal import PortalRejected, PortalUncertain, TokenResponse, WebhookSecretProvider


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
        portal_secret="sk_test_portal",
    )
    return TestClient(app)


# ── Happy path ──────────────────────────────────────────────────────────


def test_portal_token_endpoint_returns_token() -> None:
    """GET /api/portal-token?userId=test returns 200 with token and expiresAt."""
    mock_token = TokenResponse(token="tok_test_123", expires_at="2026-08-10T00:00:00Z")

    with patch("api.app.HttpPortalClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.mint_token = AsyncMock(return_value=mock_token)

        client = _build_test_app()
        resp = client.get("/api/portal-token?userId=user-1")

    assert resp.status_code == 200
    data = resp.json()
    assert data == {"token": "tok_test_123", "expiresAt": "2026-08-10T00:00:00Z"}
    instance.mint_token.assert_awaited_once_with(user_id="user-1")


# ── Error paths ──────────────────────────────────────────────────────────


def test_portal_token_endpoint_missing_user_id_returns_400() -> None:
    """GET /api/portal-token without userId returns 400."""
    client = _build_test_app()
    resp = client.get("/api/portal-token")
    assert resp.status_code == 400
    assert "userId" in resp.json()["detail"]


def test_portal_token_endpoint_propagates_portal_rejected_as_502() -> None:
    """When mint_token returns PortalRejected, endpoint returns 502."""
    mock_error = PortalRejected(code="forbidden", reason="not allowed")

    with patch("api.app.HttpPortalClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.mint_token = AsyncMock(return_value=mock_error)

        client = _build_test_app()
        resp = client.get("/api/portal-token?userId=user-1")

    assert resp.status_code == 502
    data = resp.json()
    assert data["detail"]["code"] == "forbidden"
    assert data["detail"]["reason"] == "not allowed"


def test_portal_token_endpoint_propagates_portal_uncertain_as_504() -> None:
    """When mint_token returns PortalUncertain, endpoint returns 504."""
    mock_error = PortalUncertain()

    with patch("api.app.HttpPortalClient") as MockClient:
        instance = MockClient.return_value
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=None)
        instance.mint_token = AsyncMock(return_value=mock_error)

        client = _build_test_app()
        resp = client.get("/api/portal-token?userId=user-1")

    assert resp.status_code == 504
    data = resp.json()
    assert "retry" in data["detail"].lower()
