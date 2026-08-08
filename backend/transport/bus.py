"""Internal event bus protocol. Implementations live in sibling modules."""

from __future__ import annotations

from typing import Protocol

from transport.models import TransportEnvelopeV1


class DurableEventBus(Protocol):
    async def accept(self, envelope: TransportEnvelopeV1) -> None:
        """Persist a validated envelope for durable delivery."""
