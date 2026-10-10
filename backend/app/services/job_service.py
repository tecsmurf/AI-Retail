"""Durable job queue on top of the ``processing_jobs`` table.

Why a table and not Redis: job state must survive restarts anyway, Postgres
is already required, and one fewer service is cheaper and simpler. Claiming
is atomic on both PostgreSQL and SQLite via a conditional UPDATE
(``... WHERE id = :id AND status = 'queued'``) whose rowcount tells the
worker whether it won the race.

Lifecycle::

    queued --claim--> running --ok--> completed
       ^                 |  \\--permanent error / attempts exhausted--> failed
       |                 \\--retryable error or stale heartbeat--> queued (attempts+1)
       \\--retry (failed/cancelled, by a user)
    queued/running --cancel--> cancelled (running jobs stop at the next check)
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import List, Optional

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import utcnow
from app.models.anomaly import Alert
from app.models.jobs import (
    JOB_CANCELLED,
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_QUEUED,
    JOB_RUNNING,
    ProcessingJob,
)


class JobStateError(Exception):
    pass


async def claim_next(db: AsyncSession, worker_id: str) -> Optional[ProcessingJob]:
    """Atomically move the oldest queued job to running and return it."""
    candidates = (
        await db.execute(
            select(ProcessingJob.id)
            .where(ProcessingJob.status == JOB_QUEUED, ProcessingJob.cancel_requested.is_(False))
            .order_by(ProcessingJob.created_at)
            .limit(5)
        )
    ).scalars().all()
    now = utcnow()
    for job_id in candidates:
        res = await db.execute(
            update(ProcessingJob)
            .where(ProcessingJob.id == job_id, ProcessingJob.status == JOB_QUEUED)
            .values(
                status=JOB_RUNNING,
                locked_by=worker_id,
                heartbeat_at=now,
                started_at=now,
                attempts=ProcessingJob.attempts + 1,
                stage="starting",
                progress=0.0,
                error_code=None,
                error_message=None,
                error_retryable=None,
            )
            .execution_options(synchronize_session=False)
        )
        await db.commit()
        if res.rowcount == 1:
            return (await db.execute(select(ProcessingJob).where(ProcessingJob.id == job_id))).scalar_one()
    return None


async def heartbeat(db: AsyncSession, job_id: uuid.UUID, worker_id: str, progress: float, stage: str) -> bool:
    """Update progress. Returns False if the job was cancelled or taken over."""
    res = await db.execute(
        update(ProcessingJob)
        .where(ProcessingJob.id == job_id, ProcessingJob.locked_by == worker_id, ProcessingJob.status == JOB_RUNNING)
        .values(heartbeat_at=utcnow(), progress=round(progress, 4), stage=stage)
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    if res.rowcount != 1:
        return False
    cancel = (
        await db.execute(select(ProcessingJob.cancel_requested).where(ProcessingJob.id == job_id))
    ).scalar_one()
    return not cancel


async def requeue_stale(db: AsyncSession) -> List[uuid.UUID]:
    """Recover jobs whose worker died (no heartbeat for JOB_STALE_AFTER_SECONDS)."""
    cutoff = utcnow() - timedelta(seconds=settings.job_stale_after_seconds)
    stale = (
        await db.execute(
            select(ProcessingJob).where(
                ProcessingJob.status == JOB_RUNNING,
                or_(ProcessingJob.heartbeat_at.is_(None), ProcessingJob.heartbeat_at < cutoff),
            )
        )
    ).scalars().all()
    recovered = []
    for job in stale:
        if job.cancel_requested:
            job.status = JOB_CANCELLED
            job.finished_at = utcnow()
        elif job.attempts >= job.max_attempts:
            job.status = JOB_FAILED
            job.finished_at = utcnow()
            job.error_code = "WORKER_LOST"
            job.error_message = f"Worker stopped responding during attempt {job.attempts}; no attempts left."
            job.error_retryable = True
            _failure_alert(db, job)
        else:
            job.status = JOB_QUEUED
            job.stage = "requeued"
            job.error_code = "WORKER_LOST"
            job.error_message = f"Worker {job.locked_by} stopped responding; re-queued."
        job.locked_by = None
        recovered.append(job.id)
    await db.commit()
    return recovered


def _failure_alert(db: AsyncSession, job: ProcessingJob) -> None:
    db.add(
        Alert(
            store_id=job.store_id,
            alert_type="PROCESSING_FAILED",
            title="Video processing failed",
            message=f"Job {job.id}: {job.error_code}: {job.error_message}",
            severity="high",
        )
    )


async def mark_failed(
    db: AsyncSession, job: ProcessingJob, code: str, message: str, retryable: bool
) -> str:
    """Record a failure; re-queue if retryable and attempts remain."""
    job.error_code = code
    job.error_message = message[:2000]
    job.error_retryable = retryable
    job.locked_by = None
    if retryable and job.attempts < job.max_attempts and not job.cancel_requested:
        job.status = JOB_QUEUED
        job.stage = "retry_wait"
    else:
        job.status = JOB_FAILED
        job.finished_at = utcnow()
        _failure_alert(db, job)
    await db.commit()
    return job.status


async def request_cancel(db: AsyncSession, job: ProcessingJob) -> ProcessingJob:
    if job.status == JOB_QUEUED:
        job.status = JOB_CANCELLED
        job.cancel_requested = True
        job.finished_at = utcnow()
    elif job.status == JOB_RUNNING:
        job.cancel_requested = True
    else:
        raise JobStateError(f"Job is already {job.status}")
    await db.flush()
    return job


async def retry(db: AsyncSession, job: ProcessingJob) -> ProcessingJob:
    if job.status not in (JOB_FAILED, JOB_CANCELLED):
        raise JobStateError(f"Only failed or cancelled jobs can be retried (job is {job.status})")
    job.status = JOB_QUEUED
    job.cancel_requested = False
    job.attempts = 0
    job.progress = 0.0
    job.stage = "queued"
    job.finished_at = None
    job.error_code = None
    job.error_message = None
    job.error_retryable = None
    await db.flush()
    return job


async def queue_stats(db: AsyncSession) -> dict:
    rows = await db.execute(select(ProcessingJob.status, func.count()).group_by(ProcessingJob.status))
    counts = {s: n for s, n in rows.all()}
    oldest = (
        await db.execute(select(func.min(ProcessingJob.created_at)).where(ProcessingJob.status == JOB_QUEUED))
    ).scalar()
    since = utcnow() - timedelta(hours=24)
    recent = await db.execute(
        select(ProcessingJob.status, func.count())
        .where(ProcessingJob.finished_at >= since)
        .group_by(ProcessingJob.status)
    )
    return {
        "by_status": counts,
        "queue_depth": counts.get(JOB_QUEUED, 0),
        "running": counts.get(JOB_RUNNING, 0),
        "oldest_queued_age_seconds": round((utcnow() - oldest).total_seconds()) if oldest else None,
        "finished_last_24h": {s: n for s, n in recent.all()},
    }


def active_job_filter():
    return and_(ProcessingJob.status.in_([JOB_QUEUED, JOB_RUNNING]))


__all__ = [
    "claim_next",
    "heartbeat",
    "requeue_stale",
    "mark_failed",
    "request_cancel",
    "retry",
    "queue_stats",
    "JobStateError",
    "JOB_COMPLETED",
]
