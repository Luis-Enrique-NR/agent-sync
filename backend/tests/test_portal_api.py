import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from transport.config import TransportSettings
from transport.models import TransportEnvelopeV1
from test_portal_webhooks import SECRET, event, sign

NOW = datetime(2026, 8, 7, 12, tzinfo=timezone.utc)


class FakeSecret:
    def __init__(self, value: str | None = SECRET): self.value = value
    async def get_secret(self) -> str | None: return self.value


class FakeBus:
    def __init__(self, failing: bool = False): self.items: list[TransportEnvelopeV1] = []; self.failing = failing
    async def accept(self, envelope: TransportEnvelopeV1) -> None:
        if self.failing: raise RuntimeError("unavailable")
        self.items.append(envelope)


def client(secret: str | None = SECRET, failing: bool = False) -> tuple[TestClient, FakeBus]:
    bus = FakeBus(failing)
    app = create_app(TransportSettings(300), FakeSecret(secret), bus, lambda: NOW)
    return TestClient(app), bus


def post(tc: TestClient, payload: dict, raw: bytes | None = None, timestamp: int | None = None):
    raw = raw or json.dumps(payload).encode()
    timestamp = timestamp or int(NOW.timestamp())
    return tc.post("/webhooks/portal", content=raw, headers={"portal-signature": sign(raw, timestamp)})


@pytest.mark.parametrize("raw,header,status", [(b'{"bad":', None, 401), (b'{"bad":', "bad", 401), (b'{"bad":', "stale", 401)])
def test_rejects_before_parse_or_enqueue(raw: bytes, header: str | None, status: int) -> None:
    tc, bus = client()
    if header == "stale": header = sign(raw, int((NOW - timedelta(seconds=301)).timestamp()))
    response = tc.post("/webhooks/portal", content=raw, headers={} if header is None else {"portal-signature": header})
    assert response.status_code == status and not bus.items


def test_admission_statuses_and_writes_are_closed_to_the_bus() -> None:
    message = {"id": "m1", "text": "hello", "author_id": "u1", "seq": 1}
    tc, bus = client()
    assert post(tc, event("message.published", message)).status_code == 200
    assert post(tc, event("message.retracted", None)).status_code == 200
    assert post(tc, event("message.edited", message)).status_code == 200
    assert len(bus.items) == 2 and bus.items[1].retracted
    raw = json.dumps(event("message.published", message)).encode()
    assert tc.post("/webhooks/portal", content=raw + b"x", headers={"portal-signature": sign(raw, int(NOW.timestamp()))}).status_code == 401
    malformed = b'{"id":"event"}'
    assert tc.post("/webhooks/portal", content=malformed, headers={"portal-signature": sign(malformed, int(NOW.timestamp()))}).status_code == 400
    assert client(None)[0].post("/webhooks/portal").status_code == 503
    assert post(client(failing=True)[0], event("message.published", message)).status_code == 503
