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


def _non_negative_float(name: str, default: float) -> float:
    raw_value = os.getenv(name, str(default))
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
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
    llm_provider: str = "openai"
    openai_api_key_env: str = "OPENAI_API_KEY"
    openai_base_url: str | None = None
    tools_provider: str = "mock"
    mcp_servers_json: str = "{}"
    user_requests_per_minute: int = 30
    user_max_cost_usd_per_hour: float = 5.0
    user_max_session_seconds: int = 900
    estimated_llm_cost_usd: float = 0.01

    @classmethod
    def from_env(cls) -> "AISettings":
        model = os.getenv("AGENTSYNC_LLM_MODEL", "gpt-4o-mini").strip()
        if not model:
            raise ValueError("AGENTSYNC_LLM_MODEL cannot be empty")
        llm_provider = os.getenv("AGENTSYNC_LLM_PROVIDER", "openai").strip().lower()
        if llm_provider not in {"openai", "fake"}:
            raise ValueError("AGENTSYNC_LLM_PROVIDER must be openai or fake")
        tools_provider = os.getenv("AGENTSYNC_TOOLS_PROVIDER", "mock").strip().lower()
        if tools_provider not in {"mock", "mcp"}:
            raise ValueError("AGENTSYNC_TOOLS_PROVIDER must be mock or mcp")
        api_key_env = os.getenv("AGENTSYNC_OPENAI_API_KEY_ENV", "OPENAI_API_KEY").strip()
        if not api_key_env:
            raise ValueError("AGENTSYNC_OPENAI_API_KEY_ENV cannot be empty")
        base_url = os.getenv("OPENAI_BASE_URL", "").strip() or None
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
            llm_provider=llm_provider,
            openai_api_key_env=api_key_env,
            openai_base_url=base_url,
            tools_provider=tools_provider,
            mcp_servers_json=os.getenv("AGENTSYNC_MCP_SERVERS_JSON", "{}"),
            user_requests_per_minute=_positive_int(
                "AGENTSYNC_USER_REQUESTS_PER_MINUTE", 30
            ),
            user_max_cost_usd_per_hour=_non_negative_float(
                "AGENTSYNC_USER_MAX_COST_USD_PER_HOUR", 5.0
            ),
            user_max_session_seconds=_positive_int(
                "AGENTSYNC_USER_MAX_SESSION_SECONDS", 900
            ),
            estimated_llm_cost_usd=_non_negative_float(
                "AGENTSYNC_ESTIMATED_LLM_COST_USD", 0.01
            ),
        )
