"""Low-cardinality telemetry contracts for LLM and tool execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from uuid import UUID

from ai.domain.models import EngineEvent, ToolExecutionStatus, utc_now


@dataclass(frozen=True, slots=True)
class LLMObservation:
    session_id: UUID
    user_id: UUID | None
    provider: str
    model: str | None
    started_at: datetime
    completed_at: datetime
    success: bool
    estimated_cost_usd: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    error_code: str | None = None

    @property
    def duration_ms(self) -> float:
        return max(0.0, (self.completed_at - self.started_at).total_seconds() * 1000)


@dataclass(frozen=True, slots=True)
class ToolObservation:
    session_id: UUID
    user_id: UUID | None
    tool_name: str
    call_id: UUID
    status: ToolExecutionStatus
    started_at: datetime
    completed_at: datetime
    error_code: str | None = None
    idempotent_replay: bool = False

    @property
    def duration_ms(self) -> float:
        return max(0.0, (self.completed_at - self.started_at).total_seconds() * 1000)


class TelemetrySink(Protocol):
    def record_llm(self, observation: LLMObservation) -> None:
        ...

    def record_tool(self, observation: ToolObservation) -> None:
        ...

    def record_event(self, event: EngineEvent) -> None:
        ...


class NullTelemetrySink:
    """No-op sink used when an application has not configured telemetry."""

    def record_llm(self, observation: LLMObservation) -> None:
        del observation

    def record_tool(self, observation: ToolObservation) -> None:
        del observation

    def record_event(self, event: EngineEvent) -> None:
        del event


@dataclass(slots=True)
class InMemoryTelemetrySink:
    """Bounded-friendly test sink; callers may clear the lists between runs."""

    llm_calls: list[LLMObservation] = field(default_factory=list)
    tool_calls: list[ToolObservation] = field(default_factory=list)
    events: list[EngineEvent] = field(default_factory=list)

    def record_llm(self, observation: LLMObservation) -> None:
        self.llm_calls.append(observation)

    def record_tool(self, observation: ToolObservation) -> None:
        self.tool_calls.append(observation)

    def record_event(self, event: EngineEvent) -> None:
        self.events.append(event)


class LoggingTelemetrySink:
    """Structured-log adapter that never serializes transcripts or tool output."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("agentsync.ai")

    def record_llm(self, observation: LLMObservation) -> None:
        self._logger.info(
            "llm_call provider=%s model=%s session_id=%s user_id=%s success=%s "
            "duration_ms=%.2f estimated_cost_usd=%.8f input_tokens=%s output_tokens=%s "
            "error_code=%s",
            observation.provider,
            observation.model or "unknown",
            observation.session_id,
            observation.user_id,
            observation.success,
            observation.duration_ms,
            observation.estimated_cost_usd,
            observation.input_tokens,
            observation.output_tokens,
            observation.error_code,
        )

    def record_tool(self, observation: ToolObservation) -> None:
        self._logger.info(
            "tool_call tool_name=%s call_id=%s session_id=%s user_id=%s status=%s "
            "duration_ms=%.2f error_code=%s replay=%s",
            observation.tool_name,
            observation.call_id,
            observation.session_id,
            observation.user_id,
            observation.status.value,
            observation.duration_ms,
            observation.error_code,
            observation.idempotent_replay,
        )

    def record_event(self, event: EngineEvent) -> None:
        self._logger.info(
            "engine_event event_type=%s session_id=%s event_id=%s audience=%s",
            event.event_type.value,
            event.session_id,
            event.event_id,
            event.audience.value,
        )


def telemetry_or_null(sink: TelemetrySink | None) -> TelemetrySink:
    return sink or NullTelemetrySink()


def observation_now() -> datetime:
    return utc_now()
