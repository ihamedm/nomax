"""Quote dispatch worker.

Run with `python -m app.worker`.

Two independent wake-up paths are intentional:

1. Redis Streams deliver due quote ids immediately (message broker).
2. Every loop also scans `quote_requests.next_dispatch_at`, so a lost Redis
   message, restart or Redis outage cannot strand an active request.

The worker also expires stale quotes and drains the legacy `scheduled_jobs`
outbox used by other phases.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa

from app.db.session import AsyncSessionLocal
from app.models.quote import QuoteRequest
from app.services import quote_broker
from app.services.backup_scheduler import run_backup_scheduler
from app.services.outbox import claim_due
from app.services.quote_dispatcher import retry_due_quote
from app.services.quote_service import ACTIVE, expire_stale_quotes

logger = logging.getLogger("nomax.worker")

SCAN_INTERVAL_SECONDS = 5


async def _process_quote_ids(
    session, quote_ids: list[uuid.UUID] | None = None, now: datetime | None = None
) -> int:
    now = now or datetime.now(timezone.utc)
    stmt = sa.select(QuoteRequest.id).where(
        QuoteRequest.status == ACTIVE,
        QuoteRequest.next_dispatch_at.is_not(None),
        QuoteRequest.next_dispatch_at <= now,
    )
    if quote_ids:
        stmt = stmt.where(QuoteRequest.id.in_(quote_ids))
    # Lock ids only. Postgres cannot apply FOR UPDATE to the eager-loaded
    # customer/category outer joins; locking the request ids first gives the
    # same one-worker guarantee without that limitation.
    stmt = stmt.order_by(QuoteRequest.next_dispatch_at).limit(100).with_for_update(
        skip_locked=True
    )
    locked_ids = list((await session.execute(stmt)).scalars().all())
    if not locked_ids:
        await session.rollback()
        return 0
    quotes = list(
        (
            await session.execute(
                sa.select(QuoteRequest).where(QuoteRequest.id.in_(locked_ids))
            )
        ).scalars().all()
    )
    processed = 0
    for quote in quotes:
        try:
            async with session.begin_nested():
                await retry_due_quote(session, quote, now)
                processed += 1
        except Exception:  # noqa: BLE001 - one bad quote must not stop the batch
            logger.exception("quote dispatch failed for %s", quote.id)
    await session.commit()

    # Publish the next wake-up after commit. The DB scan remains the fallback if
    # this best-effort Redis write fails.
    for quote in quotes:
        try:
            if quote.next_dispatch_at is not None:
                await quote_broker.schedule_retry(quote.id, quote.next_dispatch_at)
            else:
                await quote_broker.clear_retry(quote.id)
        except Exception:  # noqa: BLE001
            logger.warning("could not schedule redis wake-up for %s", quote.id)
    return processed


async def _sweep_scheduled_jobs(session) -> int:
    jobs = await claim_due(session)
    for job in jobs:
        logger.info("job %s %s", job.type, job.id)
        job.status = "done"
        job.attempts += 1
    await session.flush()
    return len(jobs)


async def sweep_once(now: datetime | None = None) -> int:
    """Process due quotes once (used by tests and the worker loop)."""
    async with AsyncSessionLocal() as session:
        await expire_stale_quotes(session, now)
        await session.commit()
        return await _process_quote_ids(session, now=now)


async def _run_from_broker(job_ids: list[str]) -> int:
    parsed: list[uuid.UUID] = []
    for raw in job_ids:
        try:
            parsed.append(uuid.UUID(str(raw)))
        except (ValueError, TypeError):
            continue
    if not parsed:
        return 0
    async with AsyncSessionLocal() as session:
        return await _process_quote_ids(session, parsed)


async def main() -> None:
    logger.info("quote worker started")
    # The daily database dump runs in this long-lived process; the marker file
    # in the backups volume makes it safe across container restarts.
    asyncio.create_task(run_backup_scheduler(), name="daily-database-backup")
    while True:
        try:
            moved = await quote_broker.publish_due()
            if moved:
                logger.info("moved %s delayed quote jobs to the stream", moved)
            jobs = await quote_broker.read_jobs(block_ms=500)
            for message_id, fields in jobs:
                try:
                    await _run_from_broker([fields.get("quote_id", "")])
                finally:
                    await quote_broker.ack(message_id)
        except Exception:  # noqa: BLE001 - Redis may be restarting
            logger.warning("redis quote queue unavailable; relying on DB scan", exc_info=True)

        try:
            async with AsyncSessionLocal() as session:
                await expire_stale_quotes(session)
                await _sweep_scheduled_jobs(session)
                await session.commit()
            await sweep_once()
        except Exception:  # noqa: BLE001
            logger.exception("quote dispatch sweep failed")

        await asyncio.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
