from __future__ import annotations

from datetime import timedelta

import pytest

from ai.domain.models import (
    ActionType,
    AgentTurn,
    DataRequest,
    DecisionKind,
    DecisionReason,
    DecisionStatus,
    EngineEventAudience,
    EngineEventType,
    ExternalSessionEvent,
    ExternalSessionEventType,
    GoalCompletionMode,
    GoalReviewAction,
    HumanDecision,
    HumanDecisionAction,
    NumericTerm,
    NegotiationState,
    ProposedDisclosure,
    ProviderStep,
    ProviderStepKind,
    RequestedAction,
    RevalidationOutcome,
    RevalidationResult,
    SensitiveDataCategory,
    SessionStatus,
    ToolCallRequest,
    ToolExecutionStatus,
    TurnIntent,
)
from ai.engine.graph import NegotiationEngine
from ai.providers.fake import ScriptedLLMProvider
from ai.tools.mocks import DemoToolStore, build_demo_tool_gateway


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
    assert _event_types(resolved).count(
        EngineEventType.GOAL_PROGRESS_REVIEW_REQUIRED
    ) == 2


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
        proposed_disclosures=[
            ProposedDisclosure(
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
    assert "contact_ref" not in resolved.state.transcript[0].model_dump_json()
    turn_event = next(
        event
        for event in resolved.events
        if event.event_type is EngineEventType.TURN_READY
    )
    assert turn_event.audience is EngineEventAudience.PUBLIC
    assert "contact_ref" not in turn_event.model_dump_json()


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


def test_approved_private_references_never_reach_counterpart_context_or_public_events(
    p2p_agents, fixed_now
) -> None:
    seller_offer = AgentTurn(
        public_message=(
            "Ofrezco la bicicleta por 350 USD y puedo compartir contacto "
            "después de autorización."
        ),
        intent=TurnIntent.OFFER,
        numeric_terms=[NumericTerm(key="price_usd", value=350, unit="USD")],
        proposed_disclosures=[
            ProposedDisclosure(
                category=SensitiveDataCategory.PHONE,
                value_ref="contact_ref_valentina_phone",
                purpose="coordinar la revisión",
            ),
            ProposedDisclosure(
                category=SensitiveDataCategory.MEETING_POINT,
                value_ref="location_ref_public_meeting_point",
                purpose="coordinar en un lugar público",
            ),
        ],
    )
    buyer_question = AgentTurn(
        public_message="¿Puedes confirmar el contacto después de autorización?",
        intent=TurnIntent.QUESTION,
        data_requests=[
            DataRequest(
                category=SensitiveDataCategory.PHONE,
                purpose="coordinar la revisión",
            )
        ],
    )
    provider = ScriptedLLMProvider([seller_offer, buyer_question])
    engine = NegotiationEngine(provider, clock=lambda: fixed_now)

    paused = engine.start_session(*p2p_agents, max_turns=2)

    pending = paused.state.pending_decision
    assert pending is not None
    approval_event = next(
        event
        for event in paused.events
        if event.event_type is EngineEventType.APPROVAL_REQUIRED
    )
    assert approval_event.audience is EngineEventAudience.INTERNAL
    assert "contact_ref_valentina_phone" in approval_event.model_dump_json()

    continued = engine.resume_session(
        paused.state,
        HumanDecision(
            decision_id=pending.decision_id,
            action=HumanDecisionAction.APPROVE,
        ),
    )

    assert continued.state.status is SessionStatus.PENDING_HUMAN_APPROVAL
    assert continued.state.last_error_code is None
    assert len(provider.requests) == 2
    counterpart_context = "".join(
        message.model_dump_json() for message in provider.requests[1].transcript
    )
    assert "contact_ref_valentina_phone" not in counterpart_context
    assert "location_ref_public_meeting_point" not in counterpart_context
    public_events = [
        event
        for event in continued.events
        if event.audience is EngineEventAudience.PUBLIC
    ]
    assert len(public_events) == 2
    assert all("_ref_" not in event.model_dump_json() for event in public_events)
    assert all(
        event.event_type is EngineEventType.TURN_READY for event in public_events
    )


def test_inbound_meeting_waits_a_week_then_revalidates_before_continuing(
    p2p_agents, fixed_now
) -> None:
    now = [fixed_now]
    meeting = RequestedAction(
        action_type=ActionType.MEETING,
        purpose="revisar la bicicleta en un lugar público",
        parameters={"window": "sábado entre 10:00 y 14:00"},
        valid_until=fixed_now + timedelta(days=8),
    )
    request = AgentTurn(
        public_message="¿Podemos reunirnos el sábado para revisar la bicicleta?",
        intent=TurnIntent.QUESTION,
        requested_actions=[meeting],
    )
    response = AgentTurn(
        public_message="La reunión está autorizada; confirmemos el horario.",
        intent=TurnIntent.QUESTION,
    )
    provider = ScriptedLLMProvider([request, response])
    engine = NegotiationEngine(provider, clock=lambda: now[0])

    paused = engine.start_session(*p2p_agents, max_turns=2)

    pending = paused.state.pending_decision
    assert pending is not None
    assert pending.kind is DecisionKind.INBOUND_ACTION
    assert pending.owner_agent_id == p2p_agents[1].agent_id
    assert pending.requester_agent_id == p2p_agents[0].agent_id
    assert pending.requested_actions == [meeting]
    assert paused.state.current_speaker_id == p2p_agents[1].agent_id
    assert EngineEventType.TURN_READY in _event_types(paused)
    assert EngineEventType.APPROVAL_REQUIRED in _event_types(paused)
    restored_pause = NegotiationState.model_validate_json(
        paused.state.model_dump_json()
    )
    assert restored_pause == paused.state

    now[0] = fixed_now + timedelta(days=7)
    approved = engine.resume_session(
        restored_pause,
        HumanDecision(
            decision_id=pending.decision_id,
            action=HumanDecisionAction.APPROVE,
        ),
    )

    assert approved.state.status is SessionStatus.REVALIDATING
    assert approved.state.pending_revalidation is not None
    assert len(provider.requests) == 1
    assert EngineEventType.REVALIDATION_REQUIRED in _event_types(approved)

    restored_revalidation = NegotiationState.model_validate_json(
        approved.state.model_dump_json()
    )
    revalidation = restored_revalidation.pending_revalidation
    assert revalidation is not None
    continued = engine.apply_revalidation(
        restored_revalidation,
        RevalidationResult(
            revalidation_id=revalidation.revalidation_id,
            outcome=RevalidationOutcome.CONFIRMED,
            confirmed_proposal_revision=revalidation.proposal_revision,
        ),
    )

    assert len(provider.requests) == 2
    assert provider.requests[1].action_authorizations[0].approved
    assert provider.requests[1].action_authorizations[0].action_id == meeting.action_id
    assert continued.state.deadline_at == now[0] + timedelta(seconds=90)
    assert continued.state.status is SessionStatus.PENDING_HUMAN_APPROVAL
    assert continued.state.pending_decision is not None
    assert continued.state.pending_decision.reasons == [
        DecisionReason.NON_CONVERGENCE
    ]
    duplicate = engine.apply_revalidation(
        continued.state,
        RevalidationResult(
            revalidation_id=revalidation.revalidation_id,
            outcome=RevalidationOutcome.CONFIRMED,
            confirmed_proposal_revision=revalidation.proposal_revision,
        ),
    )
    assert duplicate.events == []
    assert duplicate.state == continued.state


def test_expired_inbound_action_cannot_be_approved_late(
    p2p_agents, fixed_now
) -> None:
    now = [fixed_now]
    request = AgentTurn(
        public_message="¿Podemos reunirnos mañana?",
        intent=TurnIntent.QUESTION,
        requested_actions=[
            RequestedAction(
                action_type=ActionType.MEETING,
                purpose="revisar la bicicleta",
                valid_until=fixed_now + timedelta(days=1),
            )
        ],
    )
    provider = ScriptedLLMProvider([request])
    engine = NegotiationEngine(provider, clock=lambda: now[0])
    paused = engine.start_session(*p2p_agents)
    pending = paused.state.pending_decision
    assert pending is not None

    now[0] = fixed_now + timedelta(days=7)
    expired = engine.resume_session(
        paused.state,
        HumanDecision(
            decision_id=pending.decision_id,
            action=HumanDecisionAction.APPROVE,
        ),
    )

    assert expired.state.status is SessionStatus.EXPIRED
    assert expired.state.pending_revalidation is None
    assert expired.state.decision_history[-1].status is DecisionStatus.EXPIRED
    assert len(provider.requests) == 1
    assert EngineEventType.SESSION_EXPIRED in _event_types(expired)


def test_action_expiring_during_revalidation_cannot_be_authorized(
    p2p_agents, fixed_now
) -> None:
    now = [fixed_now]
    request = AgentTurn(
        public_message="¿Podemos reunirnos mañana?",
        intent=TurnIntent.QUESTION,
        requested_actions=[
            RequestedAction(
                action_type=ActionType.MEETING,
                purpose="revisar la bicicleta",
                valid_until=fixed_now + timedelta(days=1),
            )
        ],
    )
    provider = ScriptedLLMProvider([request])
    engine = NegotiationEngine(provider, clock=lambda: now[0])
    paused = engine.start_session(*p2p_agents)
    pending = paused.state.pending_decision
    assert pending is not None
    approved = engine.resume_session(
        paused.state,
        HumanDecision(
            decision_id=pending.decision_id,
            action=HumanDecisionAction.APPROVE,
        ),
    )
    revalidation = approved.state.pending_revalidation
    assert revalidation is not None

    now[0] = fixed_now + timedelta(days=2)
    expired = engine.apply_revalidation(
        approved.state,
        RevalidationResult(
            revalidation_id=revalidation.revalidation_id,
            outcome=RevalidationOutcome.CONFIRMED,
            confirmed_proposal_revision=revalidation.proposal_revision,
        ),
    )

    assert expired.state.status is SessionStatus.EXPIRED
    assert expired.state.pending_revalidation is None
    assert expired.state.action_authorizations == []
    expiry_event = next(
        event
        for event in expired.events
        if event.event_type is EngineEventType.SESSION_EXPIRED
    )
    assert expiry_event.payload["reason_code"] == "ACTION_VALIDITY_ELAPSED"
    assert len(provider.requests) == 1


def test_rejecting_inbound_action_continues_negotiation_without_revalidation(
    p2p_agents, fixed_now
) -> None:
    request = AgentTurn(
        public_message="¿Podemos reunirnos para revisar la bicicleta?",
        intent=TurnIntent.QUESTION,
        requested_actions=[
            RequestedAction(
                action_type=ActionType.MEETING,
                purpose="revisar la bicicleta",
            )
        ],
    )
    response = AgentTurn(
        public_message="Prefiero continuar sin coordinar una reunión.",
        intent=TurnIntent.QUESTION,
    )
    provider = ScriptedLLMProvider([request, response])
    engine = NegotiationEngine(provider, clock=lambda: fixed_now)
    paused = engine.start_session(*p2p_agents, max_turns=2)
    pending = paused.state.pending_decision
    assert pending is not None

    continued = engine.resume_session(
        paused.state,
        HumanDecision(
            decision_id=pending.decision_id,
            action=HumanDecisionAction.REJECT,
        ),
    )

    assert len(provider.requests) == 2
    assert not provider.requests[1].action_authorizations[0].approved
    assert continued.state.status is SessionStatus.PENDING_HUMAN_APPROVAL
    assert continued.state.pending_revalidation is None
    assert EngineEventType.REVALIDATION_REQUIRED not in _event_types(continued)


def test_counterpart_can_withdraw_while_human_decision_is_pending(
    p2p_agents, fixed_now
) -> None:
    request = AgentTurn(
        public_message="¿Podemos reunirnos para revisar la bicicleta?",
        intent=TurnIntent.QUESTION,
        requested_actions=[
            RequestedAction(
                action_type=ActionType.MEETING,
                purpose="revisar la bicicleta",
            )
        ],
    )
    engine = NegotiationEngine(
        ScriptedLLMProvider([request]),
        clock=lambda: fixed_now,
    )
    paused = engine.start_session(*p2p_agents)
    pending = paused.state.pending_decision
    assert pending is not None
    withdrawal = ExternalSessionEvent(
        session_id=paused.state.session_id,
        actor_agent_id=p2p_agents[0].agent_id,
        event_type=ExternalSessionEventType.COUNTERPART_WITHDREW,
        proposal_id=pending.proposal_id,
        reason_code="OUT_OF_STOCK",
    )

    withdrawn = engine.apply_external_event(paused.state, withdrawal)

    assert withdrawn.state.status is SessionStatus.WITHDRAWN
    assert withdrawn.state.pending_decision is None
    assert withdrawn.state.decision_history[-1].status is DecisionStatus.CANCELLED
    assert EngineEventType.SESSION_WITHDRAWN in _event_types(withdrawn)

    duplicate = engine.apply_external_event(withdrawn.state, withdrawal)
    assert duplicate.state.status is SessionStatus.WITHDRAWN
    assert duplicate.events == []

    late_expiry = engine.apply_external_event(
        withdrawn.state,
        ExternalSessionEvent(
            session_id=withdrawn.state.session_id,
            actor_agent_id=p2p_agents[0].agent_id,
            event_type=ExternalSessionEventType.PROPOSAL_EXPIRED,
        ),
    )
    assert late_expiry.state.status is SessionStatus.WITHDRAWN
    assert late_expiry.events[0].payload["ignored"] == "SESSION_ALREADY_TERMINAL"


def test_withdrawing_one_session_does_not_change_another_active_option(
    p2p_agents, fixed_now
) -> None:
    meeting_request = AgentTurn(
        public_message="¿Podemos reunirnos para revisar la bicicleta?",
        intent=TurnIntent.QUESTION,
        requested_actions=[
            RequestedAction(
                action_type=ActionType.MEETING,
                purpose="revisar la bicicleta",
            )
        ],
    )
    alternative_offer = AgentTurn(
        public_message="La bicicleta sigue disponible por 340 USD.",
        intent=TurnIntent.OFFER,
        numeric_terms=[NumericTerm(key="price_usd", value=340, unit="USD")],
    )
    engine = NegotiationEngine(
        ScriptedLLMProvider([meeting_request, alternative_offer]),
        clock=lambda: fixed_now,
    )
    first_option = engine.start_session(*p2p_agents)
    second_option = engine.start_session(*p2p_agents, max_turns=1)
    first_pending = first_option.state.pending_decision
    assert first_pending is not None
    assert first_option.state.session_id != second_option.state.session_id

    withdrawn = engine.apply_external_event(
        first_option.state,
        ExternalSessionEvent(
            session_id=first_option.state.session_id,
            actor_agent_id=p2p_agents[0].agent_id,
            event_type=ExternalSessionEventType.COUNTERPART_WITHDREW,
            proposal_id=first_pending.proposal_id,
        ),
    )

    assert withdrawn.state.status is SessionStatus.WITHDRAWN
    assert second_option.state.status is SessionStatus.PENDING_HUMAN_APPROVAL
    assert second_option.state.pending_decision is not None
    assert second_option.state.pending_decision.reasons == [
        DecisionReason.NON_CONVERGENCE
    ]


def test_quantity_goal_review_suggests_continuing_when_stock_remains(
    b2b_agents, fixed_now
) -> None:
    seller = b2b_agents[0].model_copy(
        update={
            "goal_completion_mode": GoalCompletionMode.QUANTITY,
            "remaining_goal_units": 3,
        },
        deep=True,
    )
    acceptance = AgentTurn(
        public_message="Acepto el acuerdo por 900 USD.",
        intent=TurnIntent.ACCEPT,
        numeric_terms=[NumericTerm(key="price_usd", value=900, unit="USD")],
    )
    engine = NegotiationEngine(
        ScriptedLLMProvider([acceptance]),
        clock=lambda: fixed_now,
    )
    paused = engine.start_session(seller, b2b_agents[1])
    pending = paused.state.pending_decision
    assert pending is not None

    resolved = engine.resume_session(
        paused.state,
        HumanDecision(
            decision_id=pending.decision_id,
            action=HumanDecisionAction.APPROVE,
        ),
    )

    seller_review = next(
        event.payload["review"]
        for event in resolved.events
        if event.event_type is EngineEventType.GOAL_PROGRESS_REVIEW_REQUIRED
        and event.payload["review"]["agent_id"] == str(seller.agent_id)
    )
    assert seller_review["suggested_action"] == GoalReviewAction.CONTINUE.value
    assert seller_review["proposed_remaining_units"] == 2


def test_read_only_tool_runs_and_feeds_private_result_to_same_agent(
    p2p_agents, fixed_now
) -> None:
    tool_call = ToolCallRequest(
        tool_name="calendar.check_availability",
        purpose="consultar disponibilidad antes de proponer una fecha",
        arguments={
            "start_date": "2026-08-15",
            "end_date": "2026-08-16",
        },
    )
    followup = AgentTurn(
        public_message="Tengo una ventana disponible para seguir coordinando.",
        intent=TurnIntent.QUESTION,
    )
    provider = ScriptedLLMProvider(
        [
            ProviderStep(
                kind=ProviderStepKind.TOOL_CALL,
                tool_call=tool_call,
            ),
            followup,
        ]
    )
    engine = NegotiationEngine(
        provider,
        tool_gateway=build_demo_tool_gateway(clock=lambda: fixed_now),
        clock=lambda: fixed_now,
    )

    result = engine.start_session(*p2p_agents, max_turns=1)

    assert len(provider.requests) == 2
    assert result.state.tool_call_count == 1
    assert result.state.tool_results[0].status is ToolExecutionStatus.SUCCEEDED
    assert provider.requests[1].tool_results == tuple(result.state.tool_results)
    assert len(result.state.transcript) == 1
    tool_event = next(
        event
        for event in result.events
        if event.event_type is EngineEventType.TOOL_EXECUTION_COMPLETED
    )
    assert tool_event.audience is EngineEventAudience.INTERNAL


def test_ungranted_tool_is_denied_without_stopping_negotiation(
    p2p_agents, fixed_now
) -> None:
    provider = ScriptedLLMProvider(
        [
            ProviderStep(
                kind=ProviderStepKind.TOOL_CALL,
                tool_call=ToolCallRequest(
                    tool_name="web.search",
                    purpose="buscar un precio de referencia",
                    arguments={"query": "bicicleta urbana usada"},
                ),
            ),
            AgentTurn(
                public_message="Continuemos con la información disponible.",
                intent=TurnIntent.QUESTION,
            ),
        ]
    )
    engine = NegotiationEngine(
        provider,
        tool_gateway=build_demo_tool_gateway(clock=lambda: fixed_now),
        clock=lambda: fixed_now,
    )

    result = engine.start_session(*p2p_agents, max_turns=1)

    denied = result.state.tool_results[0]
    assert denied.status is ToolExecutionStatus.DENIED
    assert denied.error_code == "TOOL_NOT_GRANTED"
    assert provider.requests[1].tool_results == (denied,)
    assert EngineEventType.TOOL_EXECUTION_DENIED in _event_types(result)


def test_external_write_tool_waits_for_human_before_execution(
    p2p_agents, fixed_now
) -> None:
    store = DemoToolStore()
    email_call = ToolCallRequest(
        tool_name="email.send_notification",
        purpose="avisar al propietario sobre una oportunidad",
        arguments={
            "subject": "Nueva oportunidad",
            "body": "Tu agente encontró una negociación que requiere atención.",
        },
    )
    provider = ScriptedLLMProvider(
        [
            ProviderStep(
                kind=ProviderStepKind.TOOL_CALL,
                tool_call=email_call,
            ),
            AgentTurn(
                public_message="La notificación fue autorizada.",
                intent=TurnIntent.QUESTION,
            ),
        ]
    )
    engine = NegotiationEngine(
        provider,
        tool_gateway=build_demo_tool_gateway(
            store=store,
            clock=lambda: fixed_now,
        ),
        clock=lambda: fixed_now,
    )

    paused = engine.start_session(*p2p_agents, max_turns=1)

    pending = paused.state.pending_decision
    assert pending is not None
    assert pending.kind is DecisionKind.TOOL_EXECUTION
    assert pending.tool_call == email_call
    assert store.email_notifications == []
    assert paused.state.transcript == []
    restored_pause = NegotiationState.model_validate_json(
        paused.state.model_dump_json()
    )
    assert restored_pause == paused.state

    continued = engine.resume_session(
        restored_pause,
        HumanDecision(
            decision_id=pending.decision_id,
            action=HumanDecisionAction.APPROVE,
        ),
    )

    assert len(store.email_notifications) == 1
    assert continued.state.tool_results[0].status is ToolExecutionStatus.SUCCEEDED
    assert provider.requests[1].tool_results == tuple(continued.state.tool_results)
    assert EngineEventType.TOOL_EXECUTION_COMPLETED in _event_types(continued)


def test_rejected_write_tool_has_no_side_effect_and_agent_continues(
    p2p_agents, fixed_now
) -> None:
    store = DemoToolStore()
    provider = ScriptedLLMProvider(
        [
            ProviderStep(
                kind=ProviderStepKind.TOOL_CALL,
                tool_call=ToolCallRequest(
                    tool_name="email.send_notification",
                    purpose="avisar al propietario",
                    arguments={
                        "subject": "Decisión pendiente",
                        "body": "Tu agente necesita una respuesta.",
                    },
                ),
            ),
            AgentTurn(
                public_message="Continuaré sin enviar la notificación.",
                intent=TurnIntent.QUESTION,
            ),
        ]
    )
    engine = NegotiationEngine(
        provider,
        tool_gateway=build_demo_tool_gateway(
            store=store,
            clock=lambda: fixed_now,
        ),
        clock=lambda: fixed_now,
    )
    paused = engine.start_session(*p2p_agents, max_turns=1)
    pending = paused.state.pending_decision
    assert pending is not None

    continued = engine.resume_session(
        paused.state,
        HumanDecision(
            decision_id=pending.decision_id,
            action=HumanDecisionAction.REJECT,
        ),
    )

    assert store.email_notifications == []
    assert continued.state.tool_results[0].status is ToolExecutionStatus.REJECTED
    assert provider.requests[1].tool_results == tuple(continued.state.tool_results)
    assert EngineEventType.TOOL_EXECUTION_DENIED in _event_types(continued)


def test_tool_budget_stops_a_model_tool_loop(p2p_agents, fixed_now) -> None:
    first_call = ToolCallRequest(
        tool_name="calendar.check_availability",
        purpose="primera consulta",
        arguments={
            "start_date": "2026-08-15",
            "end_date": "2026-08-16",
        },
    )
    second_call = ToolCallRequest(
        tool_name="calendar.check_availability",
        purpose="consulta repetida",
        arguments={
            "start_date": "2026-08-15",
            "end_date": "2026-08-16",
        },
    )
    provider = ScriptedLLMProvider(
        [
            ProviderStep(
                kind=ProviderStepKind.TOOL_CALL,
                tool_call=first_call,
            ),
            ProviderStep(
                kind=ProviderStepKind.TOOL_CALL,
                tool_call=second_call,
            ),
        ]
    )
    engine = NegotiationEngine(
        provider,
        tool_gateway=build_demo_tool_gateway(clock=lambda: fixed_now),
        clock=lambda: fixed_now,
    )

    result = engine.start_session(*p2p_agents, max_tool_calls=1)

    assert result.state.tool_call_count == 1
    assert len(result.state.tool_results) == 1
    assert result.state.status is SessionStatus.PENDING_HUMAN_APPROVAL
    assert result.state.pending_decision is not None
    assert result.state.pending_decision.kind is DecisionKind.SYSTEM
    assert result.state.pending_decision.reasons == [
        DecisionReason.TOOL_BUDGET_EXHAUSTED
    ]
