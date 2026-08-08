import os

import pytest
import pytest_asyncio
from redis.exceptions import ResponseError

from transport.models import TransportEnvelopeV1
from transport.redis_bus import RedisStreamsEventBus


def envelope(event_id: str = "evt_redis") -> TransportEnvelopeV1:
    return TransportEnvelopeV1.model_validate(
        {
            "event_id": event_id,
            "event_type": "message.published",
            "event_time": "2026-08-08T12:00:00Z",
            "environment": "test",
            "channel": "channel_1",
            "message": {"id": "message_1", "text": "hello", "author_id": "user_1", "seq": 1},
            "retracted": False,
        }
    )


@pytest_asyncio.fixture
async def bus():
    redis = pytest.importorskip("redis.asyncio").from_url(os.getenv("REDIS_URL", "redis://localhost:6379/15"), decode_responses=True)
    try:
        await redis.ping()
    except Exception as exc:
        await redis.aclose()
        pytest.skip(f"disposable Redis is unavailable: {exc}")
    await redis.flushdb()
    yield RedisStreamsEventBus(redis, stream="test:events", dedupe="test:ids", failures="test:failures")
    await redis.flushdb()
    await redis.aclose()


@pytest.mark.asyncio
async def test_duplicate_acceptance_writes_one_record_and_atomic_failure_writes_none(bus) -> None:
    item = envelope()
    await bus.accept(item)
    await bus.accept(item)
    assert await bus.record_counts() == (1, 1)
    await bus.redis.delete(bus.stream)
    await bus.redis.set(bus.stream, "wrong-type")
    with pytest.raises(ResponseError):
        await bus.accept(envelope("evt_atomic"))
    assert await bus.redis.get(bus.stream) == "wrong-type"
    assert await bus.redis.hexists(bus.dedupe, "evt_atomic") == 0


@pytest.mark.asyncio
async def test_restart_reclaims_pending_and_only_success_acknowledges(bus) -> None:
    await bus.accept(envelope())
    first = await bus.receive("first", lease_ms=0)
    assert first is not None
    restarted = RedisStreamsEventBus(bus.redis, stream=bus.stream, dedupe=bus.dedupe, failures=bus.failures)
    reclaimed = await restarted.receive("second", lease_ms=0)
    assert reclaimed is not None and reclaimed.message_id == first.message_id
    await restarted.fail(reclaimed, "processor_error")
    assert (await bus.redis.xpending(bus.stream, bus.group))["pending"] == 1
    retry = await restarted.receive("third", lease_ms=0)
    assert retry is not None
    await restarted.ack(retry)
    assert (await bus.redis.xpending(bus.stream, bus.group))["pending"] == 0
    assert await bus.redis.xlen(bus.failures) == 1
