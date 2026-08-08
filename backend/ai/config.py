"""Server-side configuration for the AI Brain."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _non_negative_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < 0:
        raise ValueError(f"{name} cannot be negative")
    return value


@dataclass(frozen=True, slots=True)
class AISettings:
    """Validated settings read from environment variables."""

    llm_model: str
    llm_timeout_seconds: int
    llm_max_retries: int
    max_turns: int
    session_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "AISettings":
        model = os.getenv("AGENTSYNC_LLM_MODEL", "gpt-4o-mini").strip()
        if not model:
            raise ValueError("AGENTSYNC_LLM_MODEL cannot be empty")
        return cls(
            llm_model=model,
            llm_timeout_seconds=_positive_int(
                "AGENTSYNC_LLM_TIMEOUT_SECONDS", 25
            ),
            llm_max_retries=_non_negative_int("AGENTSYNC_LLM_MAX_RETRIES", 1),
            max_turns=_positive_int("AGENTSYNC_MAX_TURNS", 8),
            session_timeout_seconds=_positive_int(
                "AGENTSYNC_SESSION_TIMEOUT_SECONDS", 90
            ),
        )
