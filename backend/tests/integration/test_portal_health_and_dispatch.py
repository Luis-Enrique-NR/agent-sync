"""Portal health and dispatch integration tests — connectivity, envelope, failback."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from transport.models import TransportEnvelopeV1, MessageSnapshot
from transport.bus import EventDelivery
from transport.webhooks import normalize_event, verify_portal_signature

logger = logging.getLogger(__name__)


# ── Portal health probe ────────────────────────────────────────────────


def test_portal_connectivity_diagnostic():
    """Probe Portal adapter availability and log status."""
    # The transport layer has a fake Portal for tests; the real Portal
    # requires deployed infrastructure.  This test verifies the adapter
    # contract works in offline mode.
    from transport.fake_portal import RecordingPortalAdmin
    from transport.portal import (
        PublishMessage, AddChannelMembers, ChannelMember, CommandApplied,
    )

    portal = RecordingPortalAdmin()

    # Publish message
    cmd = PublishMessage(
        authorization_id="auth_1",
        channel_id="ch_test",
        sender_id="agent_1",
        content={"text": "hello"},
    )
    import asyncio
    result = asyncio.run(portal.execute(cmd))
    logger.info(
        "[PORTAL_DIAGNOSTIC] Status: CONNECTED (fake) | AdapterMode: RecordingPortalAdmin | publish=%s",
        result.id,
    )
    assert result.id == "fake-1"

    # Add members
    cmd2 = AddChannelMembers(
        authorization_id="auth_1",
        channel_id="ch_test",
        members=[ChannelMember(user_id="agent_1"), ChannelMember(user_id="agent_2")],
    )
    result2 = asyncio.run(portal.execute(cmd2))
    assert isinstance(result2, CommandApplied)
    assert result2.added == 2

    assert len(portal.calls) == 2
    logger.info("[PORTAL_DIAGNOSTIC] All portal commands dispatched successfully")


# ── Envelope schema validation ─────────────────────────────────────────


def test_transport_envelope_schema_valid():
    """Verify TransportEnvelopeV1 schema matches Portal contract."""
    envelope = TransportEnvelopeV1(
        event_id="evt_test_001",
        event_type="message.published",  # type: ignore[arg-type]
        event_time=datetime.now(timezone.utc),
        environment="test",
        channel="ch_test",
        message=MessageSnapshot(
            id="msg_1", text="hola", author_id="agent_1", seq=1,
        ),
        retracted=False,
    )
    # Serialize and deserialize
    raw = envelope.model_dump(mode="json")
    rehydrated = TransportEnvelopeV1.model_validate(raw)
    assert rehydrated.event_id == envelope.event_id
    assert rehydrated.channel == "ch_test"
    assert rehydrated.message.text == "hola"
    logger.info("[PORTAL_DIAGNOSTIC] Envelope schema validated OK")


# ── Webhook signature verification ─────────────────────────────────────


def test_webhook_signature_verification():
    """HMAC-SHA256 signature verification works."""
    secret = "test-secret-123"
    body = b'{"type":"message.published","id":"evt_1","time":"2026-08-08T12:00:00Z","environment":"test","channel":"ch","message":{"id":"m","text":"h","author_id":"a","seq":1}}'

    import hmac, hashlib, time
    timestamp = int(time.time())
    payload = f"{timestamp}.".encode("utf-8") + body
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    header = f"t={timestamp},v1={expected}"

    assert verify_portal_signature(body, header, secret, tolerance_seconds=300)
    logger.info("[PORTAL_DIAGNOSTIC] Webhook signature verification OK")


def test_webhook_signature_rejects_invalid():
    """Invalid signature is rejected."""
    body = b'{"type":"message.published","id":"evt_1","time":"2026-08-08T12:00:00Z","environment":"test","channel":"ch","message":{"id":"m","text":"h","author_id":"a","seq":1}}'
    header = "t=1,v1=invalidhash"
    assert not verify_portal_signature(body, header, "secret", tolerance_seconds=999999)
    logger.info("[PORTAL_DIAGNOSTIC] Invalid signature correctly rejected")


# ── Event normalization ────────────────────────────────────────────────


def test_event_normalization_message_published():
    """message.published event → valid TransportEnvelopeV1."""
    payload = {
        "type": "message.published",
        "id": "evt_norm_1",
        "time": "2026-08-08T12:00:00Z",
        "environment": "test",
        "channel": "ch_test",
        "message": {"id": "msg_1", "text": "hello", "author_id": "a", "seq": 1},
    }
    envelope = normalize_event(payload)
    assert envelope is not None
    assert envelope.event_type == "message.published"
    assert envelope.channel == "ch_test"
    logger.info("[PORTAL_DIAGNOSTIC] Event normalization OK")


def test_event_normalization_rejects_unsupported():
    """Unsupported event type → None (not an error)."""
    payload = {
        "type": "channel.created",
        "id": "evt_unsupported",
        "time": "2026-08-08T12:00:00Z",
        "environment": "test",
        "channel": "ch_test",
        "message": None,
    }
    envelope = normalize_event(payload)
    assert envelope is None
    logger.info("[PORTAL_DIAGNOSTIC] Unsupported event correctly ignored")
