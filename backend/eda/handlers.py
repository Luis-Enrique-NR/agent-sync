"""Domain handlers that process transport deliveries.

Each handler bridges the ``TransportEnvelopeV1`` received from the
event bus into persistence CRUD and AI engine calls.  Handlers are
intentionally side-effect-free in their import surface — they depend
only on domain models, persistence, and the engine composition root.
"""

from __future__ import annotations

import logging

from transport.bus import EventDelivery

logger = logging.getLogger(__name__)


async def handle_message_published(delivery: EventDelivery) -> None:
    """Process a ``message.published`` delivery from Portal.

    TODO: extract session correlation, route to ``engine.run_until_pause``,
    persist ``EngineResult`` via repository, emit follow-up events.
    """
    envelope = delivery.envelope
    logger.info(
        "message.published  event=%s channel=%s seq=%s",
        envelope.event_id,
        envelope.channel,
        envelope.message.seq if envelope.message else None,
    )


async def handle_message_retracted(delivery: EventDelivery) -> None:
    """Process a ``message.retracted`` delivery from Portal."""
    envelope = delivery.envelope
    logger.info(
        "message.retracted  event=%s channel=%s",
        envelope.event_id,
        envelope.channel,
    )
