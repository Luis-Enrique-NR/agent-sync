"""Typed CRUD and state handoff between the AI engine and SQLModel."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlmodel import Session, select

from ai.domain.models import (
    AgentProfile,
    AgentStatus,
    AuditAction,
    EngineEvent,
    EngineEventType,
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
from persistence.sanitize import sanitize_for_persistence


TERMINAL_STATUSES = frozenset(
    {
        SessionStatus.RESOLVED,
        SessionStatus.REJECTED,
        SessionStatus.WITHDRAWN,
        SessionStatus.EXPIRED,
        SessionStatus.FAILED,
    }
)


class PersistenceConflictError(RuntimeError):
    """Raised when a stale state tries to overwrite a newer state version."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _session_or_default(session: Session | None) -> tuple[Session, bool]:
    return (session or get_session(), session is None)


def create_agent_profile(
    profile: AgentProfile,
    user_id: UUID,
    *,
    session: Session | None = None,
) -> AgentProfileRow:
    current, owns_session = _session_or_default(session)
    row = AgentProfileRow(
        agent_id=profile.agent_id,
        user_id=user_id,
        display_name=profile.display_name,
        entity_type=profile.entity_type.value,
        status=profile.status.value,
        public_description=profile.public_description,
        interests=list(profile.interests),
        capabilities=list(profile.capabilities),
        raw_profile=sanitize_for_persistence(profile.model_dump(mode="json")),
    )
    try:
        current.add(row)
        if owns_session:
            current.commit()
            current.refresh(row)
        return row
    finally:
        if owns_session:
            current.close()


def get_agent_profile(
    agent_id: UUID,
    *,
    session: Session | None = None,
) -> AgentProfileRow | None:
    current, owns_session = _session_or_default(session)
    try:
        return current.get(AgentProfileRow, agent_id)
    finally:
        if owns_session:
            current.close()


def get_agent_profile_as_domain(
    agent_id: UUID,
    *,
    session: Session | None = None,
) -> AgentProfile | None:
    row = get_agent_profile(agent_id, session=session)
    return AgentProfile.model_validate(row.raw_profile) if row else None


def update_agent_status(
    agent_id: UUID,
    new_status: AgentStatus,
    *,
    session: Session | None = None,
) -> AgentProfileRow | None:
    current, owns_session = _session_or_default(session)
    try:
        row = current.get(AgentProfileRow, agent_id)
        if row is None:
            return None
        profile = AgentProfile.model_validate(row.raw_profile)
        profile.status = new_status
        row.status = new_status.value
        row.raw_profile = sanitize_for_persistence(profile.model_dump(mode="json"))
        row.updated_at = _now()
        if owns_session:
            current.commit()
            current.refresh(row)
        return row
    finally:
        if owns_session:
            current.close()


def save_negotiation_state(
    result: EngineResult,
    portal_channel_id: str | None = None,
    initiator_id: UUID | None = None,
    *,
    session: Session | None = None,
    expected_version: int | None = None,
) -> NegotiationStateRow:
    current, owns_session = _session_or_default(session)
    state = result.state
    raw = sanitize_for_persistence(state.model_dump(mode="json"))
    existing = current.get(NegotiationStateRow, state.session_id)
    if existing is not None:
        if expected_version is not None and existing.version != expected_version:
            raise PersistenceConflictError(
                f"session {state.session_id} version {expected_version} is stale"
            )
        existing.owner_user_id = state.owner_user_id
        existing.status = state.status.value
        existing.turn_count = state.turn_count
        existing.max_turns = state.max_turns
        existing.current_speaker_id = state.current_speaker_id
        existing.deadline_at = state.deadline_at
        existing.closed_at = (
            existing.closed_at or _now() if state.status in TERMINAL_STATUSES else None
        )
        existing.last_error_code = state.last_error_code
        existing.raw_state = raw
        existing.version += 1
        existing.last_updated_at = _now()
        row = existing
    else:
        row = NegotiationStateRow(
            session_id=state.session_id,
            owner_user_id=state.owner_user_id,
            portal_channel_id=portal_channel_id,
            agent_1_id=state.agents[0].agent_id,
            agent_2_id=state.agents[1].agent_id,
            initiator_id=initiator_id or state.agents[0].agent_id,
            current_speaker_id=state.current_speaker_id,
            status=state.status.value,
            turn_count=state.turn_count,
            max_turns=state.max_turns,
            started_at=state.started_at,
            deadline_at=state.deadline_at,
            closed_at=_now() if state.status in TERMINAL_STATUSES else None,
            last_error_code=state.last_error_code,
            raw_state=raw,
        )
        current.add(row)
    try:
        if owns_session:
            current.commit()
            current.refresh(row)
        return row
    finally:
        if owns_session:
            current.close()


