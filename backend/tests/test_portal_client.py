import json

import httpx
import pytest
from pydantic import ValidationError

from transport.fake_portal import RecordingPortalAdmin
from transport.portal import (
    AddChannelMembers,
    BanChannelUser,
    CommandApplied,
    HttpPortalClient,
    PortalRejected,
    PortalRetryable,
    PortalUncertain,
    PublishedMessage,
    PublishMessage,
    RemoveChannelMember,
    TokenResponse,
    UnbanChannelUser,
    parse_authorized_command,
)


def publish() -> PublishMessage:
    return PublishMessage(
        authorization_id="auth_1",
        channel_id="channel_1",
        sender_id="server",
        content={"text": "hello"},
        type="system",
    )


def add_members() -> AddChannelMembers:
    return AddChannelMembers(
        authorization_id="auth_1",
        channel_id="channel /one",
        members=[{"user_id": "user /one", "claims": {"role": "member"}}, {"user_id": "user_2"}],
    )


@pytest.mark.asyncio
async def test_documented_authorized_publish_uses_control_plane_contract() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "message_1", "seq": 7, "timestamp": 123})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.useportal.co") as client:
        outcome = await HttpPortalClient("test-secret", client).execute(publish())

    assert outcome.id == "message_1" and outcome.seq == 7
    assert requests[0].method == "POST" and requests[0].url.path == "/v1/channels/channel_1/messages"
    assert requests[0].headers["authorization"] == "Bearer test-secret"
    assert json.loads(requests[0].content) == {"senderId": "server", "content": {"text": "hello"}, "type": "system", "kind": "text"}


@pytest.mark.asyncio
async def test_unknown_or_undocumented_shape_makes_zero_adapter_or_http_calls() -> None:
    fake = RecordingPortalAdmin()
    requests: list[httpx.Request] = []
    with pytest.raises(ValidationError):
        parse_authorized_command({"operation": "ban", "authorization_id": "auth_1", "channel_id": "channel_1", "user_id": "user_1"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: requests.append(request)), base_url="https://api.useportal.co") as client:
        assert not fake.calls and not requests
        outcome = await fake.execute(publish())
        assert isinstance(outcome, PublishedMessage) and outcome.id == "fake-1"
        assert len(fake.calls) == 1 and not requests


@pytest.mark.asyncio
async def test_mutating_timeout_is_uncertain_and_never_retried() -> None:
    calls = 0

    def timeout(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("timed out")

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout), base_url="https://api.useportal.co") as client:
        outcome = await HttpPortalClient("test-secret", client).execute(publish())

    assert isinstance(outcome, PortalUncertain) and calls == 1


@pytest.mark.asyncio
async def test_documented_access_commands_use_typed_control_plane_contracts() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/members"):
            return httpx.Response(200, json={"added": 2})
        return httpx.Response(200, json={})

    commands = [
        add_members(),
        RemoveChannelMember(authorization_id="auth_1", channel_id="channel /one", user_id="user /one"),
        BanChannelUser(authorization_id="auth_1", channel_id="channel /one", user_id="user /one", expires_at="2026-08-09T10:00:00Z"),
        UnbanChannelUser(authorization_id="auth_1", channel_id="channel /one", user_id="user /one"),
    ]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.useportal.co") as client:
        outcomes = [await HttpPortalClient("test-secret", client).execute(command) for command in commands]

    assert outcomes == [
        CommandApplied(operation="add_members", added=2),
        CommandApplied(operation="remove_member"),
        CommandApplied(operation="ban_user"),
        CommandApplied(operation="unban_user"),
    ]
    assert [(request.method, request.url.raw_path.decode()) for request in requests] == [
        ("POST", "/v1/channels/channel%20%2Fone/members"),
        ("DELETE", "/v1/channels/channel%20%2Fone/members/user%20%2Fone"),
        ("POST", "/v1/channels/channel%20%2Fone/bans"),
        ("DELETE", "/v1/channels/channel%20%2Fone/bans/user%20%2Fone"),
    ]
    assert json.loads(requests[0].content) == {"members": [{"userId": "user /one", "claims": {"role": "member"}}, {"userId": "user_2"}]}
    assert json.loads(requests[2].content) == {"userId": "user /one", "expiresAt": "2026-08-09T10:00:00Z"}
    assert all(request.headers["authorization"] == "Bearer test-secret" for request in requests)


