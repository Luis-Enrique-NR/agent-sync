"""Bridge: transport bus deliveries → AI engine + persistence.

Each delivery received from the ``DurableEventBus`` is dispatched to
the appropriate handler.  Handlers never import transport adapters
directly — they operate on domain models and persistence primitives.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from transport.bus import DurableEventBus, EventDelivery

logger = logging.getLogger(__name__)


class EventHandler(Protocol):
    async def handle(self, delivery: EventDelivery) -> None: ...


async def consume_forever(
    bus: DurableEventBus,
    consumer: str,
    handler: EventHandler,
    *,
    lease_ms: int = 30_000,
    poll_interval_seconds: float = 1.0,
) -> None:
    """Poll ``bus`` forever and invoke ``handler`` for each leased delivery.

    A graceful shutdown mechanism (signal handler) should cancel the
    running task from the caller side.
    """
    logger.info("consumer %r started (lease=%dms)", consumer, lease_ms)
    while True:
        try:
            delivery = await bus.receive(consumer, lease_ms=lease_ms)
        except Exception:
            logger.exception("bus.receive failed, retrying in %.1fs", poll_interval_seconds)
            await asyncio.sleep(poll_interval_seconds)
            continue

        if delivery is None:
            await asyncio.sleep(poll_interval_seconds)
            continue

        try:
            await handler.handle(delivery)
        except Exception:
            logger.exception("handler failed for delivery %s", delivery.message_id)
            try:
                await bus.fail(delivery, "HANDLER_ERROR")
            except Exception:
                logger.exception("bus.fail failed for %s", delivery.message_id)
        else:
            try:
                await bus.ack(delivery)
            except Exception:
                logger.exception("bus.ack failed for %s", delivery.message_id)
