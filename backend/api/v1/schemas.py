"""DTOs for the AgentSync Frontend API — strict Pydantic, no domain coupling."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── Agent ──────────────────────────────────────────────────────────────


class AgentRegisterDTO(StrictDTO):
    display_name: str = Field(min_length=1, max_length=120)
    entity_type: str = Field(pattern=r"^(company|person)$")
    public_description: str = Field(min_length=1, max_length=500)
    personality: str = Field(min_length=1, max_length=1_000)
    objectives: list[str] = Field(min_length=1, max_length=20)
    interests: list[str] = Field(default_factory=list, max_length=20)
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    price_range: dict[str, float] | None = None
    logistics_preferences: list[str] = Field(default_factory=list, max_length=10)


class AgentProfileResponseDTO(StrictDTO):
    agent_id: UUID
    user_id: UUID
    display_name: str
    entity_type: str
    status: str
    public_description: str
    interests: list[str]
    capabilities: list[str]
    price_range: dict[str, float] | None = None
    logistics_preferences: list[str] = Field(default_factory=list)
    objectives: list[str]
    created_at: datetime
    updated_at: datetime


# ── Negotiation ────────────────────────────────────────────────────────


class NegotiationSummaryDTO(StrictDTO):
    session_id: UUID
    agent_1_id: UUID
    agent_2_id: UUID
    status: str
    portal_channel_id: str | None
    turn_count: int
    started_at: datetime
    closed_at: datetime | None


class TranscriptMessageDTO(StrictDTO):
    speaker_id: UUID
    turn_index: int
    public_message: str
    intent: str
    approved_by_human: bool
    created_at: datetime


class NegotiationDetailDTO(NegotiationSummaryDTO):
    initiator_id: UUID
    max_turns: int
    deadline_at: datetime | None
    last_error_code: str | None
    transcript: list[TranscriptMessageDTO] = Field(default_factory=list)


# ── Human decision ─────────────────────────────────────────────────────


class HumanDecisionDTO(StrictDTO):
    action: str = Field(pattern=r"^(APPROVE|REJECT|REPLACE)$")
    reason: str | None = Field(default=None, max_length=200)
    counter_offer_text: str | None = Field(default=None, max_length=1_500)


class DecisionResponseDTO(StrictDTO):
    decision_id: UUID
    session_id: UUID
    action: str
    new_status: str


# ── Audit ──────────────────────────────────────────────────────────────


class AuditRecordDTO(StrictDTO):
    audit_id: UUID
    action: str
    actor_type: str
    severity: str
    reason: str | None
    occurred_at: datetime


class AgentListResponseDTO(StrictDTO):
    agents: list[AgentProfileResponseDTO]
    total: int


class NegotiationListResponseDTO(StrictDTO):
    negotiations: list[NegotiationSummaryDTO]
    total: int


class AuditListResponseDTO(StrictDTO):
    records: list[AuditRecordDTO]
    total: int
