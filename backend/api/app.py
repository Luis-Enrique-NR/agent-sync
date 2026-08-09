"""FastAPI composition root."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.portal_webhooks import build_portal_webhook_router
from api.v1.router import router as v1_router
from transport.bus import DurableEventBus
from transport.config import TransportSettings
from transport.portal import WebhookSecretProvider


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_app(
    settings: TransportSettings | None = None,
    secret_provider: WebhookSecretProvider | None = None,
    bus: DurableEventBus | None = None,
    clock: Callable[[], datetime] | None = None,
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
    app.include_router(
        build_portal_webhook_router(settings, secret_provider, bus, clock or _utc_now)
    )
    app.include_router(v1_router)
    return app
