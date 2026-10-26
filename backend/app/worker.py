"""Minimal outbox sweeper.

Run with `python -m app.worker`. Claims due scheduled_jobs and marks them done.
Handlers are intentionally simple for Phase 5; quote dispatch/expiry jobs are
added as they appear (Phase 6 push work uses this queue).
"""
import asyncio
import logging

from app.db.session import AsyncSessionLocal
from app.services.outbox import claim_due

logger = logging.getLogger("nomax.worker")


async def sweep_once() -> int:
    async with AsyncSessionLocal() as session:
        jobs = await claim_due(session)
        for job in jobs:
            logger.info("job %s %s", job.type, job.id)
            job.status = "done"
            job.attempts += 1
        await session.commit()
        return len(jobs)


async def main() -> None:
    while True:
        await sweep_once()
        await asyncio.sleep(30)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
