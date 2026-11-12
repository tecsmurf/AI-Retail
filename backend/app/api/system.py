"""Health, readiness and operational status.

``/health/live``  process is up (no dependencies checked).
``/health/ready`` database reachable, schema at the Alembic head, storage usable.
``/api/system/status`` (signed in) workers, queue and non-secret configuration.
``/api/system/metrics`` (admin) in-process request counters and latency.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import defaultdict
from datetime import timedelta
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import Scope, get_scope, require_org_admin, scoped_store_ids
from app.config import settings
from app.database import engine, get_db, utcnow
from app.models.jobs import ProcessingJob, WorkerHeartbeat
from app.models.org import DEFAULT_ORG_ID
from app.services import job_service
from app.storage import get_storage

router = APIRouter(tags=["System"])
STARTED = time.time()


class RequestMetrics:
    """Per-route counters kept in memory (reset on restart, per replica)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.counts: Dict[str, int] = defaultdict(int)
        self.errors: Dict[str, int] = defaultdict(int)
        self.latency_ms: Dict[str, float] = defaultdict(float)
        self.max_ms: Dict[str, float] = defaultdict(float)

    def observe(self, route: str, status: int, ms: float) -> None:
        with self._lock:
            self.counts[route] += 1
            self.latency_ms[route] += ms
            self.max_ms[route] = max(self.max_ms[route], ms)
            if status >= 500:
                self.errors[route] += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                route: {
                    "requests": n,
                    "server_errors": self.errors.get(route, 0),
                    "avg_ms": round(self.latency_ms[route] / n, 1),
                    "max_ms": round(self.max_ms[route], 1),
                }
                for route, n in sorted(self.counts.items())
            }


request_metrics = RequestMetrics()


async def _check_database() -> dict:
    from alembic.runtime.migration import MigrationContext

    from app.migrate import head_revision

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            current = await conn.run_sync(lambda c: MigrationContext.configure(c).get_current_revision())
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        return {"ok": False, "error": type(exc).__name__}
    head = head_revision()
    if settings.db_auto_create:
        return {"ok": True, "schema": "auto-created (DB_AUTO_CREATE)", "revision": current}
    return {"ok": current == head, "revision": current, "expected": head,
            **({} if current == head else {"error": "Database schema is not at the latest migration"})}


def _check_storage() -> dict:
    try:
        storage = get_storage()
        storage.check()
        return {"ok": True, "backend": storage.name}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "backend": settings.storage_backend, "error": type(exc).__name__}


@router.get("/health/live")
async def live():
    return {"status": "ok"}


@router.get("/health/ready")
async def ready():
    db, storage = await asyncio.gather(_check_database(), asyncio.to_thread(_check_storage))
    ok = db["ok"] and storage["ok"]
    body = {"status": "ready" if ok else "not_ready", "checks": {"database": db, "storage": storage},
            "version": settings.app_version}
    return JSONResponse(body, status_code=200 if ok else 503)


@router.get("/health")
async def health():
    """Alias of /health/ready (kept for existing monitors)."""
    return await ready()


@router.get("/api/system/status")
async def system_status(scope: Scope = Depends(get_scope), db: AsyncSession = Depends(get_db)):
    """Workers are shared by every organisation; job ids and queue counts are
    limited to the stores the caller may see."""
    now = utcnow()
    store_ids = await scoped_store_ids(db, scope)
    busy = [w_id for (w_id,) in (await db.execute(
        select(WorkerHeartbeat.current_job_id).where(WorkerHeartbeat.current_job_id.is_not(None))
    )).all()]
    own_jobs = set()
    if busy and store_ids:
        own_jobs = {j for (j,) in (await db.execute(
            select(ProcessingJob.id).where(ProcessingJob.id.in_(busy), ProcessingJob.store_id.in_(store_ids))
        )).all()}
    stale = timedelta(seconds=max(settings.worker_heartbeat_seconds * 3, 60))
    workers = (await db.execute(select(WorkerHeartbeat).order_by(WorkerHeartbeat.last_seen_at.desc()))).scalars().all()
    return {
        "api": {"version": settings.app_version, "env": settings.app_env, "uptime_seconds": round(time.time() - STARTED)},
        "workers": [
            {
                "worker_id": w.worker_id, "hostname": w.hostname,
                "online": now - w.last_seen_at <= stale,
                "last_seen_at": w.last_seen_at.isoformat() + "Z",
                "last_seen_seconds_ago": round((now - w.last_seen_at).total_seconds()),
                "busy": w.current_job_id is not None,
                "current_job_id": str(w.current_job_id) if w.current_job_id in own_jobs else None,
                "model_loaded": w.model_loaded, "model_error": w.model_error, "device": w.device,
            }
            for w in workers[:20]
        ],
        "queue": await job_service.queue_stats(db, store_ids),
        "config": {
            "storage_backend": settings.storage_backend,
            "database": "postgresql" if settings.database_url.startswith("postgres") else "sqlite",
            "yolo_model": settings.yolo_model,
            "analysis_fps": settings.analysis_fps,
            "max_upload_mb": settings.max_upload_bytes // (1024 * 1024),
            "video_retention_days": settings.video_retention_days,
            "audit_ip_retention_days": settings.audit_ip_retention_days,
            "session_ttl_hours": settings.session_ttl_hours,
            "job_max_attempts": settings.job_max_attempts,
        },
    }


@router.get("/api/system/metrics")
async def system_metrics(scope: Scope = Depends(require_org_admin)):
    """Request counters for the whole deployment: operator (default organisation) admins only."""
    if scope.org_id != DEFAULT_ORG_ID:
        raise HTTPException(403, "Only the deployment's operator can see request metrics")
    return {"since_seconds": round(time.time() - STARTED), "routes": request_metrics.snapshot()}
