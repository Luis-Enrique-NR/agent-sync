from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from ai.domain.models import (
    AgentProfile,
    EngineEvent,
    EngineEventAudience,
    EngineEventType,
    EngineResult,
    EntityType,
    NegotiationState,
)
from ai.api.dto import to_agent_profile_dto
from ai.integration.events import (
    IntegrationEventType,
    SUPPORTED_INTEGRATION_EVENTS,
)
from ai.integration.portal import public_portal_messages, to_public_portal_message


def test_agent_profile_accepts_matchmaking_contract_fields() -> None:
    profile = AgentProfile(
        display_name="Vendedor",
        entity_type=EntityType.COMPANY,
        public_description="Lotes textiles",
        personality="Directo",
        objectives=["Vender"],
        price_range={"min": 800, "max": 1_000},
        logistics_preferences=["pickup", "delivery"],
    )

    assert profile.price_range == {"min": 800, "max": 1_000}
    assert profile.logistics_preferences == ["pickup", "delivery"]


def test_agent_profile_rejects_invalid_matchmaking_price_range() -> None:
    with pytest.raises(ValueError, match="min cannot exceed"):
        AgentProfile(
            display_name="Vendedor",
            entity_type=EntityType.COMPANY,
            public_description="Lotes textiles",
            personality="Directo",
            objectives=["Vender"],
            price_range={"min": 1_000, "max": 800},
        )


def test_agent_profile_dto_exposes_matchmaking_fields() -> None:
    profile = AgentProfile(
        display_name="Vendedor",
        entity_type=EntityType.COMPANY,
        public_description="Lotes textiles",
        personality="Directo",
        objectives=["Vender"],
        price_range={"min": 800, "max": 1_000},
        logistics_preferences=["pickup"],
    )

    dto = to_agent_profile_dto(profile)

    assert dto.price_range == {"min": 800, "max": 1_000}
    assert dto.logistics_preferences == ["pickup"]


def test_portal_adapter_uses_generated_public_turn_and_redacts_text() -> None:
    session_id = uuid4()
    speaker_id = uuid4()
    event = EngineEvent(
        session_id=session_id,
        event_type=EngineEventType.TURN_READY,
        audience=EngineEventAudience.PUBLIC,
        payload={
            "message": {
                "speaker_id": str(speaker_id),
                "public_message": "Oferta confirmada; email owner@example.com",
            }
        },
    )

    intent = to_public_portal_message(
        event,
        channel_id="channel-1",
        authorization_id="session-1",
    )

    assert intent is not None
    assert intent.sender_id == speaker_id
    assert intent.content == {"text": "Oferta confirmada; email [REDACTED]"}
    assert intent.correlation_id == session_id


def test_portal_adapter_never_maps_internal_event() -> None:
    event = EngineEvent(
        session_id=uuid4(),
        event_type=EngineEventType.APPROVAL_REQUIRED,
        payload={"message": {"public_message": "No debe publicarse"}},
    )

    assert (
        to_public_portal_message(
            event,
            channel_id="channel-1",
            authorization_id="session-1",
        )
        is None
    )


def test_public_portal_messages_extracts_only_generated_turns(b2b_agents, fixed_now):
    state = NegotiationState(
        agents=b2b_agents,
        current_speaker_id=b2b_agents[0].agent_id,
        started_at=fixed_now,
        deadline_at=fixed_now + timedelta(seconds=90),
    )
    event = EngineEvent(
        session_id=state.session_id,
        event_type=EngineEventType.TURN_READY,
        audience=EngineEventAudience.PUBLIC,
        payload={
            "message": {
                "speaker_id": str(b2b_agents[0].agent_id),
                "public_message": "Turn generado por AI",
            }
        },
    )

    intents = public_portal_messages(
        EngineResult(state=state, events=[event]),
        channel_id="channel-1",
        authorization_id="session-1",
    )

    assert len(intents) == 1
    assert intents[0].content["text"] == "Turn generado por AI"


def test_integration_event_catalog_contains_eda_lifecycle_events() -> None:
    assert IntegrationEventType.AGENT_REGISTERED.value in SUPPORTED_INTEGRATION_EVENTS
    assert IntegrationEventType.NEGOTIATION_REJECTED.value in SUPPORTED_INTEGRATION_EVENTS
