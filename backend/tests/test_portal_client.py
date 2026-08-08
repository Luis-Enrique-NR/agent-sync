import json

import httpx
import pytest
from pydantic import ValidationError

from transport.fake_portal import RecordingPortalAdmin
from transport.portal import HttpPortalClient, PortalUncertain, PublishedMessage, PublishMessage, parse_authorized_command


def publish() -> PublishMessage:
    return PublishMessage(
        authorization_id="auth_1",
        channel_id="channel_1",
        sender_id="server",
        content={"text": "hello"},
        type="system",
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
