"""Environment-only configuration for the first-party AgentSync MCP server.

The MCP process owns credentials for external providers.  Agent profiles and
LLM prompts only ever see the sanitized tool result, never these values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse


def _int_env(environ: Mapping[str, str], name: str, default: int, *, minimum: int) -> int:
    raw = environ.get(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _csv_env(environ: Mapping[str, str], name: str, default: str) -> tuple[str, ...]:
    raw = environ.get(name, default)
    return tuple(value.strip() for value in raw.split(",") if value.strip())


@dataclass(frozen=True, slots=True)
class MCPSettings:
    host: str = "127.0.0.1"
    port: int = 8001
    allowed_hosts: tuple[str, ...] = ("127.0.0.1:8001", "localhost:8001")
    allowed_origins: tuple[str, ...] = ("http://localhost:3000", "http://localhost:8000")
    auth_token_env: str | None = None
    search_provider: str = "generic"
    search_endpoint: str | None = None
    search_token_env: str | None = None
    prices_provider: str = "generic"
    prices_endpoint: str | None = None
    prices_token_env: str | None = None
    email_provider: str = "generic"
    email_endpoint: str | None = None
    email_token_env: str | None = None
    email_from: str | None = None
    email_logo_path: str | None = None
    upstream_timeout_seconds: int = 15
    upstream_max_response_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        if not self.host.strip():
            raise ValueError("AGENTSYNC_MCP_HOST cannot be empty")
        if not 1 <= self.port <= 65_535:
            raise ValueError("AGENTSYNC_MCP_PORT must be between 1 and 65535")
        if not self.allowed_hosts:
            raise ValueError("AGENTSYNC_MCP_ALLOWED_HOSTS cannot be empty")
        if self.upstream_timeout_seconds < 1:
            raise ValueError("upstream timeout must be positive")
        if self.upstream_max_response_bytes < 1_024:
            raise ValueError("upstream response limit is too small")
        for name in (
            "search_endpoint",
            "prices_endpoint",
            "email_endpoint",
        ):
            endpoint = getattr(self, name)
            if endpoint and urlparse(endpoint).scheme.lower() not in {"http", "https"}:
                raise ValueError(f"{name} must use http or https")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "MCPSettings":
        env = os.environ if environ is None else environ
        provider = env.get("AGENTSYNC_MCP_SEARCH_PROVIDER", "generic").strip().lower()
        if provider not in {"generic", "brave", "tavily"}:
            raise ValueError("AGENTSYNC_MCP_SEARCH_PROVIDER must be generic, brave, or tavily")
        prices_provider = env.get("AGENTSYNC_MCP_PRICES_PROVIDER", "generic").strip().lower()
        if prices_provider not in {"generic", "serpapi"}:
            raise ValueError("AGENTSYNC_MCP_PRICES_PROVIDER must be generic or serpapi")
        email_provider = env.get("AGENTSYNC_MCP_EMAIL_PROVIDER", "generic").strip().lower()
        if email_provider not in {"generic", "resend"}:
            raise ValueError("AGENTSYNC_MCP_EMAIL_PROVIDER must be generic or resend")
        port = _int_env(env, "AGENTSYNC_MCP_PORT", 8001, minimum=1)
        host = env.get("AGENTSYNC_MCP_HOST", "127.0.0.1").strip() or "127.0.0.1"
        default_hosts = f"{host}:{port},localhost:{port}"
        return cls(
            host=host,
            port=port,
            allowed_hosts=_csv_env(env, "AGENTSYNC_MCP_ALLOWED_HOSTS", default_hosts),
            allowed_origins=_csv_env(
                env,
                "AGENTSYNC_MCP_ALLOWED_ORIGINS",
                "http://localhost:3000,http://localhost:8000",
            ),
            auth_token_env=(env.get("AGENTSYNC_MCP_AUTH_TOKEN_ENV") or None),
            search_provider=provider,
            search_endpoint=(env.get("AGENTSYNC_MCP_SEARCH_ENDPOINT") or None),
            search_token_env=(env.get("AGENTSYNC_MCP_SEARCH_TOKEN_ENV") or None),
            prices_provider=prices_provider,
            prices_endpoint=(env.get("AGENTSYNC_MCP_PRICES_ENDPOINT") or None),
            prices_token_env=(env.get("AGENTSYNC_MCP_PRICES_TOKEN_ENV") or None),
            email_provider=email_provider,
            email_endpoint=(env.get("AGENTSYNC_MCP_EMAIL_ENDPOINT") or None),
            email_token_env=(env.get("AGENTSYNC_MCP_EMAIL_TOKEN_ENV") or None),
            email_from=(env.get("AGENTSYNC_MCP_EMAIL_FROM") or None),
            email_logo_path=(env.get("AGENTSYNC_MCP_EMAIL_LOGO_PATH") or None),
            upstream_timeout_seconds=_int_env(
                env, "AGENTSYNC_MCP_UPSTREAM_TIMEOUT_SECONDS", 15, minimum=1
            ),
            upstream_max_response_bytes=_int_env(
                env, "AGENTSYNC_MCP_UPSTREAM_MAX_RESPONSE_BYTES", 1_000_000, minimum=1_024
            ),
        )

    def configured_providers(self) -> dict[str, bool]:
        return {
            "search": self.search_provider != "generic" or bool(self.search_endpoint),
            "prices": self.prices_provider != "generic" or bool(self.prices_endpoint),
            "email": (self.email_provider == "resend" and bool(self.email_from))
            or bool(self.email_endpoint),
        }
