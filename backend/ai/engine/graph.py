"""Bounded LangGraph state machine for two-agent negotiations."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from ai.domain.models import (
    AgentProfile,
    AgentTurn,
    DecisionReason,
    DecisionRequest,
    DecisionStatus,
    EngineEvent,
    EngineEventType,
    EngineResult,
    HumanDecision,
    HumanDecisionAction,
    NegotiationState,
    SessionStatus,
    TranscriptMessage,
    TurnIntent,
    utc_now,
)
from ai.policies.escalation import EscalationEvaluator
from ai.policies.guardrails import GuardrailPipeline
from ai.providers.base import GenerationRequest, LLMProvider


class _GraphState(TypedDict):
    session: NegotiationState
    events: list[EngineEvent]
    candidate: AgentTurn | None
    guardrail_feedback: list[str]
    candidate_attempts: int
    route: str


class NegotiationEngine:
    """Run until a human decision or terminal state is reached."""

    def __init__(
        self,
        provider: LLMProvider,
        *,
        guardrails: GuardrailPipeline | None = None,
        escalation: EscalationEvaluator | None = None,
        clock: Callable[[], datetime] = utc_now,
        max_candidate_retries: int = 1,
        history_window: int = 8,
    ) -> None:
        if max_candidate_retries < 0:
            raise ValueError("max_candidate_retries cannot be negative")
        if history_window <= 0:
            raise ValueError("history_window must be positive")
        self._provider = provider
        self._guardrails = guardrails or GuardrailPipeline()
        self._escalation = escalation or EscalationEvaluator()
        self._clock = clock
        self._max_candidate_retries = max_candidate_retries
        self._history_window = history_window
        self._graph = self._build_graph()

    def start_session(
        self,
        agent_a: AgentProfile,
        agent_b: AgentProfile,
        *,
        max_turns: int = 8,
        timeout_seconds: int = 90,
    ) -> EngineResult:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        started_at = self._clock()
        state = NegotiationState(
            agents=(agent_a, agent_b),
            current_speaker_id=agent_a.agent_id,
            max_turns=max_turns,
            started_at=started_at,
            deadline_at=started_at + timedelta(seconds=timeout_seconds),
        )
        return self.run_until_pause(state)

    def run_until_pause(self, state: NegotiationState) -> EngineResult:
        working_state = state.model_copy(deep=True)
        if working_state.status is not SessionStatus.ACTIVE:
            return EngineResult(state=working_state, events=[])

        graph_input: _GraphState = {
            "session": working_state,
            "events": [],
            "candidate": None,
            "guardrail_feedback": [],
            "candidate_attempts": 0,
            "route": "prepare",
        }
        result = self._graph.invoke(
            graph_input,
            config={"recursion_limit": max(50, working_state.max_turns * 8)},
        )
        return EngineResult(state=result["session"], events=result["events"])

    def resume_session(
        self, state: NegotiationState, human_decision: HumanDecision
    ) -> EngineResult:
        session = state.model_copy(deep=True)
        pending = session.pending_decision
        if session.status is not SessionStatus.PENDING_HUMAN_APPROVAL or not pending:
            raise ValueError("session has no pending human decision")
        if pending.decision_id != human_decision.decision_id:
            raise ValueError("decision_id does not match the pending decision")

        events: list[EngineEvent] = []
        pending.resolution = human_decision.action
        pending.resolved_at = self._clock()

        if human_decision.action is HumanDecisionAction.REJECT:
            pending.status = DecisionStatus.REJECTED
            session.decision_history.append(pending)
            session.pending_decision = None
            session.status = SessionStatus.REJECTED
            events.append(
                self._event(
                    session,
                    EngineEventType.DECISION_RESOLVED,
                    {"decision_id": str(pending.decision_id), "action": "REJECT"},
                )
            )
            events.append(self._event(session, EngineEventType.SESSION_REJECTED))
            return EngineResult(state=session, events=events)

        if human_decision.action is HumanDecisionAction.APPROVE:
            if pending.candidate_turn is None:
                raise ValueError("a non-convergence decision cannot be approved directly")
            candidate = pending.candidate_turn
            pending.status = DecisionStatus.APPROVED
        else:
            candidate = human_decision.replacement_turn
            if candidate is None:
                raise ValueError("REPLACE requires replacement_turn")
            guardrail_result = self._guardrails.evaluate(session.speaker(), candidate)
            if not guardrail_result.allowed:
                codes = ", ".join(
                    violation.code for violation in guardrail_result.violations
                )
                raise ValueError(f"replacement turn violates hard guardrails: {codes}")
            pending.status = DecisionStatus.REPLACED

        session.decision_history.append(pending)
        session.pending_decision = None
        session.status = SessionStatus.ACTIVE
        events.append(
            self._event(
                session,
                EngineEventType.DECISION_RESOLVED,
                {
                    "decision_id": str(pending.decision_id),
                    "action": human_decision.action.value,
                },
            )
        )
        self._publish_candidate(session, candidate, events, approved_by_human=True)

        if session.status is not SessionStatus.ACTIVE:
            return EngineResult(state=session, events=events)

        continued = self.run_until_pause(session)
        return EngineResult(
            state=continued.state,
            events=[*events, *continued.events],
        )

    def _build_graph(self):
        builder = StateGraph(_GraphState)
        builder.add_node("prepare", self._prepare_node)
        builder.add_node("generate", self._generate_node)
        builder.add_node("guardrail", self._guardrail_node)
        builder.add_node("escalate", self._escalate_node)
        builder.add_node("publish", self._publish_node)
        builder.add_edge(START, "prepare")
        builder.add_conditional_edges("prepare", self._route)
        builder.add_conditional_edges("generate", self._route)
        builder.add_conditional_edges("guardrail", self._route)
        builder.add_conditional_edges("escalate", self._route)
        builder.add_conditional_edges("publish", self._route)
        return builder.compile()

    @staticmethod
    def _route(state: _GraphState) -> str:
        return END if state["route"] == "end" else state["route"]

    def _prepare_node(self, state: _GraphState) -> _GraphState:
        session = state["session"]
        if session.status is not SessionStatus.ACTIVE:
            state["route"] = "end"
            return state
        if self._clock() >= session.deadline_at:
            self._pause_for_system_reason(state, DecisionReason.TIMEOUT)
            return state
        if session.turn_count >= session.max_turns:
            self._pause_for_system_reason(state, DecisionReason.NON_CONVERGENCE)
            return state
        state["route"] = "generate"
        return state

    def _generate_node(self, state: _GraphState) -> _GraphState:
        session = state["session"]
        try:
            state["candidate"] = self._provider.generate_turn(
                GenerationRequest(
                    speaker=session.speaker(),
                    counterpart=session.counterpart(),
                    transcript=tuple(session.transcript[-self._history_window :]),
                    guardrail_feedback=tuple(state["guardrail_feedback"]),
                )
            )
        except Exception:
            session.status = SessionStatus.FAILED
            session.last_error_code = "LLM_GENERATION_FAILED"
            state["events"].append(
                self._event(
                    session,
                    EngineEventType.SESSION_FAILED,
                    {"error_code": session.last_error_code},
                )
            )
            state["route"] = "end"
            return state
        if self._clock() >= session.deadline_at:
            state["candidate"] = None
            self._pause_for_system_reason(state, DecisionReason.TIMEOUT)
            return state
        state["route"] = "guardrail"
        return state

    def _guardrail_node(self, state: _GraphState) -> _GraphState:
        candidate = state["candidate"]
        if candidate is None:
            state["session"].status = SessionStatus.FAILED
            state["session"].last_error_code = "MISSING_CANDIDATE"
            state["route"] = "end"
            return state

        result = self._guardrails.evaluate(state["session"].speaker(), candidate)
        if result.allowed:
            state["route"] = "escalate"
            return state

        codes = [violation.code for violation in result.violations]
        state["events"].append(
            self._event(
                state["session"],
                EngineEventType.CANDIDATE_BLOCKED,
                {"violation_codes": codes},
            )
        )
        state["candidate_attempts"] += 1
        if state["candidate_attempts"] <= self._max_candidate_retries:
            state["guardrail_feedback"] = codes
            state["candidate"] = None
            state["route"] = "generate"
            return state

        state["session"].status = SessionStatus.FAILED
        state["session"].last_error_code = "GUARDRAIL_RETRY_EXHAUSTED"
        state["events"].append(
            self._event(
                state["session"],
                EngineEventType.SESSION_FAILED,
                {"error_code": state["session"].last_error_code},
            )
        )
        state["route"] = "end"
        return state

    def _escalate_node(self, state: _GraphState) -> _GraphState:
        candidate = state["candidate"]
        if candidate is None:
            state["session"].status = SessionStatus.FAILED
            state["session"].last_error_code = "MISSING_CANDIDATE"
            state["route"] = "end"
            return state
        result = self._escalation.evaluate(state["session"].speaker(), candidate)
        if not result.required:
            state["route"] = "publish"
            return state

        decision = DecisionRequest(
            session_id=state["session"].session_id,
            speaker_id=state["session"].current_speaker_id,
            reasons=list(result.reasons),
            matched_rule_ids=list(result.matched_rule_ids),
            candidate_turn=candidate,
        )
        state["session"].pending_decision = decision
        state["session"].status = SessionStatus.PENDING_HUMAN_APPROVAL
        state["events"].append(
            self._event(
                state["session"],
                EngineEventType.APPROVAL_REQUIRED,
                {"decision": decision.model_dump(mode="json")},
            )
        )
        state["route"] = "end"
        return state

    def _publish_node(self, state: _GraphState) -> _GraphState:
        candidate = state["candidate"]
        if candidate is None:
            state["session"].status = SessionStatus.FAILED
            state["session"].last_error_code = "MISSING_CANDIDATE"
            state["route"] = "end"
            return state
        self._publish_candidate(state["session"], candidate, state["events"])
        state["candidate"] = None
        state["candidate_attempts"] = 0
        state["guardrail_feedback"] = []
        state["route"] = (
            "prepare"
            if state["session"].status is SessionStatus.ACTIVE
            else "end"
        )
        return state

    def _publish_candidate(
        self,
        session: NegotiationState,
        candidate: AgentTurn,
        events: list[EngineEvent],
        *,
        approved_by_human: bool = False,
    ) -> None:
        session.turn_count += 1
        message = TranscriptMessage(
            speaker_id=session.current_speaker_id,
            turn_index=session.turn_count,
            public_message=candidate.public_message,
            intent=candidate.intent,
            numeric_terms=candidate.numeric_terms,
            disclosures=candidate.disclosure_requests,
            created_at=self._clock(),
            approved_by_human=approved_by_human,
        )
        session.transcript.append(message)
        events.append(
            self._event(
                session,
                EngineEventType.TURN_READY,
                {"message": message.model_dump(mode="json")},
            )
        )

        if candidate.intent is TurnIntent.ACCEPT:
            session.status = SessionStatus.RESOLVED
            events.append(self._event(session, EngineEventType.SESSION_RESOLVED))
        elif candidate.intent is TurnIntent.DECLINE:
            session.status = SessionStatus.REJECTED
            events.append(self._event(session, EngineEventType.SESSION_REJECTED))
        else:
            session.toggle_speaker()

    def _pause_for_system_reason(
        self, state: _GraphState, reason: DecisionReason
    ) -> None:
        session = state["session"]
        decision = DecisionRequest(
            session_id=session.session_id,
            speaker_id=session.current_speaker_id,
            reasons=[reason],
        )
        session.pending_decision = decision
        session.status = SessionStatus.PENDING_HUMAN_APPROVAL
        state["events"].append(
            self._event(
                session,
                EngineEventType.APPROVAL_REQUIRED,
                {"decision": decision.model_dump(mode="json")},
            )
        )
        state["route"] = "end"

    def _event(
        self,
        session: NegotiationState,
        event_type: EngineEventType,
        payload: dict | None = None,
    ) -> EngineEvent:
        return EngineEvent(
            session_id=session.session_id,
            event_type=event_type,
            payload=payload or {},
            occurred_at=self._clock(),
        )
