"""Negotiation session and human decision endpoints."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ai.domain.models import (
    AgentStatus,
    AuditAction,
    HumanDecision,
    HumanDecisionAction,
    NegotiationState,
    SessionStatus,
)
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


def _session() -> Session:
    return get_session()


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
    """List negotiations, optionally filtered by agent."""
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
def get_negotiation(
    session_id: UUID,
    session: Session = Depends(_session),
) -> NegotiationDetailDTO:
    """Retrieve full negotiation state with transcript."""
    row = session.get(NegotiationStateRow, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="negotiation not found")
    return _row_to_detail(row)


@router.post("/{session_id}/approval", response_model=DecisionResponseDTO)
def submit_decision(
    session_id: UUID,
    body: HumanDecisionDTO,
    session: Session = Depends(_session),
) -> DecisionResponseDTO:
    """Submit a human decision on a pending negotiation."""
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
    human_decision = HumanDecision(
        decision_id=state.pending_decision.decision_id,
        action=action,
    )

    if action == HumanDecisionAction.REJECT:
        row.status = SessionStatus.REJECTED.value
        update_agent_status(row.agent_1_id, AgentStatus.AVAILABLE, session=session)
        update_agent_status(row.agent_2_id, AgentStatus.AVAILABLE, session=session)
        audit_action = AuditAction.DECISION_REJECTED
        new_status = "REJECTED"

    elif action == HumanDecisionAction.APPROVE:
        row.status = SessionStatus.ACTIVE.value
        audit_action = AuditAction.DECISION_APPROVED
        new_status = "ACTIVE"

    else:  # REPLACE
        row.status = SessionStatus.ACTIVE.value
        audit_action = AuditAction.DECISION_REPLACED
        new_status = "ACTIVE"

    write_audit(
        correlation_id=uuid4(),
        session_id=session_id,
        user_id=uuid4(),  # TODO: real user auth
        actor_type="HUMAN",
        actor_id="frontend",
        action=audit_action,
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
        new_status=new_status,
    )


@router.get("/{session_id}/audit", response_model=AuditListResponseDTO)
def get_audit_trail(
    session_id: UUID,
    session: Session = Depends(_session),
) -> AuditListResponseDTO:
    """Retrieve audit trail for a negotiation session."""
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
