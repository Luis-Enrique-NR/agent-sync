"""First-party AgentSync MCP server.

This process is deliberately narrow: it exposes external capabilities through
MCP and does not contain negotiation state or LLM prompts.  The AI gateway
remains the policy authority; this server owns provider credentials and
sanitizes provider responses before they cross the MCP boundary.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from dotenv import load_dotenv
from pydantic import Field
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .config import MCPSettings
from .security import BearerTokenMiddleware
from .upstream import (
    HTTPUpstream,
    ResendAdapter,
    SearchAdapter,
    SerpApiAdapter,
    UpstreamError,
    sanitize_output,
)


load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


def _raise_tool_error(exc: UpstreamError) -> None:
    # Keep provider details out of the public tool response.  The code is
    # stable enough for the AI gateway to turn into a decision/audit event.
    raise RuntimeError(exc.code) from exc


class AgentSyncMCP:
    def __init__(self, settings: MCPSettings, *, environ: dict[str, str] | None = None) -> None:
        self.settings = settings
        self.environ = os.environ if environ is None else environ

    def _search(self, query: str) -> dict[str, Any]:
        return SearchAdapter(
            provider=self.settings.search_provider,
            endpoint=self.settings.search_endpoint,
            token_env=self.settings.search_token_env,
            timeout_seconds=self.settings.upstream_timeout_seconds,
            max_response_bytes=self.settings.upstream_max_response_bytes,
            environ=self.environ,
        ).search(query, idempotency_key=str(uuid4()))

    def _upstream(self, endpoint: str | None, token_env: str | None) -> HTTPUpstream:
        return HTTPUpstream(
            endpoint=endpoint,
            token_env=token_env,
            timeout_seconds=self.settings.upstream_timeout_seconds,
            max_response_bytes=self.settings.upstream_max_response_bytes,
            environ=self.environ,
        )

    @staticmethod
    def _collection(raw: dict[str, Any], key: str) -> dict[str, Any]:
        items = raw.get(key, raw.get("data", []))
        if not isinstance(items, list):
            raise UpstreamError("UPSTREAM_INVALID_ITEMS")
        return {**raw, key: sanitize_output(items)}

    async def web_search(self, query: str) -> dict[str, Any]:
        try:
            return await asyncio.to_thread(self._search, query)
        except UpstreamError as exc:
            _raise_tool_error(exc)

    async def market_reference_prices(
        self, item: str, region: str = "", currency: str = "USD"
    ) -> dict[str, Any]:
        try:
            if self.settings.prices_provider == "serpapi":
                return await asyncio.to_thread(
                    SerpApiAdapter(
                        endpoint=self.settings.prices_endpoint,
                        token_env=self.settings.prices_token_env,
                        timeout_seconds=self.settings.upstream_timeout_seconds,
                        max_response_bytes=self.settings.upstream_max_response_bytes,
                        environ=self.environ,
                    ).search,
                    item,
                    region,
                    currency,
                )
            raw = await asyncio.to_thread(
                self._upstream(self.settings.prices_endpoint, self.settings.prices_token_env).post_json,
                {"item": item, "region": region, "currency": currency},
                idempotency_key=str(uuid4()),
            )
            return self._collection(raw, "items")
        except UpstreamError as exc:
            _raise_tool_error(exc)

    async def email_send_notification(self, subject: str, body: str) -> dict[str, Any]:
        try:
            if self.settings.email_provider == "resend":
                return await asyncio.to_thread(
                    ResendAdapter(
                        endpoint=self.settings.email_endpoint,
                        token_env=self.settings.email_token_env,
                        from_address=self.settings.email_from,
                        to_address=self.settings.email_to,
                        timeout_seconds=self.settings.upstream_timeout_seconds,
                        max_response_bytes=self.settings.upstream_max_response_bytes,
                        environ=self.environ,
                    ).send,
                    subject,
                    body,
                    idempotency_key=str(uuid4()),
                )
            raw = await asyncio.to_thread(
                self._upstream(self.settings.email_endpoint, self.settings.email_token_env).post_json,
                {"subject": subject, "body": body},
                idempotency_key=str(uuid4()),
            )
            return write_result(raw, operation="email")
        except UpstreamError as exc:
            _raise_tool_error(exc)

def build_server(
    settings: MCPSettings | None = None,
    *,
    environ: dict[str, str] | None = None,
) -> tuple[MCPServer, Starlette]:
    resolved = settings or MCPSettings.from_env(environ)
    service = AgentSyncMCP(resolved, environ=environ)
    mcp = MCPServer(
        "AgentSync Tools",
        title="AgentSync external capabilities",
        description="Controlled tools for research, pricing, inventory and owner notifications.",
        instructions="The caller must apply its own user policy and approval flow before invoking sensitive tools.",
        version="0.1.0",
    )

    @mcp.tool(
        name="web.search",
        title="Search public web sources",
        annotations=ToolAnnotations(
            title="Search public web sources",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
        structured_output=True,
    )
    async def web_search(
        query: Annotated[str, Field(min_length=1, max_length=300)],
    ) -> dict[str, Any]:
        """Search configured public sources and return bounded result snippets."""

        return await service.web_search(query)

    @mcp.tool(
        name="market.reference_prices",
        title="Look up reference prices",
        annotations=ToolAnnotations(
            title="Look up reference prices",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
        structured_output=True,
    )
    async def market_reference_prices(
        item: Annotated[str, Field(min_length=1, max_length=160)],
        region: Annotated[str, Field(max_length=120)] = "",
        currency: Annotated[str, Field(min_length=3, max_length=3)] = "USD",
    ) -> dict[str, Any]:
        """Compare current reference prices without changing an objective."""

        return await service.market_reference_prices(item, region, currency.upper())

    @mcp.tool(
        name="email.send_notification",
        title="Send owner notification",
        annotations=ToolAnnotations(
            title="Send owner notification",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        structured_output=True,
    )
    async def email_send_notification(
        subject: Annotated[str, Field(min_length=1, max_length=160)],
        body: Annotated[str, Field(min_length=1, max_length=2_000)],
    ) -> dict[str, Any]:
        """Send a notification to the owner through the configured provider."""

        return await service.email_send_notification(subject, body)

    async def health(_: Request) -> JSONResponse:
        return JSONResponse(
            {
                "service": "agentsync-mcp",
                "version": "0.1.0",
                "transport": "streamable-http",
                "configured_providers": resolved.configured_providers(),
                "tools": [
                    "web.search",
                    "market.reference_prices",
                    "email.send_notification",
                ],
            }
        )

    security = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            allowed_hosts=list(resolved.allowed_hosts),
            allowed_origins=list(resolved.allowed_origins),
        ),
        host=resolved.host,
    )
    # Keep the SDK app as the root ASGI application so its lifespan initializes
    # the Streamable HTTP task group (wrapping it in a Mount would lose that
    # lifecycle in Starlette's test/deployment runners).
    security.routes.insert(0, Route("/health", health))
    app = security
    app.add_middleware(
        BearerTokenMiddleware,
        token_env=resolved.auth_token_env,
        environ=environ,
    )
    return mcp, app


mcp, app = build_server()


if __name__ == "__main__":  # pragma: no cover - exercised by uvicorn in deployment
    import uvicorn

    settings = MCPSettings.from_env()
    uvicorn.run(app, host=settings.host, port=settings.port)
