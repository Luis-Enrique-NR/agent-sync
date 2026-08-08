"""Domain handlers that process transport deliveries.

Each handler bridges a ``TransportEnvelopeV1`` received from the
event bus into persistence CRUD and, when a correlated session is
active, AI engine calls.  Handlers only import domain models,
persistence primitives, and the engine composition root — never
transport adapters directly.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlmodel import Session, select

from ai.domain.models import AuditAction
from persistence.database import get_session
from persistence.models import NegotiationStateRow
from persistence.repository import write_audit
from transport.bus import EventDelivery

logger = logging.getLogger(__name__)


async def handle_message_published(delivery: EventDelivery) -> None:
    """Process a ``message.published`` delivery from Portal.

    1. Look up an active ``negotiation_states`` row by ``portal_channel_id``.
    2. Write an audit record with ``TURN_PUBLISHED`` action.
    3. If a correlated session exists, reload its ``NegotiationState``,
       invoke ``engine.run_until_pause()``, and persist the result.
    """
    envelope = delivery.envelope
    channel = envelope.channel
    seq = envelope.message.seq if envelope.message else None
    author = envelope.message.author_id if envelope.message else None

    logger.info("message.published  event=%s channel=%s seq=%s", envelope.event_id, channel, seq)

    session = get_session()
    try:
        # Look up correlated negotiation
        stmt = select(NegotiationStateRow).where(
            NegotiationStateRow.portal_channel_id == channel,
            NegotiationStateRow.status.in_(["ACTIVE", "SEARCHING"]),
        )
        state_row = session.exec(stmt).first()

        agent_id: UUID | None = None
        if state_row is not None:
            agent_id = state_row.current_speaker_id

        write_audit(
            correlation_id=UUID(envelope.event_id) if _is_uuid(envelope.event_id) else None,
            session_id=state_row.session_id if state_row else None,
            agent_id=agent_id,
            user_id=None,
            actor_type="SYSTEM",
            actor_id="transport",
            action=AuditAction.TURN_PUBLISHED,
            severity="INFO",
            entity_type="TransportEnvelope",
            entity_id=None,
            reason=f"channel={channel} author={author} seq={seq}",
            delivery_status="DELIVERED",
            payload=envelope.model_dump(mode="json"),
            session=session,
        )
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("failed to persist message.published %s", envelope.event_id)
        raise
    finally:
        session.close()


async def handle_message_retracted(delivery: EventDelivery) -> None:
    """Process a ``message.retracted`` delivery from Portal.

    Writes a CANDIDATE_BLOCKED audit record.  The retracted message is
    not forwarded to the AI engine.
    """
    envelope = delivery.envelope
    logger.info("message.retracted  event=%s channel=%s", envelope.event_id, envelope.channel)

    session = get_session()
    try:
        stmt = select(NegotiationStateRow).where(
            NegotiationStateRow.portal_channel_id == envelope.channel,
        )
        state_row = session.exec(stmt).first()

        write_audit(
            correlation_id=UUID(envelope.event_id) if _is_uuid(envelope.event_id) else None,
            session_id=state_row.session_id if state_row else None,
            agent_id=None,
            user_id=None,
            actor_type="SYSTEM",
            actor_id="transport",
            action=AuditAction.CANDIDATE_BLOCKED,
            severity="WARNING",
            entity_type="TransportEnvelope",
            entity_id=None,
            reason=f"message retracted channel={envelope.channel}",
            delivery_status="DELIVERED",
            payload=envelope.model_dump(mode="json"),
            session=session,
        )
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("failed to persist message.retracted %s", envelope.event_id)
        raise
    finally:
        session.close()


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except ValueError:
        return False
