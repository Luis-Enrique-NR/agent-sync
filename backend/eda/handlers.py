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

from sqlmodel import select

from ai.domain.models import (
    AgentProfile,
    AgentStatus,
    AuditAction,
    NegotiationState,
    SessionStatus,
)
from ai.domain.models import EngineEventType
from ai.engine.graph import NegotiationEngine
from persistence.database import get_session
from persistence.models import NegotiationStateRow, AgentProfileRow
from persistence.repository import (
    load_negotiation_state,
    save_negotiation_state,
    update_agent_status,
    write_audit,
)
from transport.bus import EventDelivery
from transport.portal import PortalAdmin, PublishMessage
from matchmaking.orchestrator import process_agent_matching
from eda.trace import trace

logger = logging.getLogger(__name__)

# ── Legacy standalone handlers (kept for compatibility) ──────────────────


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
    trace("HANDLER_LOOKUP", f"querying negotiation_states by portal_channel_id={channel}")

    session = get_session()
    try:
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
        trace("AUDIT_WRITE", f"TURN_PUBLISHED session={state_row.session_id if state_row else 'none'} channel={channel}")
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


# ── NegotiationHandler: production dispatcher with engine + portal ──────


class NegotiationHandler:
    """Dispatches transport deliveries to the AI engine and Portal.

    Receives the AI engine and Portal publisher as constructor
    dependencies — never imports transport adapters directly.
    """

    def __init__(
        self,
        engine: NegotiationEngine,
        portal: PortalAdmin | None = None,
    ) -> None:
        self._engine = engine
        self._portal = portal

    async def handle(self, delivery: EventDelivery) -> None:
        envelope = delivery.envelope
        event_type = envelope.event_type

        if event_type == "message.published":
            await self._handle_message_published(delivery)
        elif event_type == "message.retracted":
            await handle_message_retracted(delivery)
        elif event_type in ("agent.registered", "intent.published"):
            await self._handle_agent_event(delivery)
        elif event_type in ("negotiation.failed", "negotiation.rejected"):
            await self._handle_negotiation_closed(delivery)
        else:
            logger.warning("unhandled event type %s — acking silently", event_type)

    async def _handle_message_published(self, delivery: EventDelivery) -> None:
        envelope = delivery.envelope
        channel = envelope.channel
        seq = envelope.message.seq if envelope.message else None
        author = envelope.message.author_id if envelope.message else None

        logger.info("message.published  event=%s channel=%s seq=%s", envelope.event_id, channel, seq)
        trace("HANDLER_LOOKUP", f"querying negotiation_states by portal_channel_id={channel}")

        session = get_session()
        try:
            stmt = select(NegotiationStateRow).where(
                NegotiationStateRow.portal_channel_id == channel,
                NegotiationStateRow.status.in_(["ACTIVE", "SEARCHING"]),
            )
            state_row = session.exec(stmt).first()

            agent_id: UUID | None = None
            state: NegotiationState | None = None

            if state_row is not None:
                agent_id = state_row.current_speaker_id
                state = load_negotiation_state(state_row.session_id, session=session)

            # Invoke AI engine if correlated session exists
            if state is not None and state.status == SessionStatus.ACTIVE:
                from ai.domain.models import EngineResult
                result: EngineResult = self._engine.run_until_pause(state)
                save_negotiation_state(result, portal_channel_id=channel, session=session)

                # Check for pending human decision
                if result.state.status == SessionStatus.PENDING_HUMAN_APPROVAL:
                    write_audit(
                        correlation_id=UUID(envelope.event_id) if _is_uuid(envelope.event_id) else None,
                        session_id=state_row.session_id,
                        agent_id=agent_id,
                        user_id=None,
                        actor_type="SYSTEM",
                        actor_id="engine",
                        action=AuditAction.APPROVAL_REQUESTED,
                        severity="WARNING",
                        entity_type="NegotiationState",
                        entity_id=state_row.session_id,
                        reason=f"pending_decision channel={channel}",
                        delivery_status="PENDING",
                        payload=envelope.model_dump(mode="json"),
                        session=session,
                    )
                    trace("AUDIT_WRITE", f"APPROVAL_REQUESTED session={state_row.session_id} — pausing outbound")
                else:
                    # Publish only generated public turns to Portal.  The
                    # inbound envelope is an event trigger, never the
                    # outbound message body.
                    if self._portal is not None and state_row is not None:
                        for speaker_id, text in _public_turns(result):
                            try:
                                cmd = PublishMessage(
                                    # Portal authorization belongs to the
                                    # initiating agent, not to the internal
                                    # negotiation session identifier.
                                    authorization_id=str(state_row.initiator_id),
                                    channel_id=channel,
                                    sender_id=str(speaker_id),
                                    content={"text": text},
                                )
                                await self._portal.execute(cmd)
                                trace("OUTBOUND_PUBLISH", f"published to channel={channel}")
                            except Exception:
                                logger.exception("portal publish failed channel=%s", channel)

            # Write audit
            write_audit(
                correlation_id=UUID(envelope.event_id) if _is_uuid(envelope.event_id) else None,
                session_id=state_row.session_id if state_row else None,
                agent_id=agent_id,
                user_id=None,
                actor_type="LLM",
                actor_id="engine",
                action=AuditAction.TURN_PUBLISHED,
                severity="INFO",
                entity_type="TransportEnvelope",
                entity_id=None,
                reason=f"channel={channel} author={author} seq={seq}",
                delivery_status="DELIVERED",
                payload=envelope.model_dump(mode="json"),
                session=session,
            )
            trace("AUDIT_WRITE", f"TURN_PUBLISHED session={state_row.session_id if state_row else 'none'} channel={channel}")
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("failed to process message.published %s", envelope.event_id)
            raise
        finally:
            session.close()

    async def _handle_agent_event(self, delivery: EventDelivery) -> None:
        """Process agent.registered / intent.published events.

        Writes a registration audit and triggers matchmaking for the
        newly published agent if its interests and capabilities allow it.
        """
        envelope = delivery.envelope
        logger.info("%s  event=%s", envelope.event_type, envelope.event_id)
        trace("AGENT_EVENT", f"{envelope.event_type} channel={envelope.channel}")

        session = get_session()
        try:
            write_audit(
                correlation_id=UUID(envelope.event_id) if _is_uuid(envelope.event_id) else None,
                session_id=None,
                agent_id=None,
                user_id=None,
                actor_type="SYSTEM",
                actor_id="transport",
                action=AuditAction.AGENT_PUBLISHED,
                severity="INFO",
                entity_type="TransportEnvelope",
                entity_id=None,
                reason=f"{envelope.event_type} channel={envelope.channel}",
                delivery_status="DELIVERED",
                payload=envelope.model_dump(mode="json"),
                session=session,
            )

            # Trigger matchmaking if envelope carries an author_id as agent UUID
            author = envelope.message.author_id if envelope.message else None
            if author and _is_uuid(author):
                agent_uuid = UUID(author)
                logger.info("[EDA Worker] Extracted agent_id: %s. Executing process_agent_matching...", agent_uuid)
                trace("MATCHMAKING", f"triggering matchmaking for agent={agent_uuid}")
                row = session.get(AgentProfileRow, agent_uuid)
                if row is not None:
                    await process_agent_matching(
                        agent_uuid,
                        session=session,
                        engine=self._engine,
                        portal=self._portal,
                    )
            else:
                logger.warning(
                    "[EDA Worker] Event '%s' received without valid agent_id in message (author=%s)",
                    envelope.event_type, author,
                )

            session.commit()
        except Exception:
            session.rollback()
            logger.exception("failed to process %s %s", envelope.event_type, envelope.event_id)
            raise
        finally:
            session.close()

    async def _handle_negotiation_closed(self, delivery: EventDelivery) -> None:
        """Process negotiation.failed / negotiation.rejected events.

        Releases both agents back to AVAILABLE and triggers re-matchmaking
        for the initiator so the next-best candidate can be evaluated.
        """
        envelope = delivery.envelope
        channel = envelope.channel
        logger.info("negotiation closed  event=%s channel=%s", envelope.event_type, channel)
        trace("NEGOTIATION_CLOSED", f"{envelope.event_type} channel={channel}")

        session = get_session()
        try:
            stmt = select(NegotiationStateRow).where(
                NegotiationStateRow.portal_channel_id == channel,
            )
            state_row = session.exec(stmt).first()

            if state_row is None:
                logger.warning("no session found for channel=%s", channel)
                return

            # Release both agents
            update_agent_status(state_row.agent_1_id, AgentStatus.AVAILABLE, session=session)
            update_agent_status(state_row.agent_2_id, AgentStatus.AVAILABLE, session=session)

            write_audit(
                correlation_id=UUID(envelope.event_id) if _is_uuid(envelope.event_id) else None,
                session_id=state_row.session_id,
                agent_id=state_row.initiator_id,
                user_id=None,
                actor_type="SYSTEM",
                actor_id="engine",
                action=AuditAction.SESSION_FAILED if envelope.event_type == "negotiation.failed" else AuditAction.SESSION_REJECTED,
                severity="WARNING",
                entity_type="NegotiationState",
                entity_id=state_row.session_id,
                reason=f"{envelope.event_type} channel={channel}",
                delivery_status="DELIVERED",
                payload=envelope.model_dump(mode="json"),
                session=session,
            )

            session.commit()
            trace("RELEASE", f"agents {state_row.agent_1_id} and {state_row.agent_2_id} released to AVAILABLE")

            # Re-trigger matchmaking for the initiator
            await process_agent_matching(
                state_row.initiator_id,
                session=session,
                engine=self._engine,
                portal=self._portal,
            )

        except Exception:
            session.rollback()
            logger.exception("failed to process %s %s", envelope.event_type, envelope.event_id)
            raise
        finally:
            session.close()


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except ValueError:
        return False


def _public_turns(result: object) -> list[tuple[UUID, str]]:
    """Extract generated public turns, failing closed for malformed events.

    The current EDA branch uses the legacy event model (without an audience
    field).  ``getattr`` keeps this adapter compatible with the newer AI
    model, where internal events carry ``audience=INTERNAL`` and must never be
    sent to Portal.
    """

    turns: list[tuple[UUID, str]] = []
    for event in getattr(result, "events", []):
        if event.event_type is not EngineEventType.TURN_READY:
            continue
        audience = getattr(event, "audience", None)
        if audience is not None and getattr(audience, "value", audience) != "PUBLIC":
            continue
        message = event.payload.get("message")
        if not isinstance(message, dict):
            continue
        text = message.get("public_message")
        if not isinstance(text, str) or not text.strip():
            continue
        raw_speaker_id = message.get("speaker_id")
        try:
            speaker_id = UUID(str(raw_speaker_id))
        except (TypeError, ValueError):
            speaker_id = result.state.current_speaker_id
        turns.append((speaker_id, text.strip()))
    return turns
