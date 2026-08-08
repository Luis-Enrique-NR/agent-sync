"""SQLModel tables for AgentSync persistence.

The JSON columns are the source of truth. Relational columns are derived caches
used for filtering and operational dashboards.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlmodel import JSON, Column, Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentProfileRow(SQLModel, table=True):
    __tablename__ = "agent_profiles"

    agent_id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(index=True)
    display_name: str = Field(max_length=120, index=True)
    entity_type: str = Field(max_length=20, index=True)
    status: str = Field(max_length=20, index=True)
    public_description: str = Field(sa_column=Column(JSON))
    interests: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    capabilities: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    raw_profile: dict = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class NegotiationStateRow(SQLModel, table=True):
    __tablename__ = "negotiation_states"

    session_id: UUID = Field(default_factory=uuid4, primary_key=True)
    owner_user_id: UUID | None = Field(default=None, index=True)
    portal_channel_id: str | None = Field(default=None, max_length=100, index=True)
    agent_1_id: UUID = Field(index=True)
    agent_2_id: UUID = Field(index=True)
    initiator_id: UUID = Field(index=True)
    current_speaker_id: UUID | None = Field(default=None, index=True)
    status: str = Field(max_length=30, index=True)
    turn_count: int = Field(default=0)
    max_turns: int = Field(default=8)
    started_at: datetime = Field(default_factory=utc_now)
    deadline_at: datetime | None = None
    closed_at: datetime | None = None
    last_error_code: str | None = Field(default=None, max_length=80)
    raw_state: dict = Field(sa_column=Column(JSON))
    version: int = Field(default=1, ge=1)
    last_updated_at: datetime = Field(default_factory=utc_now)


class NegotiationOutcomeRow(SQLModel, table=True):
    __tablename__ = "negotiation_outcomes"

    outcome_id: UUID = Field(default_factory=uuid4, primary_key=True)
    session_id: UUID = Field(index=True, unique=True)
    resolution: str = Field(max_length=30)
    agreed_price: Decimal | None = Field(default=None, max_digits=12, decimal_places=2)
    agreed_terms: dict | None = Field(default=None, sa_column=Column(JSON))
    disclosed_data: dict | None = Field(default=None, sa_column=Column(JSON))
    summary: str = Field(default="")
    created_at: datetime = Field(default_factory=utc_now)


class PrivateResolutionRow(SQLModel, table=True):
    __tablename__ = "private_resolutions"

    resolution_id: UUID = Field(default_factory=uuid4, primary_key=True)
    agent_id: UUID = Field(index=True)
    value_ref: str = Field(max_length=100, unique=True, index=True)
    category: str = Field(max_length=50)
    real_value: str = Field()
    created_at: datetime = Field(default_factory=utc_now)


class AuditRecordRow(SQLModel, table=True):
    __tablename__ = "audit_records"

    audit_id: UUID = Field(default_factory=uuid4, primary_key=True)
    correlation_id: UUID = Field(index=True)
    session_id: UUID | None = Field(default=None, index=True)
    agent_id: UUID | None = Field(default=None, index=True)
    user_id: UUID | None = Field(default=None, index=True)
    actor_type: str = Field(max_length=20, index=True)
    actor_id: str = Field(max_length=100)
    action: str = Field(max_length=80, index=True)
    severity: str = Field(max_length=20)
    entity_type: str | None = Field(default=None, max_length=50)
    entity_id: UUID | None = Field(default=None)
    previous_state: dict | None = Field(default=None, sa_column=Column(JSON))
    new_state: dict | None = Field(default=None, sa_column=Column(JSON))
    reason: str | None = Field(default=None, max_length=100)
    delivery_status: str | None = Field(default=None, max_length=20)
    source_ip: str | None = Field(default=None, max_length=45)
    payload: dict | None = Field(default=None, sa_column=Column(JSON))
    occurred_at: datetime = Field(default_factory=utc_now, index=True)
