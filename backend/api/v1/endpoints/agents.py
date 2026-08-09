"""Agent registration and profile endpoints."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from ai.domain.models import AgentProfile, AuditAction, EntityType
from api.v1.schemas import (
    AgentListResponseDTO,
    AgentProfileResponseDTO,
    AgentRegisterDTO,
)
from persistence.database import get_session
from persistence.models import AgentProfileRow
from persistence.repository import create_agent_profile, write_audit
from transport.models import TransportEnvelopeV1, MessageSnapshot

router = APIRouter(prefix="/agents", tags=["agents"])


def _session() -> Generator[Session, None, None]:
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def _row_to_dto(row: AgentProfileRow) -> AgentProfileResponseDTO:
    profile = AgentProfile.model_validate(row.raw_profile)
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
            text=f"agent registered: {body.display_name}",
            author_id=agent_id_str,
            seq=0,
        ),
        retracted=False,
    )
    await bus.accept(envelope)

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
