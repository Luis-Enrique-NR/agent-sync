from __future__ import annotations

import json
import time
from datetime import timedelta
from uuid import uuid4

import pytest

from ai.api.dto import DecisionRequestDTO, to_engine_result_dto
from ai.config import AISettings
from ai.domain.models import (
    AgentTurn,
    DecisionKind,
    DecisionReason,
    DecisionRequest,
    EngineEvent,
    EngineEventType,
    EngineResult,
    NegotiationState,
    ProviderStep,
    ProviderStepKind,
    TurnIntent,
)
from ai.engine.graph import NegotiationEngine
from ai.policies.guardrails import GuardrailPipeline
from ai.providers.fake import ScriptedLLMProvider
from ai.tools.mcp_http import HTTPMCPClient, MCPProtocolError


def test_engine_uses_configured_defaults_for_turns_and_tools(
    b2b_agents, fixed_now
) -> None:
    engine = NegotiationEngine(
        ScriptedLLMProvider(
            [
                AgentTurn(
                    public_message="Oferta inicial.",
                    intent=TurnIntent.OFFER,
                )
            ]
        ),
        clock=lambda: fixed_now,
        default_max_turns=1,
        default_session_timeout_seconds=17,
        default_max_tool_calls=0,
    )

    result = engine.start_session(*b2b_agents)

    assert result.state.max_turns == 1
    assert result.state.execution_timeout_seconds == 17
    assert result.state.max_tool_calls == 0


def test_engine_enforces_provider_timeout(b2b_agents, fixed_now) -> None:
    class SlowProvider:
        def generate_step(self, request):
            del request
            time.sleep(0.08)
            return ProviderStep(
                kind=ProviderStepKind.TURN,
                turn=AgentTurn(
                    public_message="Demasiado tarde.",
                    intent=TurnIntent.QUESTION,
                ),
            )

    engine = NegotiationEngine(
        SlowProvider(),
        clock=lambda: fixed_now,
        llm_timeout_seconds=0.01,
    )

    result = engine.start_session(*b2b_agents, max_turns=1)

    assert result.state.last_error_code == "LLM_TIMEOUT"
    assert result.state.status.value == "FAILED"


def test_guardrails_reject_invented_private_reference(b2b_agents) -> None:
    result = GuardrailPipeline().evaluate(
        b2b_agents[0],
        AgentTurn(
            public_message="Puedes usar contact_ref_invented para escribirme.",
            intent=TurnIntent.QUESTION,
        ),
    )

    assert not result.allowed
    assert "PRIVATE_REFERENCE_IN_PUBLIC_TEXT" in {
        violation.code for violation in result.violations
    }


class _MCPResponse:
    def __init__(self, body: bytes, content_type: str) -> None:
        self._body = body
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size: int) -> bytes:
        return self._body[:size]


def test_mcp_client_supports_sse_and_server_allowlist() -> None:
    def opener(request, timeout):
        del timeout
        request_id = json.loads(request.data.decode())["id"]
        payload = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"structuredContent": {"source": "mcp"}},
            }
        )
        return _MCPResponse(
            f"event: message\ndata: {payload}\n\n".encode(),
            "text/event-stream",
        )

    client = HTTPMCPClient.from_json(
        json.dumps(
            {
                "default": {
                    "endpoint": "https://mcp.invalid",
                    "allowed_tools": ["web.search"],
                }
            }
        ),
        opener=opener,
    )

    assert client.call_tool(
        server_label="default",
        tool_name="web.search",
        arguments={"query": "agent sync"},
        idempotency_key="call-1",
        timeout_seconds=1,
    ) == {"source": "mcp"}
    with pytest.raises(MCPProtocolError, match="NOT_ALLOWLISTED"):
        client.call_tool(
            server_label="default",
            tool_name="calendar.check_availability",
            arguments={},
            idempotency_key="call-2",
            timeout_seconds=1,
        )


def test_result_dto_is_versioned_typed_and_correlated(b2b_agents, fixed_now) -> None:
    session_id = uuid4()
    state = NegotiationState(
        session_id=session_id,
        agents=b2b_agents,
        current_speaker_id=b2b_agents[0].agent_id,
        started_at=fixed_now,
        deadline_at=fixed_now + timedelta(seconds=90),
        pending_decision=DecisionRequest(
            session_id=session_id,
            owner_agent_id=b2b_agents[0].agent_id,
            kind=DecisionKind.SYSTEM,
            reasons=[DecisionReason.TIMEOUT],
        ),
    )
    result = to_engine_result_dto(
        EngineResult(
            state=state,
            events=[
                EngineEvent(
                    session_id=state.session_id,
                    event_type=EngineEventType.SESSION_FAILED,
                    payload={"email": "private@example.com"},
                )
            ],
        )
    )

    assert result.schema_version == "ai.v1"
    assert isinstance(result.state.pending_decision, DecisionRequestDTO)
    assert result.state.pending_decision.schema_version == "ai.v1"
    assert result.events[0].correlation_id == state.session_id
    assert result.events[0].payload["email"] == "[REDACTED]"


def test_config_reads_max_tool_calls_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("AGENTSYNC_MAX_TOOL_CALLS", "3")

    settings = AISettings.from_env()

    assert settings.max_tool_calls == 3
