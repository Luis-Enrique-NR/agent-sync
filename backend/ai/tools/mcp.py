"""MCP adapter boundary; credentials and transport stay server-side."""

from __future__ import annotations

from typing import Any, Protocol

from ai.domain.models import (
    ToolCallRequest,
    ToolDescriptor,
    ToolParameterDefinition,
    ToolRiskLevel,
    ToolValueType,
)
from ai.tools.base import ToolExecutionContext
from ai.tools.gateway import ToolGateway


class MCPClient(Protocol):
    def call_tool(
        self,
        *,
        server_label: str,
        tool_name: str,
        arguments: dict[str, str | int | float | bool | None],
        idempotency_key: str,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        """Call one allowlisted remote MCP tool."""


class MCPToolAdapter:
    """Bind one local capability to one remote MCP tool."""

    def __init__(
        self,
        *,
        client: MCPClient,
        server_label: str,
        remote_tool_name: str,
    ) -> None:
        if not server_label.strip() or not remote_tool_name.strip():
            raise ValueError("MCP server and tool names cannot be empty")
        self._client = client
        self._server_label = server_label
        self._remote_tool_name = remote_tool_name

    def execute(
        self,
        call: ToolCallRequest,
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        result = self._client.call_tool(
            server_label=self._server_label,
            tool_name=self._remote_tool_name,
            arguments=call.arguments,
            idempotency_key=context.idempotency_key,
            timeout_seconds=context.timeout_seconds,
        )
        if not isinstance(result, dict):
            raise TypeError("MCP tool result must be an object")
        return result


def build_mcp_tool_gateway(
    client: MCPClient,
    *,
    server_label: str = "default",
) -> ToolGateway:
    """Register the MVP tool catalog against a real MCP client."""

    gateway = ToolGateway()
    gateway.register(
        ToolDescriptor(
            name="web.search",
            description="Search configured public sources.",
            risk_level=ToolRiskLevel.READ_ONLY,
            parameters=[
                ToolParameterDefinition(
                    name="query",
                    value_type=ToolValueType.STRING,
                    description="Concise search query.",
                    max_length=300,
                )
            ],
        ),
        MCPToolAdapter(
            client=client,
            server_label=server_label,
            remote_tool_name="web.search",
        ),
    )
    gateway.register(
        ToolDescriptor(
            name="market.reference_prices",
            description="Compare reference prices from configured market sources.",
            risk_level=ToolRiskLevel.READ_ONLY,
            parameters=[
                ToolParameterDefinition(
                    name="item",
                    value_type=ToolValueType.STRING,
                    description="Product or service to compare.",
                    max_length=160,
                ),
                ToolParameterDefinition(
                    name="region",
                    value_type=ToolValueType.STRING,
                    description="Optional market region.",
                    required=False,
                    max_length=120,
                ),
                ToolParameterDefinition(
                    name="currency",
                    value_type=ToolValueType.STRING,
                    description="ISO currency code.",
                    required=False,
                    max_length=3,
                ),
            ],
        ),
        MCPToolAdapter(
            client=client,
            server_label=server_label,
            remote_tool_name="market.reference_prices",
        ),
    )
    gateway.register(
        ToolDescriptor(
            name="email.send_notification",
            description="Send an email notification to the agent owner.",
            risk_level=ToolRiskLevel.EXTERNAL_WRITE,
            requires_human_approval=True,
            parameters=[
                ToolParameterDefinition(
                    name="subject",
                    value_type=ToolValueType.STRING,
                    description="Notification subject.",
                    max_length=160,
                ),
                ToolParameterDefinition(
                    name="body",
                    value_type=ToolValueType.STRING,
                    description="Notification body.",
                    max_length=2_000,
                ),
            ],
        ),
        MCPToolAdapter(
            client=client,
            server_label=server_label,
            remote_tool_name="email.send_notification",
        ),
    )
    return gateway
