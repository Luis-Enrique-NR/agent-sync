"""Allowlisted, approval-aware and idempotent tool gateway."""

from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from collections.abc import Callable
from datetime import datetime
from threading import Lock
from typing import Any
from uuid import UUID

from ai.domain.models import (
    AgentProfile,
    ToolApprovalMode,
    ToolCallRequest,
    ToolDescriptor,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolPolicyOutcome,
    ToolValueType,
    utc_now,
)
from ai.observability import NullTelemetrySink, TelemetrySink, ToolObservation
from ai.tools.base import (
    ToolAdapter,
    ToolExecutionContext,
    ToolPolicyEvaluation,
)


class ToolGateway:
    """Own tool policy and execution; the model can only submit requests."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = utc_now,
        telemetry_sink: TelemetrySink | None = None,
    ) -> None:
        self._clock = clock
        self._registry: dict[str, tuple[ToolDescriptor, ToolAdapter]] = {}
        self._execution_cache: dict[
            tuple[UUID, UUID, UUID], ToolExecutionResult
        ] = {}
        self._cache_lock = Lock()
        self._execution_locks: dict[tuple[UUID, UUID, UUID], Lock] = {}
        self._telemetry = telemetry_sink or NullTelemetrySink()

    def set_telemetry(self, telemetry_sink: TelemetrySink) -> None:
        """Attach the application sink after composition of the engine."""

        self._telemetry = telemetry_sink

    def register(
        self,
        descriptor: ToolDescriptor,
        adapter: ToolAdapter,
    ) -> None:
        if descriptor.name in self._registry:
            raise ValueError(f"tool already registered: {descriptor.name}")
        self._registry[descriptor.name] = (descriptor, adapter)

    def available_tools(self, profile: AgentProfile) -> tuple[ToolDescriptor, ...]:
        enabled = {
            grant.tool_name
            for grant in profile.tool_grants
            if grant.enabled
        }
        return tuple(
            descriptor.model_copy(deep=True)
            for name, (descriptor, _) in sorted(self._registry.items())
            if name in enabled
        )

    def evaluate(
        self,
        profile: AgentProfile,
        call: ToolCallRequest,
    ) -> ToolPolicyEvaluation:
        grant = next(
            (
                item
                for item in profile.tool_grants
                if item.tool_name == call.tool_name and item.enabled
            ),
            None,
        )
        if grant is None:
            return ToolPolicyEvaluation(
                outcome=ToolPolicyOutcome.DENY,
                reason_code="TOOL_NOT_GRANTED",
            )

        registration = self._registry.get(call.tool_name)
        if registration is None:
            return ToolPolicyEvaluation(
                outcome=ToolPolicyOutcome.DENY,
                reason_code="TOOL_NOT_REGISTERED",
            )
        descriptor, _ = registration
        argument_error = self._validate_arguments(descriptor, call.arguments)
        if argument_error is not None:
            return ToolPolicyEvaluation(
                outcome=ToolPolicyOutcome.DENY,
                descriptor=descriptor,
                reason_code=argument_error,
            )

        if (
            descriptor.requires_human_approval
            or grant.approval_mode is ToolApprovalMode.ALWAYS
        ):
            return ToolPolicyEvaluation(
                outcome=ToolPolicyOutcome.REQUIRE_APPROVAL,
                descriptor=descriptor,
            )
        return ToolPolicyEvaluation(
            outcome=ToolPolicyOutcome.AUTO_EXECUTE,
            descriptor=descriptor,
        )

    def execute(
        self,
        *,
        session_id: UUID,
        profile: AgentProfile,
        call: ToolCallRequest,
        human_approved: bool = False,
        user_id: UUID | None = None,
    ) -> ToolExecutionResult:
        cache_key = (session_id, profile.agent_id, call.call_id)
        policy = self.evaluate(profile, call)
        if policy.outcome is ToolPolicyOutcome.DENY:
            result = self._failure_result(
                call=call,
                agent_id=profile.agent_id,
                status=ToolExecutionStatus.DENIED,
                error_code=policy.reason_code or "TOOL_DENIED",
            )
            self._record_tool(session_id, user_id, result)
            return result
        if (
            policy.outcome is ToolPolicyOutcome.REQUIRE_APPROVAL
            and not human_approved
        ):
            result = self._failure_result(
                call=call,
                agent_id=profile.agent_id,
                status=ToolExecutionStatus.DENIED,
                error_code="TOOL_APPROVAL_REQUIRED",
            )
            self._record_tool(session_id, user_id, result)
            return result

        with self._cache_lock:
            cached = self._execution_cache.get(cache_key)
            if cached is not None:
                result = self._replay(cached)
                self._record_tool(session_id, user_id, result)
                return result
            execution_lock = self._execution_locks.setdefault(cache_key, Lock())

        with execution_lock:
            with self._cache_lock:
                cached = self._execution_cache.get(cache_key)
                if cached is not None:
                    result = self._replay(cached)
                    self._record_tool(session_id, user_id, result)
                    return result

            result = self._execute_once(
                session_id=session_id,
                profile=profile,
                call=call,
            )
            self._record_tool(session_id, user_id, result)
            with self._cache_lock:
                self._execution_cache[cache_key] = result.model_copy(deep=True)
                self._execution_locks.pop(cache_key, None)
            return result

    def _execute_once(
        self,
        *,
        session_id: UUID,
        profile: AgentProfile,
        call: ToolCallRequest,
    ) -> ToolExecutionResult:
        descriptor, adapter = self._registry[call.tool_name]
        started_at = self._clock()
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(
                adapter.execute,
                call,
                ToolExecutionContext(
                    session_id=session_id,
                    agent_id=profile.agent_id,
                    idempotency_key=str(call.call_id),
                    timeout_seconds=descriptor.timeout_seconds,
                ),
            )
            output = future.result(timeout=descriptor.timeout_seconds)
            serialized = json.dumps(output, ensure_ascii=False, allow_nan=False)
            if len(serialized) > descriptor.max_output_chars:
                raise ValueError("tool output exceeds configured limit")
            return ToolExecutionResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                requested_by_agent_id=profile.agent_id,
                status=ToolExecutionStatus.SUCCEEDED,
                output=output,
                started_at=started_at,
                completed_at=self._clock(),
            )
        except (TimeoutError, FutureTimeoutError):
            if "future" in locals():
                future.cancel()
            error_code = "TOOL_TIMEOUT"
        except Exception:
            error_code = "TOOL_EXECUTION_FAILED"
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        return ToolExecutionResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            requested_by_agent_id=profile.agent_id,
            status=ToolExecutionStatus.FAILED,
            error_code=error_code,
            started_at=started_at,
            completed_at=self._clock(),
        )

    @staticmethod
    def _replay(result: ToolExecutionResult) -> ToolExecutionResult:
        return result.model_copy(
            update={"idempotent_replay": True},
            deep=True,
        )

    def rejection_result(
        self,
        profile: AgentProfile,
        call: ToolCallRequest,
        *,
        session_id: UUID | None = None,
        user_id: UUID | None = None,
    ) -> ToolExecutionResult:
        result = self._failure_result(
            call=call,
            agent_id=profile.agent_id,
            status=ToolExecutionStatus.REJECTED,
            error_code="TOOL_REJECTED_BY_HUMAN",
        )
        if session_id is not None:
            self._record_tool(session_id, user_id, result)
        return result

    def _failure_result(
        self,
        *,
        call: ToolCallRequest,
        agent_id: UUID,
        status: ToolExecutionStatus,
        error_code: str,
    ) -> ToolExecutionResult:
        now = self._clock()
        return ToolExecutionResult(
            call_id=call.call_id,
            tool_name=call.tool_name,
            requested_by_agent_id=agent_id,
            status=status,
            error_code=error_code,
            started_at=now,
            completed_at=now,
        )

    def _record_tool(
        self,
        session_id: UUID,
        user_id: UUID | None,
        result: ToolExecutionResult,
    ) -> None:
        self._telemetry.record_tool(
            ToolObservation(
                session_id=session_id,
                user_id=user_id,
                tool_name=result.tool_name,
                call_id=result.call_id,
                status=result.status,
                started_at=result.started_at,
                completed_at=result.completed_at,
                error_code=result.error_code,
                idempotent_replay=result.idempotent_replay,
            )
        )

    @classmethod
    def _validate_arguments(
        cls,
        descriptor: ToolDescriptor,
        arguments: dict[str, Any],
    ) -> str | None:
        definitions = {item.name: item for item in descriptor.parameters}
        if set(arguments) - set(definitions):
            return "TOOL_UNKNOWN_ARGUMENT"
        if any(
            item.required and item.name not in arguments
            for item in descriptor.parameters
        ):
            return "TOOL_MISSING_ARGUMENT"
        for name, value in arguments.items():
            definition = definitions[name]
            if value is None and not definition.required:
                continue
            if not cls._matches_type(value, definition.value_type):
                return "TOOL_ARGUMENT_TYPE_MISMATCH"
            if (
                isinstance(value, str)
                and definition.max_length is not None
                and len(value) > definition.max_length
            ):
                return "TOOL_ARGUMENT_TOO_LONG"
        return None

    @staticmethod
    def _matches_type(value: Any, expected: ToolValueType) -> bool:
        if expected is ToolValueType.STRING:
            return isinstance(value, str)
        if expected is ToolValueType.BOOLEAN:
            return isinstance(value, bool)
        if expected is ToolValueType.INTEGER:
            return isinstance(value, int) and not isinstance(value, bool)
        if expected is ToolValueType.NUMBER:
            return (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(value)
            )
        return False
