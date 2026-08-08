"""Bounded LangGraph state machine for two-agent negotiations."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timedelta
from typing import TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph

from ai.domain.models import (
    ActionAuthorization,
    AgentProfile,
    AgentTurn,
    DecisionKind,
    DecisionReason,
    DecisionRequest,
    DecisionStatus,
    EngineEvent,
    EngineEventAudience,
    EngineEventType,
    EngineResult,
    ExternalSessionEvent,
    ExternalSessionEventType,
    GoalCompletionMode,
    GoalProgressReview,
    GoalReviewAction,
    HumanDecision,
    HumanDecisionAction,
    NegotiationState,
    ProviderStepKind,
    RevalidationOutcome,
    RevalidationRequest,
    RevalidationResult,
    SessionStatus,
    TranscriptMessage,
    ToolCallRequest,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolPolicyOutcome,
    TurnIntent,
    utc_now,
)
from ai.observability import (
    LLMObservation,
    NullTelemetrySink,
    TelemetrySink,
)
from ai.policies.escalation import EscalationEvaluator, InboundEscalationEvaluator
from ai.policies.budget import BudgetExceededError, UserBudgetManager
from ai.policies.guardrails import GuardrailPipeline
from ai.providers.base import GenerationRequest, LLMProvider
from ai.tools.gateway import ToolGateway


class _GraphState(TypedDict):
    session: NegotiationState
    events: list[EngineEvent]
    candidate: AgentTurn | None
    tool_call: ToolCallRequest | None
    guardrail_feedback: list[str]
    candidate_attempts: int
    route: str


class LLMTimeoutError(TimeoutError):
    """Raised when one provider step exceeds the engine's hard time budget."""


