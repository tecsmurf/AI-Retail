"""Event ingestion and querying."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.event import Event
from app.models.store import Store
from app.models.user import User
from app.schemas.event import EventCreate, EventPage, IngestResult
from app.security import current_user, ingest_principal
from app.services.ingest import insert_events

router = APIRouter(prefix="/api/events", tags=["Events"])
MAX_BATCH = 1000


def content_key(e: EventCreate) -> str:
    raw = json.dumps(
        [e.store_code, e.event_type, e.customer_id, e.timestamp.isoformat(), e.camera_id, e.zone_name],
        separators=(",", ":"),
    )
    return "auto-" + hashlib.sha256(raw.encode()).hexdigest()[:40]


async def _ingest(db: AsyncSession, events: List[EventCreate]) -> IngestResult:
    codes = {e.store_code for e in events}
    stores = {
        s.store_code: s.id
        for s in (await db.execute(select(Store).where(Store.store_code.in_(codes)))).scalars().all()
    }
    rows = []
    errors = []
    seen = set()
    for i, e in enumerate(events):
        sid = stores.get(e.store_code)
        if sid is None:
            errors.append(f"item {i}: unknown store_code '{e.store_code}'")
            continue
        key = e.event_key or content_key(e)
        if (sid, key) in seen:
            continue
        seen.add((sid, key))
        rows.append({
            "store_id": sid, "event_type": e.event_type, "customer_id": e.customer_id,
            "camera_id": e.camera_id, "zone_id": e.zone_id, "zone_name": e.zone_name, "zone_type": e.zone_type,
            "timestamp": e.timestamp, "source": "api", "event_key": key, "confidence": e.confidence,
            "dwell_seconds": e.dwell_seconds, "queue_wait_seconds": e.queue_wait_seconds,
            "queue_abandoned": e.queue_abandoned, "is_staff": e.is_staff, "metadata_json": e.metadata_json,
        })
    inserted = await insert_events(db, rows)
    return IngestResult(received=len(events), inserted=inserted, duplicates=len(events) - len(errors) - inserted,
                        errors=errors)


@router.post("", response_model=IngestResult, status_code=201)
async def create_event(event: EventCreate, _: str = Depends(ingest_principal), db: AsyncSession = Depends(get_db)):
    """Ingest one event. Idempotent on (store, event_key)."""
    result = await _ingest(db, [event])
    if result.errors:
        raise HTTPException(422, result.errors[0])
    return result


@router.post("/batch", response_model=IngestResult, status_code=201)
async def create_batch(events: List[EventCreate], _: str = Depends(ingest_principal), db: AsyncSession = Depends(get_db)):
    if len(events) > MAX_BATCH:
        raise HTTPException(413, f"At most {MAX_BATCH} events per batch")
    return await _ingest(db, events)


@router.get("", response_model=EventPage)
async def list_events(
    store_id: uuid.UUID = Query(...),
    event_type: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    zone_name: Optional[str] = Query(None),
    job_id: Optional[uuid.UUID] = Query(None),
    source: Optional[str] = Query(None, description="cv, api, sample, demo, legacy_cv"),
    start_time: Optional[datetime] = Query(None, description="UTC (or with offset)"),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Event).where(Event.store_id == store_id)
    if event_type:
        q = q.where(Event.event_type == event_type.upper())
    if customer_id:
        q = q.where(Event.customer_id == customer_id)
    if zone_name:
        q = q.where(Event.zone_name == zone_name)
    if job_id:
        q = q.where(Event.job_id == job_id)
    if source:
        q = q.where(Event.source == source)
    for bound, op in ((start_time, ">="), (end_time, "<")):
        if bound is not None:
            if bound.tzinfo is not None:

                bound = bound.astimezone(UTC).replace(tzinfo=None)
            q = q.where(Event.timestamp >= bound) if op == ">=" else q.where(Event.timestamp < bound)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    rows = (await db.execute(q.order_by(Event.timestamp.desc(), Event.id).limit(limit).offset(offset))).scalars().all()
    return EventPage(total=total, limit=limit, offset=offset, items=list(rows))
