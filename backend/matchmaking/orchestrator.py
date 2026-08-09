"""Matchmaking orchestrator — connects match discovery to AI negotiation.

Bridges ``find_matches`` → Portal channel creation → engine invocation,
persisting every state change through the repository layer.
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from sqlmodel import Session

from ai.domain.models import (
    AgentProfile,
    AgentStatus,
    AuditAction,
)
from ai.engine.graph import NegotiationEngine
from matchmaking.service import find_matches
from persistence.models import AgentProfileRow, NegotiationStateRow
from persistence.repository import (
    get_agent_profile_as_domain,
    save_negotiation_state,
    update_agent_status,
    write_audit,
)
from transport.portal import (
    AddChannelMembers,
    ChannelMember,
    PortalAdmin,
)

logger = logging.getLogger(__name__)


async def process_agent_matching(
    agent_id: UUID,
    *,
    session: Session,
    engine: NegotiationEngine,
    portal: PortalAdmin | None = None,
    max_turns: int = 8,
    timeout_seconds: int = 90,
) -> list[UUID]:
    """Run matchmaking for one agent and start negotiations where possible.

    Returns the list of ``session_id`` values created.
    """
    matches = find_matches(agent_id, session=session, limit=5)
    if not matches:
        logger.info("no matches found for agent %s", agent_id)
        return []

    candidate = session.get(AgentProfileRow, agent_id)
    if candidate is None:
        return []

    candidate_domain = AgentProfile.model_validate(candidate.raw_profile)
    created_sessions: list[UUID] = []

    for counterpart_row in matches:
        counterpart_domain = AgentProfile.model_validate(counterpart_row.raw_profile)

        channel_id = f"ch_match_{agent_id.hex[:8]}_{counterpart_row.agent_id.hex[:8]}"

        # 1. Create Portal channel
        if portal is not None:
            try:
                await portal.execute(
                    AddChannelMembers(
                        authorization_id=str(agent_id),
                        channel_id=channel_id,
                        members=[
                            ChannelMember(user_id=str(agent_id)),
                            ChannelMember(user_id=str(counterpart_row.agent_id)),
                        ],
                    )
                )
                logger.info("portal channel created %s", channel_id)
            except Exception:
                logger.exception("portal channel creation failed %s — continuing match without Portal", channel_id)

        # 2. Create negotiation state
        result = engine.start_session(
            candidate_domain,
            counterpart_domain,
            max_turns=max_turns,
            timeout_seconds=timeout_seconds,
        )
        state_row = save_negotiation_state(
            result,
            portal_channel_id=channel_id,
            initiator_id=agent_id,
            session=session,
        )
        created_sessions.append(state_row.session_id)

        # 3. Mark both agents BUSY
        update_agent_status(agent_id, AgentStatus.BUSY, session=session)
        update_agent_status(counterpart_row.agent_id, AgentStatus.BUSY, session=session)

        # 4. Audit
        write_audit(
            correlation_id=uuid4(),
            session_id=state_row.session_id,
            agent_id=agent_id,
            user_id=None,
            actor_type="SYSTEM",
            actor_id="matchmaking",
            action=AuditAction.SESSION_CREATED,
            severity="INFO",
            entity_type="NegotiationState",
            entity_id=state_row.session_id,
            reason=f"matched agent={counterpart_row.agent_id} interests->capabilities channel={channel_id}",
            delivery_status="DELIVERED",
            session=session,
        )

        # 5. Publish opening message to Portal
        if portal is not None and result.events:
            from transport.portal import PublishMessage
            for event in result.events:
                if event.event_type.value == "TURN_READY":
                    try:
                        await portal.execute(
                            PublishMessage(
                                authorization_id=str(agent_id),
                                channel_id=channel_id,
                                sender_id=str(candidate_domain.agent_id),
                                content={"text": event.payload.get("message", {}).get("public_message", "Negotiation started")},
                            )
                        )
                    except Exception:
                        logger.exception("opening message publish failed channel=%s", channel_id)

    return created_sessions
