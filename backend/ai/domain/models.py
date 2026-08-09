"""Strict domain contracts for negotiations, policies, and engine events."""

from __future__ import annotations

import json
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
    """Lifecycle state exposed to matchmaking and the Frontend."""

    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    PAUSED = "PAUSED"


class SessionStatus(str, Enum):
    SEARCHING = "SEARCHING"
    ACTIVE = "ACTIVE"
    PENDING_HUMAN_APPROVAL = "PENDING_HUMAN_APPROVAL"
    REVALIDATING = "REVALIDATING"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"
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


class ToolRiskLevel(str, Enum):
    READ_ONLY = "READ_ONLY"
    SENSITIVE_READ = "SENSITIVE_READ"
    EXTERNAL_WRITE = "EXTERNAL_WRITE"


class ToolApprovalMode(str, Enum):
    AUTO = "AUTO"
    ALWAYS = "ALWAYS"


class ToolValueType(str, Enum):
    STRING = "STRING"
    INTEGER = "INTEGER"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"


class ToolExecutionStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    DENIED = "DENIED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class ToolPolicyOutcome(str, Enum):
    AUTO_EXECUTE = "AUTO_EXECUTE"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


class ProviderStepKind(str, Enum):
    TURN = "TURN"
    TOOL_CALL = "TOOL_CALL"


class EscalationRuleType(str, Enum):
    ANY_FINAL_PRICE = "ANY_FINAL_PRICE"
    AMOUNT_ABOVE = "AMOUNT_ABOVE"
    SHARE_PERSONAL_DATA = "SHARE_PERSONAL_DATA"
    COMMIT_DATE = "COMMIT_DATE"
    FINAL_AGREEMENT = "FINAL_AGREEMENT"
    REQUEST_ACTION = "REQUEST_ACTION"


class ActionType(str, Enum):
    MEETING = "MEETING"
    RESERVE_RESOURCE = "RESERVE_RESOURCE"
    SEND_DOCUMENT = "SEND_DOCUMENT"
    SEND_EMAIL = "SEND_EMAIL"
    OTHER = "OTHER"


class CommitmentKind(str, Enum):
    DATE = "DATE"
    MEETING = "MEETING"
    OTHER = "OTHER"


class DecisionReason(str, Enum):
    MANDATORY_PERSONAL_DATA = "MANDATORY_PERSONAL_DATA"
    USER_RULE = "USER_RULE"
    INBOUND_ACTION = "INBOUND_ACTION"
    TOOL_EXECUTION = "TOOL_EXECUTION"
    TOOL_BUDGET_EXHAUSTED = "TOOL_BUDGET_EXHAUSTED"
    NON_CONVERGENCE = "NON_CONVERGENCE"
    TIMEOUT = "TIMEOUT"


class DecisionStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REPLACED = "REPLACED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class DecisionKind(str, Enum):
    OUTBOUND_TURN = "OUTBOUND_TURN"
    INBOUND_ACTION = "INBOUND_ACTION"
    TOOL_EXECUTION = "TOOL_EXECUTION"
    SYSTEM = "SYSTEM"


