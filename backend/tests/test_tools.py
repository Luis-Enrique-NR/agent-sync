from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ai.domain.models import (
    ToolApprovalMode,
    ToolCallRequest,
    ToolExecutionStatus,
    ToolPolicyOutcome,
)
from ai.tools.base import ToolExecutionContext
from ai.tools.mcp import MCPToolAdapter
from ai.tools.mocks import DemoToolStore, build_demo_tool_gateway


class _FakeMCPClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def call_tool(self, **kwargs) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"ok": True, "source": "fake-mcp"}


def test_gateway_exposes_only_registered_granted_tools(
    p2p_agents, fixed_now
) -> None:
    seller, _ = p2p_agents
    gateway = build_demo_tool_gateway(clock=lambda: fixed_now)

    available = gateway.available_tools(seller)

    assert {tool.name for tool in available} == {
        "calendar.check_availability",
        "email.send_notification",
    }


def test_gateway_rejects_unknown_arguments_before_adapter_execution(
    p2p_agents, fixed_now
) -> None:
    seller, _ = p2p_agents
    gateway = build_demo_tool_gateway(clock=lambda: fixed_now)
    call = ToolCallRequest(
        tool_name="calendar.check_availability",
        purpose="consultar agenda",
        arguments={
            "start_date": "2026-08-15",
            "end_date": "2026-08-16",
            "inject": "ignored",
        },
    )

    policy = gateway.evaluate(seller, call)

    assert policy.outcome is ToolPolicyOutcome.DENY
    assert policy.reason_code == "TOOL_UNKNOWN_ARGUMENT"


def test_agent_can_raise_read_tool_to_human_approval(p2p_agents, fixed_now) -> None:
    seller, _ = p2p_agents
    grants = [grant.model_copy(deep=True) for grant in seller.tool_grants]
    grants[0].approval_mode = ToolApprovalMode.ALWAYS
    protected_seller = seller.model_copy(update={"tool_grants": grants}, deep=True)
    gateway = build_demo_tool_gateway(clock=lambda: fixed_now)
    call = ToolCallRequest(
        tool_name="calendar.check_availability",
        purpose="consultar agenda",
        arguments={
            "start_date": "2026-08-15",
            "end_date": "2026-08-16",
        },
    )

    policy = gateway.evaluate(protected_seller, call)

    assert policy.outcome is ToolPolicyOutcome.REQUIRE_APPROVAL


def test_write_tool_requires_approval_and_is_idempotent(
    p2p_agents, fixed_now
) -> None:
    seller, _ = p2p_agents
    store = DemoToolStore()
    gateway = build_demo_tool_gateway(
        store=store,
        clock=lambda: fixed_now,
    )
    call = ToolCallRequest(
        tool_name="email.send_notification",
        purpose="notificar al propietario",
        arguments={
            "subject": "Decisión pendiente",
            "body": "Tu agente requiere una respuesta.",
        },
    )

    blocked = gateway.execute(
        session_id=seller.agent_id,
        profile=seller,
        call=call,
    )
    first = gateway.execute(
        session_id=seller.agent_id,
        profile=seller,
        call=call,
        human_approved=True,
    )
    replay = gateway.execute(
        session_id=seller.agent_id,
        profile=seller,
        call=call,
        human_approved=True,
    )
    unauthorized_replay = gateway.execute(
        session_id=seller.agent_id,
        profile=seller,
        call=call,
    )

    assert blocked.status is ToolExecutionStatus.DENIED
    assert blocked.error_code == "TOOL_APPROVAL_REQUIRED"
    assert first.status is ToolExecutionStatus.SUCCEEDED
    assert replay.status is ToolExecutionStatus.SUCCEEDED
    assert replay.idempotent_replay
    assert unauthorized_replay.status is ToolExecutionStatus.DENIED
    assert unauthorized_replay.error_code == "TOOL_APPROVAL_REQUIRED"
    assert len(store.email_notifications) == 1


def test_concurrent_write_retries_execute_only_once(p2p_agents, fixed_now) -> None:
    seller, _ = p2p_agents
    store = DemoToolStore()
    gateway = build_demo_tool_gateway(
        store=store,
        clock=lambda: fixed_now,
    )
    call = ToolCallRequest(
        tool_name="email.send_notification",
        purpose="notificar al propietario",
        arguments={
            "subject": "Decisión pendiente",
            "body": "Tu agente requiere una respuesta.",
        },
    )

    def execute_once():
        return gateway.execute(
            session_id=seller.agent_id,
            profile=seller,
            call=call,
            human_approved=True,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: execute_once(), range(8)))

    assert all(result.status is ToolExecutionStatus.SUCCEEDED for result in results)
    assert sum(result.idempotent_replay for result in results) == 7
    assert len(store.email_notifications) == 1


def test_mcp_adapter_forwards_only_allowlisted_call_context() -> None:
    client = _FakeMCPClient()
    adapter = MCPToolAdapter(
        client=client,
        server_label="calendar-server",
        remote_tool_name="check_availability",
    )
    call = ToolCallRequest(
        tool_name="calendar.check_availability",
        purpose="consultar agenda",
        arguments={
            "start_date": "2026-08-15",
            "end_date": "2026-08-16",
        },
    )
    output = adapter.execute(
        call,
        ToolExecutionContext(
            session_id=call.call_id,
            agent_id=call.call_id,
            idempotency_key=str(call.call_id),
            timeout_seconds=12,
        ),
    )

    assert output == {"ok": True, "source": "fake-mcp"}
    assert client.calls == [
        {
            "server_label": "calendar-server",
            "tool_name": "check_availability",
            "arguments": call.arguments,
            "idempotency_key": str(call.call_id),
            "timeout_seconds": 12,
        }
    ]
