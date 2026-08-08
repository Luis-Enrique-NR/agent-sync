"""Redis Streams implementation of the durable transport bus seam."""

from __future__ import annotations

from typing import Any

from redis.exceptions import ResponseError

from transport.bus import EventDelivery
from transport.models import TransportEnvelopeV1

_ACCEPT = """
local dedupe_type = redis.call('TYPE', KEYS[1]).ok
local stream_type = redis.call('TYPE', KEYS[2]).ok
if dedupe_type ~= 'none' and dedupe_type ~= 'hash' then return redis.error_reply('dedupe key has incompatible type') end
if stream_type ~= 'none' and stream_type ~= 'stream' then return redis.error_reply('stream key has incompatible type') end
if redis.call('HEXISTS', KEYS[1], ARGV[1]) == 1 then return {0, redis.call('HGET', KEYS[1], ARGV[1])} end
local id = redis.call('XADD', KEYS[2], '*', 'event_id', ARGV[1], 'payload', ARGV[2])
redis.call('HSET', KEYS[1], ARGV[1], id)
return {1, id}
"""


class RedisStreamsEventBus:
    """Hide Redis group setup, atomic acceptance, reclaim, and failure journaling."""

    group = "transport-workers"

    def __init__(self, redis: Any, *, stream: str = "transport:events", dedupe: str = "transport:event-ids", failures: str = "transport:failures") -> None:
        self.redis = redis
        self.stream = stream
        self.dedupe = dedupe
        self.failures = failures

    async def accept(self, envelope: TransportEnvelopeV1) -> None:
        await self.redis.eval(_ACCEPT, 2, self.dedupe, self.stream, envelope.event_id, envelope.model_dump_json())

    async def receive(self, consumer: str, lease_ms: int) -> EventDelivery | None:
        await self._ensure_group()
        claimed = await self.redis.xautoclaim(self.stream, self.group, consumer, lease_ms, "0-0", count=1)
        entries = claimed[1]
        if entries:
            return self._delivery(entries[0])
        fresh = await self.redis.xreadgroup(self.group, consumer, {self.stream: ">"}, count=1)
        return self._delivery(fresh[0][1][0]) if fresh else None

    async def ack(self, delivery: EventDelivery) -> None:
        await self.redis.xack(self.stream, self.group, delivery.message_id)

    async def fail(self, delivery: EventDelivery, code: str) -> None:
        await self.redis.xadd(self.failures, {"event_id": delivery.envelope.event_id, "message_id": delivery.message_id, "code": code}, maxlen=1000, approximate=True)

    async def record_counts(self) -> tuple[int, int]:
        return await self.redis.hlen(self.dedupe), await self.redis.xlen(self.stream)

    async def _ensure_group(self) -> None:
        try:
            await self.redis.xgroup_create(self.stream, self.group, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    @staticmethod
    def _delivery(entry: tuple[str, dict[str, str]]) -> EventDelivery:
        message_id, fields = entry
        return EventDelivery(message_id=message_id, envelope=TransportEnvelopeV1.model_validate_json(fields["payload"]))
