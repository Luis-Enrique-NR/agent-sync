"""Deterministic demo tools matching the MVP's simulated integrations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ai.domain.models import (
    ToolCallRequest,
    ToolDescriptor,
    ToolParameterDefinition,
    ToolRiskLevel,
    ToolValueType,
    utc_now,
)
from ai.tools.base import ToolExecutionContext
from ai.tools.gateway import ToolGateway


class CallableToolAdapter:
    def __init__(
        self,
        handler: Callable[[ToolCallRequest, ToolExecutionContext], dict[str, Any]],
    ) -> None:
        self._handler = handler

    def execute(
        self,
        call: ToolCallRequest,
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        return self._handler(call, context)


@dataclass(slots=True)
class DemoToolStore:
    email_notifications: list[dict[str, Any]] = field(default_factory=list)


def build_demo_tool_gateway(
    *,
    store: DemoToolStore | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> ToolGateway:
    demo_store = store or DemoToolStore()
    gateway = ToolGateway(clock=clock)

    gateway.register(
        ToolDescriptor(
            name="web.search",
            description="Search simulated public sources for demo research.",
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
        CallableToolAdapter(_mock_web_search),
    )
    gateway.register(
        ToolDescriptor(
            name="calendar.check_availability",
            description="Read simulated owner availability within a date range.",
            risk_level=ToolRiskLevel.SENSITIVE_READ,
            parameters=[
                ToolParameterDefinition(
                    name="start_date",
                    value_type=ToolValueType.STRING,
                    description="Inclusive ISO date.",
                    max_length=10,
                ),
                ToolParameterDefinition(
                    name="end_date",
                    value_type=ToolValueType.STRING,
                    description="Inclusive ISO date.",
                    max_length=10,
                ),
            ],
        ),
        CallableToolAdapter(_mock_calendar_availability),
    )
    gateway.register(
        ToolDescriptor(
            name="email.send_notification",
            description="Send a simulated email notification to the agent owner.",
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
        CallableToolAdapter(
            lambda call, context: _mock_email_notification(
                call,
                context,
                demo_store,
            )
        ),
    )
    return gateway


def _mock_web_search(
    call: ToolCallRequest,
    context: ToolExecutionContext,
) -> dict[str, Any]:
    query = str(call.arguments["query"])
    return {
        "mode": "SIMULATED",
        "query": query,
        "results": [
            {
                "title": "Demo market reference",
                "url": "https://example.invalid/demo-market-reference",
                "snippet": f"Simulated public information relevant to: {query}",
            }
        ],
    }


def _mock_calendar_availability(
    call: ToolCallRequest,
    context: ToolExecutionContext,
) -> dict[str, Any]:
    return {
        "mode": "SIMULATED",
        "requested_range": {
            "start_date": call.arguments["start_date"],
            "end_date": call.arguments["end_date"],
        },
        "available_windows": [
            "2026-08-15T10:00:00-05:00/2026-08-15T12:00:00-05:00"
        ],
    }


def _mock_email_notification(
    call: ToolCallRequest,
    context: ToolExecutionContext,
    store: DemoToolStore,
) -> dict[str, Any]:
    notification = {
        "delivery_id": context.idempotency_key,
        "recipient": "AGENT_OWNER",
        "subject": call.arguments["subject"],
        "body": call.arguments["body"],
        "mode": "SIMULATED",
    }
    store.email_notifications.append(notification)
    return notification

