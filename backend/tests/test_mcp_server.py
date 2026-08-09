from __future__ import annotations

import json

import pytest
from starlette.testclient import TestClient

from ai.tools.mcp_http import HTTPMCPClient, MCPProtocolError
from mcp_servers.agentsync.config import MCPSettings
from mcp_servers.agentsync.server import build_server
from mcp_servers.agentsync.upstream import HTTPUpstream, SearchAdapter, UpstreamError


class _Response:
    def __init__(self, body: bytes, content_type: str = "application/json") -> None:
        self.body = body
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size: int) -> bytes:
        return self.body[:size]


def test_server_catalog_and_health_are_explicit() -> None:
    settings = MCPSettings(search_endpoint="https://search.internal")
    _, app = build_server(settings, environ={})
    with TestClient(app, base_url="http://localhost:8001") as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["configured_providers"]["search"] is True
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": "2026-07-28",
            "mcp-method": "tools/list",
        }
        meta = {
            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "1"},
            "io.modelcontextprotocol/clientCapabilities": {},
        }
        response = client.post(
            "/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "id": "1", "method": "tools/list", "params": {"_meta": meta}},
        )
        assert response.status_code == 200
        assert {tool["name"] for tool in response.json()["result"]["tools"]} == {
            "web.search",
            "calendar.check_availability",
            "market.reference_prices",
            "inventory.check_stock",
            "email.send_notification",
            "calendar.request_meeting",
        }


def test_unconfigured_provider_fails_closed() -> None:
    settings = MCPSettings()
    _, app = build_server(settings, environ={})
    with TestClient(app, base_url="http://localhost:8001") as client:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": "2026-07-28",
            "mcp-method": "tools/call",
            "mcp-name": "web.search",
        }
        meta = {
            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientInfo": {"name": "test", "version": "1"},
            "io.modelcontextprotocol/clientCapabilities": {},
        }
        response = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": "1",
                "method": "tools/call",
                "params": {"name": "web.search", "arguments": {"query": "x"}, "_meta": meta},
            },
        )
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["isError"] is True
        assert "UPSTREAM_NOT_CONFIGURED" in result["content"][0]["text"]


def test_bearer_auth_is_optional_but_enforced_when_configured() -> None:
    settings = MCPSettings(auth_token_env="MCP_TEST_TOKEN")
    _, app = build_server(settings, environ={"MCP_TEST_TOKEN": "expected"})
    with TestClient(app, base_url="http://localhost:8001") as client:
        assert client.get("/health").status_code == 200
        assert client.post("/mcp").status_code == 401
        assert client.post("/mcp", headers={"Authorization": "Bearer expected"}).status_code != 401


def test_upstream_is_bounded_and_sends_idempotency_and_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _Response(json.dumps({"items": [{"price": 900, "email": "private"}]}).encode())

    monkeypatch.setattr("mcp_servers.agentsync.upstream.urlopen", fake_urlopen)
    upstream = HTTPUpstream(
        "https://prices.internal",
        "PRICES_TOKEN",
        4,
        10_000,
        {"PRICES_TOKEN": "secret"},
    )
    output = upstream.post_json({"item": "cotton"}, idempotency_key="call-1")
    assert output == {"items": [{"price": 900}]}
    assert captured["timeout"] == 4
    assert captured["request"].headers["Authorization"] == "Bearer secret"
    assert captured["request"].headers["X-idempotency-key"] == "call-1"
    assert "secret" not in captured["request"].data.decode()


def test_search_normalizes_brave_results() -> None:
    output = SearchAdapter._normalize_results(
        {"web": {"results": [{"title": "A", "url": "https://a", "description": "B"}]}},
        provider="brave",
        query="cotton",
    )
    assert output == {
        "query": "cotton",
        "provider": "brave",
        "results": [{"title": "A", "url": "https://a", "snippet": "B"}],
    }


def test_http_client_emits_current_mcp_headers_and_meta() -> None:
    captured = {}

    def opener(request, timeout):
        captured["request"] = request
        request_id = json.loads(request.data.decode())["id"]
        return _Response(
            json.dumps(
                {"jsonrpc": "2.0", "id": request_id, "result": {"structuredContent": {"ok": True}}}
            ).encode()
        )

    client = HTTPMCPClient.from_json(
        '{"default":{"endpoint":"https://mcp.internal","allowed_tools":["web.search"]}}',
        opener=opener,
    )
    assert client.call_tool(
        server_label="default",
        tool_name="web.search",
        arguments={"query": "x"},
        idempotency_key="call-1",
        timeout_seconds=3,
    ) == {"ok": True}
    request = captured["request"]
    assert request.headers["Mcp-protocol-version"] == "2026-07-28"
    assert request.headers["Mcp-method"] == "tools/call"
    assert request.headers["Mcp-name"] == "web.search"
    body = json.loads(request.data.decode())
    assert body["params"]["_meta"]["io.modelcontextprotocol/clientCapabilities"] == {}


def test_http_client_does_not_turn_mcp_tool_errors_into_success() -> None:
    def opener(request, timeout):
        request_id = json.loads(request.data.decode())["id"]
        return _Response(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"isError": True, "content": [{"text": "provider down"}]},
                }
            ).encode()
        )

    client = HTTPMCPClient.from_json(
        '{"default":{"endpoint":"https://mcp.internal","allowed_tools":["web.search"]}}',
        opener=opener,
    )
    with pytest.raises(MCPProtocolError, match="MCP_REMOTE_TOOL_ERROR"):
        client.call_tool(
            server_label="default",
            tool_name="web.search",
            arguments={"query": "x"},
            idempotency_key="call-1",
            timeout_seconds=3,
        )
