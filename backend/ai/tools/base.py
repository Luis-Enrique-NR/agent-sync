"""Ports and policy results for deterministic tool execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from ai.domain.models import (
    ToolCallRequest,
    ToolDescriptor,
    ToolPolicyOutcome,
)


@dataclass(frozen=True, slots=True)
class ToolExecutionContext:
    session_id: UUID
    agent_id: UUID
    idempotency_key: str
    timeout_seconds: int


class ToolAdapter(Protocol):
    def execute(
        self,
        call: ToolCallRequest,
        context: ToolExecutionContext,
    ) -> dict[str, Any]:
        """Execute one already-authorized call and return JSON-safe data."""


@dataclass(frozen=True, slots=True)
class ToolPolicyEvaluation:
    outcome: ToolPolicyOutcome
    descriptor: ToolDescriptor | None = None
    reason_code: str | None = None