@pytest.mark.asyncio
async def test_single_member_fake_parity_and_structured_portal_error() -> None:
    fake = RecordingPortalAdmin()
    command = AddChannelMembers(authorization_id="auth_1", channel_id="channel_1", members=[{"user_id": "user_1"}])
    assert await fake.execute(command) == CommandApplied(operation="add_members", added=1)
    assert fake.calls == [command]

    async def error_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"code": "forbidden", "reason": "not allowed"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(error_handler), base_url="https://api.useportal.co") as client:
        outcome = await HttpPortalClient("test-secret", client).execute(command)
    assert outcome == PortalRejected(code="forbidden", reason="not allowed")


@pytest.mark.asyncio
async def test_single_member_uses_documented_single_member_body() -> None:
    requests: list[httpx.Request] = []
    command = AddChannelMembers(
        authorization_id="auth_1",
        channel_id="channel_1",
        members=[{"user_id": "user_1", "claims": {"role": "member"}}],
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"added": 1})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.useportal.co") as client:
        outcome = await HttpPortalClient("test-secret", client).execute(command)

    assert outcome == CommandApplied(operation="add_members", added=1)
    assert json.loads(requests[0].content) == {"userId": "user_1", "claims": {"role": "member"}}


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{}, {"added": True}, {"added": "1"}])
async def test_add_members_rejects_malformed_success_response(payload: dict[str, object]) -> None:
    command = AddChannelMembers(authorization_id="auth_1", channel_id="channel_1", members=[{"user_id": "user_1"}])
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)), base_url="https://api.useportal.co") as client:
        outcome = await HttpPortalClient("test-secret", client).execute(command)
    assert outcome == PortalRejected(code="invalid_response", reason="missing or non-integer added")


@pytest.mark.asyncio
@pytest.mark.parametrize(("status_code", "code"), [(429, "rate_limited"), (503, "transient")])
async def test_transient_portal_responses_are_retryable_without_automatic_retry(status_code: int, code: str) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status_code, json={"code": "unavailable"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.useportal.co") as client:
        outcome = await HttpPortalClient("test-secret", client).execute(publish())
    assert outcome == PortalRetryable(code=code)
    assert calls == 1


# ── Mint token RED tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mint_token_returns_token_and_expiry() -> None:
    """mint_token() calls POST /v1/tokens with userId and returns TokenResponse."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"token": "tok_abc123", "expiresAt": "2026-08-10T00:00:00Z"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.useportal.co") as client:
        outcome = await HttpPortalClient("test-secret", client).mint_token(user_id="user-1")

    assert isinstance(outcome, TokenResponse)
    assert outcome.token == "tok_abc123"
    assert outcome.expires_at == "2026-08-10T00:00:00Z"
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/v1/tokens"
    assert requests[0].headers["authorization"] == "Bearer test-secret"
    assert json.loads(requests[0].content) == {"userId": "user-1", "ttl": "1h"}


@pytest.mark.asyncio
async def test_mint_token_with_optional_fields() -> None:
    """mint_token() sends claims, channels, and ttl when provided."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"token": "tok_xyz", "expiresAt": "2026-08-10T01:00:00Z"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.useportal.co") as client:
        outcome = await HttpPortalClient("test-secret", client).mint_token(
            user_id="user-2",
            claims={"role": "admin"},
            channels={"ch_1": "read"},
            ttl="2h",
        )

    assert outcome.token == "tok_xyz"
    assert outcome.expires_at == "2026-08-10T01:00:00Z"
    body = json.loads(requests[0].content)
    assert body["userId"] == "user-2"
    assert body["claims"] == {"role": "admin"}
    assert body["channels"] == {"ch_1": "read"}
    assert body["ttl"] == "2h"


@pytest.mark.asyncio
async def test_mint_token_rejected_on_error_response() -> None:
    """mint_token() returns PortalRejected on non-200 response."""
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"code": "unauthorized", "reason": "invalid secret"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://api.useportal.co") as client:
        outcome = await HttpPortalClient("test-secret", client).mint_token(user_id="user-1")

    assert isinstance(outcome, PortalRejected)
    assert outcome.code == "unauthorized"
    assert outcome.reason == "invalid secret"


@pytest.mark.asyncio
async def test_mint_token_timeout_returns_uncertain() -> None:
    """mint_token() returns PortalUncertain on timeout."""
    calls = 0

    def timeout(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("timed out")

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout), base_url="https://api.useportal.co") as client:
        outcome = await HttpPortalClient("test-secret", client).mint_token(user_id="user-1")

    assert isinstance(outcome, PortalUncertain)
    assert calls == 1
