"""Typed CRUD operations for the AgentSync persistence layer."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import Session, select

from ai.domain.models import (
    AgentProfile,
    AgentStatus,
    EngineEvent,
    EngineResult,
    NegotiationState,
    SessionStatus,
)
from persistence.database import get_session
from persistence.models import (
    AgentProfileRow,
    AuditRecordRow,
    NegotiationOutcomeRow,
    NegotiationStateRow,
    PrivateResolutionRow,
)

# ---------------------------------------------------------------------------
# Agent profiles
# ---------------------------------------------------------------------------


def create_agent_profile(
    profile: AgentProfile,
    user_id: UUID,
    *,
    session: Session | None = None,
) -> AgentProfileRow:
    _session = session or get_session()
    row = AgentProfileRow(
        agent_id=profile.agent_id,
        user_id=user_id,
        display_name=profile.display_name,
        entity_type=profile.entity_type.value,
        status=profile.status.value,
        public_description=profile.public_description,
        interests=profile.interests,
        capabilities=profile.capabilities,
        raw_profile=profile.model_dump(mode="json"),
    )
    try:
        _session.add(row)
        if session is None:
            _session.commit()
            _session.refresh(row)
        return row
    finally:
        if session is None:
            _session.close()


def get_agent_profile(
    agent_id: UUID,
    *,
    session: Session | None = None,
) -> AgentProfileRow | None:
    _session = session or get_session()
    try:
        return _session.get(AgentProfileRow, agent_id)
    finally:
        if session is None:
            _session.close()


def get_agent_profile_as_domain(
    agent_id: UUID,
    *,
    session: Session | None = None,
) -> AgentProfile | None:
    row = get_agent_profile(agent_id, session=session)
    if row is None:
        return None
    return AgentProfile.model_validate(row.raw_profile)


def update_agent_status(
    agent_id: UUID,
    new_status: AgentStatus,
    *,
    session: Session | None = None,
) -> AgentProfileRow | None:
    _session = session or get_session()
    try:
        row = _session.get(AgentProfileRow, agent_id)
        if row is None:
            return None
        row.status = new_status.value
        profile = AgentProfile.model_validate(row.raw_profile)
        profile.status = new_status
        row.raw_profile = profile.model_dump(mode="json")
        row.updated_at = datetime.now(timezone.utc)
        if session is None:
            _session.commit()
            _session.refresh(row)
        return row
    finally:
        if session is None:
            _session.close()


# ---------------------------------------------------------------------------
# Negotiation states
# ---------------------------------------------------------------------------


def save_negotiation_state(
    result: EngineResult,
    portal_channel_id: str | None = None,
    initiator_id: UUID | None = None,
    *,
    session: Session | None = None,
) -> NegotiationStateRow:
    _session = session or get_session()
    state = result.state
    agents = state.agents
    raw = state.model_dump(mode="json")
    existing = _session.get(NegotiationStateRow, state.session_id)

    if existing is not None:
        existing.status = state.status.value
        existing.turn_count = state.turn_count
        existing.max_turns = state.max_turns
        existing.current_speaker_id = state.current_speaker_id
        existing.deadline_at = state.deadline_at
        existing.closed_at = (
            datetime.now(timezone.utc)
            if state.status in (SessionStatus.RESOLVED, SessionStatus.REJECTED, SessionStatus.FAILED)
            else existing.closed_at
        )
        existing.last_error_code = state.last_error_code
        existing.raw_state = raw
        existing.last_updated_at = datetime.now(timezone.utc)
        row = existing
    else:
        row = NegotiationStateRow(
            session_id=state.session_id,
            portal_channel_id=portal_channel_id,
            agent_1_id=agents[0].agent_id,
            agent_2_id=agents[1].agent_id,
            initiator_id=initiator_id or agents[0].agent_id,
            current_speaker_id=state.current_speaker_id,
            status=state.status.value,
            turn_count=state.turn_count,
            max_turns=state.max_turns,
            started_at=state.started_at,
            deadline_at=state.deadline_at,
            closed_at=(
                datetime.now(timezone.utc)
                if state.status in (SessionStatus.RESOLVED, SessionStatus.REJECTED, SessionStatus.FAILED)
                else None
            ),
            last_error_code=state.last_error_code,
            raw_state=raw,
        )
        _session.add(row)

    try:
        if session is None:
            _session.commit()
            _session.refresh(row)
        return row
    finally:
        if session is None:
            _session.close()


def load_negotiation_state(
    session_id: UUID,
    *,
    session: Session | None = None,
) -> NegotiationState | None:
    _session = session or get_session()
    try:
        row = _session.get(NegotiationStateRow, session_id)
        if row is None:
            return None
        return NegotiationState.model_validate(row.raw_state)
    finally:
        if session is None:
            _session.close()


# ---------------------------------------------------------------------------
# Negotiation outcomes
# ---------------------------------------------------------------------------


def save_negotiation_outcome(
    session_id: UUID,
    resolution: str,
    *,
    agreed_price: float | None = None,
    agreed_terms: dict | None = None,
    disclosed_data: dict | None = None,
    summary: str = "",
    session: Session | None = None,
) -> NegotiationOutcomeRow:
    _session = session or get_session()
    row = NegotiationOutcomeRow(
        session_id=session_id,
        resolution=resolution,
        agreed_price=agreed_price,
        agreed_terms=agreed_terms,
        disclosed_data=disclosed_data,
        summary=summary,
    )
    try:
        _session.add(row)
        if session is None:
            _session.commit()
            _session.refresh(row)
        return row
    finally:
        if session is None:
            _session.close()


# ---------------------------------------------------------------------------
# Private resolutions
# ---------------------------------------------------------------------------


def create_private_resolution(
    agent_id: UUID,
    value_ref: str,
    category: str,
    real_value: str,
    *,
    session: Session | None = None,
) -> PrivateResolutionRow:
    _session = session or get_session()
    row = PrivateResolutionRow(
        agent_id=agent_id,
        value_ref=value_ref,
        category=category,
        real_value=real_value,
    )
    try:
        _session.add(row)
        if session is None:
            _session.commit()
            _session.refresh(row)
        return row
    finally:
        if session is None:
            _session.close()


def resolve_private_value(
    agent_id: UUID,
    value_ref: str,
    *,
    session: Session | None = None,
) -> str | None:
    _session = session or get_session()
    try:
        statement = select(PrivateResolutionRow).where(
            PrivateResolutionRow.agent_id == agent_id,
            PrivateResolutionRow.value_ref == value_ref,
        )
        row = _session.exec(statement).first()
        if row is None:
            return None
        return row.real_value
    finally:
        if session is None:
            _session.close()


# ---------------------------------------------------------------------------
# Audit records
# ---------------------------------------------------------------------------


def write_audit(
    *,
    correlation_id: UUID | None = None,
    session_id: UUID | None = None,
    agent_id: UUID | None = None,
    user_id: UUID | None = None,
    actor_type: str,
    actor_id: str,
    action: str,
    severity: str = "INFO",
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    previous_state: dict | None = None,
    new_state: dict | None = None,
    reason: str | None = None,
    delivery_status: str | None = None,
    source_ip: str | None = None,
    payload: dict | None = None,
    session: Session | None = None,
) -> AuditRecordRow:
    _session = session or get_session()
    row = AuditRecordRow(
        correlation_id=correlation_id or uuid4(),
        session_id=session_id,
        agent_id=agent_id,
        user_id=user_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        severity=severity,
        entity_type=entity_type,
        entity_id=entity_id,
        previous_state=previous_state,
        new_state=new_state,
        reason=reason,
        delivery_status=delivery_status,
        source_ip=source_ip,
        payload=payload,
    )
    try:
        _session.add(row)
        if session is None:
            _session.commit()
            _session.refresh(row)
        return row
    finally:
        if session is None:
            _session.close()
