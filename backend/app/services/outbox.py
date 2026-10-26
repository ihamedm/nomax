from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import ScheduledJob


async def enqueue(
    session: AsyncSession,
    *,
    job_type: str,
    payload: dict,
    run_at: datetime,
    idempotency_key: str,
) -> ScheduledJob:
    job = ScheduledJob(
        type=job_type,
        payload=payload,
        run_at=run_at,
        idempotency_key=idempotency_key,
    )
    session.add(job)
    await session.flush()
    return job


async def claim_due(session: AsyncSession, limit: int = 50) -> list[ScheduledJob]:
    now = datetime.now(timezone.utc)
    stmt = (
        sa.select(ScheduledJob)
        .where(ScheduledJob.status == "pending", ScheduledJob.run_at <= now)
        .order_by(ScheduledJob.run_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    jobs = (await session.execute(stmt)).scalars().all()
    for job in jobs:
        job.status = "locked"
        job.locked_at = now
    await session.flush()
    return jobs
