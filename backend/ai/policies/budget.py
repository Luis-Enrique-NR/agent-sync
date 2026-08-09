"""Per-user rate, cost, and execution-time budgets.

The manager is deliberately independent from the web framework.  API workers can
share a durable implementation later, while this thread-safe in-process version
already protects a single worker and is useful for tests and local deployments.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from typing import Deque
from uuid import UUID

from ai.domain.models import utc_now


class BudgetExceededError(RuntimeError):
    """Raised when a user cannot start another LLM/tool operation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class UserBudgetLimits:
    requests_per_minute: int = 30
    max_cost_usd_per_hour: float = 5.0
    max_session_seconds: int = 900

    def __post_init__(self) -> None:
        if self.requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        if self.max_cost_usd_per_hour < 0:
            raise ValueError("max_cost_usd_per_hour cannot be negative")
        if self.max_session_seconds <= 0:
            raise ValueError("max_session_seconds must be positive")


@dataclass(frozen=True, slots=True)
class UserBudgetSnapshot:
    user_id: UUID
    requests_last_minute: int
    estimated_cost_usd_last_hour: float
    active_sessions: int


@dataclass(slots=True)
class _UserUsage:
    calls: Deque[tuple[datetime, float]]
    sessions: dict[UUID, datetime]


class UserBudgetManager:
    """Enforce simple sliding-window limits for one authenticated user.

    Costs are estimates charged before a provider/tool call.  A production
    deployment can replace this implementation with Redis or a database-backed
    ledger without changing the engine contract.
    """

    def __init__(
        self,
        limits: UserBudgetLimits | None = None,
        *,
        clock=utc_now,
    ) -> None:
        self.limits = limits or UserBudgetLimits()
        self._clock = clock
        self._usage: dict[UUID, _UserUsage] = {}
        self._lock = Lock()

    def start_session(
        self,
        user_id: UUID,
        session_id: UUID,
        *,
        started_at: datetime | None = None,
    ) -> None:
        now = started_at or self._clock()
        self._validate_timestamp(now)
        with self._lock:
            usage = self._usage.setdefault(
                user_id, _UserUsage(calls=deque(), sessions={})
            )
            usage.sessions[session_id] = now

    def finish_session(self, user_id: UUID, session_id: UUID) -> None:
        with self._lock:
            usage = self._usage.get(user_id)
            if usage is not None:
                usage.sessions.pop(session_id, None)

    def ensure_session_within_limit(
        self,
        user_id: UUID,
        session_id: UUID,
        *,
        now: datetime | None = None,
    ) -> None:
        timestamp = now or self._clock()
        self._validate_timestamp(timestamp)
        with self._lock:
            usage = self._usage.setdefault(
                user_id, _UserUsage(calls=deque(), sessions={})
            )
            started_at = usage.sessions.get(session_id)
            if started_at is None:
                usage.sessions[session_id] = timestamp
                return
            if (timestamp - started_at).total_seconds() > self.limits.max_session_seconds:
                raise BudgetExceededError(
                    "USER_SESSION_TIME_LIMIT",
                    "user session exceeded its maximum execution time",
                )

    def reserve(
        self,
        user_id: UUID,
        *,
        session_id: UUID | None = None,
        estimated_cost_usd: float = 0.0,
        now: datetime | None = None,
    ) -> UserBudgetSnapshot:
        if estimated_cost_usd < 0:
            raise ValueError("estimated_cost_usd cannot be negative")
        timestamp = now or self._clock()
        self._validate_timestamp(timestamp)
        with self._lock:
            usage = self._usage.setdefault(
                user_id, _UserUsage(calls=deque(), sessions={})
            )
            self._prune(usage, timestamp)
            if session_id is not None:
                started_at = usage.sessions.get(session_id)
                if started_at is None:
                    usage.sessions[session_id] = timestamp
                    started_at = timestamp
                elapsed = (timestamp - started_at).total_seconds()
                if elapsed > self.limits.max_session_seconds:
                    raise BudgetExceededError(
                        "USER_SESSION_TIME_LIMIT",
                        "user session exceeded its maximum execution time",
                    )
            minute_cutoff = timestamp - timedelta(minutes=1)
            requests_last_minute = sum(
                1 for call_timestamp, _ in usage.calls
                if call_timestamp >= minute_cutoff
            )
            if requests_last_minute >= self.limits.requests_per_minute:
                raise BudgetExceededError(
                    "USER_RATE_LIMIT",
                    "user exceeded the requests-per-minute limit",
                )
            cost = sum(item[1] for item in usage.calls)
            if cost + estimated_cost_usd > self.limits.max_cost_usd_per_hour:
                raise BudgetExceededError(
                    "USER_COST_LIMIT",
                    "user exceeded the hourly estimated cost limit",
                )
            usage.calls.append((timestamp, estimated_cost_usd))
            return self._snapshot(user_id, usage, now=timestamp)

    def snapshot(self, user_id: UUID, *, now: datetime | None = None) -> UserBudgetSnapshot:
        timestamp = now or self._clock()
        with self._lock:
            usage = self._usage.setdefault(
                user_id, _UserUsage(calls=deque(), sessions={})
            )
            self._prune(usage, timestamp)
            return self._snapshot(user_id, usage, now=timestamp)

    def _prune(self, usage: _UserUsage, now: datetime) -> None:
        minute_cutoff = now - timedelta(minutes=1)
        hour_cutoff = now - timedelta(hours=1)
        while usage.calls and usage.calls[0][0] < hour_cutoff:
            usage.calls.popleft()
        # Keep the hourly queue intact for cost accounting.  Rate accounting
        # filters the same queue without mutating it.
        del minute_cutoff

    def _snapshot(
        self,
        user_id: UUID,
        usage: _UserUsage,
        *,
        now: datetime,
    ) -> UserBudgetSnapshot:
        minute_cutoff = now - timedelta(minutes=1)
        return UserBudgetSnapshot(
            user_id=user_id,
            requests_last_minute=sum(
                1 for timestamp, _ in usage.calls if timestamp >= minute_cutoff
            ),
            estimated_cost_usd_last_hour=round(
                sum(cost for _, cost in usage.calls), 8
            ),
            active_sessions=len(usage.sessions),
        )

    @staticmethod
    def _validate_timestamp(timestamp: datetime) -> None:
        if timestamp.tzinfo is None:
            raise ValueError("budget timestamps must be timezone-aware")
