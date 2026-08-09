"""Tests for WebhookSecretFetcher — RED phase (tests written first)."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from transport.secret_fetcher import WebhookSecretFetcher


# ── Helpers ───────────────────────────────────────────────────────────────


def _secret_response(secret: str = "whsec_test_123") -> httpx.Response:
    return httpx.Response(200, json={"secret": secret})


# ── Happy path ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_secret_on_first_call_caches_and_returns() -> None:
    """First get_secret() fetches from Portal API and caches the result."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _secret_response("whsec_first_call")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        fetcher = WebhookSecretFetcher(secret_key="sk_test", client=client)

        secret = await fetcher.get_secret()
        assert secret == "whsec_first_call"
        assert len(requests) == 1
        assert requests[0].method == "GET"
        assert "Authorization" in requests[0].headers

        # Second call returns cached value without another request
        secret2 = await fetcher.get_secret()
        assert secret2 == "whsec_first_call"
        assert len(requests) == 1  # still only 1 request


@pytest.mark.asyncio
async def test_fetch_secret_returns_none_on_http_connect_error() -> None:
    """When Portal API is unreachable, get_secret() returns None (fail closed)."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        fetcher = WebhookSecretFetcher(secret_key="sk_test", client=client)
        secret = await fetcher.get_secret()
        assert secret is None


@pytest.mark.asyncio
async def test_fetch_secret_returns_none_on_http_error() -> None:
    """When Portal API returns non-200, get_secret() returns None."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "internal"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        fetcher = WebhookSecretFetcher(secret_key="sk_test", client=client)
        secret = await fetcher.get_secret()
        assert secret is None


@pytest.mark.asyncio
async def test_fetch_secret_returns_none_on_malformed_json() -> None:
    """Portal API returns 200 but secret missing → None."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"wrong_field": "no_secret_here"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        fetcher = WebhookSecretFetcher(secret_key="sk_test", client=client)
        secret = await fetcher.get_secret()
        assert secret is None


@pytest.mark.asyncio
async def test_invalidate_clears_cache_for_next_fetch() -> None:
    """After invalidation, next get_secret() re-fetches from Portal."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return _secret_response(f"whsec_call_{call_count}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        # Zero cooldown → invalidate re-fetches immediately
        fetcher = WebhookSecretFetcher(secret_key="sk_test", client=client, cooldown_seconds=0)

        secret1 = await fetcher.get_secret()
        assert secret1 == "whsec_call_1"
        assert call_count == 1

        # Second call: cached
        secret1b = await fetcher.get_secret()
        assert secret1b == "whsec_call_1"
        assert call_count == 1

        # Invalidate → re-fetches immediately (cooldown=0)
        fetcher.invalidate()
        secret2 = await fetcher.get_secret()
        assert secret2 == "whsec_call_2"
        assert call_count == 2


@pytest.mark.asyncio
async def test_cooldown_prevents_refetch_within_window() -> None:
    """Within cooldown, invalidated cache returns stale; after cooldown, re-fetches."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return _secret_response(f"whsec_call_{call_count}")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        # Short cooldown: 0.5s
        fetcher = WebhookSecretFetcher(secret_key="sk_test", client=client, cooldown_seconds=0.5)

        secret1 = await fetcher.get_secret()
        assert secret1 == "whsec_call_1"
        assert call_count == 1

        # Invalidate — within cooldown returns stale
        fetcher.invalidate()
        secret2 = await fetcher.get_secret()
        assert secret2 == "whsec_call_1"  # stale cached value
        assert call_count == 1  # no new request

        # Wait out cooldown
        await asyncio.sleep(0.6)
        secret3 = await fetcher.get_secret()
        assert secret3 == "whsec_call_2"  # fresh fetch
        assert call_count == 2
