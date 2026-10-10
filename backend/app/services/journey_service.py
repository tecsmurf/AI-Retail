"""Journey reconstruction and analysis.

A journey is the ordered event sequence of one anonymous track on one camera
in one processed video. There is no cross-camera re-identification, so a
journey only covers what that camera saw; ``observed_entry``/``observed_exit``
say whether the store entry/exit was actually observed.

Journey types (business-rule classification, not model output):
* ``bounce``: ENTRY then EXIT within 60 s with no zone visit
* ``billing_visit``: visited a QUEUE or BILLING zone
* ``browse``: visited at least one other zone
* ``entry_only`` / ``exit_only``: only a line crossing was observed
* ``other``: anything else
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from statistics import mean
from typing import Dict, List, Optional, Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.event import CustomerJourney, Event, JourneyEvent
from app.services.timerange import TimeRange

BOUNCE_SECONDS = 60.0


def classify(zones: List[str], zone_types: List[str], entered: bool, exited: bool, duration: Optional[float]) -> str:
    if any(t in ("QUEUE", "BILLING") for t in zone_types):
        return "billing_visit"
    if zones:
        return "browse"
    if entered and exited and duration is not None and duration <= BOUNCE_SECONDS:
        return "bounce"
    if entered and not exited:
        return "entry_only"
    if exited and not entered:
        return "exit_only"
    return "other"


def build_journeys(store_id: uuid.UUID, job_id: Optional[uuid.UUID], events: Sequence[Event], source: str) -> List[CustomerJourney]:
    by_track: Dict[str, List[Event]] = defaultdict(list)
    for e in events:
        by_track[e.customer_id].append(e)
    journeys = []
    for customer_id, evs in by_track.items():
        evs.sort(key=lambda e: (e.timestamp, e.event_type))
        zones: List[str] = []
        zone_types: List[str] = []
        total_dwell = 0.0
        for e in evs:
            if e.event_type in ("ZONE_ENTER", "QUEUE_ENTER") and e.zone_name:
                zones.append(e.zone_name)
                zone_types.append(e.zone_type or "")
            if e.event_type == "ZONE_EXIT" and e.dwell_seconds:
                total_dwell += float(e.dwell_seconds)
            if e.event_type == "QUEUE_EXIT" and e.queue_wait_seconds:
                total_dwell += float(e.queue_wait_seconds)
        entered = any(e.event_type == "ENTRY" for e in evs)
        exited = any(e.event_type == "EXIT" for e in evs)
        start, end = evs[0].timestamp, evs[-1].timestamp
        duration = (end - start).total_seconds()
        j = CustomerJourney(
            store_id=store_id,
            job_id=job_id,
            customer_id=customer_id,
            camera_id=evs[0].camera_id,
            source=source,
            entry_time=start,
            exit_time=end,
            duration_seconds=round(duration, 2),
            zones_visited=zones,
            zone_count=len(set(zones)),
            total_dwell_seconds=round(total_dwell, 2) if total_dwell else None,
            visited_billing=any(t in ("QUEUE", "BILLING") for t in zone_types),
            made_purchase=False,
            observed_entry=entered,
            observed_exit=exited,
            journey_type=classify(zones, zone_types, entered, exited, duration),
        )
        for seq, e in enumerate(evs, 1):
            j.journey_events.append(
                JourneyEvent(
                    sequence=seq,
                    event_type=e.event_type,
                    zone_name=e.zone_name,
                    timestamp=e.timestamp,
                    dwell_seconds=e.dwell_seconds if e.dwell_seconds is not None else e.queue_wait_seconds,
                )
            )
        journeys.append(j)
    return journeys


async def rebuild_for_job(db: AsyncSession, store_id: uuid.UUID, job_id: uuid.UUID) -> int:
    await db.execute(delete(CustomerJourney).where(CustomerJourney.job_id == job_id))
    events = (await db.execute(select(Event).where(Event.job_id == job_id))).scalars().all()
    journeys = build_journeys(store_id, job_id, events, "cv")
    db.add_all(journeys)
    await db.flush()
    return len(journeys)


async def list_journeys(
    db: AsyncSession,
    store_id: uuid.UUID,
    tr: TimeRange,
    sources: Sequence[str],
    journey_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict:
    q = select(CustomerJourney).where(
        CustomerJourney.store_id == store_id,
        CustomerJourney.entry_time >= tr.start_utc,
        CustomerJourney.entry_time < tr.end_utc,
        CustomerJourney.source.in_(list(sources)),
    )
    if journey_type:
        q = q.where(CustomerJourney.journey_type == journey_type)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    rows = await db.execute(
        q.options(selectinload(CustomerJourney.journey_events))
        .order_by(CustomerJourney.entry_time.desc())
        .limit(limit)
        .offset(offset)
    )
    return {"total": total, "limit": limit, "offset": offset, "items": list(rows.scalars().all())}


async def journey_analytics(db: AsyncSession, store_id: uuid.UUID, tr: TimeRange, sources: Sequence[str], top: int = 10) -> Dict:
    rows = (
        await db.execute(
            select(CustomerJourney).where(
                CustomerJourney.store_id == store_id,
                CustomerJourney.entry_time >= tr.start_utc,
                CustomerJourney.entry_time < tr.end_utc,
                CustomerJourney.source.in_(list(sources)),
            )
        )
    ).scalars().all()
    types = Counter(j.journey_type for j in rows)
    durations = [j.duration_seconds for j in rows if j.duration_seconds is not None]
    paths: Counter = Counter()
    path_durations: Dict[tuple, List[float]] = defaultdict(list)
    for j in rows:
        if not j.zones_visited:
            continue
        # Collapse consecutive repeats (A, A, B -> A, B).
        path: List[str] = []
        for z in j.zones_visited:
            if not path or path[-1] != z:
                path.append(z)
        key = tuple(path)
        paths[key] += 1
        if j.duration_seconds is not None:
            path_durations[key].append(j.duration_seconds)
    return {
        "total_journeys": len(rows),
        "by_type": dict(types),
        "with_observed_entry": sum(1 for j in rows if j.observed_entry),
        "with_observed_exit": sum(1 for j in rows if j.observed_exit),
        "avg_duration_seconds": round(mean(durations), 1) if durations else None,
        "avg_zones_visited": round(mean(j.zone_count for j in rows), 2) if rows else None,
        "top_paths": [
            {
                "path": list(p),
                "count": c,
                "avg_duration_seconds": round(mean(path_durations[p]), 1) if path_durations[p] else None,
            }
            for p, c in paths.most_common(top)
        ],
        "scope_note": "Journeys are per camera: tracks are not linked across cameras.",
    }
