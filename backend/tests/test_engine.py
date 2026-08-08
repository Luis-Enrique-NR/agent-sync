from __future__ import annotations

from datetime import timedelta

import pytest

from ai.domain.models import (
    AgentTurn,
    DecisionReason,
    DisclosureRequest,
    EngineEventType,
    HumanDecision,
    HumanDecisionAction,
    NumericTerm,
    NegotiationState,
    SensitiveDataCategory,
    SessionStatus,
    TurnIntent,
)
from ai.engine.graph import NegotiationEngine
from ai.providers.fake import ScriptedLLMProvider


def _event_types(result):
    return [event.event_type for event in result.events]


def test_b2b_conversation_pauses_then_resolves_after_approval(
    b2b_agents, fixed_now
) -> None:
    offer = AgentTurn(
        public_message="Ofrezco el lote por 900 USD.",
        intent=TurnIntent.OFFER,
        numeric_terms=[NumericTerm(key="price_usd", value=900, unit="USD")],
    )
    acceptance = AgentTurn(
        public_message="Acepto el lote por 900 USD.",
        intent=TurnIntent.ACCEPT,
        numeric_terms=[NumericTerm(key="price_usd", value=900, unit="USD")],
    )
    engine = NegotiationEngine(
        ScriptedLLMProvider([offer, acceptance]), clock=lambda: fixed_now
    )

    paused = engine.start_session(*b2b_agents)

    assert paused.state.status is SessionStatus.PENDING_HUMAN_APPROVAL
    assert paused.state.turn_count == 1
    assert len(paused.state.transcript) == 1
    assert EngineEventType.APPROVAL_REQUIRED in _event_types(paused)
    decision = paused.state.pending_decision
    assert decision is not None

    resolved = engine.resume_session(
        paused.state,
        HumanDecision(
            decision_id=decision.decision_id,
            action=HumanDecisionAction.APPROVE,
        ),
    )

    assert resolved.state.status is SessionStatus.RESOLVED
    assert resolved.state.turn_count == 2
    assert resolved.state.transcript[-1].approved_by_human
    assert _event_types(resolved).count(EngineEventType.TURN_READY) == 1
    assert EngineEventType.SESSION_RESOLVED in _event_types(resolved)


def test_blocked_candidate_is_never_added_to_transcript(p2p_agents, fixed_now) -> None:
    invalid = AgentTurn(
        public_message="La dejo en 250 USD.",
        intent=TurnIntent.OFFER,
        numeric_terms=[NumericTerm(key="price_usd", value=250, unit="USD")],
    )
    valid = AgentTurn(
        public_message="La oferta válida es 320 USD.",
        intent=TurnIntent.OFFER,
        numeric_terms=[NumericTerm(key="price_usd", value=320, unit="USD")],
    )
    engine = NegotiationEngine(
        ScriptedLLMProvider([invalid, valid]), clock=lambda: fixed_now
    )

    result = engine.start_session(*p2p_agents, max_turns=1)

    assert result.state.status is SessionStatus.PENDING_HUMAN_APPROVAL
    assert result.state.transcript[0].public_message == valid.public_message
    assert all(
        message.public_message != invalid.public_message
        for message in result.state.transcript
    )
    assert EngineEventType.CANDIDATE_BLOCKED in _event_types(result)
    assert result.state.pending_decision is not None
    assert result.state.pending_decision.reasons == [DecisionReason.NON_CONVERGENCE]


def test_p2p_disclosure_pauses_before_publication_and_can_be_approved(
    p2p_agents, fixed_now
) -> None:
    candidate = AgentTurn(
        public_message="Acepto 330 USD y puedo compartir mi contacto tras autorización.",
        intent=TurnIntent.ACCEPT,
        numeric_terms=[NumericTerm(key="price_usd", value=330, unit="USD")],
        disclosure_requests=[
            DisclosureRequest(
                category=SensitiveDataCategory.PHONE,
                value_ref="contact_ref_valentina_phone",
                purpose="coordinar la revisión",
            )
        ],
    )
    engine = NegotiationEngine(
        ScriptedLLMProvider([candidate]), clock=lambda: fixed_now
    )

    paused = engine.start_session(*p2p_agents)

    assert paused.state.status is SessionStatus.PENDING_HUMAN_APPROVAL
    assert paused.state.transcript == []
    pending = paused.state.pending_decision
    assert pending is not None
    assert DecisionReason.MANDATORY_PERSONAL_DATA in pending.reasons

    resolved = engine.resume_session(
        paused.state,
        HumanDecision(
            decision_id=pending.decision_id,
            action=HumanDecisionAction.APPROVE,
        ),
    )

    assert resolved.state.status is SessionStatus.RESOLVED
    assert len(resolved.state.transcript) == 1
    assert "contact_ref" not in resolved.state.transcript[0].public_message


