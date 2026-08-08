"""Strict domain contracts for negotiations, policies, and engine events."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class EntityType(str, Enum):
    COMPANY = "company"
    PERSON = "person"


class AgentStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    PAUSED = "PAUSED"


class SessionStatus(str, Enum):
    SEARCHING = "SEARCHING"
    ACTIVE = "ACTIVE"
    PENDING_HUMAN_APPROVAL = "PENDING_HUMAN_APPROVAL"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class TurnIntent(str, Enum):
    QUESTION = "QUESTION"
    OFFER = "OFFER"
    COUNTER_OFFER = "COUNTER_OFFER"
    ACCEPT = "ACCEPT"
    DECLINE = "DECLINE"


class NumericOperator(str, Enum):
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    EQUAL = "eq"


class SensitiveDataCategory(str, Enum):
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    EXACT_ADDRESS = "EXACT_ADDRESS"
    LIVE_LOCATION = "LIVE_LOCATION"
    MEETING_POINT = "MEETING_POINT"


MANDATORY_APPROVAL_CATEGORIES = frozenset(
    {
        SensitiveDataCategory.PHONE,
        SensitiveDataCategory.EMAIL,
        SensitiveDataCategory.EXACT_ADDRESS,
        SensitiveDataCategory.LIVE_LOCATION,
    }
)


class ToolFactVisibility(str, Enum):
    PUBLIC = "PUBLIC"
    PRIVATE_REFERENCE = "PRIVATE_REFERENCE"


class EscalationRuleType(str, Enum):
    ANY_FINAL_PRICE = "ANY_FINAL_PRICE"
    AMOUNT_ABOVE = "AMOUNT_ABOVE"
    SHARE_PERSONAL_DATA = "SHARE_PERSONAL_DATA"
    COMMIT_DATE = "COMMIT_DATE"
    FINAL_AGREEMENT = "FINAL_AGREEMENT"


class CommitmentKind(str, Enum):
    DATE = "DATE"
    MEETING = "MEETING"
    OTHER = "OTHER"


class DecisionReason(str, Enum):
    MANDATORY_PERSONAL_DATA = "MANDATORY_PERSONAL_DATA"
    USER_RULE = "USER_RULE"
    NON_CONVERGENCE = "NON_CONVERGENCE"
    TIMEOUT = "TIMEOUT"


class DecisionStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REPLACED = "REPLACED"


class HumanDecisionAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REPLACE = "REPLACE"


class EngineEventType(str, Enum):
    TURN_READY = "TURN_READY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    DECISION_RESOLVED = "DECISION_RESOLVED"
    CANDIDATE_BLOCKED = "CANDIDATE_BLOCKED"
    SESSION_RESOLVED = "SESSION_RESOLVED"
    SESSION_REJECTED = "SESSION_REJECTED"
    SESSION_FAILED = "SESSION_FAILED"


class AuditAction(str, Enum):
    """Canonical actions for audit_records consumed by Backend API and Frontend."""

    # Agent lifecycle
    AGENT_CREATED = "AGENT_CREATED"
    AGENT_UPDATED = "AGENT_UPDATED"
    AGENT_PUBLISHED = "AGENT_PUBLISHED"
    AGENT_PAUSED = "AGENT_PAUSED"
    AGENT_RESUMED = "AGENT_RESUMED"
    AGENT_UNPUBLISHED = "AGENT_UNPUBLISHED"

    # Session lifecycle
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_SEARCHING = "SESSION_SEARCHING"
    MATCHMAKING_EVALUATED = "MATCHMAKING_EVALUATED"

    # Engine / AI execution
    TURN_PUBLISHED = "TURN_PUBLISHED"
    GUARDRAIL_PASSED = "GUARDRAIL_PASSED"
    GUARDRAIL_RETRY = "GUARDRAIL_RETRY"
    CANDIDATE_BLOCKED = "CANDIDATE_BLOCKED"

    # Human supervision / PII
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    DECISION_APPROVED = "DECISION_APPROVED"
    DECISION_REJECTED = "DECISION_REJECTED"
    DECISION_REPLACED = "DECISION_REPLACED"
    PRIVATE_DATA_RESOLVED = "PRIVATE_DATA_RESOLVED"
    PRIVATE_DATA_DISCLOSED = "PRIVATE_DATA_DISCLOSED"

    # Terminal events
    SESSION_RESOLVED = "SESSION_RESOLVED"
    SESSION_REJECTED = "SESSION_REJECTED"
    SESSION_FAILED = "SESSION_FAILED"


class NumericTerm(StrictModel):
    key: str = Field(min_length=1, max_length=80)
    value: float
    unit: str | None = Field(default=None, max_length=20)


class NumericLimit(StrictModel):
    key: str = Field(min_length=1, max_length=80)
    operator: NumericOperator
    value: float
    unit: str | None = Field(default=None, max_length=20)


class DisclosureRequest(StrictModel):
    category: SensitiveDataCategory
    value_ref: str = Field(min_length=3, max_length=120)
    purpose: str = Field(min_length=1, max_length=240)


class Commitment(StrictModel):
    kind: CommitmentKind
    value: str = Field(min_length=1, max_length=160)


class ToolFact(StrictModel):
    key: str = Field(min_length=1, max_length=80)
    visibility: ToolFactVisibility
    value: str | int | float | bool | None = None
    value_ref: str | None = Field(default=None, max_length=120)
    category: SensitiveDataCategory | None = None

    @model_validator(mode="after")
    def protect_private_values(self) -> Self:
        if self.visibility is ToolFactVisibility.PUBLIC:
            if self.value is None or self.value_ref is not None or self.category is not None:
                raise ValueError("public facts require value and forbid private metadata")
        else:
            if self.value is not None or not self.value_ref or self.category is None:
                raise ValueError(
                    "private facts require value_ref and category, and forbid value"
                )
        return self


class EscalationRule(StrictModel):
    rule_id: str = Field(min_length=1, max_length=80)
    rule_type: EscalationRuleType
    key: str | None = Field(default=None, max_length=80)
    threshold: float | None = None
    categories: set[SensitiveDataCategory] = Field(default_factory=set)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_rule_shape(self) -> Self:
        if self.rule_type is EscalationRuleType.AMOUNT_ABOVE:
            if not self.key or self.threshold is None:
                raise ValueError("AMOUNT_ABOVE requires key and threshold")
        if self.rule_type is EscalationRuleType.SHARE_PERSONAL_DATA:
            if not self.categories:
                raise ValueError("SHARE_PERSONAL_DATA requires at least one category")
        return self


class AgentProfile(StrictModel):
    agent_id: UUID = Field(default_factory=uuid4)
    display_name: str = Field(min_length=1, max_length=120)
    entity_type: EntityType
    public_description: str = Field(min_length=1, max_length=500)
    personality: str = Field(min_length=1, max_length=1_000)
    objectives: list[str] = Field(min_length=1, max_length=20)
    hard_limits: list[NumericLimit] = Field(default_factory=list)
    never_disclose: set[SensitiveDataCategory] = Field(default_factory=set)
    escalation_rules: list[EscalationRule] = Field(default_factory=list)
    tool_facts: list[ToolFact] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list, max_length=20)
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    status: AgentStatus = AgentStatus.AVAILABLE
    price_range: dict[str, float] | None = None
    logistics_preferences: list[str] = Field(default_factory=list, max_length=10)


class AgentTurn(StrictModel):
    public_message: str = Field(min_length=1, max_length=1_500)
    intent: TurnIntent
    numeric_terms: list[NumericTerm] = Field(default_factory=list, max_length=20)
    disclosure_requests: list[DisclosureRequest] = Field(
        default_factory=list, max_length=10
    )
    commitments: list[Commitment] = Field(default_factory=list, max_length=10)


class TranscriptMessage(StrictModel):
    speaker_id: UUID
    turn_index: int = Field(ge=1)
    public_message: str
    intent: TurnIntent
    numeric_terms: list[NumericTerm] = Field(default_factory=list)
    disclosures: list[DisclosureRequest] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    approved_by_human: bool = False


class DecisionRequest(StrictModel):
    decision_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    speaker_id: UUID
    reasons: list[DecisionReason] = Field(min_length=1)
    matched_rule_ids: list[str] = Field(default_factory=list)
    candidate_turn: AgentTurn | None = None
    status: DecisionStatus = DecisionStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None
    resolution: HumanDecisionAction | None = None


class HumanDecision(StrictModel):
    decision_id: UUID
    action: HumanDecisionAction
    replacement_turn: AgentTurn | None = None

    @model_validator(mode="after")
    def validate_replacement(self) -> Self:
        if self.action is HumanDecisionAction.REPLACE:
            if self.replacement_turn is None:
                raise ValueError("REPLACE requires replacement_turn")
        elif self.replacement_turn is not None:
            raise ValueError("replacement_turn is only valid for REPLACE")
        return self


class NegotiationState(StrictModel):
    session_id: UUID = Field(default_factory=uuid4)
    agents: tuple[AgentProfile, AgentProfile]
    current_speaker_id: UUID
    status: SessionStatus = SessionStatus.ACTIVE
    transcript: list[TranscriptMessage] = Field(default_factory=list)
    turn_count: int = Field(default=0, ge=0)
    max_turns: int = Field(default=8, ge=1, le=100)
    started_at: datetime = Field(default_factory=utc_now)
    deadline_at: datetime
    pending_decision: DecisionRequest | None = None
    decision_history: list[DecisionRequest] = Field(default_factory=list)
    last_error_code: str | None = None

    @model_validator(mode="after")
    def validate_participants(self) -> Self:
        agent_ids = {agent.agent_id for agent in self.agents}
        if len(agent_ids) != 2:
            raise ValueError("a negotiation requires two different agents")
        if self.current_speaker_id not in agent_ids:
            raise ValueError("current_speaker_id must belong to the session")
        if self.started_at.tzinfo is None or self.deadline_at.tzinfo is None:
            raise ValueError("session timestamps must be timezone-aware")
        if self.deadline_at <= self.started_at:
            raise ValueError("deadline_at must be later than started_at")
        return self

    def speaker(self) -> AgentProfile:
        return next(
            agent for agent in self.agents if agent.agent_id == self.current_speaker_id
        )

    def counterpart(self) -> AgentProfile:
        return next(
            agent for agent in self.agents if agent.agent_id != self.current_speaker_id
        )

    def toggle_speaker(self) -> None:
        self.current_speaker_id = self.counterpart().agent_id


class EngineEvent(StrictModel):
    event_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    event_type: EngineEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=utc_now)


class EngineResult(StrictModel):
    state: NegotiationState
    events: list[EngineEvent] = Field(default_factory=list)
