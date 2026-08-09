"""Protocol-neutral outbound mapping from AI events to Portal messages.

The transport layer owns the concrete Portal SDK command. This module owns the
security boundary: only a public ``TURN_READY`` event can become outbound
agent speech, and its text is taken from the generated event rather than from
the inbound webhook that triggered the engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from ai.api.dto import to_public_event_dto
from ai.domain.models import EngineEvent, EngineEventAudience, EngineEventType
from ai.domain.models import EngineResult
from persistence.sanitize import sanitize_text


@dataclass(frozen=True, slots=True)
class PortalMessageIntent:
    """Minimal command data that a transport adapter can map to Portal."""

    authorization_id: str
    channel_id: str
    sender_id: UUID
    content: dict[str, Any]
    source_event_id: UUID
    correlation_id: UUID


def to_public_portal_message(
    event: EngineEvent,
    *,
    channel_id: str,
    authorization_id: str,
) -> PortalMessageIntent | None:
    """Map one AI event to outbound Portal speech, fail-closed.

    Internal events, approvals, tool results, and lifecycle notifications return
    ``None``. The adapter verifies the generated message shape and applies a
    final text redaction defense before a transport adapter serializes it.
    """

    if (
        event.audience is not EngineEventAudience.PUBLIC
        or event.event_type is not EngineEventType.TURN_READY
    ):
        return None
    raw_message = event.payload.get("message")
    if not isinstance(raw_message, dict):
        raise ValueError("public TURN_READY event has no message payload")
    speaker_id = raw_message.get("speaker_id")
    public_message = raw_message.get("public_message")
    if not isinstance(speaker_id, str) or not isinstance(public_message, str):
        raise ValueError("public TURN_READY message is missing speaker or text")
    try:
        sender_id = UUID(speaker_id)
    except ValueError as exc:
        raise ValueError("public TURN_READY speaker_id is not a UUID") from exc
    if not public_message.strip():
        raise ValueError("public TURN_READY message cannot be empty")
    correlation_id = event.correlation_id or event.session_id
    if to_public_event_dto(event) is None:
        return None
    return PortalMessageIntent(
        authorization_id=authorization_id,
        channel_id=channel_id,
        sender_id=sender_id,
        content={"text": sanitize_text(public_message)},
        source_event_id=event.event_id,
        correlation_id=correlation_id,
    )


def public_portal_messages(
    result: EngineResult,
    *,
    channel_id: str,
    authorization_id: str,
) -> tuple[PortalMessageIntent, ...]:
    """Extract only generated public turns from one engine result."""

    intents: list[PortalMessageIntent] = []
    for event in result.events:
        intent = to_public_portal_message(
            event,
            channel_id=channel_id,
            authorization_id=authorization_id,
        )
        if intent is not None:
            intents.append(intent)
    return tuple(intents)
