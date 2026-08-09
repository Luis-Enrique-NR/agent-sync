"""Negotiation session and human decision endpoints."""

from __future__ import annotations

from collections.abc import Generator
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from ai.domain.models import (
    AgentStatus,
    AgentTurn,
    AuditAction,
    HumanDecision,
    HumanDecisionAction,
    NegotiationState,
    SessionStatus,
    TurnIntent,
)
from ai.service import build_engine_from_env
from api.v1.schemas import (
    AuditListResponseDTO,
    AuditRecordDTO,
    DecisionResponseDTO,
    HumanDecisionDTO,
    NegotiationDetailDTO,
    NegotiationListResponseDTO,
    NegotiationSummaryDTO,
    TranscriptMessageDTO,
)
from persistence.database import get_session
from persistence.models import AuditRecordRow, NegotiationStateRow
from persistence.repository import (
    load_negotiation_state,
    save_negotiation_state,
    update_agent_status,
    write_audit,
)

router = APIRouter(prefix="/negotiations", tags=["negotiations"])


def _session() -> Generator[Session, None, None]:
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def _row_to_summary(row: NegotiationStateRow) -> NegotiationSummaryDTO:
    return NegotiationSummaryDTO(
        session_id=row.session_id,
        agent_1_id=row.agent_1_id,
        agent_2_id=row.agent_2_id,
        status=row.status,
        portal_channel_id=row.portal_channel_id,
        turn_count=row.turn_count,
        started_at=row.started_at,
        closed_at=row.closed_at,
    )


def _row_to_detail(row: NegotiationStateRow) -> NegotiationDetailDTO:
    state = NegotiationState.model_validate(row.raw_state)
    transcript = [
        TranscriptMessageDTO(
            speaker_id=m.speaker_id,
            turn_index=m.turn_index,
            public_message=m.public_message,
            intent=m.intent.value,
            approved_by_human=m.approved_by_human,
            created_at=m.created_at,
        )
        for m in state.transcript
    ]
    return NegotiationDetailDTO(
        session_id=row.session_id,
        agent_1_id=row.agent_1_id,
        agent_2_id=row.agent_2_id,
        status=row.status,
        portal_channel_id=row.portal_channel_id,
        turn_count=row.turn_count,
        started_at=row.started_at,
        closed_at=row.closed_at,
        initiator_id=row.initiator_id,
        max_turns=row.max_turns,
        deadline_at=row.deadline_at,
        last_error_code=row.last_error_code,
        transcript=transcript,
    )


@router.get("", response_model=NegotiationListResponseDTO)
def list_negotiations(
    agent_id: UUID | None = None,
    session: Session = Depends(_session),
) -> NegotiationListResponseDTO:
    stmt = select(NegotiationStateRow)
    if agent_id is not None:
        stmt = stmt.where(
            (NegotiationStateRow.agent_1_id == agent_id)
            | (NegotiationStateRow.agent_2_id == agent_id)
        )
    rows = session.exec(stmt).all()
    return NegotiationListResponseDTO(
        negotiations=[_row_to_summary(r) for r in rows],
        total=len(rows),
    )


@router.get("/{session_id}", response_model=NegotiationDetailDTO)
def get_negotiation(session_id: UUID, session: Session = Depends(_session)) -> NegotiationDetailDTO:
    row = session.get(NegotiationStateRow, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="negotiation not found")
    return _row_to_detail(row)


@router.post("/{session_id}/approval", response_model=DecisionResponseDTO)
def submit_decision(
    session_id: UUID,
    body: HumanDecisionDTO,
    request: Request,
    session: Session = Depends(_session),
) -> DecisionResponseDTO:
    """Submit a human decision — invokes engine.resume_session()."""
    row = session.get(NegotiationStateRow, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="negotiation not found")
    if row.status != SessionStatus.PENDING_HUMAN_APPROVAL.value:
        raise HTTPException(
            status_code=400,
            detail=f"session is not pending approval (current: {row.status})",
        )

    state = load_negotiation_state(session_id, session=session)
    if state is None or state.pending_decision is None:
        raise HTTPException(status_code=400, detail="no pending decision")

    action = HumanDecisionAction(body.action)

    # Build replacement_turn for REPLACE
    replacement_turn = None
    if action == HumanDecisionAction.REPLACE:
        if not body.replacement_turn:
            raise HTTPException(status_code=422, detail="REPLACE requires replacement_turn")
        replacement_turn = AgentTurn(
            public_message=body.replacement_turn,
            intent=TurnIntent.COUNTER_OFFER,
        )

    human_decision = HumanDecision(
        decision_id=state.pending_decision.decision_id,
        action=action,
        replacement_turn=replacement_turn,
    )

    # Invoke domain engine
    engine = (
        request.app.state.engine
        if hasattr(request.app.state, "engine")
        else build_engine_from_env()
    )
    result = engine.resume_session(state, human_decision)
    save_negotiation_state(result, portal_channel_id=row.portal_channel_id, session=session)
    session.commit()

    audit_map = {
        HumanDecisionAction.APPROVE: AuditAction.DECISION_APPROVED,
        HumanDecisionAction.REJECT: AuditAction.DECISION_REJECTED,
        HumanDecisionAction.REPLACE: AuditAction.DECISION_REPLACED,
    }

    if action == HumanDecisionAction.REJECT:
        update_agent_status(row.agent_1_id, AgentStatus.AVAILABLE, session=session)
        update_agent_status(row.agent_2_id, AgentStatus.AVAILABLE, session=session)

    write_audit(
        correlation_id=uuid4(),
        session_id=session_id,
        user_id=uuid4(),
        actor_type="HUMAN",
        actor_id="frontend",
        action=audit_map[action],
        severity="INFO",
        entity_type="DecisionRequest",
        entity_id=state.pending_decision.decision_id,
        reason=body.reason or f"human {body.action}",
        session=session,
    )

    return DecisionResponseDTO(
        decision_id=state.pending_decision.decision_id,
        session_id=session_id,
        action=body.action,
        new_status=result.state.status.value,
    )


@router.get("/{session_id}/audit", response_model=AuditListResponseDTO)
def get_audit_trail(session_id: UUID, session: Session = Depends(_session)) -> AuditListResponseDTO:
    stmt = select(AuditRecordRow).where(
        AuditRecordRow.session_id == session_id,
    ).order_by(AuditRecordRow.occurred_at.asc())
    rows = session.exec(stmt).all()
    return AuditListResponseDTO(
        records=[
            AuditRecordDTO(
                audit_id=r.audit_id,
                action=r.action,
                actor_type=r.actor_type,
                severity=r.severity,
                reason=r.reason,
                occurred_at=r.occurred_at,
            )
            for r in rows
        ],
        total=len(rows),
    )
