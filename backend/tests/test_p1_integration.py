from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlmodel import Session, SQLModel, select

from ai.api.dto import to_engine_result_dto, to_public_transcript_dto
from ai.domain.models import (
    EngineEvent,
    EngineEventType,
    EngineResult,
    AgentTurn,
    NegotiationState,
    ToolExecutionResult,
    ToolExecutionStatus,
    TranscriptMessage,
    TurnIntent,
)
from ai.policies.budget import (
    BudgetExceededError,
    UserBudgetLimits,
    UserBudgetManager,
)
from ai.engine.graph import NegotiationEngine
from ai.observability import InMemoryTelemetrySink
from ai.providers.fake import ScriptedLLMProvider
from ai.tools.mcp_http import HTTPMCPClient
from persistence.models import AuditRecordRow, NegotiationStateRow
from persistence.repository import PersistenceRepository


def test_user_budget_enforces_rate_cost_and_session_time(fixed_now) -> None:
    manager = UserBudgetManager(
        UserBudgetLimits(
            requests_per_minute=1,
            max_cost_usd_per_hour=0.10,
            max_session_seconds=5,
        ),
        clock=lambda: fixed_now,
    )
    user_id = uuid4()
    session_id = uuid4()
    manager.start_session(user_id, session_id, started_at=fixed_now)
    manager.reserve(
        user_id,
        session_id=session_id,
        estimated_cost_usd=0.10,
        now=fixed_now,
    )
    with pytest.raises(BudgetExceededError, match="requests-per-minute"):
        manager.reserve(user_id, session_id=session_id, now=fixed_now)
    with pytest.raises(BudgetExceededError, match="maximum execution time"):
        manager.ensure_session_within_limit(
            user_id,
            session_id,
            now=fixed_now + timedelta(seconds=6),
        )


def test_engine_records_llm_observability_and_applies_user_budget(
    b2b_agents, fixed_now
) -> None:
    sink = InMemoryTelemetrySink()
    manager = UserBudgetManager(
        UserBudgetLimits(requests_per_minute=1, max_cost_usd_per_hour=1.0),
        clock=lambda: fixed_now,
    )
    provider = ScriptedLLMProvider(
        [
            # The first offer is enough to demonstrate a bounded LLM call.
            AgentTurn(
                public_message="Oferta inicial.",
                intent=TurnIntent.OFFER,
            )
        ]
    )
    engine = NegotiationEngine(
        provider,
        clock=lambda: fixed_now,
        telemetry_sink=sink,
        budget_manager=manager,
        estimated_llm_cost_usd=0.05,
    )
    user_id = uuid4()
    result = engine.start_session(
        *b2b_agents,
        max_turns=1,
        user_id=user_id,
    )
    assert result.state.turn_count == 1
    assert len(sink.llm_calls) == 1
    assert sink.llm_calls[0].user_id == user_id
    assert sink.llm_calls[0].success


def test_persistence_roundtrip_sanitizes_tool_output_and_writes_audit(
    b2b_agents, tmp_path, fixed_now
) -> None:
    from persistence.database import build_engine

    db_engine = build_engine(f"sqlite:///{tmp_path / 'p1.db'}")
    SQLModel.metadata.create_all(db_engine)
    repository = PersistenceRepository(lambda: Session(db_engine))
    owner_id = uuid4()
    state = NegotiationState(
        owner_user_id=owner_id,
        agents=b2b_agents,
        current_speaker_id=b2b_agents[0].agent_id,
        started_at=fixed_now,
        deadline_at=fixed_now + timedelta(seconds=90),
        tool_results=[
            ToolExecutionResult(
                call_id=uuid4(),
                tool_name="web.search",
                requested_by_agent_id=b2b_agents[0].agent_id,
                status=ToolExecutionStatus.SUCCEEDED,
                output={
                    "email": "owner@example.com",
                    "phone": "+57 300 123 4567",
                    "public": "safe result",
                },
                started_at=fixed_now,
                completed_at=fixed_now,
            )
        ],
    )
    result = EngineResult(
        state=state,
        events=[
            EngineEvent(
                session_id=state.session_id,
                event_type=EngineEventType.TOOL_EXECUTION_COMPLETED,
                payload={"email": "audit@example.com", "status": "ok"},
            )
        ],
    )
    repository.save_engine_result(result, user_id=owner_id)

    with Session(db_engine) as session:
        row = session.get(NegotiationStateRow, state.session_id)
        audits = session.exec(select(AuditRecordRow)).all()
    assert row is not None
    assert row.raw_state["tool_results"][0]["output"]["email"] == "[REDACTED]"
    assert row.raw_state["tool_results"][0]["output"]["phone"] == "[REDACTED]"
    assert len(audits) == 1
    restored = repository.load_negotiation_state(state.session_id)
    assert restored is not None
    assert restored.session_id == state.session_id


def test_api_dtos_do_not_publish_private_event_payload(b2b_agents, fixed_now) -> None:
    message = TranscriptMessage(
        speaker_id=b2b_agents[0].agent_id,
        turn_index=1,
        public_message="Escríbeme a owner@example.com",
        intent=TurnIntent.QUESTION,
        created_at=fixed_now,
    )
    dto = to_public_transcript_dto(message)
    assert "owner@example.com" not in dto.public_message
    state = NegotiationState(
        agents=b2b_agents,
        current_speaker_id=b2b_agents[0].agent_id,
        started_at=fixed_now,
        deadline_at=fixed_now + timedelta(seconds=90),
        transcript=[message],
    )
    result_dto = to_engine_result_dto(EngineResult(state=state))
    assert result_dto.state.transcript[0].public_message == dto.public_message


class _Response:
    def __init__(self, payload: dict, *, content_type: str = "application/json") -> None:
        self._payload = payload
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size: int) -> bytes:
        return json.dumps(self._payload).encode()[:size]


def test_http_mcp_client_sends_server_side_authentication() -> None:
    calls: list[tuple[object, int]] = []

    def opener(request, timeout):
        calls.append((request, timeout))
        request_id = json.loads(request.data.decode())["id"]
        return _Response(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"structuredContent": {"ok": True}},
            }
        )

    client = HTTPMCPClient.from_json(
        '{"default":{"endpoint":"https://mcp.invalid","token_env_var":"MCP_TOKEN"}}',
        environ={"MCP_TOKEN": "secret-token"},
        opener=opener,
    )
    result = client.call_tool(
        server_label="default",
        tool_name="web.search",
        arguments={"query": "textiles"},
        idempotency_key="call-1",
        timeout_seconds=4,
    )
    assert result == {"ok": True}
    request, timeout = calls[0]
    assert timeout == 4
    assert request.headers["Authorization"] == "Bearer secret-token"
    assert "secret-token" not in request.data.decode()
