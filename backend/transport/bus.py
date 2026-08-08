"""Internal event bus protocol. Implementations live in sibling modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from transport.models import TransportEnvelopeV1


@dataclass(frozen=True, slots=True)
class EventDelivery:
    """A leased stream entry that a consumer may acknowledge after success."""

    message_id: str
    envelope: TransportEnvelopeV1


class DurableEventBus(Protocol):
    async def accept(self, envelope: TransportEnvelopeV1) -> None:
        """Persist a validated envelope for durable delivery."""

    async def receive(self, consumer: str, lease_ms: int) -> EventDelivery | None:
        """Lease the next pending or new delivery for a named consumer."""

    async def ack(self, delivery: EventDelivery) -> None:
        """Acknowledge only a successfully completed delivery."""

    async def fail(self, delivery: EventDelivery, code: str) -> None:
        """Record bounded failure metadata while leaving the entry pending."""