class NegotiationEngine:
    """Run until a human decision or terminal state is reached."""

    def __init__(
        self,
        provider: LLMProvider,
        *,
        guardrails: GuardrailPipeline | None = None,
        escalation: EscalationEvaluator | None = None,
        inbound_escalation: InboundEscalationEvaluator | None = None,
        tool_gateway: ToolGateway | None = None,
        clock: Callable[[], datetime] = utc_now,
        max_candidate_retries: int = 1,
        history_window: int = 8,
        budget_manager: UserBudgetManager | None = None,
        telemetry_sink: TelemetrySink | None = None,
        estimated_llm_cost_usd: float = 0.0,
        llm_timeout_seconds: float = 25.0,
        default_max_turns: int = 8,
        default_session_timeout_seconds: int = 90,
        default_max_tool_calls: int = 6,
    ) -> None:
        if max_candidate_retries < 0:
            raise ValueError("max_candidate_retries cannot be negative")
        if history_window <= 0:
            raise ValueError("history_window must be positive")
        if llm_timeout_seconds <= 0:
            raise ValueError("llm_timeout_seconds must be positive")
        if default_max_turns <= 0:
            raise ValueError("default_max_turns must be positive")
        if default_session_timeout_seconds <= 0:
            raise ValueError("default_session_timeout_seconds must be positive")
        if default_max_tool_calls < 0:
            raise ValueError("default_max_tool_calls cannot be negative")
        self._provider = provider
        self._guardrails = guardrails or GuardrailPipeline()
        self._escalation = escalation or EscalationEvaluator()
        self._inbound_escalation = (
            inbound_escalation or InboundEscalationEvaluator()
        )
        self._tool_gateway = tool_gateway or ToolGateway(clock=clock)
        self._clock = clock
        self._max_candidate_retries = max_candidate_retries
        self._history_window = history_window
        self._budget_manager = budget_manager
        self._telemetry = telemetry_sink or NullTelemetrySink()
        if estimated_llm_cost_usd < 0:
            raise ValueError("estimated_llm_cost_usd cannot be negative")
        self._estimated_llm_cost_usd = estimated_llm_cost_usd
        self._llm_timeout_seconds = llm_timeout_seconds
        self._default_max_turns = default_max_turns
        self._default_session_timeout_seconds = default_session_timeout_seconds
        self._default_max_tool_calls = default_max_tool_calls
        self._provider_name = type(provider).__name__
        self._provider_model = getattr(provider, "model", None)
        if hasattr(self._tool_gateway, "set_telemetry"):
            self._tool_gateway.set_telemetry(self._telemetry)
        self._graph = self._build_graph()

    def start_session(
        self,
        agent_a: AgentProfile,
        agent_b: AgentProfile,
        *,
        max_turns: int | None = None,
        timeout_seconds: int | None = None,
        max_tool_calls: int | None = None,
        user_id: UUID | None = None,
    ) -> EngineResult:
        resolved_max_turns = (
            self._default_max_turns if max_turns is None else max_turns
        )
        resolved_timeout_seconds = (
            self._default_session_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )
        resolved_max_tool_calls = (
            self._default_max_tool_calls
            if max_tool_calls is None
            else max_tool_calls
        )
        if resolved_max_turns <= 0:
            raise ValueError("max_turns must be positive")
        if resolved_timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if resolved_max_tool_calls < 0:
            raise ValueError("max_tool_calls cannot be negative")
        started_at = self._clock()
        state = NegotiationState(
            owner_user_id=user_id,
            agents=(agent_a, agent_b),
            current_speaker_id=agent_a.agent_id,
            max_turns=resolved_max_turns,
            started_at=started_at,
            deadline_at=started_at + timedelta(seconds=resolved_timeout_seconds),
            execution_timeout_seconds=resolved_timeout_seconds,
            max_tool_calls=resolved_max_tool_calls,
        )
        if user_id is not None and self._budget_manager is not None:
            self._budget_manager.start_session(
                user_id,
                state.session_id,
                started_at=started_at,
            )
        return self.run_until_pause(state)

    def run_until_pause(self, state: NegotiationState) -> EngineResult:
        working_state = state.model_copy(deep=True)
        if (
            working_state.owner_user_id is not None
            and self._budget_manager is not None
        ):
            try:
                self._budget_manager.ensure_session_within_limit(
                    working_state.owner_user_id,
                    working_state.session_id,
                    now=self._clock(),
                )
            except BudgetExceededError as exc:
                working_state.status = SessionStatus.FAILED
                working_state.last_error_code = exc.code
                event = self._event(
                    working_state,
                    EngineEventType.SESSION_FAILED,
                    {"error_code": exc.code},
                )
                return EngineResult(state=working_state, events=[event])
        if working_state.status is not SessionStatus.ACTIVE:
            return EngineResult(state=working_state, events=[])

        graph_input: _GraphState = {
            "session": working_state,
            "events": [],
            "candidate": None,
            "tool_call": None,
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

        if pending.kind is DecisionKind.TOOL_EXECUTION:
            return self._resume_tool_decision(
                session,
                pending,
                human_decision,
                events,
            )

        if pending.kind is DecisionKind.INBOUND_ACTION:
            return self._resume_inbound_decision(
                session,
                pending,
                human_decision,
                events,
            )

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
                raise ValueError("a system decision cannot be approved directly")
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

        return self._continue_with_fresh_budget(session, events)

    def apply_revalidation(
        self,
        state: NegotiationState,
        result: RevalidationResult,
    ) -> EngineResult:
        """Resume an approved inbound action after its source confirms validity."""

        session = state.model_copy(deep=True)
        if result.revalidation_id in session.processed_revalidation_ids:
            return EngineResult(state=session, events=[])
        pending = session.pending_revalidation
        if session.status is not SessionStatus.REVALIDATING or pending is None:
            raise ValueError("session has no pending revalidation")
        if result.revalidation_id != pending.revalidation_id:
            raise ValueError("revalidation_id does not match the pending request")
        if (
            result.outcome is RevalidationOutcome.CONFIRMED
            and result.confirmed_proposal_revision != pending.proposal_revision
        ):
            raise ValueError("confirmed revision differs from the approved proposal")

        events = [
            self._event(
                session,
                EngineEventType.REVALIDATION_RESOLVED,
                {
                    "revalidation_id": str(pending.revalidation_id),
                    "outcome": result.outcome.value,
                    "reason_code": result.reason_code,
                },
            )
        ]
        session.processed_revalidation_ids.add(result.revalidation_id)
        session.pending_revalidation = None

        if result.outcome is RevalidationOutcome.CONFIRMED:
            now = self._clock()
            if any(
                action.valid_until is not None and action.valid_until <= now
                for action in pending.requested_actions
            ):
                session.status = SessionStatus.EXPIRED
                events.append(
                    self._event(
                        session,
                        EngineEventType.SESSION_EXPIRED,
                        {"reason_code": "ACTION_VALIDITY_ELAPSED"},
                    )
                )
                return EngineResult(state=session, events=events)
            session.action_authorizations.extend(
                ActionAuthorization(
                    action_id=action.action_id,
                    decision_id=pending.source_decision_id,
                    owner_agent_id=pending.owner_agent_id,
                    requester_agent_id=pending.requester_agent_id,
                    approved=True,
                    decided_at=now,
                )
                for action in pending.requested_actions
            )
            session.status = SessionStatus.ACTIVE
            return self._continue_with_fresh_budget(session, events)

        if result.outcome is RevalidationOutcome.WITHDRAWN:
            session.status = SessionStatus.WITHDRAWN
            events.append(self._event(session, EngineEventType.SESSION_WITHDRAWN))
        else:
            session.status = SessionStatus.EXPIRED
            events.append(self._event(session, EngineEventType.SESSION_EXPIRED))
        return EngineResult(state=session, events=events)

    def apply_external_event(
        self,
        state: NegotiationState,
        external_event: ExternalSessionEvent,
    ) -> EngineResult:
        """Apply an authenticated withdrawal or expiry while the engine is idle."""

        session = state.model_copy(deep=True)
        if external_event.session_id != session.session_id:
            raise ValueError("external event belongs to a different session")
        if external_event.event_id in session.processed_external_event_ids:
            return EngineResult(state=session, events=[])
        if external_event.actor_agent_id not in {
            agent.agent_id for agent in session.agents
        }:
            raise ValueError("external event actor does not belong to the session")
        if session.is_terminal():
            session.processed_external_event_ids.add(external_event.event_id)
            return EngineResult(
                state=session,
                events=[
                    self._event(
                        session,
                        EngineEventType.EXTERNAL_EVENT_APPLIED,
                        {
                            "external_event_id": str(external_event.event_id),
                            "event_type": external_event.event_type.value,
                            "ignored": "SESSION_ALREADY_TERMINAL",
                        },
                    )
                ],
            )

        active_proposal_id = None
        if session.pending_decision is not None:
            active_proposal_id = session.pending_decision.proposal_id
        elif session.pending_revalidation is not None:
            active_proposal_id = session.pending_revalidation.proposal_id
        if (
            external_event.proposal_id is not None
            and active_proposal_id is not None
            and external_event.proposal_id != active_proposal_id
        ):
            raise ValueError("external event references a stale proposal")

        session.processed_external_event_ids.add(external_event.event_id)
        if session.pending_decision is not None:
            pending_decision = session.pending_decision
            pending_decision.status = (
                DecisionStatus.EXPIRED
                if external_event.event_type
                is ExternalSessionEventType.PROPOSAL_EXPIRED
                else DecisionStatus.CANCELLED
            )
            pending_decision.resolved_at = external_event.occurred_at
            session.decision_history.append(pending_decision)
            session.pending_decision = None
        session.pending_revalidation = None

        events = [
            self._event(
                session,
                EngineEventType.EXTERNAL_EVENT_APPLIED,
                {
                    "external_event_id": str(external_event.event_id),
                    "event_type": external_event.event_type.value,
                    "reason_code": external_event.reason_code,
                },
            )
        ]
        if (
            external_event.event_type
            is ExternalSessionEventType.COUNTERPART_WITHDREW
        ):
            session.status = SessionStatus.WITHDRAWN
            events.append(self._event(session, EngineEventType.SESSION_WITHDRAWN))
        else:
            session.status = SessionStatus.EXPIRED
            events.append(self._event(session, EngineEventType.SESSION_EXPIRED))
        return EngineResult(state=session, events=events)

    def _resume_inbound_decision(
        self,
        session: NegotiationState,
        pending: DecisionRequest,
        human_decision: HumanDecision,
        events: list[EngineEvent],
    ) -> EngineResult:
        requester_id = pending.requester_agent_id
        if requester_id is None:
            raise ValueError("inbound decision has no requester")

        if human_decision.action is HumanDecisionAction.REPLACE:
            replacement = human_decision.replacement_turn
            if replacement is None:
                raise ValueError("REPLACE requires replacement_turn")
            guardrail_result = self._guardrails.evaluate(session.speaker(), replacement)
            if not guardrail_result.allowed:
                codes = ", ".join(
                    violation.code for violation in guardrail_result.violations
                )
                raise ValueError(f"replacement turn violates hard guardrails: {codes}")
            pending.status = DecisionStatus.REPLACED
            self._record_action_authorizations(session, pending, approved=False)
            session.decision_history.append(pending)
            session.pending_decision = None
            session.status = SessionStatus.ACTIVE
            events.append(self._decision_resolved_event(session, pending))
            self._publish_candidate(
                session,
                replacement,
                events,
                approved_by_human=True,
            )
            if session.status is not SessionStatus.ACTIVE:
                return EngineResult(state=session, events=events)
            return self._continue_with_fresh_budget(session, events)

        if human_decision.action is HumanDecisionAction.REJECT:
            pending.status = DecisionStatus.REJECTED
            self._record_action_authorizations(session, pending, approved=False)
            session.decision_history.append(pending)
            session.pending_decision = None
            session.status = SessionStatus.ACTIVE
            events.append(self._decision_resolved_event(session, pending))
            return self._continue_with_fresh_budget(session, events)

        expired = any(
            action.valid_until is not None
            and action.valid_until <= pending.resolved_at
            for action in pending.requested_actions
        )
        if expired:
            pending.status = DecisionStatus.EXPIRED
            session.decision_history.append(pending)
            session.pending_decision = None
            session.status = SessionStatus.EXPIRED
            events.append(self._decision_resolved_event(session, pending))
            events.append(self._event(session, EngineEventType.SESSION_EXPIRED))
            return EngineResult(state=session, events=events)

        pending.status = DecisionStatus.APPROVED
        session.decision_history.append(pending)
        session.pending_decision = None
        revalidation = RevalidationRequest(
            session_id=session.session_id,
            source_decision_id=pending.decision_id,
            owner_agent_id=pending.owner_agent_id,
            requester_agent_id=requester_id,
            proposal_id=pending.proposal_id,
            proposal_revision=pending.proposal_revision,
            requested_actions=pending.requested_actions,
            created_at=self._clock(),
        )
        session.pending_revalidation = revalidation
        session.status = SessionStatus.REVALIDATING
        events.append(self._decision_resolved_event(session, pending))
        events.append(
            self._event(
                session,
                EngineEventType.REVALIDATION_REQUIRED,
                {"revalidation": revalidation.model_dump(mode="json")},
            )
        )
        return EngineResult(state=session, events=events)

    def _record_action_authorizations(
        self,
        session: NegotiationState,
        decision: DecisionRequest,
        *,
        approved: bool,
    ) -> None:
        requester_id = decision.requester_agent_id
        if requester_id is None:
            raise ValueError("inbound decision has no requester")
        session.action_authorizations.extend(
            ActionAuthorization(
                action_id=action.action_id,
                decision_id=decision.decision_id,
                owner_agent_id=decision.owner_agent_id,
                requester_agent_id=requester_id,
                approved=approved,
                decided_at=decision.resolved_at or self._clock(),
            )
            for action in decision.requested_actions
        )

    def _resume_tool_decision(
        self,
        session: NegotiationState,
        pending: DecisionRequest,
        human_decision: HumanDecision,
        events: list[EngineEvent],
    ) -> EngineResult:
        call = pending.tool_call
        if call is None:
            raise ValueError("tool decision has no call")
        if human_decision.action is HumanDecisionAction.REPLACE:
            raise ValueError("tool decisions cannot be replaced with a public turn")

        profile = next(
            (
                agent
                for agent in session.agents
                if agent.agent_id == pending.owner_agent_id
            ),
            None,
        )
        if profile is None:
            raise ValueError("tool decision owner does not belong to the session")
        if human_decision.action is HumanDecisionAction.REJECT:
            pending.status = DecisionStatus.REJECTED
            result = self._tool_gateway.rejection_result(
                profile,
                call,
                session_id=session.session_id,
                user_id=session.owner_user_id,
            )
        else:
            pending.status = DecisionStatus.APPROVED
            result = self._tool_gateway.execute(
                session_id=session.session_id,
                profile=profile,
                call=call,
                human_approved=True,
                user_id=session.owner_user_id,
            )

        session.decision_history.append(pending)
        session.pending_decision = None
        session.status = SessionStatus.ACTIVE
        session.tool_results.append(result)
        events.append(self._decision_resolved_event(session, pending))
        events.append(self._tool_result_event(session, call, result))
        return self._continue_with_fresh_budget(session, events)

    def _decision_resolved_event(
        self,
        session: NegotiationState,
        decision: DecisionRequest,
    ) -> EngineEvent:
        return self._event(
            session,
            EngineEventType.DECISION_RESOLVED,
            {
                "decision_id": str(decision.decision_id),
                "action": decision.resolution.value if decision.resolution else None,
                "kind": decision.kind.value,
                "status": decision.status.value,
            },
        )

    def _tool_result_event(
        self,
        session: NegotiationState,
        call: ToolCallRequest,
        result: ToolExecutionResult,
    ) -> EngineEvent:
        event_type = (
            EngineEventType.TOOL_EXECUTION_COMPLETED
            if result.status
            in {ToolExecutionStatus.SUCCEEDED, ToolExecutionStatus.FAILED}
            else EngineEventType.TOOL_EXECUTION_DENIED
        )
        return self._event(
            session,
            event_type,
            {
                "call": call.model_dump(mode="json"),
                "result": result.model_dump(mode="json"),
            },
        )

    def _continue_with_fresh_budget(
        self,
        session: NegotiationState,
        events: list[EngineEvent],
    ) -> EngineResult:
        session.deadline_at = self._clock() + timedelta(
            seconds=session.execution_timeout_seconds
        )
        continued = self.run_until_pause(session)
        return EngineResult(
            state=continued.state,
            events=[*events, *continued.events],
        )

    def _build_graph(self):
        builder = StateGraph(_GraphState)
        builder.add_node("prepare", self._prepare_node)
        builder.add_node("generate", self._generate_node)
        builder.add_node("tool", self._tool_node)
        builder.add_node("guardrail", self._guardrail_node)
        builder.add_node("escalate", self._escalate_node)
        builder.add_node("publish", self._publish_node)
        builder.add_edge(START, "prepare")
        builder.add_conditional_edges("prepare", self._route)
        builder.add_conditional_edges("generate", self._route)
        builder.add_conditional_edges("tool", self._route)
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
        observe_call = (
            self._budget_manager is not None
            or not isinstance(self._telemetry, NullTelemetrySink)
        )
        started_at = self._clock() if observe_call else None
        try:
            if session.owner_user_id is not None and self._budget_manager is not None:
                self._budget_manager.reserve(
                    session.owner_user_id,
                    session_id=session.session_id,
                    estimated_cost_usd=self._estimated_llm_cost_usd,
                    now=started_at or self._clock(),
                )
            step = self._generate_with_timeout(
                GenerationRequest(
                    speaker=session.speaker(),
                    counterpart=session.counterpart(),
                    transcript=tuple(session.transcript[-self._history_window :]),
                    action_authorizations=tuple(
                        authorization
                        for authorization in session.action_authorizations
                        if authorization.owner_agent_id
                        == session.current_speaker_id
                    ),
                    available_tools=(
                        self._tool_gateway.available_tools(session.speaker())
                        if session.tool_call_count < session.max_tool_calls
                        else ()
                    ),
                    tool_results=tuple(
                        result
                        for result in session.tool_results[-8:]
                        if result.requested_by_agent_id
                        == session.current_speaker_id
                    ),
                    guardrail_feedback=tuple(state["guardrail_feedback"]),
                ),
                timeout_seconds=self._llm_timeout_seconds,
            )
            if observe_call:
                completed_at = self._clock()
                self._telemetry.record_llm(
                    LLMObservation(
                        session_id=session.session_id,
                        user_id=session.owner_user_id,
                        provider=self._provider_name,
                        model=self._provider_model,
                        started_at=started_at or completed_at,
                        completed_at=completed_at,
                        success=True,
                        estimated_cost_usd=self._estimated_llm_cost_usd,
                    )
                )
            if step.kind is ProviderStepKind.TURN:
                state["candidate"] = step.turn
                state["tool_call"] = None
            else:
                state["candidate"] = None
                state["tool_call"] = step.tool_call
        except BudgetExceededError as exc:
            session.status = SessionStatus.FAILED
            session.last_error_code = exc.code
            state["events"].append(
                self._event(
                    session,
                    EngineEventType.SESSION_FAILED,
                    {"error_code": exc.code},
                )
            )
            state["route"] = "end"
            return state
        except LLMTimeoutError:
            if observe_call:
                completed_at = self._clock()
                self._telemetry.record_llm(
                    LLMObservation(
                        session_id=session.session_id,
                        user_id=session.owner_user_id,
                        provider=self._provider_name,
                        model=self._provider_model,
                        started_at=started_at or completed_at,
                        completed_at=completed_at,
                        success=False,
                        estimated_cost_usd=self._estimated_llm_cost_usd,
                        error_code="LLM_TIMEOUT",
                    )
                )
            session.status = SessionStatus.FAILED
            session.last_error_code = "LLM_TIMEOUT"
            state["events"].append(
                self._event(
                    session,
                    EngineEventType.SESSION_FAILED,
                    {"error_code": session.last_error_code},
                )
            )
            state["route"] = "end"
            return state
        except Exception:
            if observe_call:
                completed_at = self._clock()
                self._telemetry.record_llm(
                    LLMObservation(
                        session_id=session.session_id,
                        user_id=session.owner_user_id,
                        provider=self._provider_name,
                        model=self._provider_model,
                        started_at=started_at or completed_at,
                        completed_at=completed_at,
                        success=False,
                        estimated_cost_usd=self._estimated_llm_cost_usd,
                        error_code="LLM_GENERATION_FAILED",
                    )
                )
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
            state["tool_call"] = None
            self._pause_for_system_reason(state, DecisionReason.TIMEOUT)
            return state
        state["route"] = (
            "tool" if state["tool_call"] is not None else "guardrail"
        )
        return state

    def _generate_with_timeout(
        self,
        request: GenerationRequest,
        *,
        timeout_seconds: float,
    ):
        """Run one provider step behind an engine-level hard timeout.

        Providers normally have their own network timeout, but the engine also
        needs a bound when a custom provider blocks or ignores that setting.
        The worker is asked to cancel on timeout; a provider implementation must
        still honor its own cancellation/network timeout to stop promptly.
        """

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self._provider.generate_step, request)
        try:
            return future.result(timeout=timeout_seconds)
        except FutureTimeoutError as exc:
            future.cancel()
            raise LLMTimeoutError("provider step exceeded engine timeout") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _tool_node(self, state: _GraphState) -> _GraphState:
        session = state["session"]
        call = state["tool_call"]
        if call is None:
            session.status = SessionStatus.FAILED
            session.last_error_code = "MISSING_TOOL_CALL"
            state["route"] = "end"
            return state
        if session.tool_call_count >= session.max_tool_calls:
            state["tool_call"] = None
            self._pause_for_system_reason(
                state,
                DecisionReason.TOOL_BUDGET_EXHAUSTED,
            )
            return state

        if session.owner_user_id is not None and self._budget_manager is not None:
            try:
                self._budget_manager.reserve(
                    session.owner_user_id,
                    session_id=session.session_id,
                    now=self._clock(),
                )
            except BudgetExceededError as exc:
                session.status = SessionStatus.FAILED
                session.last_error_code = exc.code
                state["events"].append(
                    self._event(
                        session,
                        EngineEventType.SESSION_FAILED,
                        {"error_code": exc.code},
                    )
                )
                state["tool_call"] = None
                state["route"] = "end"
                return state

        session.tool_call_count += 1
        policy = self._tool_gateway.evaluate(session.speaker(), call)
        if policy.outcome is ToolPolicyOutcome.REQUIRE_APPROVAL:
            decision = DecisionRequest(
                session_id=session.session_id,
                owner_agent_id=session.current_speaker_id,
                kind=DecisionKind.TOOL_EXECUTION,
                reasons=[DecisionReason.TOOL_EXECUTION],
                tool_call=call,
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
            state["tool_call"] = None
            state["route"] = "end"
            return state

        result = self._tool_gateway.execute(
            session_id=session.session_id,
            profile=session.speaker(),
            call=call,
            user_id=session.owner_user_id,
        )
        session.tool_results.append(result)
        state["events"].append(self._tool_result_event(session, call, result))
        state["tool_call"] = None
        state["route"] = "generate"
        return state

    def _guardrail_node(self, state: _GraphState) -> _GraphState:
        candidate = state["candidate"]
        if candidate is None:
            state["session"].status = SessionStatus.FAILED
            state["session"].last_error_code = "MISSING_CANDIDATE"
            state["route"] = "end"
            return state

        result = self._guardrails.evaluate(state["session"].speaker(), candidate)
        codes = [violation.code for violation in result.violations]
        if candidate.requested_actions:
            now = self._clock()
            if any(
                action.valid_until is not None and action.valid_until <= now
                for action in candidate.requested_actions
            ):
                codes.append("EXPIRED_REQUESTED_ACTION")
        if not codes:
            state["route"] = "escalate"
            return state

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
            owner_agent_id=state["session"].current_speaker_id,
            kind=DecisionKind.OUTBOUND_TURN,
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
        requester_id = session.current_speaker_id
        recipient = session.counterpart()
        session.turn_count += 1
        message = TranscriptMessage(
            speaker_id=requester_id,
            turn_index=session.turn_count,
            proposal_id=candidate.proposal_id,
            proposal_revision=candidate.proposal_revision,
            responds_to=candidate.responds_to,
            public_message=candidate.public_message,
            intent=candidate.intent,
            numeric_terms=candidate.numeric_terms,
            data_requests=candidate.data_requests,
            disclosed_categories=[
                disclosure.category for disclosure in candidate.proposed_disclosures
            ],
            requested_actions=candidate.requested_actions,
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

        inbound_result = self._inbound_escalation.evaluate(recipient, candidate)
        if inbound_result.required:
            session.toggle_speaker()
            decision = DecisionRequest(
                session_id=session.session_id,
                owner_agent_id=recipient.agent_id,
                requester_agent_id=requester_id,
                kind=DecisionKind.INBOUND_ACTION,
                reasons=list(inbound_result.reasons),
                matched_rule_ids=list(inbound_result.matched_rule_ids),
                proposal_id=candidate.proposal_id,
                proposal_revision=candidate.proposal_revision,
                requested_actions=candidate.requested_actions,
                requires_revalidation=True,
            )
            session.pending_decision = decision
            session.status = SessionStatus.PENDING_HUMAN_APPROVAL
            events.append(
                self._event(
                    session,
                    EngineEventType.APPROVAL_REQUIRED,
                    {"decision": decision.model_dump(mode="json")},
                )
            )
            return

        if candidate.intent is TurnIntent.ACCEPT:
            session.status = SessionStatus.RESOLVED
            events.append(self._event(session, EngineEventType.SESSION_RESOLVED))
            self._emit_goal_reviews(session, events)
        elif candidate.intent is TurnIntent.DECLINE:
            session.status = SessionStatus.REJECTED
            events.append(self._event(session, EngineEventType.SESSION_REJECTED))
        else:
            session.toggle_speaker()

    def _emit_goal_reviews(
        self,
        session: NegotiationState,
        events: list[EngineEvent],
    ) -> None:
        for agent in session.agents:
            remaining_units = agent.remaining_goal_units
            if agent.goal_completion_mode is GoalCompletionMode.CONTINUOUS:
                suggested_action = GoalReviewAction.CONTINUE
                proposed_remaining = remaining_units
            elif agent.goal_completion_mode is GoalCompletionMode.QUANTITY:
                proposed_remaining = max(0, (remaining_units or 1) - 1)
                suggested_action = (
                    GoalReviewAction.COMPLETE
                    if proposed_remaining == 0
                    else GoalReviewAction.CONTINUE
                )
            else:
                suggested_action = GoalReviewAction.COMPLETE
                proposed_remaining = None

            review = GoalProgressReview(
                session_id=session.session_id,
                agent_id=agent.agent_id,
                objectives=agent.objectives,
                suggested_action=suggested_action,
                proposed_remaining_units=proposed_remaining,
            )
            events.append(
                self._event(
                    session,
                    EngineEventType.GOAL_PROGRESS_REVIEW_REQUIRED,
                    {"review": review.model_dump(mode="json")},
                )
            )

    def _pause_for_system_reason(
        self, state: _GraphState, reason: DecisionReason
    ) -> None:
        session = state["session"]
        decision = DecisionRequest(
            session_id=session.session_id,
            owner_agent_id=session.current_speaker_id,
            kind=DecisionKind.SYSTEM,
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
        event = EngineEvent(
            session_id=session.session_id,
            event_type=event_type,
            audience=(
                EngineEventAudience.PUBLIC
                if event_type is EngineEventType.TURN_READY
                else EngineEventAudience.INTERNAL
            ),
            payload=payload or {},
            occurred_at=self._clock(),
        )
        self._telemetry.record_event(event)
        return event
