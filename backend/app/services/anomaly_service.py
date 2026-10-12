"""Transparent, configurable rule-based anomaly detection.

Rules run over persisted events / occupancy samples in a store-local date
range. Each anomaly records the metric, the threshold, and a dedupe key, so
re-running detection over the same range never creates duplicates.

Rules
* LONG_QUEUE_WAIT: >= ``min_long_waits`` queue waits longer than
  ``long_wait_seconds`` within one local hour.
* QUEUE_BUILDUP: queue length >= ``buildup_length`` for at least
  ``buildup_seconds`` of consecutive samples.
* TRAFFIC_DROP: an hour's entries are below ``drop_ratio`` x the baseline
  (mean of the same hour on previous days with data). Requires at least
  ``baseline_min_days`` days of history; otherwise reported as
  insufficient data instead of guessing.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from statistics import mean
from typing import Dict, List, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import utcnow
from app.models.anomaly import Alert, Anomaly
from app.models.event import Event
from app.models.jobs import OccupancySample
from app.models.store import Store
from app.services.timerange import TimeRange, hour_label, resolve_range, to_local


@dataclass
class Thresholds:
    long_wait_seconds: float = 300.0
    min_long_waits: int = 3
    buildup_length: int = 5
    buildup_seconds: float = 120.0
    drop_ratio: float = 0.5
    baseline_min_days: int = 7
    min_baseline_entries: float = 5.0


async def detect(db: AsyncSession, store: Store, tr: TimeRange, sources: Sequence[str], th: Thresholds | None = None) -> Dict:
    th = th or Thresholds()
    found: List[Dict] = []
    notes: List[str] = []

    # LONG_QUEUE_WAIT
    rows = (
        await db.execute(
            select(Event).where(
                Event.store_id == store.id,
                Event.event_type == "QUEUE_EXIT",
                Event.source.in_(list(sources)),
                Event.timestamp >= tr.start_utc,
                Event.timestamp < tr.end_utc,
            )
        )
    ).scalars().all()
    by_hour: Dict[str, List[Event]] = defaultdict(list)
    for e in rows:
        if (e.queue_wait_seconds or 0) > th.long_wait_seconds:
            local = to_local(e.timestamp, tr.tz).replace(minute=0, second=0, microsecond=0)
            by_hour[local.isoformat()].append(e)
    for hour, evs in by_hour.items():
        if len(evs) >= th.min_long_waits:
            avg = mean(float(e.queue_wait_seconds) for e in evs)
            found.append({
                "type": "LONG_QUEUE_WAIT", "severity": "high" if avg > 2 * th.long_wait_seconds else "medium",
                "zone_name": evs[0].zone_name, "detected_at": min(e.timestamp for e in evs),
                "title": "Long queue waits",
                "description": f"{len(evs)} shoppers waited more than {th.long_wait_seconds:.0f}s (avg {avg:.0f}s) in the hour starting {hour}.",
                "metric_value": avg, "threshold_value": th.long_wait_seconds, "dedupe_key": f"LONG_QUEUE_WAIT:{hour}",
            })

    # QUEUE_BUILDUP
    samples = (
        await db.execute(
            select(OccupancySample).where(
                OccupancySample.store_id == store.id,
                OccupancySample.zone_type == "QUEUE",
                OccupancySample.timestamp >= tr.start_utc,
                OccupancySample.timestamp < tr.end_utc,
            ).order_by(OccupancySample.zone_name, OccupancySample.timestamp)
        )
    ).scalars().all() if "cv" in sources else []
    run_start = None
    run_peak = 0
    prev = None
    for s in samples + [None]:
        breaks = s is None or prev is None or s.zone_name != prev.zone_name or (s.timestamp - prev.timestamp).total_seconds() > 30
        if run_start is not None and (breaks or s.count < th.buildup_length):
            duration = (prev.timestamp - run_start.timestamp).total_seconds()
            if duration >= th.buildup_seconds:
                found.append({
                    "type": "QUEUE_BUILDUP", "severity": "high" if run_peak >= 2 * th.buildup_length else "medium",
                    "zone_name": run_start.zone_name, "detected_at": run_start.timestamp,
                    "title": "Queue building up",
                    "description": f"{run_start.zone_name}: {th.buildup_length}+ people queued for {duration:.0f}s (peak {run_peak}).",
                    "metric_value": float(run_peak), "threshold_value": float(th.buildup_length),
                    "dedupe_key": f"QUEUE_BUILDUP:{run_start.zone_name}:{run_start.timestamp.isoformat()}",
                })
            run_start = None
            run_peak = 0
        if s is not None and s.count >= th.buildup_length:
            if run_start is None:
                run_start = s
            run_peak = max(run_peak, s.count)
        prev = s

    # TRAFFIC_DROP
    history = resolve_range(store.timezone, tr.start_date - timedelta(days=28), tr.end_date)
    entries = (
        await db.execute(
            select(Event.timestamp).where(
                Event.store_id == store.id,
                Event.event_type == "ENTRY",
                Event.source.in_(list(sources)),
                Event.timestamp >= history.start_utc,
                Event.timestamp < tr.end_utc,
            )
        )
    ).scalars().all()
    counts: Dict[tuple, int] = defaultdict(int)
    days_with_data = set()
    for ts in entries:
        local = to_local(ts, tr.tz)
        counts[(local.date(), local.hour)] += 1
        days_with_data.add(local.date())
    for day in tr.local_days():
        prior = sorted(d for d in days_with_data if d < day)
        if len(prior) < th.baseline_min_days:
            if day in days_with_data:
                notes.append(
                    f"{day}: traffic-drop check skipped, only {len(prior)} prior day(s) of entry data "
                    f"(needs {th.baseline_min_days})."
                )
            continue
        for hour in range(24):
            baseline = mean(counts.get((d, hour), 0) for d in prior)
            actual = counts.get((day, hour), 0)
            if baseline >= th.min_baseline_entries and actual < baseline * th.drop_ratio and day in days_with_data:
                found.append({
                    "type": "TRAFFIC_DROP", "severity": "medium", "zone_name": None,
                    "detected_at": history.start_utc,  # replaced below
                    "title": "Traffic drop",
                    "description": f"{day} {hour_label(hour)}: {actual} entries vs baseline {baseline:.1f} ({len(prior)} days).",
                    "metric_value": float(actual), "threshold_value": baseline * th.drop_ratio,
                    "dedupe_key": f"TRAFFIC_DROP:{day}:{hour}",
                    "_local": (day, hour),
                })
    from datetime import datetime, time

    from app.services.timerange import to_utc_naive

    for a in found:
        if "_local" in a:
            d, h = a.pop("_local")
            a["detected_at"] = to_utc_naive(datetime.combine(d, time(hour=h)), tr.tz)

    # Persist idempotently.
    existing = {
        k for (k,) in (
            await db.execute(select(Anomaly.dedupe_key).where(Anomaly.store_id == store.id))
        ).all()
    }
    created = 0
    for a in found:
        if a["dedupe_key"] in existing:
            continue
        anomaly = Anomaly(
            store_id=store.id, anomaly_type=a["type"], severity=a["severity"], zone_name=a["zone_name"],
            description=a["description"], metric_value=a["metric_value"], threshold_value=a["threshold_value"],
            detected_at=a["detected_at"], dedupe_key=a["dedupe_key"],
            metadata_json={"rule_thresholds": th.__dict__, "sources": list(sources)},
        )
        db.add(anomaly)
        await db.flush()
        db.add(Alert(store_id=store.id, anomaly_id=anomaly.id, alert_type=a["type"], title=a["title"],
                     message=a["description"], severity=a["severity"]))
        created += 1
    await db.flush()
    return {"evaluated_range": tr.as_dict(), "found": len(found), "created": created,
            "thresholds": th.__dict__, "notes": notes[:20]}


async def list_anomalies(db: AsyncSession, store_id: uuid.UUID, tr: TimeRange, limit: int = 100) -> List[Anomaly]:
    q = (
        select(Anomaly)
        .where(Anomaly.store_id == store_id, Anomaly.detected_at >= tr.start_utc, Anomaly.detected_at < tr.end_utc)
        .order_by(Anomaly.detected_at.desc())
        .limit(limit)
    )
    return list((await db.execute(q)).scalars().all())


async def list_alerts(db: AsyncSession, store_id: uuid.UUID, unread_only: bool = False, limit: int = 50) -> List[Alert]:
    q = select(Alert).where(Alert.store_id == store_id)
    if unread_only:
        q = q.where(Alert.is_read.is_(False))
    return list((await db.execute(q.order_by(Alert.created_at.desc()).limit(limit))).scalars().all())


async def resolve_anomaly(db: AsyncSession, anomaly: Anomaly) -> None:
    anomaly.is_resolved = True
    anomaly.resolved_at = utcnow()
