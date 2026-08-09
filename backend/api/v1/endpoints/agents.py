"""Agent registration and profile endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from ai.domain.models import AgentProfile, AgentStatus, AuditAction, EntityType
from api.v1.schemas import (
    AgentListResponseDTO,
    AgentProfileResponseDTO,
    AgentRegisterDTO,
    AgentStatusUpdateDTO,
    AgentUpdateDTO,
)
from persistence.database import get_session
from persistence.models import AgentProfileRow
from persistence.repository import create_agent_profile, update_agent_status, write_audit
from persistence.sanitize import sanitize_for_persistence
from transport.models import TransportEnvelopeV1, MessageSnapshot

router = APIRouter(prefix="/agents", tags=["agents"])


def _session() -> Session:
    return get_session()


def _row_to_dto(row: AgentProfileRow) -> AgentProfileResponseDTO:
    profile = AgentProfile.model_validate(row.raw_profile)
    payload = profile.model_dump(mode="json")
    return AgentProfileResponseDTO(
        agent_id=row.agent_id,
        user_id=row.user_id,
        display_name=row.display_name,
        entity_type=row.entity_type,
        status=row.status,
        public_description=row.public_description,
        interests=row.interests or [],
        capabilities=row.capabilities or [],
        price_range=profile.price_range,
        logistics_preferences=profile.logistics_preferences or [],
        objectives=profile.objectives,
        personality=profile.personality,
        hard_limits=payload.get("hard_limits", []),
        never_disclose=sorted(item.value for item in profile.never_disclose),
        escalation_rules=payload.get("escalation_rules", []),
        tool_grants=payload.get("tool_grants", []),
        goal_completion_mode=(
            profile.goal_completion_mode.value
            if profile.goal_completion_mode is not None
            else None
        ),
        remaining_goal_units=profile.remaining_goal_units,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("", response_model=AgentProfileResponseDTO, status_code=status.HTTP_201_CREATED)
async def register_agent(
    body: AgentRegisterDTO,
    request: Request,
    session: Session = Depends(_session),
) -> AgentProfileResponseDTO:
    """Register a new agent and trigger matchmaking via the event bus."""
    profile = AgentProfile(
        display_name=body.display_name,
        entity_type=EntityType(body.entity_type),
        public_description=body.public_description,
        personality=body.personality,
        objectives=body.objectives,
        interests=body.interests,
        capabilities=body.capabilities,
        price_range=body.price_range,
        logistics_preferences=body.logistics_preferences,
    )
    row = create_agent_profile(profile, user_id=uuid4(), session=session)

    write_audit(
        agent_id=row.agent_id,
        user_id=row.user_id,
        actor_type="HUMAN",
        actor_id=str(row.user_id),
        action=AuditAction.AGENT_CREATED,
        severity="INFO",
        entity_type="AgentProfile",
        entity_id=row.agent_id,
        reason=f"agent registered via API: {body.display_name}",
        session=session,
    )

    # Publish agent.registered event to the bus → triggers matchmaking
    await _publish_agent_registered(request, row, f"agent registered: {body.display_name}")

    session.commit()
    return _row_to_dto(row)


async def _publish_agent_registered(
    request: Request, row: AgentProfileRow, reason: str
) -> None:
    bus = request.app.state.bus
    agent_id_str = str(row.agent_id)
    envelope = TransportEnvelopeV1(
        event_id=str(uuid4()),
        event_type="agent.registered",  # type: ignore[arg-type]
        event_time=datetime.now(timezone.utc),
        environment="api",
        channel=f"agent_{row.agent_id.hex[:8]}",
        message=MessageSnapshot(
            id=f"agent_{agent_id_str[:8]}",
            text=reason,
            author_id=agent_id_str,
            seq=0,
        ),
        retracted=False,
    )
    await bus.accept(envelope)


@router.patch("/{agent_id}/status", response_model=AgentProfileResponseDTO)
def update_agent_status_endpoint(
    agent_id: UUID,
    body: AgentStatusUpdateDTO,
    session: Session = Depends(_session),
) -> AgentProfileResponseDTO:
    """Update an agent's availability status (AVAILABLE / BUSY / PAUSED)."""
    row = update_agent_status(agent_id, AgentStatus(body.status), session=session)
    if row is None:
        raise HTTPException(status_code=404, detail="agent not found")
    write_audit(
        agent_id=row.agent_id,
        user_id=row.user_id,
        actor_type="HUMAN",
        actor_id=str(row.user_id),
        action=AuditAction.AGENT_UPDATED,
        severity="INFO",
        entity_type="AgentProfile",
        entity_id=row.agent_id,
        reason=f"agent status -> {body.status}",
        session=session,
    )
    session.commit()
    return _row_to_dto(row)


@router.put("/{agent_id}", response_model=AgentProfileResponseDTO)
async def update_agent(
    agent_id: UUID,
    body: AgentUpdateDTO,
    request: Request,
    session: Session = Depends(_session),
) -> AgentProfileResponseDTO:
    """Update an agent profile and re-run matchmaking via the event bus."""
    row = session.get(AgentProfileRow, agent_id)
    if row is None:
        raise HTTPException(status_code=404, detail="agent not found")

    profile = AgentProfile.model_validate(row.raw_profile)
    profile.display_name = body.display_name
    profile.public_description = body.public_description
    profile.personality = body.personality or profile.personality
    profile.objectives = body.objectives
    profile.interests = body.interests
    profile.capabilities = body.capabilities
    profile.price_range = body.price_range
    profile.logistics_preferences = body.logistics_preferences

    raw = sanitize_for_persistence(profile.model_dump(mode="json"))
    row.raw_profile = raw
    row.display_name = body.display_name
    row.public_description = body.public_description
    row.interests = list(body.interests)
    row.capabilities = list(body.capabilities)
    row.updated_at = datetime.now(timezone.utc)

    write_audit(
        agent_id=row.agent_id,
        user_id=row.user_id,
        actor_type="HUMAN",
        actor_id=str(row.user_id),
        action=AuditAction.AGENT_UPDATED,
        severity="INFO",
        entity_type="AgentProfile",
        entity_id=row.agent_id,
        reason=f"agent updated via API: {body.display_name}",
        session=session,
    )
    await _publish_agent_registered(request, row, f"agent updated: {body.display_name}")
    session.commit()
    return _row_to_dto(row)


@router.get("/{agent_id}", response_model=AgentProfileResponseDTO)
def get_agent(agent_id: UUID, session: Session = Depends(_session)) -> AgentProfileResponseDTO:
    """Retrieve agent profile and current status."""
    row = session.get(AgentProfileRow, agent_id)
    if row is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return _row_to_dto(row)


@router.get("", response_model=AgentListResponseDTO)
def list_agents(session: Session = Depends(_session)) -> AgentListResponseDTO:
    """List all registered agents."""
    rows = session.exec(select(AgentProfileRow)).all()
    return AgentListResponseDTO(
        agents=[_row_to_dto(r) for r in rows],
        total=len(rows),
    )
