"""Minimal server-side MCP Streamable HTTP client.

The client intentionally implements only the JSON-RPC ``tools/call`` operation
needed by the MVP. Authentication and endpoints are loaded from server-side
configuration and never enter an agent profile or an LLM prompt.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class MCPServerConfig:
    label: str
    endpoint: str
    token_env_var: str | None = None
    max_response_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        if not self.label.strip() or not self.endpoint.strip():
            raise ValueError("MCP server label and endpoint are required")
        if self.max_response_bytes < 1_024:
            raise ValueError("max_response_bytes is too small")


class MCPProtocolError(RuntimeError):
    """Raised when an MCP endpoint returns invalid JSON-RPC data."""


class HTTPMCPClient:
    """Authenticated, bounded JSON-RPC client for configured MCP servers."""

    def __init__(
        self,
        servers: Mapping[str, MCPServerConfig],
        *,
        environ: Mapping[str, str] | None = None,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self._servers = dict(servers)
        self._environ = environ or os.environ
        self._opener = opener

    @classmethod
    def from_json(
        cls,
        raw: str,
        *,
        environ: Mapping[str, str] | None = None,
        opener: Callable[..., Any] = urlopen,
    ) -> "HTTPMCPClient":
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("AGENTSYNC_MCP_SERVERS_JSON is invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("AGENTSYNC_MCP_SERVERS_JSON must be an object")
        servers: dict[str, MCPServerConfig] = {}
        for label, value in payload.items():
            if not isinstance(value, dict):
                raise ValueError(f"MCP server {label!r} must be an object")
            servers[str(label)] = MCPServerConfig(
                label=str(label),
                endpoint=str(value.get("endpoint", "")),
                token_env_var=(
                    str(value["token_env_var"])
                    if value.get("token_env_var")
                    else None
                ),
                max_response_bytes=int(value.get("max_response_bytes", 1_000_000)),
            )
        return cls(servers, environ=environ, opener=opener)

    def call_tool(
        self,
        *,
        server_label: str,
        tool_name: str,
        arguments: dict[str, str | int | float | bool | None],
        idempotency_key: str,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        config = self._servers.get(server_label)
        if config is None:
            raise MCPProtocolError("MCP_SERVER_NOT_CONFIGURED")
        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": str(uuid4()),
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "X-Idempotency-Key": idempotency_key,
        }
        if config.token_env_var:
            token = self._environ.get(config.token_env_var)
            if not token:
                raise MCPProtocolError("MCP_TOKEN_NOT_CONFIGURED")
            headers["Authorization"] = f"Bearer {token}"
        request = Request(config.endpoint, data=body, headers=headers, method="POST")
        try:
            with self._opener(request, timeout=timeout_seconds) as response:
                raw_response = response.read(config.max_response_bytes + 1)
        except HTTPError as exc:
            raise MCPProtocolError(f"MCP_HTTP_{exc.code}") from exc
        except URLError as exc:
            raise MCPProtocolError("MCP_NETWORK_ERROR") from exc
        if len(raw_response) > config.max_response_bytes:
            raise MCPProtocolError("MCP_RESPONSE_TOO_LARGE")
        try:
            payload = json.loads(raw_response.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MCPProtocolError("MCP_INVALID_JSON") from exc
        if not isinstance(payload, dict):
            raise MCPProtocolError("MCP_INVALID_RESPONSE")
        if payload.get("error"):
            error = payload["error"]
            code = error.get("code", "UNKNOWN") if isinstance(error, dict) else "UNKNOWN"
            raise MCPProtocolError(f"MCP_REMOTE_ERROR_{code}")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise MCPProtocolError("MCP_MISSING_RESULT")
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            return structured
        content = result.get("content")
        if isinstance(content, list):
            return {"content": content}
        return {key: value for key, value in result.items() if key != "_meta"}
