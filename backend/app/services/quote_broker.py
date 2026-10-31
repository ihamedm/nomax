"""Redis-backed wake-up queue for quote dispatch.

Redis Streams provide low-latency wake-ups, while `quote_requests.next_dispatch_at`
is the durable schedule. If Redis is unavailable or a message is lost, the
worker reconciles due quotes directly from Postgres. That split is intentional:
the broker is an accelerator, never the source of truth.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from app.core.redis import get_redis

logger = logging.getLogger("nomax.quote_broker")

STREAM_KEY = "nomax:quote:dispatch"
DELAYED_KEY = "nomax:quote:dispatch:delayed"
GROUP = "nomax-quote-workers"
CONSUMER = f"{os.getenv('HOSTNAME', 'local')}-{os.getpid()}"


async def schedule_retry(quote_id: uuid.UUID, run_at: datetime) -> None:
    """Put a quote on the delayed queue. Best-effort by design."""
    client = await get_redis()
    timestamp = run_at.astimezone(timezone.utc).timestamp()
    await client.zadd(DELAYED_KEY, {str(quote_id): timestamp})


async def clear_retry(quote_id: uuid.UUID) -> None:
    client = await get_redis()
    await client.zrem(DELAYED_KEY, str(quote_id))


async def publish_due(limit: int = 100) -> int:
    """Move due delayed messages onto the stream."""
    client = await get_redis()
    now_ts = datetime.now(timezone.utc).timestamp()
    ids = await client.zrangebyscore(
        DELAYED_KEY, "-inf", now_ts, start=0, num=limit
    )
    moved = 0
    for raw_id in ids:
        # Remove first so two workers cannot both enqueue the same wake-up.
        removed = await client.zrem(DELAYED_KEY, raw_id)
        if not removed:
            continue
        await client.xadd(
            STREAM_KEY,
            {"quote_id": raw_id, "reason": "retry"},
            maxlen=5000,
            approximate=True,
        )
        moved += 1
    return moved


async def _ensure_group(client) -> None:
    try:
        await client.xgroup_create(STREAM_KEY, GROUP, id="0", mkstream=True)
    except Exception as exc:  # noqa: BLE001 - BUSYGROUP or fake clients
        if "BUSYGROUP" not in str(exc):
            raise


async def read_jobs(count: int = 20, block_ms: int = 500) -> list[tuple[str, dict]]:
    client = await get_redis()
    await _ensure_group(client)
    response = await client.xreadgroup(
        GROUP,
        CONSUMER,
        {STREAM_KEY: ">"},
        count=count,
        block=block_ms,
    )
    if not response:
        return []
    jobs: list[tuple[str, dict]] = []
    for _, messages in response:
        for message_id, fields in messages:
            jobs.append((message_id, dict(fields)))
    return jobs


async def ack(message_id: str) -> None:
    client = await get_redis()
    await client.xack(STREAM_KEY, GROUP, message_id)