def load_negotiation_state(
    session_id: UUID,
    *,
    session: Session | None = None,
) -> NegotiationState | None:
    current, owns_session = _session_or_default(session)
    try:
        row = current.get(NegotiationStateRow, session_id)
        return NegotiationState.model_validate(row.raw_state) if row else None
    finally:
        if owns_session:
            current.close()


def save_negotiation_outcome(
    session_id: UUID,
    resolution: str,
    *,
    agreed_price: float | None = None,
    agreed_terms: dict[str, Any] | None = None,
    disclosed_data: dict[str, Any] | None = None,
    summary: str = "",
    session: Session | None = None,
) -> NegotiationOutcomeRow:
    current, owns_session = _session_or_default(session)
    row = NegotiationOutcomeRow(
        session_id=session_id,
        resolution=resolution,
        agreed_price=agreed_price,
        agreed_terms=sanitize_for_persistence(agreed_terms) if agreed_terms else None,
        disclosed_data=(
            sanitize_for_persistence(disclosed_data) if disclosed_data else None
        ),
        summary=sanitize_for_persistence(summary),
    )
    try:
        current.add(row)
        if owns_session:
            current.commit()
            current.refresh(row)
        return row
    finally:
        if owns_session:
            current.close()


def create_private_resolution(
    agent_id: UUID,
    value_ref: str,
    category: str,
    real_value: str,
    *,
    session: Session | None = None,
) -> PrivateResolutionRow:
    current, owns_session = _session_or_default(session)
    row = PrivateResolutionRow(
        agent_id=agent_id,
        value_ref=value_ref,
        category=category,
        real_value=real_value,
    )
    try:
        current.add(row)
        if owns_session:
            current.commit()
            current.refresh(row)
        return row
    finally:
        if owns_session:
            current.close()


def resolve_private_value(
    agent_id: UUID,
    value_ref: str,
    *,
    session: Session | None = None,
) -> str | None:
    current, owns_session = _session_or_default(session)
    try:
        statement = select(PrivateResolutionRow).where(
            PrivateResolutionRow.agent_id == agent_id,
            PrivateResolutionRow.value_ref == value_ref,
        )
        row = current.exec(statement).first()
        return row.real_value if row else None
    finally:
        if owns_session:
            current.close()


