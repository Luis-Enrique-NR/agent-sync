"""Composition root used by Backend API."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv

from ai.api.dto import EngineResultDTO, to_engine_result_dto
from ai.config import AISettings
from ai.domain.models import (
    AgentProfile,
    EngineResult,
    ExternalSessionEvent,
    HumanDecision,
    RevalidationResult,
)
from ai.engine.graph import NegotiationEngine
from ai.observability import LoggingTelemetrySink, TelemetrySink
from ai.policies.budget import UserBudgetLimits, UserBudgetManager
from ai.providers.fake import OfflineLLMProvider
from ai.providers.openai_provider import OpenAIProvider
from ai.tools.mcp import build_mcp_tool_gateway
from ai.tools.mcp_http import HTTPMCPClient
from ai.tools.mocks import build_demo_tool_gateway
from persistence.repository import PersistenceRepository


class SessionOwnershipError(PermissionError):
    """The authenticated user does not own the requested session."""


def _build_provider(configured: AISettings):
    if configured.llm_provider == "fake":
        return OfflineLLMProvider()
    api_key = os.getenv(configured.openai_api_key_env)
    if not api_key:
        raise RuntimeError(
            f"missing server-side secret in {configured.openai_api_key_env}; "
            "the Frontend must never provide the OpenAI key"
        )
    return OpenAIProvider(
        model=configured.llm_model,
        timeout_seconds=configured.llm_timeout_seconds,
        max_retries=configured.llm_max_retries,
        api_key=api_key,
        base_url=configured.openai_base_url,
    )


def build_engine_from_env(settings: AISettings | None = None) -> NegotiationEngine:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    configured = settings or AISettings.from_env()
    provider = _build_provider(configured)
    telemetry: TelemetrySink = LoggingTelemetrySink()
    budget = UserBudgetManager(
        UserBudgetLimits(
            requests_per_minute=configured.user_requests_per_minute,
            max_cost_usd_per_hour=configured.user_max_cost_usd_per_hour,
            max_session_seconds=configured.user_max_session_seconds,
        )
    )
    if configured.tools_provider == "mcp":
        client = HTTPMCPClient.from_json(configured.mcp_servers_json)
        tool_gateway = build_mcp_tool_gateway(
            client,
            server_label=os.getenv("AGENTSYNC_MCP_DEFAULT_SERVER", "default"),
        )
    else:
        tool_gateway = build_demo_tool_gateway()
    return NegotiationEngine(
        provider,
        tool_gateway=tool_gateway,
        budget_manager=budget,
        telemetry_sink=telemetry,
        estimated_llm_cost_usd=configured.estimated_llm_cost_usd,
    )


class AIBackendService:
    """Orchestration facade used by REST/WebSocket handlers.

    It is deliberately small: authentication, routing and HTTP concerns stay in
    Backend API, while this facade guarantees every state transition is loaded,
    authorized, persisted and returned as a DTO.
    """

    def __init__(
        self,
        engine: NegotiationEngine,
        *,
        repository: PersistenceRepository | None = None,
    ) -> None:
        self._engine = engine
        self._repository = repository or PersistenceRepository()

    def start_negotiation(
        self,
        user_id: UUID,
        agent_a: AgentProfile,
        agent_b: AgentProfile,
        *,
        max_turns: int = 8,
        timeout_seconds: int = 90,
        max_tool_calls: int = 6,
    ) -> EngineResultDTO:
        result = self._engine.start_session(
            agent_a,
            agent_b,
            max_turns=max_turns,
            timeout_seconds=timeout_seconds,
            max_tool_calls=max_tool_calls,
            user_id=user_id,
        )
        self._repository.save_engine_result(result, user_id=user_id)
        return to_engine_result_dto(result)

    def resume_negotiation(
        self,
        user_id: UUID,
        session_id: UUID,
        human_decision: HumanDecision,
    ) -> EngineResultDTO:
        state = self._owned_state(user_id, session_id)
        result = self._engine.resume_session(state, human_decision)
        self._repository.save_engine_result(result, user_id=user_id)
        return to_engine_result_dto(result)

    def apply_revalidation(
        self,
        user_id: UUID,
        session_id: UUID,
        revalidation: RevalidationResult,
    ) -> EngineResultDTO:
        state = self._owned_state(user_id, session_id)
        result = self._engine.apply_revalidation(state, revalidation)
        self._repository.save_engine_result(result, user_id=user_id)
        return to_engine_result_dto(result)

    def apply_external_event(
        self,
        user_id: UUID,
        session_id: UUID,
        external_event: ExternalSessionEvent,
    ) -> EngineResultDTO:
        state = self._owned_state(user_id, session_id)
        result = self._engine.apply_external_event(state, external_event)
        self._repository.save_engine_result(result, user_id=user_id)
        return to_engine_result_dto(result)

    def get_negotiation(self, user_id: UUID, session_id: UUID) -> EngineResultDTO:
        state = self._owned_state(user_id, session_id)
        return to_engine_result_dto(EngineResult(state=state))

    def _owned_state(self, user_id: UUID, session_id: UUID):
        state = self._repository.load_negotiation_state(session_id)
        if state is None:
            raise KeyError(f"negotiation session {session_id} was not found")
        if state.owner_user_id != user_id:
            raise SessionOwnershipError("session does not belong to the authenticated user")
        return state
