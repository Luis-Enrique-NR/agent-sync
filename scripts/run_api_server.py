"""Local dev server for the Frontend REST API (no Redis required).

Composes the FastAPI app with an in-memory event bus that dispatches
agent.registered envelopes straight to the EDA NegotiationHandler, so the
full matchmaking cycle works end-to-end over HTTP.

Usage:
    python scripts/run_api_server.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

import uvicorn

from ai.domain.models import AgentTurn, TurnIntent
from ai.engine.graph import NegotiationEngine
from ai.providers.fake import ScriptedLLMProvider
from api.app import create_app
from eda.handlers import NegotiationHandler
from persistence.database import init_db
from transport.bus import EventDelivery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run_api_server")


class LocalSecret:
    async def get_secret(self) -> str | None:
        return "local-dev-secret"


class InMemoryBus:
    """Processes each accepted envelope through the handler immediately."""

    def __init__(self, handler: NegotiationHandler) -> None:
        self._handler = handler
        self._seq = 0

    async def accept(self, envelope: Any) -> None:
        self._seq += 1
        delivery = EventDelivery(message_id=f"local_{self._seq}", envelope=envelope)
        logger.info("dispatching event=%s channel=%s", envelope.event_type, envelope.channel)
        await self._handler.handle(delivery)

    async def receive(self, consumer: str, lease_ms: int) -> EventDelivery | None:
        return None

    async def ack(self, delivery: EventDelivery) -> None:
        pass

    async def fail(self, delivery: EventDelivery, code: str) -> None:
        logger.error("delivery failed code=%s", code)


def build_app() -> Any:
    init_db()
    turns = [AgentTurn(public_message="oferta de prueba", intent=TurnIntent.OFFER)] * 20
    engine = NegotiationEngine(ScriptedLLMProvider(turns))
    handler = NegotiationHandler(engine=engine, portal=None)
    bus = InMemoryBus(handler)
    app = create_app(secret_provider=LocalSecret(), bus=bus)
    app.state.bus = bus
    app.state.engine = engine
    return app


if __name__ == "__main__":
    app = build_app()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