def write_audit(
    *,
    correlation_id: UUID | None = None,
    session_id: UUID | None = None,
    agent_id: UUID | None = None,
    user_id: UUID | None = None,
    actor_type: str,
    actor_id: str,
    action: str | AuditAction,
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
    current, owns_session = _session_or_default(session)
    action_value = action.value if isinstance(action, AuditAction) else action
    row = AuditRecordRow(
        correlation_id=correlation_id or uuid4(),
        session_id=session_id,
        agent_id=agent_id,
        user_id=user_id,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action_value,
        severity=severity,
        entity_type=entity_type,
        entity_id=entity_id,
        previous_state=sanitize_for_persistence(previous_state),
        new_state=sanitize_for_persistence(new_state),
        reason=reason,
        delivery_status=delivery_status,
        source_ip=source_ip,
        payload=sanitize_for_persistence(payload),
    )
    try:
        current.add(row)
        if owns_session:
            current.commit()
            current.refresh(row)
        return row
    finally:
        if owns_session:
            current.close()


def _event_action(event_type: EngineEventType) -> AuditAction:
    mapping = {
        EngineEventType.TURN_READY: AuditAction.TURN_PUBLISHED,
        EngineEventType.APPROVAL_REQUIRED: AuditAction.APPROVAL_REQUESTED,
        EngineEventType.DECISION_RESOLVED: AuditAction.DECISION_APPROVED,
        EngineEventType.REVALIDATION_REQUIRED: AuditAction.REVALIDATION_REQUESTED,
        EngineEventType.REVALIDATION_RESOLVED: AuditAction.REVALIDATION_RESOLVED,
        EngineEventType.CANDIDATE_BLOCKED: AuditAction.CANDIDATE_BLOCKED,
        EngineEventType.SESSION_RESOLVED: AuditAction.SESSION_RESOLVED,
        EngineEventType.SESSION_REJECTED: AuditAction.SESSION_REJECTED,
        EngineEventType.SESSION_WITHDRAWN: AuditAction.SESSION_WITHDRAWN,
        EngineEventType.SESSION_EXPIRED: AuditAction.SESSION_EXPIRED,
        EngineEventType.SESSION_FAILED: AuditAction.SESSION_FAILED,
        EngineEventType.TOOL_EXECUTION_COMPLETED: AuditAction.TOOL_EXECUTION_COMPLETED,
        EngineEventType.TOOL_EXECUTION_DENIED: AuditAction.TOOL_EXECUTION_DENIED,
        EngineEventType.GOAL_PROGRESS_REVIEW_REQUIRED: AuditAction.GOAL_PROGRESS_REVIEWED,
    }
    return mapping.get(event_type, AuditAction.SESSION_FAILED)


def persist_engine_result(
    result: EngineResult,
    *,
    user_id: UUID | None = None,
    portal_channel_id: str | None = None,
    initiator_id: UUID | None = None,
    session: Session | None = None,
) -> NegotiationStateRow:
    """Atomically save state and its engine events to the audit trail."""

    current, owns_session = _session_or_default(session)
    try:
        if user_id is not None and result.state.owner_user_id != user_id:
            result = result.model_copy(
                update={
                    "state": result.state.model_copy(update={"owner_user_id": user_id})
                }
            )
        row = save_negotiation_state(
            result,
            portal_channel_id=portal_channel_id,
            initiator_id=initiator_id,
            session=current,
        )
        for event in result.events:
            write_audit(
                correlation_id=event.correlation_id or event.event_id,
                session_id=event.session_id,
                user_id=user_id or result.state.owner_user_id,
                actor_type="SYSTEM",
                actor_id="ai-engine",
                action=_event_action(event.event_type),
                reason=event.event_type.value,
                payload=event.payload,
                session=current,
            )
        if owns_session:
            current.commit()
        return row
    except Exception:
        if owns_session:
            current.rollback()
        raise
    finally:
        if owns_session:
            current.close()


class PersistenceRepository:
    """Application-facing repository with an injectable SQLModel session factory."""

    def __init__(self, session_factory: Callable[[], Session] = get_session) -> None:
        self._session_factory = session_factory

    def save_engine_result(self, result: EngineResult, **kwargs: Any) -> NegotiationStateRow:
        with self._session_factory() as session:
            row = persist_engine_result(result, session=session, **kwargs)
            session.commit()
            return row

    def load_negotiation_state(self, session_id: UUID) -> NegotiationState | None:
        with self._session_factory() as session:
            return load_negotiation_state(session_id, session=session)

    def get_agent_profile(self, agent_id: UUID) -> AgentProfile | None:
        with self._session_factory() as session:
            return get_agent_profile_as_domain(agent_id, session=session)

    def save_agent_profile(self, profile: AgentProfile, user_id: UUID) -> AgentProfileRow:
        with self._session_factory() as session:
            row = create_agent_profile(profile, user_id, session=session)
            session.commit()
            return row
