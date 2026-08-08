import hmac
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from transport.models import TransportEnvelopeV1
from transport.webhooks import normalize_event, verify_portal_signature

SECRET = "portal-test-secret"
NOW = datetime(2026, 8, 7, 12, tzinfo=timezone.utc)


def sign(raw: bytes, timestamp: int) -> str:
    digest = hmac.new(SECRET.encode(), f"{timestamp}.".encode() + raw, sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def event(type_: str, message: dict | None) -> dict:
    return {"id": "evt_1", "type": type_, "time": NOW.isoformat(), "environment": "test", "channel": "ch_1", "message": message}


def test_signature_requires_current_exact_bytes_and_valid_header() -> None:
    raw, timestamp = b'{"id":"evt_1"}', int(NOW.timestamp())
    assert verify_portal_signature(raw, sign(raw, timestamp), SECRET, NOW)
    for header, body in [(None, raw), ("bad", raw), (sign(raw, timestamp), raw + b"x"), (sign(raw, timestamp - 301), raw)]:
        assert not verify_portal_signature(body, header, SECRET, NOW)


def test_normalizes_only_published_and_audit_retracted() -> None:
    message = {"id": "m1", "text": "hello", "author_id": "u1", "seq": 1}
    published = normalize_event(event("message.published", message))
    retracted = normalize_event(event("message.retracted", None))
    assert isinstance(published, TransportEnvelopeV1) and published.message.model_dump() == message
    assert isinstance(retracted, TransportEnvelopeV1) and retracted.retracted and retracted.message is None
    assert normalize_event(event("message.edited", message)) is None


@pytest.mark.parametrize("type_,message", [("message.published", None), ("message.retracted", {"id": "m1", "text": "x", "author_id": "u1", "seq": 1})])
def test_rejects_invalid_supported_shapes(type_: str, message: dict | None) -> None:
    with pytest.raises(ValueError):
        normalize_event(event(type_, message))