def test_reject_does_not_publish_pending_candidate(p2p_agents, fixed_now) -> None:
    candidate = AgentTurn(
        public_message="Acepto 330 USD.",
        intent=TurnIntent.ACCEPT,
        numeric_terms=[NumericTerm(key="price_usd", value=330, unit="USD")],
    )
    engine = NegotiationEngine(
        ScriptedLLMProvider([candidate]), clock=lambda: fixed_now
    )
    paused = engine.start_session(*p2p_agents)
    pending = paused.state.pending_decision
    assert pending is not None

    rejected = engine.resume_session(
        paused.state,
        HumanDecision(
            decision_id=pending.decision_id,
            action=HumanDecisionAction.REJECT,
        ),
    )

    assert rejected.state.status is SessionStatus.REJECTED
    assert rejected.state.transcript == []
    assert EngineEventType.TURN_READY not in _event_types(rejected)


def test_timeout_pauses_without_calling_provider(b2b_agents, fixed_now) -> None:
    provider = ScriptedLLMProvider([])
    engine = NegotiationEngine(provider, clock=lambda: fixed_now + timedelta(seconds=2))
    state = NegotiationState(
        agents=b2b_agents,
        current_speaker_id=b2b_agents[0].agent_id,
        max_turns=8,
        started_at=fixed_now,
        deadline_at=fixed_now + timedelta(seconds=1),
    )

    result = engine.run_until_pause(state)

    assert result.state.status is SessionStatus.PENDING_HUMAN_APPROVAL
    assert result.state.pending_decision is not None
    assert result.state.pending_decision.reasons == [DecisionReason.TIMEOUT]
    assert provider.requests == []


def test_candidate_returned_after_deadline_is_not_published(
    b2b_agents, fixed_now
) -> None:
    clock_values = iter(
        [
            fixed_now,
            fixed_now,
            fixed_now + timedelta(seconds=2),
            fixed_now + timedelta(seconds=2),
        ]
    )
    candidate = AgentTurn(
        public_message="Ofrezco el lote por 900 USD.",
        intent=TurnIntent.OFFER,
        numeric_terms=[NumericTerm(key="price_usd", value=900, unit="USD")],
    )
    engine = NegotiationEngine(
        ScriptedLLMProvider([candidate]), clock=lambda: next(clock_values)
    )

    result = engine.start_session(*b2b_agents, timeout_seconds=1)

    assert result.state.status is SessionStatus.PENDING_HUMAN_APPROVAL
    assert result.state.transcript == []
    assert result.state.pending_decision is not None
    assert result.state.pending_decision.reasons == [DecisionReason.TIMEOUT]
    assert EngineEventType.TURN_READY not in _event_types(result)


def test_provider_failure_fails_closed(b2b_agents, fixed_now) -> None:
    engine = NegotiationEngine(
        ScriptedLLMProvider([RuntimeError("network secret should not leak")]),
        clock=lambda: fixed_now,
    )

    result = engine.start_session(*b2b_agents)

    assert result.state.status is SessionStatus.FAILED
    assert result.state.last_error_code == "LLM_GENERATION_FAILED"
    serialized = result.model_dump_json()
    assert "network secret" not in serialized


def test_manual_replacement_still_passes_hard_guardrails(p2p_agents, fixed_now) -> None:
    candidate = AgentTurn(
        public_message="Acepto 330 USD.",
        intent=TurnIntent.ACCEPT,
        numeric_terms=[NumericTerm(key="price_usd", value=330, unit="USD")],
    )
    engine = NegotiationEngine(
        ScriptedLLMProvider([candidate]), clock=lambda: fixed_now
    )
    paused = engine.start_session(*p2p_agents)
    pending = paused.state.pending_decision
    assert pending is not None

    unsafe_replacement = AgentTurn(
        public_message="Acepto 250 USD.",
        intent=TurnIntent.ACCEPT,
        numeric_terms=[NumericTerm(key="price_usd", value=250, unit="USD")],
    )
    with pytest.raises(ValueError, match="HARD_NUMERIC_LIMIT"):
        engine.resume_session(
            paused.state,
            HumanDecision(
                decision_id=pending.decision_id,
                action=HumanDecisionAction.REPLACE,
                replacement_turn=unsafe_replacement,
            ),
        )
