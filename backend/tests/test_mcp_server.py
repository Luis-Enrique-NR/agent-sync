from __future__ import annotations

import json

import pytest
from starlette.testclient import TestClient

from ai.tools.mcp_http import HTTPMCPClient, MCPProtocolError
from mcp_servers.agentsync.config import MCPSettings
from mcp_servers.agentsync.server import build_server
from mcp_servers.agentsync.upstream import (
    HTTPUpstream,
    ResendAdapter,
    SearchAdapter,
    SerpApiAdapter,
    UpstreamError,
)


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
        tools = response.json()["result"]["tools"]
        assert {tool["name"] for tool in tools} == {
            "web.search",
            "market.reference_prices",
            "email.send_notification",
        }
        email_tool = next(tool for tool in tools if tool["name"] == "email.send_notification")
        assert "to" in email_tool["inputSchema"]["required"]


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


def test_serpapi_normalizes_google_shopping_results(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return _Response(
            json.dumps(
                {
                    "shopping_results": [
                        {
                            "product_id": "p-1",
                            "title": "Cotton lot",
                            "extracted_price": 900,
                            "source": "Vendor",
                            "link": "https://vendor.example/p-1",
                        }
                    ]
                }
            ).encode()
        )

    monkeypatch.setattr("mcp_servers.agentsync.upstream.urlopen", fake_urlopen)
    result = SerpApiAdapter(
        endpoint=None,
        token_env=None,
        timeout_seconds=5,
        max_response_bytes=10_000,
        environ={"SERPAPI_API_KEY": "secret"},
    ).search("cotton", "Bogota", "USD")
    assert result["items"] == [
        {
            "product_id": "p-1",
            "name": "Cotton lot",
            "price": 900,
            "currency": "USD",
            "seller": "Vendor",
            "url": "https://vendor.example/p-1",
        }
    ]
    assert "api_key=secret" in captured["request"].full_url


def test_resend_sends_per_call_recipient_without_exposing_addresses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        return _Response(json.dumps({"id": "email-1"}).encode())

    monkeypatch.setattr("mcp_servers.agentsync.upstream.urlopen", fake_urlopen)
    result = ResendAdapter(
        endpoint=None,
        token_env=None,
        from_address="agent@example.com",
        timeout_seconds=5,
        max_response_bytes=10_000,
        environ={"RESEND_API_KEY": "secret"},
    ).send("Decision", "Please approve", "owner@example.com", idempotency_key="call-1")
    assert result == {"delivery_id": "email-1", "status": "accepted"}
    assert captured["request"].headers["Authorization"] == "Bearer secret"
    assert "owner@example.com" in captured["request"].data.decode()
    assert "secret" not in captured["request"].data.decode()


def test_resend_rejects_invalid_per_call_recipient(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mcp_servers.agentsync.upstream.urlopen",
        lambda request, timeout: pytest.fail("provider must not be called"),
    )
    adapter = ResendAdapter(
        endpoint=None,
        token_env=None,
        from_address="agent@example.com",
        timeout_seconds=5,
        max_response_bytes=10_000,
        environ={"RESEND_API_KEY": "secret"},
    )
    with pytest.raises(UpstreamError, match="INVALID_EMAIL_RECIPIENT"):
        adapter.send("Decision", "Please approve", "not-an-email", idempotency_key="call-1")


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