class HumanDecisionAction(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REPLACE = "REPLACE"


class RevalidationOutcome(str, Enum):
    CONFIRMED = "CONFIRMED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"


class ExternalSessionEventType(str, Enum):
    COUNTERPART_WITHDREW = "COUNTERPART_WITHDREW"
    PROPOSAL_EXPIRED = "PROPOSAL_EXPIRED"


class GoalCompletionMode(str, Enum):
    ONE_SHOT = "ONE_SHOT"
    QUANTITY = "QUANTITY"
    CONTINUOUS = "CONTINUOUS"


class GoalReviewAction(str, Enum):
    COMPLETE = "COMPLETE"
    CONTINUE = "CONTINUE"


class EngineEventType(str, Enum):
    TURN_READY = "TURN_READY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    DECISION_RESOLVED = "DECISION_RESOLVED"
    REVALIDATION_REQUIRED = "REVALIDATION_REQUIRED"
    REVALIDATION_RESOLVED = "REVALIDATION_RESOLVED"
    EXTERNAL_EVENT_APPLIED = "EXTERNAL_EVENT_APPLIED"
    CANDIDATE_BLOCKED = "CANDIDATE_BLOCKED"
    SESSION_RESOLVED = "SESSION_RESOLVED"
    SESSION_REJECTED = "SESSION_REJECTED"
    SESSION_WITHDRAWN = "SESSION_WITHDRAWN"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_FAILED = "SESSION_FAILED"
    GOAL_PROGRESS_REVIEW_REQUIRED = "GOAL_PROGRESS_REVIEW_REQUIRED"
    TOOL_EXECUTION_COMPLETED = "TOOL_EXECUTION_COMPLETED"
    TOOL_EXECUTION_DENIED = "TOOL_EXECUTION_DENIED"


class AuditAction(str, Enum):
    """Stable action catalog persisted by the audit trail."""

    AGENT_CREATED = "AGENT_CREATED"
    AGENT_UPDATED = "AGENT_UPDATED"
    AGENT_PUBLISHED = "AGENT_PUBLISHED"
    AGENT_PAUSED = "AGENT_PAUSED"
    AGENT_RESUMED = "AGENT_RESUMED"
    AGENT_UNPUBLISHED = "AGENT_UNPUBLISHED"
    SESSION_CREATED = "SESSION_CREATED"
    SESSION_SEARCHING = "SESSION_SEARCHING"
    MATCHMAKING_EVALUATED = "MATCHMAKING_EVALUATED"
    TURN_PUBLISHED = "TURN_PUBLISHED"
    GUARDRAIL_PASSED = "GUARDRAIL_PASSED"
    GUARDRAIL_RETRY = "GUARDRAIL_RETRY"
    CANDIDATE_BLOCKED = "CANDIDATE_BLOCKED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    DECISION_APPROVED = "DECISION_APPROVED"
    DECISION_REJECTED = "DECISION_REJECTED"
    DECISION_REPLACED = "DECISION_REPLACED"
    PRIVATE_DATA_RESOLVED = "PRIVATE_DATA_RESOLVED"
    PRIVATE_DATA_DISCLOSED = "PRIVATE_DATA_DISCLOSED"
    TOOL_EXECUTION_REQUESTED = "TOOL_EXECUTION_REQUESTED"
    TOOL_EXECUTION_COMPLETED = "TOOL_EXECUTION_COMPLETED"
    TOOL_EXECUTION_DENIED = "TOOL_EXECUTION_DENIED"
    REVALIDATION_REQUESTED = "REVALIDATION_REQUESTED"
    REVALIDATION_RESOLVED = "REVALIDATION_RESOLVED"
    SESSION_WITHDRAWN = "SESSION_WITHDRAWN"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_RESOLVED = "SESSION_RESOLVED"
    SESSION_REJECTED = "SESSION_REJECTED"
    SESSION_FAILED = "SESSION_FAILED"
    GOAL_PROGRESS_REVIEWED = "GOAL_PROGRESS_REVIEWED"


class EngineEventAudience(str, Enum):
    INTERNAL = "INTERNAL"
    PUBLIC = "PUBLIC"


class NumericTerm(StrictModel):
    key: str = Field(min_length=1, max_length=80)
    value: float
    unit: str | None = Field(default=None, max_length=20)


class NumericLimit(StrictModel):
    key: str = Field(min_length=1, max_length=80)
    operator: NumericOperator
    value: float
    unit: str | None = Field(default=None, max_length=20)


class DataRequest(StrictModel):
    category: SensitiveDataCategory
    purpose: str = Field(min_length=1, max_length=240)


class ProposedDisclosure(StrictModel):
    category: SensitiveDataCategory
    value_ref: str = Field(min_length=3, max_length=120)
    purpose: str = Field(min_length=1, max_length=240)


class ProposalReference(StrictModel):
    proposal_id: UUID
    revision: int = Field(ge=1)


class RequestedAction(StrictModel):
    action_id: UUID = Field(default_factory=uuid4)
    action_type: ActionType
    purpose: str = Field(min_length=1, max_length=240)
    parameters: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict, max_length=20
    )
    valid_until: datetime | None = None

    @model_validator(mode="after")
    def validate_valid_until(self) -> Self:
        if self.valid_until is not None and self.valid_until.tzinfo is None:
            raise ValueError("valid_until must be timezone-aware")
        return self


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
    action_types: set[ActionType] = Field(default_factory=set)
    enabled: bool = True

    @model_validator(mode="after")
    def validate_rule_shape(self) -> Self:
        if self.rule_type is EscalationRuleType.AMOUNT_ABOVE:
            if not self.key or self.threshold is None:
                raise ValueError("AMOUNT_ABOVE requires key and threshold")
        if self.rule_type is EscalationRuleType.SHARE_PERSONAL_DATA:
            if not self.categories:
                raise ValueError("SHARE_PERSONAL_DATA requires at least one category")
        if self.rule_type is EscalationRuleType.REQUEST_ACTION:
            if not self.action_types:
                raise ValueError("REQUEST_ACTION requires at least one action type")
        return self


