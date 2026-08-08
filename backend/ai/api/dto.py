"""Explicit API DTOs; domain models are never serialized directly to clients."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import ConfigDict, Field

from ai.domain.models import (
    AgentProfile,
    AgentTurn,
    DecisionRequest,
    EngineEvent,
    EngineEventAudience,
    EngineResult,
    HumanDecision,
    NegotiationState,
    SessionStatus,
    StrictModel,
    TranscriptMessage,
    TurnIntent,
)
from persistence.sanitize import sanitize_for_persistence, sanitize_text


class PublicTranscriptMessageDTO(StrictModel):
    speaker_id: UUID
    turn_index: int = Field(ge=1)
    proposal_id: UUID
    proposal_revision: int = Field(ge=1)
    responds_to: dict[str, Any] | None = None
    public_message: str
    intent: TurnIntent
    numeric_terms: list[dict[str, Any]] = Field(default_factory=list)
    data_requests: list[dict[str, Any]] = Field(default_factory=list)
    disclosed_categories: list[str] = Field(default_factory=list)
    requested_actions: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    approved_by_human: bool = False


class AgentProfileDTO(StrictModel):
    """Configuration DTO returned to the profile owner."""

    model_config = ConfigDict(extra="forbid")

    agent_id: UUID
    display_name: str
    entity_type: str
    status: str
    public_description: str
    interests: list[str]
    capabilities: list[str]
    personality: str
    objectives: list[str]
    hard_limits: list[dict[str, Any]]
    never_disclose: list[str]
    escalation_rules: list[dict[str, Any]]
    tool_grants: list[dict[str, Any]]
    goal_completion_mode: str
    remaining_goal_units: int | None


class NegotiationStateDTO(StrictModel):
    session_id: UUID
    owner_user_id: UUID | None
    status: SessionStatus
    current_speaker_id: UUID
    turn_count: int
    max_turns: int
    deadline_at: datetime
    pending_decision: dict[str, Any] | None
    pending_revalidation: dict[str, Any] | None
    transcript: list[PublicTranscriptMessageDTO]
    last_error_code: str | None


class EngineEventDTO(StrictModel):
    event_id: UUID
    session_id: UUID
    event_type: str
    audience: EngineEventAudience
    occurred_at: datetime
    payload: dict[str, Any]


class EngineResultDTO(StrictModel):
    state: NegotiationStateDTO
    events: list[EngineEventDTO]


class HumanDecisionDTO(StrictModel):
    decision_id: UUID
    action: str
    replacement_turn: dict[str, Any] | None = None

    def to_domain(self) -> HumanDecision:
        return HumanDecision.model_validate(self.model_dump(mode="json"))


def to_agent_profile_dto(profile: AgentProfile) -> AgentProfileDTO:
    payload = profile.model_dump(mode="json")
    return AgentProfileDTO(
        agent_id=profile.agent_id,
        display_name=profile.display_name,
        entity_type=profile.entity_type.value,
        status=profile.status.value,
        public_description=profile.public_description,
        interests=list(profile.interests),
        capabilities=list(profile.capabilities),
        personality=profile.personality,
        objectives=list(profile.objectives),
        hard_limits=payload["hard_limits"],
        never_disclose=sorted(item.value for item in profile.never_disclose),
        escalation_rules=payload["escalation_rules"],
        tool_grants=payload["tool_grants"],
        goal_completion_mode=profile.goal_completion_mode.value,
        remaining_goal_units=profile.remaining_goal_units,
    )


def to_public_transcript_dto(message: TranscriptMessage) -> PublicTranscriptMessageDTO:
    payload = message.model_dump(mode="json")
    return PublicTranscriptMessageDTO(
        speaker_id=message.speaker_id,
        turn_index=message.turn_index,
        proposal_id=message.proposal_id,
        proposal_revision=message.proposal_revision,
        responds_to=payload["responds_to"],
        public_message=sanitize_text(message.public_message),
        intent=message.intent,
        numeric_terms=payload["numeric_terms"],
        data_requests=payload["data_requests"],
        disclosed_categories=[item.value for item in message.disclosed_categories],
        requested_actions=[
            sanitize_for_persistence(item)
            for item in payload["requested_actions"]
        ],
        created_at=message.created_at,
        approved_by_human=message.approved_by_human,
    )


def _decision_payload(decision: DecisionRequest | None) -> dict[str, Any] | None:
    if decision is None:
        return None
    return decision.model_dump(mode="json")


def to_negotiation_state_dto(state: NegotiationState) -> NegotiationStateDTO:
    return NegotiationStateDTO(
        session_id=state.session_id,
        owner_user_id=state.owner_user_id,
        status=state.status,
        current_speaker_id=state.current_speaker_id,
        turn_count=state.turn_count,
        max_turns=state.max_turns,
        deadline_at=state.deadline_at,
        pending_decision=_decision_payload(state.pending_decision),
        pending_revalidation=(
            state.pending_revalidation.model_dump(mode="json")
            if state.pending_revalidation
            else None
        ),
        transcript=[to_public_transcript_dto(item) for item in state.transcript],
        last_error_code=state.last_error_code,
    )


def to_public_event_dto(event: EngineEvent) -> EngineEventDTO | None:
    if event.audience is not EngineEventAudience.PUBLIC:
        return None
    return EngineEventDTO(
        event_id=event.event_id,
        session_id=event.session_id,
        event_type=event.event_type.value,
        audience=event.audience,
        occurred_at=event.occurred_at,
        payload=sanitize_for_persistence(event.payload),
    )


def to_engine_result_dto(result: EngineResult) -> EngineResultDTO:
    return EngineResultDTO(
        state=to_negotiation_state_dto(result.state),
        events=[
            EngineEventDTO(
                event_id=event.event_id,
                session_id=event.session_id,
                event_type=event.event_type.value,
                audience=event.audience,
                occurred_at=event.occurred_at,
                payload=sanitize_for_persistence(event.payload),
            )
            for event in result.events
        ],
    )


def turn_to_api_payload(turn: AgentTurn) -> dict[str, Any]:
    """Small helper for API replacement-turn validation."""

    return sanitize_for_persistence(turn.model_dump(mode="json"))
