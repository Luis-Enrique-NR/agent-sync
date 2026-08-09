"""Pure Portal webhook signature verification and event normalization."""

from __future__ import annotations

import hmac
from datetime import datetime, timezone
from hashlib import sha256

from ai.integration.events import SUPPORTED_INTEGRATION_EVENTS
from transport.models import PortalEvent, TransportEnvelopeV1


def _parse_signature_header(header: str | None) -> tuple[int, str] | None:
    if not header:
        return None
    try:
        pairs = dict(part.strip().split("=", 1) for part in header.split(","))
        return int(pairs["t"]), pairs["v1"]
    except (ValueError, KeyError):
        return None


def _sign(secret: str, timestamp: int, raw_body: bytes) -> str:
    payload = f"{timestamp}.".encode("utf-8") + raw_body
    return hmac.new(secret.encode("utf-8"), payload, sha256).hexdigest()


def verify_portal_signature(
    raw_body: bytes,
    header: str | None,
    secret: str,
    now: datetime | None = None,
    tolerance_seconds: int = 300,
) -> bool:
    """Verify a Portal HMAC-SHA256 signature over exact raw request bytes."""
    parsed = _parse_signature_header(header)
    if parsed is None:
        return False
    timestamp, expected = parsed
    if not expected:
        return False
    now = now or datetime.now(timezone.utc)
    if abs(now.timestamp() - timestamp) > tolerance_seconds:
        return False
    return hmac.compare_digest(_sign(secret, timestamp, raw_body), expected)


def normalize_event(data: dict) -> TransportEnvelopeV1 | None:
    """Turn a verified Portal payload into a transport envelope, or None if unsupported."""
    event = PortalEvent.model_validate(data)
    if event.type not in SUPPORTED_INTEGRATION_EVENTS:
        return None
    published = event.type == "message.published"
    if published and event.message is None:
        raise ValueError("published event requires a message")
    if event.type == "message.retracted" and event.message is not None:
        raise ValueError("retracted event must have a null message")
    if not published and event.type != "message.retracted" and event.message is not None:
        raise ValueError("lifecycle event must not contain a message")
    return TransportEnvelopeV1(
        event_id=event.id,
        event_type=event.type,
        event_time=event.time,
        environment=event.environment,
        channel=event.channel,
        message=event.message if published else None,
        retracted=event.type == "message.retracted",
    )