class ToolParameterDefinition(StrictModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    value_type: ToolValueType
    description: str = Field(min_length=1, max_length=240)
    required: bool = True
    max_length: int | None = Field(default=None, ge=1, le=4_000)

    @model_validator(mode="after")
    def validate_max_length(self) -> Self:
        if self.max_length is not None and self.value_type is not ToolValueType.STRING:
            raise ValueError("max_length is only valid for STRING parameters")
        return self


class ToolDescriptor(StrictModel):
    name: str = Field(
        min_length=3,
        max_length=120,
        pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$",
    )
    description: str = Field(min_length=1, max_length=500)
    risk_level: ToolRiskLevel
    parameters: list[ToolParameterDefinition] = Field(
        default_factory=list, max_length=20
    )
    requires_human_approval: bool = False
    timeout_seconds: int = Field(default=15, ge=1, le=60)
    max_output_chars: int = Field(default=12_000, ge=100, le=50_000)

    @model_validator(mode="after")
    def validate_descriptor(self) -> Self:
        names = [parameter.name for parameter in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError("tool parameter names must be unique")
        if (
            self.risk_level is ToolRiskLevel.EXTERNAL_WRITE
            and not self.requires_human_approval
        ):
            raise ValueError("EXTERNAL_WRITE tools must require human approval")
        return self


class ToolGrant(StrictModel):
    tool_name: str = Field(
        min_length=3,
        max_length=120,
        pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$",
    )
    enabled: bool = True
    approval_mode: ToolApprovalMode = ToolApprovalMode.AUTO


class ToolCallRequest(StrictModel):
    call_id: UUID = Field(default_factory=uuid4)
    tool_name: str = Field(
        min_length=3,
        max_length=120,
        pattern=r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$",
    )
    purpose: str = Field(min_length=1, max_length=300)
    arguments: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict, max_length=20
    )


class ToolExecutionResult(StrictModel):
    call_id: UUID
    tool_name: str = Field(min_length=3, max_length=120)
    requested_by_agent_id: UUID
    status: ToolExecutionStatus
    output: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = Field(default=None, max_length=100)
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime = Field(default_factory=utc_now)
    idempotent_replay: bool = False

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.started_at.tzinfo is None or self.completed_at.tzinfo is None:
            raise ValueError("tool result timestamps must be timezone-aware")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at")
        if self.status is ToolExecutionStatus.SUCCEEDED and self.error_code is not None:
            raise ValueError("successful tool results cannot contain error_code")
        if self.status is not ToolExecutionStatus.SUCCEEDED and not self.error_code:
            raise ValueError("non-successful tool results require error_code")
        try:
            serialized = json.dumps(
                self.output,
                ensure_ascii=False,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("tool output must be JSON serializable") from exc
        if len(serialized) > 50_000:
            raise ValueError("tool output exceeds the domain maximum")
        return self


class AgentProfile(StrictModel):
    agent_id: UUID = Field(default_factory=uuid4)
    display_name: str = Field(min_length=1, max_length=120)
    entity_type: EntityType
    public_description: str = Field(min_length=1, max_length=500)
    interests: list[str] = Field(default_factory=list, max_length=20)
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    status: AgentStatus = AgentStatus.AVAILABLE
    price_range: dict[str, float] | None = None
    logistics_preferences: list[str] = Field(default_factory=list, max_length=10)
    personality: str = Field(min_length=1, max_length=1_000)
    objectives: list[str] = Field(min_length=1, max_length=20)
    hard_limits: list[NumericLimit] = Field(default_factory=list)
    never_disclose: set[SensitiveDataCategory] = Field(default_factory=set)
    escalation_rules: list[EscalationRule] = Field(default_factory=list)
    tool_facts: list[ToolFact] = Field(default_factory=list)
    tool_grants: list[ToolGrant] = Field(default_factory=list, max_length=50)
    goal_completion_mode: GoalCompletionMode = GoalCompletionMode.ONE_SHOT
    remaining_goal_units: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_goal_tracking(self) -> Self:
        if self.price_range is not None:
            unknown_keys = set(self.price_range) - {"min", "max"}
            if unknown_keys:
                raise ValueError("price_range only supports min and max")
            minimum = self.price_range.get("min")
            maximum = self.price_range.get("max")
            if minimum is not None and minimum < 0:
                raise ValueError("price_range.min cannot be negative")
            if maximum is not None and maximum < 0:
                raise ValueError("price_range.max cannot be negative")
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError("price_range.min cannot exceed price_range.max")
        if (
            self.goal_completion_mode is GoalCompletionMode.QUANTITY
            and self.remaining_goal_units is None
        ):
            raise ValueError("QUANTITY goals require remaining_goal_units")
        grant_names = [grant.tool_name for grant in self.tool_grants]
        if len(grant_names) != len(set(grant_names)):
            raise ValueError("tool grants must be unique per agent")
        return self


class AgentTurn(StrictModel):
    proposal_id: UUID = Field(default_factory=uuid4)
    proposal_revision: int = Field(default=1, ge=1)
    responds_to: ProposalReference | None = None
    public_message: str = Field(min_length=1, max_length=1_500)
    intent: TurnIntent
    numeric_terms: list[NumericTerm] = Field(default_factory=list, max_length=20)
    data_requests: list[DataRequest] = Field(default_factory=list, max_length=10)
    proposed_disclosures: list[ProposedDisclosure] = Field(
        default_factory=list, max_length=10
    )
    requested_actions: list[RequestedAction] = Field(
        default_factory=list, max_length=10
    )
    commitments: list[Commitment] = Field(default_factory=list, max_length=10)


class ProviderStep(StrictModel):
    kind: ProviderStepKind
    turn: AgentTurn | None = None
    tool_call: ToolCallRequest | None = None

    @model_validator(mode="after")
    def validate_step(self) -> Self:
        if self.kind is ProviderStepKind.TURN:
            if self.turn is None or self.tool_call is not None:
                raise ValueError("TURN steps require only turn")
        elif self.tool_call is None or self.turn is not None:
            raise ValueError("TOOL_CALL steps require only tool_call")
        return self


class TranscriptMessage(StrictModel):
    speaker_id: UUID
    turn_index: int = Field(ge=1)
    proposal_id: UUID = Field(default_factory=uuid4)
    proposal_revision: int = Field(default=1, ge=1)
    responds_to: ProposalReference | None = None
    public_message: str
    intent: TurnIntent
    numeric_terms: list[NumericTerm] = Field(default_factory=list)
    data_requests: list[DataRequest] = Field(default_factory=list)
    disclosed_categories: list[SensitiveDataCategory] = Field(default_factory=list)
    requested_actions: list[RequestedAction] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    approved_by_human: bool = False


class DecisionRequest(StrictModel):
    decision_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    owner_agent_id: UUID
    requester_agent_id: UUID | None = None
    kind: DecisionKind
    reasons: list[DecisionReason] = Field(min_length=1)
    matched_rule_ids: list[str] = Field(default_factory=list)
    candidate_turn: AgentTurn | None = None
    proposal_id: UUID | None = None
    proposal_revision: int | None = Field(default=None, ge=1)
    requested_actions: list[RequestedAction] = Field(default_factory=list)
    tool_call: ToolCallRequest | None = None
    requires_revalidation: bool = False
    status: DecisionStatus = DecisionStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None
    resolution: HumanDecisionAction | None = None

    @model_validator(mode="after")
    def validate_decision_shape(self) -> Self:
        if self.kind is DecisionKind.OUTBOUND_TURN:
            if self.candidate_turn is None or self.tool_call is not None:
                raise ValueError("OUTBOUND_TURN requires candidate_turn")
        elif self.kind is DecisionKind.INBOUND_ACTION:
            if self.candidate_turn is not None or self.tool_call is not None:
                raise ValueError("INBOUND_ACTION forbids candidate_turn")
            if self.requester_agent_id is None or not self.requested_actions:
                raise ValueError(
                    "INBOUND_ACTION requires requester and requested actions"
                )
            if self.proposal_id is None or self.proposal_revision is None:
                raise ValueError("INBOUND_ACTION requires proposal identity")
            if not self.requires_revalidation:
                raise ValueError("INBOUND_ACTION must require revalidation")
        elif self.kind is DecisionKind.TOOL_EXECUTION:
            if self.tool_call is None:
                raise ValueError("TOOL_EXECUTION requires tool_call")
            if self.candidate_turn is not None or self.requested_actions:
                raise ValueError("TOOL_EXECUTION forbids public turn content")
        elif (
            self.candidate_turn is not None
            or self.requested_actions
            or self.tool_call is not None
        ):
            raise ValueError("SYSTEM decisions cannot carry turn content")
        return self


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


class ActionAuthorization(StrictModel):
    action_id: UUID
    decision_id: UUID
    owner_agent_id: UUID
    requester_agent_id: UUID
    approved: bool
    decided_at: datetime = Field(default_factory=utc_now)


class RevalidationRequest(StrictModel):
    revalidation_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    source_decision_id: UUID
    owner_agent_id: UUID
    requester_agent_id: UUID
    proposal_id: UUID
    proposal_revision: int = Field(ge=1)
    requested_actions: list[RequestedAction] = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)


class RevalidationResult(StrictModel):
    revalidation_id: UUID
    outcome: RevalidationOutcome
    confirmed_proposal_revision: int | None = Field(default=None, ge=1)
    reason_code: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def validate_confirmation(self) -> Self:
        if (
            self.outcome is RevalidationOutcome.CONFIRMED
            and self.confirmed_proposal_revision is None
        ):
            raise ValueError("CONFIRMED requires confirmed_proposal_revision")
        return self


class ExternalSessionEvent(StrictModel):
    event_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    actor_agent_id: UUID
    event_type: ExternalSessionEventType
    proposal_id: UUID | None = None
    reason_code: str | None = Field(default=None, max_length=80)
    occurred_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_occurred_at(self) -> Self:
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        return self


class GoalProgressReview(StrictModel):
    review_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    agent_id: UUID
    objectives: list[str] = Field(min_length=1)
    suggested_action: GoalReviewAction
    proposed_remaining_units: int | None = Field(default=None, ge=0)


class NegotiationState(StrictModel):
    session_id: UUID = Field(default_factory=uuid4)
    owner_user_id: UUID | None = None
    agents: tuple[AgentProfile, AgentProfile]
    current_speaker_id: UUID
    status: SessionStatus = SessionStatus.ACTIVE
    transcript: list[TranscriptMessage] = Field(default_factory=list)
    turn_count: int = Field(default=0, ge=0)
    max_turns: int = Field(default=8, ge=1, le=100)
    started_at: datetime = Field(default_factory=utc_now)
    deadline_at: datetime
    execution_timeout_seconds: int = Field(default=90, ge=1)
    tool_call_count: int = Field(default=0, ge=0)
    max_tool_calls: int = Field(default=6, ge=0, le=50)
    pending_decision: DecisionRequest | None = None
    pending_revalidation: RevalidationRequest | None = None
    decision_history: list[DecisionRequest] = Field(default_factory=list)
    action_authorizations: list[ActionAuthorization] = Field(default_factory=list)
    tool_results: list[ToolExecutionResult] = Field(default_factory=list)
    processed_external_event_ids: set[UUID] = Field(default_factory=set)
    processed_revalidation_ids: set[UUID] = Field(default_factory=set)
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

    def is_terminal(self) -> bool:
        return self.status in {
            SessionStatus.RESOLVED,
            SessionStatus.REJECTED,
            SessionStatus.WITHDRAWN,
            SessionStatus.EXPIRED,
            SessionStatus.FAILED,
        }


class EngineEvent(StrictModel):
    event_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    correlation_id: UUID | None = None
    event_type: EngineEventType
    audience: EngineEventAudience = EngineEventAudience.INTERNAL
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=utc_now)


class EngineResult(StrictModel):
    state: NegotiationState
    events: list[EngineEvent] = Field(default_factory=list)
