"""AgentSync backend entry point.

Loads environment, wires transport + AI dependencies, starts the FastAPI
application with an EDA consumer running in the same event loop.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os

import redis.asyncio as redis
import uvicorn
from dotenv import load_dotenv

from ai.service import build_engine_from_env
from api.app import create_app
from api.v1.endpoints.sse import SessionQueueManager
from eda.consumer import consume_forever
from eda.handlers import NegotiationHandler
from transport.config import TransportSettings
from transport.portal import HttpPortalClient
from transport.redis_bus import RedisStreamsEventBus
from transport.secret_fetcher import WebhookSecretFetcher

logger = logging.getLogger(__name__)
_CONSUMER_NAME = "eda-consumer"


def _build_app() -> "FastAPI":  # noqa: F821
    """Wire all dependencies and return the application."""

    load_dotenv(override=False)

    settings = TransportSettings.from_env()

    secret_key = os.getenv("PORTAL_SECRET_KEY")
    if not secret_key:
        raise RuntimeError(
            "PORTAL_SECRET_KEY is required — set it in .env or the environment"
        )

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_conn = redis.from_url(redis_url)

    # Lazy webhook secret fetcher (implements WebhookSecretProvider)
    secret_provider = WebhookSecretFetcher(secret_key=secret_key)

    # Durable event bus backed by Redis Streams
    bus = RedisStreamsEventBus(redis_conn)

    # AI negotiation engine (reads AI_* env vars from .env)
    engine = build_engine_from_env()

    # Portal mutation client (uses the same secret key as Bearer token)
    portal_client = HttpPortalClient(secret=secret_key)

    # ── SSE broadcaster shared between handler and API ──────────────
    sse_broadcaster = SessionQueueManager()

    # Handler bridges bus deliveries → engine + Portal + SSE
    handler = NegotiationHandler(
        engine=engine, portal=portal_client, sse_broadcaster=sse_broadcaster,
    )

    # FastAPI application with injected transport deps
    app = create_app(
        settings=settings,
        secret_provider=secret_provider,
        bus=bus,
        sse_broadcaster=sse_broadcaster,
    )

    @contextlib.asynccontextmanager
    async def _lifespan(app: "FastAPI") -> "AsyncIterator[None]":  # noqa: F821
        task = asyncio.create_task(
            consume_forever(bus, _CONSUMER_NAME, handler)
        )
        logger.info("EDA consumer %r started", _CONSUMER_NAME)
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info("EDA consumer %r shut down gracefully", _CONSUMER_NAME)

    app.router.lifespan_context = _lifespan  # type: ignore[assignment]
    return app


app = _build_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
