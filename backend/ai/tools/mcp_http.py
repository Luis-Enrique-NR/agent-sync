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
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class MCPServerConfig:
    label: str
    endpoint: str
    token_env_var: str | None = None
    max_response_bytes: int = 1_000_000
    allowed_tools: frozenset[str] = frozenset()
    protocol_version: str = "2026-07-28"

    def __post_init__(self) -> None:
        if not self.label.strip() or not self.endpoint.strip():
            raise ValueError("MCP server label and endpoint are required")
        if self.max_response_bytes < 1_024:
            raise ValueError("max_response_bytes is too small")
        scheme = urlparse(self.endpoint).scheme.lower()
        if scheme not in {"http", "https"}:
            raise ValueError("MCP endpoint must use http or https")
        if any(
            not isinstance(tool, str) or not tool.strip()
            for tool in self.allowed_tools
        ):
            raise ValueError("MCP allowed tool names cannot be empty")
        if not self.protocol_version.strip():
            raise ValueError("MCP protocol_version cannot be empty")


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
        self._environ = os.environ if environ is None else environ
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
            raw_allowed_tools = value.get("allowed_tools", [])
            if not isinstance(raw_allowed_tools, list):
                raise ValueError(f"MCP server {label!r} allowed_tools must be a list")
            servers[str(label)] = MCPServerConfig(
                label=str(label),
                endpoint=str(value.get("endpoint", "")),
                token_env_var=(
                    str(value["token_env_var"])
                    if value.get("token_env_var")
                    else None
                ),
                max_response_bytes=int(value.get("max_response_bytes", 1_000_000)),
                allowed_tools=frozenset(str(tool) for tool in raw_allowed_tools),
                protocol_version=str(value.get("protocol_version", "2026-07-28")),
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
        if config.allowed_tools and tool_name not in config.allowed_tools:
            raise MCPProtocolError("MCP_TOOL_NOT_ALLOWLISTED")
        request_id = str(uuid4())
        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                    "_meta": self._request_meta(config.protocol_version),
                },
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "X-Idempotency-Key": idempotency_key,
            "MCP-Protocol-Version": config.protocol_version,
            "mcp-method": "tools/call",
            "mcp-name": tool_name,
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
                content_type = str(
                    getattr(response, "headers", {}).get("Content-Type", "")
                )
        except HTTPError as exc:
            raise MCPProtocolError(f"MCP_HTTP_{exc.code}") from exc
        except URLError as exc:
            raise MCPProtocolError("MCP_NETWORK_ERROR") from exc
        if len(raw_response) > config.max_response_bytes:
            raise MCPProtocolError("MCP_RESPONSE_TOO_LARGE")
        payload = self._decode_rpc_response(
            raw_response,
            content_type=content_type,
            request_id=request_id,
        )
        if payload.get("error"):
            error = payload["error"]
            code = error.get("code", "UNKNOWN") if isinstance(error, dict) else "UNKNOWN"
            raise MCPProtocolError(f"MCP_REMOTE_ERROR_{code}")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise MCPProtocolError("MCP_MISSING_RESULT")
        if result.get("isError") is True:
            raise MCPProtocolError("MCP_REMOTE_TOOL_ERROR")
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            return structured
        content = result.get("content")
        if isinstance(content, list):
            return {"content": content}
        return {key: value for key, value in result.items() if key != "_meta"}

    def list_tools(self, *, server_label: str, timeout_seconds: int) -> list[dict[str, Any]]:
        """Discover a server catalog for diagnostics; execution remains allowlisted."""

        config = self._servers.get(server_label)
        if config is None:
            raise MCPProtocolError("MCP_SERVER_NOT_CONFIGURED")
        request_id = str(uuid4())
        body = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/list",
                "params": {"_meta": self._request_meta(config.protocol_version)},
            },
            separators=(",", ":"),
        ).encode("utf-8")
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": config.protocol_version,
            "mcp-method": "tools/list",
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
                content_type = str(getattr(response, "headers", {}).get("Content-Type", ""))
        except HTTPError as exc:
            raise MCPProtocolError(f"MCP_HTTP_{exc.code}") from exc
        except URLError as exc:
            raise MCPProtocolError("MCP_NETWORK_ERROR") from exc
        if len(raw_response) > config.max_response_bytes:
            raise MCPProtocolError("MCP_RESPONSE_TOO_LARGE")
        payload = self._decode_rpc_response(
            raw_response,
            content_type=content_type,
            request_id=request_id,
        )
        if payload.get("error"):
            error = payload["error"]
            code = error.get("code", "UNKNOWN") if isinstance(error, dict) else "UNKNOWN"
            raise MCPProtocolError(f"MCP_REMOTE_ERROR_{code}")
        result = payload.get("result")
        tools = result.get("tools") if isinstance(result, dict) else None
        if not isinstance(tools, list) or not all(isinstance(tool, dict) for tool in tools):
            raise MCPProtocolError("MCP_INVALID_TOOLS_LIST")
        return tools

    @staticmethod
    def _decode_rpc_response(
        raw_response: bytes,
        *,
        content_type: str,
        request_id: str,
    ) -> dict[str, Any]:
        try:
            decoded = raw_response.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MCPProtocolError("MCP_INVALID_UTF8") from exc

        candidates = [decoded]
        if "text/event-stream" in content_type.lower():
            candidates = [
                line[5:].strip()
                for line in decoded.splitlines()
                if line.startswith("data:") and line[5:].strip()
            ]
        payload: dict[str, Any] | None = None
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                if str(parsed.get("id")) == request_id:
                    payload = parsed
                    break
                if payload is None:
                    payload = parsed
        if payload is None:
            raise MCPProtocolError("MCP_INVALID_RESPONSE")
        if payload.get("jsonrpc") != "2.0":
            raise MCPProtocolError("MCP_INVALID_JSONRPC_VERSION")
        if str(payload.get("id")) != request_id:
            raise MCPProtocolError("MCP_RESPONSE_ID_MISMATCH")
        return payload

    @staticmethod
    def _request_meta(protocol_version: str) -> dict[str, Any]:
        """Supply the 2026 per-request envelope; older servers ignore it."""

        return {
            "io.modelcontextprotocol/protocolVersion": protocol_version,
            "io.modelcontextprotocol/clientInfo": {
                "name": "AgentSync AI Backend",
                "version": "0.1.0",
            },
            "io.modelcontextprotocol/clientCapabilities": {},
        }
