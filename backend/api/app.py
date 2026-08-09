"""FastAPI composition root."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.portal_webhooks import build_portal_webhook_router
from api.v1.router import router as v1_router
from transport.bus import DurableEventBus
from transport.config import TransportSettings
from transport.portal import (
    HttpPortalClient,
    PortalRejected,
    PortalUncertain,
    TokenResponse,
    WebhookSecretProvider,
)

if TYPE_CHECKING:
    from api.v1.endpoints.sse import SessionQueueManager


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_app(
    settings: TransportSettings | None = None,
    secret_provider: WebhookSecretProvider | None = None,
    bus: DurableEventBus | None = None,
    clock: Callable[[], datetime] | None = None,
    portal_secret: str | None = None,
    sse_broadcaster: SessionQueueManager | None = None,
) -> FastAPI:
    """Create the ASGI application with injected transport dependencies."""
    settings = settings or TransportSettings.from_env()
    if secret_provider is None or bus is None:
        raise ValueError("webhook dependencies must be injected")
    app = FastAPI(title="AgentSync API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.bus = bus
    app.state.portal_secret = portal_secret

    # Lazy-import to avoid circular deps at module level
    from api.v1.endpoints.sse import SessionQueueManager as _SQM

    app.state.sse_broadcaster = sse_broadcaster or _SQM()

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": "0.1.0"}

    if portal_secret is not None:
        @app.get("/api/portal-token")
        async def portal_token(userId: str = Query(default="")) -> JSONResponse:
            if not userId:
                return JSONResponse(
                    {"detail": "userId query param is required"},
                    status_code=400,
                )
            async with HttpPortalClient(portal_secret) as client:
                outcome = await client.mint_token(user_id=userId)

            if isinstance(outcome, TokenResponse):
                return JSONResponse(
                    {"token": outcome.token, "expiresAt": outcome.expires_at},
                    status_code=200,
                )
            if isinstance(outcome, PortalRejected):
                return JSONResponse(
                    {"detail": {"code": outcome.code, "reason": outcome.reason}},
                    status_code=502,
                )
            if isinstance(outcome, PortalUncertain):
                return JSONResponse(
                    {"detail": "Portal token API unreachable, retry later"},
                    status_code=504,
                )
            return JSONResponse(
                {"detail": "Unexpected response from Portal"},
                status_code=502,
            )

    app.include_router(
        build_portal_webhook_router(settings, secret_provider, bus, clock or _utc_now)
    )
    app.include_router(v1_router)
    return app
