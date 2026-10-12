"""Single source of truth for every dashboard metric.

Every page and endpoint calls these functions; nothing else computes metrics.
Definitions are documented in docs/METRICS.md and repeated in the
``definitions`` block of each response so the UI can show them.

Conventions
* All counts come from persisted events/transactions in the requested
  store-local date range and data sources (``data=real`` by default).
* ``None`` means "not measurable from the available data"; ``0`` means
  "measured and zero". Responses say *why* a value is unavailable.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from statistics import mean, median
from typing import Dict, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event
from app.models.jobs import JOB_COMPLETED, OccupancySample, ProcessingJob, VideoAsset
from app.models.pos import POSTransaction
from app.models.store import Camera, Store
from app.services.timerange import TimeRange, hour_label, percentile, to_local

DEFINITIONS = {
    "entries": "Number of ENTRY events: an anonymous track crossed a camera's entry line into the store and stayed inside for the confirmation window. People who enter twice count twice.",
    "exits": "Number of EXIT events (line crossings out of the store).",
    "zone_visits": "Completed visits to a zone (ZONE_EXIT events). A visit starts after the person's ground point stays in the zone for the enter threshold and ends after it stays outside for the exit grace period.",
    "dwell_time": "Seconds between a visit's ZONE_ENTER and ZONE_EXIT for the same track.",
    "queue_wait": "Seconds a track spent inside a QUEUE zone (QUEUE_EXIT.queue_wait_seconds).",
    "queue_completed": "Observed: after leaving the queue the track reached a counter (BILLING) zone within the link window.",
    "queue_abandoned": "Inferred: the track left the queue, stayed visible, and did not reach the counter within the link window. Needs a counter zone on the same camera.",
    "queue_length": "People inside QUEUE zones per occupancy sample (every 5 s of processed video).",
    "transactions": "Distinct POS order ids for the store's POS code in the range.",
    "conversion_rate": "Transactions / entries in the same range. An estimate: footfall and POS must cover the same hours, and one entry is not one person.",
    "pos_match": "A POS order is matched to a counter visit (BILLING zone, dwell >= threshold) when the order time falls between the visit start and its end plus a grace period. Greedy, one-to-one, nearest in time. Estimated link, not an identification.",
}


async def _events(
    db: AsyncSession,
    store_id: uuid.UUID,
    tr: TimeRange,
    sources: Sequence[str],
    types: Optional[Sequence[str]] = None,
) -> List[Event]:
    q = select(Event).where(
        Event.store_id == store_id,
        Event.timestamp >= tr.start_utc,
        Event.timestamp < tr.end_utc,
        Event.source.in_(list(sources)),
        Event.is_staff.is_(False),
    )
    if types:
        q = q.where(Event.event_type.in_(list(types)))
    return list((await db.execute(q.order_by(Event.timestamp))).scalars().all())


async def source_breakdown(db: AsyncSession, store_id: uuid.UUID, tr: TimeRange) -> Dict[str, int]:
    rows = await db.execute(
        select(Event.source, func.count(Event.id))
        .where(Event.store_id == store_id, Event.timestamp >= tr.start_utc, Event.timestamp < tr.end_utc)
        .group_by(Event.source)
    )
    return {s: c for s, c in rows.all()}


async def data_extent(db: AsyncSession, store: Store) -> Dict:
    """First/last event per source, so the UI can jump to where data exists."""
    rows = await db.execute(
        select(Event.source, func.min(Event.timestamp), func.max(Event.timestamp), func.count(Event.id))
        .where(Event.store_id == store.id)
        .group_by(Event.source)
    )
    out = {}
    from app.services.timerange import store_tz

    tz = store_tz(store.timezone)
    for source, first, last, count in rows.all():
        out[source] = {
            "first_local_date": to_local(first, tz).date().isoformat() if first else None,
            "last_local_date": to_local(last, tz).date().isoformat() if last else None,
            "events": count,
        }
    pos = await db.execute(
        select(func.min(POSTransaction.ordered_at_utc), func.max(POSTransaction.ordered_at_utc), func.count())
        .where(POSTransaction.store_id == (store.pos_store_code or "__none__"))
    )
    first, last, count = pos.one()
    out["pos"] = {
        "first_local_date": to_local(first, tz).date().isoformat() if first else None,
        "last_local_date": to_local(last, tz).date().isoformat() if last else None,
        "transactions": count,
    }
    return out


async def coverage(db: AsyncSession, store_id: uuid.UUID, tr: TimeRange) -> Dict:
    """Which cameras have processed footage in the range (seconds of video)."""
    rows = await db.execute(
        select(Camera.camera_code, Camera.camera_type, ProcessingJob.results)
        .join(ProcessingJob, ProcessingJob.camera_id == Camera.id)
        .join(VideoAsset, VideoAsset.id == ProcessingJob.video_id)
        .where(
            ProcessingJob.store_id == store_id,
            ProcessingJob.status == JOB_COMPLETED,
            VideoAsset.recorded_start < tr.end_utc,
            VideoAsset.recorded_start >= tr.start_utc - timedelta(days=1),
        )
    )
    per_camera: Dict[str, Dict] = {}
    for code, ctype, results in rows.all():
        if (results or {}).get("superseded_by"):
            continue
        secs = float((results or {}).get("decoded_seconds") or 0)
        cam = per_camera.setdefault(code, {"camera_type": ctype, "videos": 0, "seconds": 0.0})
        cam["videos"] += 1
        cam["seconds"] += secs
    return {
        "cameras": per_camera,
        "has_entrance_footage": any(c["camera_type"] == "entrance" for c in per_camera.values()),
        "has_queue_footage": any(c["camera_type"] == "billing" for c in per_camera.values()),
        "processed_video_seconds": round(sum(c["seconds"] for c in per_camera.values()), 1),
    }


# ── Footfall ─────────────────────────────────────────────────────


async def footfall(db: AsyncSession, store: Store, tr: TimeRange, sources: Sequence[str]) -> Dict:
    events = await _events(db, store.id, tr, sources, ["ENTRY", "EXIT"])
    hourly = [0] * 24
    daily: Dict[str, Dict[str, int]] = {d.isoformat(): {"entries": 0, "exits": 0} for d in tr.local_days()}
    entries = exits = 0
    for e in events:
        local = to_local(e.timestamp, tr.tz)
        key = local.date().isoformat()
        if e.event_type == "ENTRY":
            entries += 1
            hourly[local.hour] += 1
            if key in daily:
                daily[key]["entries"] += 1
        else:
            exits += 1
            if key in daily:
                daily[key]["exits"] += 1
    peak_hour = max(range(24), key=lambda h: hourly[h]) if entries else None
    return {
        "entries": entries,
        "exits": exits,
        "net_in_store_change": entries - exits,
        "avg_daily_entries": round(entries / tr.days, 2),
        "peak_hour": hour_label(peak_hour) if peak_hour is not None else None,
        "peak_hour_entries": hourly[peak_hour] if peak_hour is not None else 0,
        "hourly": [{"hour": h, "label": hour_label(h), "entries": hourly[h]} for h in range(24)],
        "daily": [{"date": k, **v} for k, v in daily.items()],
    }


# ── Zones ────────────────────────────────────────────────────────


async def zones(db: AsyncSession, store: Store, tr: TimeRange, sources: Sequence[str]) -> List[Dict]:
    events = await _events(db, store.id, tr, sources, ["ZONE_EXIT", "ZONE_ENTER"])
    by_zone: Dict[str, Dict] = {}
    for e in events:
        if not e.zone_name:
            continue
        z = by_zone.setdefault(
            e.zone_name,
            {"zone_name": e.zone_name, "zone_type": e.zone_type, "visits": 0, "dwell": [], "tracks": set(),
             "hourly": [0] * 24, "cameras": set()},
        )
        if e.event_type == "ZONE_EXIT":
            z["visits"] += 1
            if e.dwell_seconds is not None:
                z["dwell"].append(float(e.dwell_seconds))
            z["tracks"].add(e.customer_id)
            z["hourly"][to_local(e.timestamp, tr.tz).hour] += 1
            if e.camera_id:
                z["cameras"].add(e.camera_id)
    rows = []
    for z in by_zone.values():
        dw = z["dwell"]
        rows.append({
            "zone_name": z["zone_name"],
            "zone_type": z["zone_type"],
            "visits": z["visits"],
            "unique_tracks": len(z["tracks"]),
            "avg_dwell_seconds": round(mean(dw), 1) if dw else None,
            "median_dwell_seconds": round(median(dw), 1) if dw else None,
            "p90_dwell_seconds": round(percentile(dw, 0.9), 1) if dw else None,
            "max_dwell_seconds": round(max(dw), 1) if dw else None,
            "total_dwell_seconds": round(sum(dw), 1),
            "hourly_visits": z["hourly"],
            "cameras": sorted(z["cameras"]),
        })
    rows.sort(key=lambda r: (-r["visits"], r["zone_name"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


# ── Queue ────────────────────────────────────────────────────────


async def queue(db: AsyncSession, store: Store, tr: TimeRange, sources: Sequence[str], live_window_s: int = 300) -> Dict:
    events = await _events(
        db, store.id, tr, sources, ["QUEUE_EXIT", "QUEUE_COMPLETED", "QUEUE_ABANDONED", "QUEUE_ENTER"]
    )
    waits = [float(e.queue_wait_seconds) for e in events if e.event_type == "QUEUE_EXIT" and e.queue_wait_seconds is not None]
    completed = sum(1 for e in events if e.event_type == "QUEUE_COMPLETED")
    abandoned = sum(1 for e in events if e.event_type == "QUEUE_ABANDONED")
    exits = sum(1 for e in events if e.event_type == "QUEUE_EXIT")
    # Legacy imported data has QUEUE_COMPLETED with wait but no QUEUE_EXIT.
    if not waits:
        waits = [float(e.queue_wait_seconds) for e in events if e.event_type == "QUEUE_COMPLETED" and e.queue_wait_seconds]

    samples = []
    if "cv" in sources:
        rows = await db.execute(
            select(OccupancySample.timestamp, OccupancySample.count, OccupancySample.zone_name)
            .where(
                OccupancySample.store_id == store.id,
                OccupancySample.zone_type == "QUEUE",
                OccupancySample.timestamp >= tr.start_utc,
                OccupancySample.timestamp < tr.end_utc,
            )
            .order_by(OccupancySample.timestamp)
        )
        samples = rows.all()
    # Sum queue zones that share a timestamp (one camera can have several).
    per_ts: Dict[datetime, int] = defaultdict(int)
    for ts, count, _ in samples:
        per_ts[ts] += count
    lengths = list(per_ts.values())
    hourly_len: Dict[int, List[int]] = defaultdict(list)
    for ts, n in per_ts.items():
        hourly_len[to_local(ts, tr.tz).hour].append(n)
    hourly_wait: Dict[int, List[float]] = defaultdict(list)
    for e in events:
        if e.event_type == "QUEUE_EXIT" and e.queue_wait_seconds is not None:
            hourly_wait[to_local(e.timestamp, tr.tz).hour].append(float(e.queue_wait_seconds))

    current = None
    current_as_of = None
    if per_ts:
        last_ts = max(per_ts)
        current_as_of = last_ts.isoformat() + "Z"
        from app.database import utcnow

        if (utcnow() - last_ts).total_seconds() <= live_window_s:
            current = per_ts[last_ts]
    observed_hours = len(lengths) * 5 / 3600 if lengths else 0
    return {
        "queue_visits": exits,
        "avg_wait_seconds": round(mean(waits), 1) if waits else None,
        "median_wait_seconds": round(median(waits), 1) if waits else None,
        "p90_wait_seconds": round(percentile(waits, 0.9), 1) if waits else None,
        "max_wait_seconds": round(max(waits), 1) if waits else None,
        "completed": completed,
        "abandoned": abandoned,
        "outcome_unknown": max(0, exits - completed - abandoned),
        "abandonment_rate": round(abandoned / (completed + abandoned) * 100, 1) if (completed + abandoned) else None,
        "avg_queue_length": round(mean(lengths), 2) if lengths else None,
        "max_queue_length": max(lengths) if lengths else None,
        "current_queue_length": current,
        "last_sample_at": current_as_of,
        "throughput_per_hour": round(completed / observed_hours, 1) if observed_hours >= 0.05 else None,
        "observed_queue_hours": round(observed_hours, 2),
        "hourly": [
            {
                "hour": h,
                "label": hour_label(h),
                "avg_wait_seconds": round(mean(hourly_wait[h]), 1) if hourly_wait[h] else None,
                "avg_queue_length": round(mean(hourly_len[h]), 2) if hourly_len[h] else None,
            }
            for h in range(24)
        ],
    }


# ── POS / revenue / conversion ───────────────────────────────────


async def _pos_rows(db: AsyncSession, store: Store, tr: TimeRange) -> List[POSTransaction]:
    if not store.pos_store_code:
        return []
    rows = await db.execute(
        select(POSTransaction).where(
            POSTransaction.store_id == store.pos_store_code,
            POSTransaction.ordered_at_utc >= tr.start_utc,
            POSTransaction.ordered_at_utc < tr.end_utc,
        )
    )
    return list(rows.scalars().all())


async def revenue(db: AsyncSession, store: Store, tr: TimeRange) -> Dict:
    if not store.pos_store_code:
        return {"available": False, "reason": "No POS store code is configured for this store.",
                "total_revenue": None, "transactions": None, "items": None, "avg_order_value": None,
                "top_brands": [], "hourly": []}
    rows = await _pos_rows(db, store, tr)
    orders: Dict[int, float] = defaultdict(float)
    brands: Dict[str, Dict] = {}
    hourly: Dict[int, float] = defaultdict(float)
    for r in rows:
        orders[r.order_id] += r.total_amount
        b = brands.setdefault(r.brand_name, {"brand": r.brand_name, "revenue": 0.0, "items": 0})
        b["revenue"] += r.total_amount
        b["items"] += 1
        hourly[to_local(r.ordered_at_utc, tr.tz).hour] += r.total_amount
    total = sum(orders.values())
    top = sorted(brands.values(), key=lambda b: -b["revenue"])[:10]
    for b in top:
        b["revenue"] = round(b["revenue"], 2)
    return {
        "available": True,
        "total_revenue": round(total, 2),
        "transactions": len(orders),
        "items": len(rows),
        "avg_order_value": round(total / len(orders), 2) if orders else None,
        "top_brands": top,
        "hourly": [{"hour": h, "label": hour_label(h), "revenue": round(hourly[h], 2)} for h in range(24)],
    }


async def conversion(db: AsyncSession, store: Store, tr: TimeRange, sources: Sequence[str]) -> Dict:
    ff = await footfall(db, store, tr, sources)
    rev = await revenue(db, store, tr)
    entries = ff["entries"]
    tx = rev.get("transactions")
    notes = []
    rate = None
    if not rev["available"]:
        notes.append(rev["reason"])
    elif entries == 0:
        notes.append("No ENTRY events in this range (no processed entrance footage or no entry line configured).")
    elif not tx:
        notes.append("No POS transactions in this range.")
    else:
        rate = round(tx / entries * 100, 1)
        notes.append("Transactions per entry. Check that footfall and POS cover the same hours before comparing.")
    return {
        "entries": entries,
        "transactions": tx,
        "conversion_rate": rate,
        "revenue_per_entry": round(rev["total_revenue"] / entries, 2) if rate is not None else None,
        "basis": "transactions / entries",
        "notes": notes,
    }


async def pos_correlation(
    db: AsyncSession,
    store: Store,
    tr: TimeRange,
    sources: Sequence[str],
    min_counter_dwell_s: float = 10.0,
    grace_s: float = 120.0,
) -> Dict:
    """Match POS orders to observed counter visits (see DEFINITIONS['pos_match'])."""
    rows = await _pos_rows(db, store, tr)
    orders: Dict[int, Dict] = {}
    for r in rows:
        o = orders.setdefault(r.order_id, {"order_id": r.order_id, "at": r.ordered_at_utc, "amount": 0.0, "items": 0})
        o["amount"] += r.total_amount
        o["items"] += 1
    events = await _events(db, store.id, tr, sources, ["ZONE_EXIT"])
    visits = []
    for e in events:
        if e.zone_type == "BILLING" and (e.dwell_seconds or 0) >= min_counter_dwell_s:
            start = e.timestamp - timedelta(seconds=float(e.dwell_seconds or 0))
            visits.append({"customer_id": e.customer_id, "camera_id": e.camera_id, "start": start,
                           "end": e.timestamp, "dwell_seconds": e.dwell_seconds, "matched": False})
    matched = []
    unmatched_orders = []
    for o in sorted(orders.values(), key=lambda o: o["at"]):
        candidates = [
            v for v in visits
            if not v["matched"] and v["start"] <= o["at"] <= v["end"] + timedelta(seconds=grace_s)
        ]
        if not candidates:
            unmatched_orders.append(o)
            continue
        best = min(candidates, key=lambda v: abs((v["end"] - o["at"]).total_seconds()))
        best["matched"] = True
        matched.append({"order": o, "visit": best})

    def _fmt_order(o: Dict) -> Dict:
        return {"order_id": o["order_id"], "ordered_at": to_local(o["at"], tr.tz).isoformat(),
                "amount": round(o["amount"], 2), "items": o["items"]}

    def _fmt_visit(v: Dict) -> Dict:
        return {"track": v["customer_id"], "camera": v["camera_id"],
                "start": to_local(v["start"], tr.tz).isoformat(), "end": to_local(v["end"], tr.tz).isoformat(),
                "dwell_seconds": v["dwell_seconds"]}

    return {
        "method": DEFINITIONS["pos_match"],
        "parameters": {"min_counter_dwell_seconds": min_counter_dwell_s, "grace_seconds": grace_s},
        "pos_configured": bool(store.pos_store_code),
        "orders": len(orders),
        "counter_visits": len(visits),
        "matched": [{"order": _fmt_order(m["order"]), "visit": _fmt_visit(m["visit"])} for m in matched],
        "unmatched_orders": [_fmt_order(o) for o in unmatched_orders],
        "unmatched_counter_visits": [_fmt_visit(v) for v in visits if not v["matched"]],
    }


async def unassigned_pos(db: AsyncSession) -> List[Dict]:
    """POS store codes present in the data but not mapped to any store."""
    mapped = {c for (c,) in (await db.execute(select(Store.pos_store_code))).all() if c}
    rows = await db.execute(
        select(POSTransaction.store_id, func.count(), func.count(func.distinct(POSTransaction.order_id)),
               func.min(POSTransaction.order_date), func.max(POSTransaction.order_date))
        .group_by(POSTransaction.store_id)
    )
    return [
        {"pos_store_code": code, "line_items": n, "orders": orders,
         "first_date": first.isoformat() if first else None, "last_date": last.isoformat() if last else None}
        for code, n, orders, first, last in rows.all()
        if code not in mapped
    ]


# ── Summary for the overview page ────────────────────────────────


async def overview(db: AsyncSession, store: Store, tr: TimeRange, sources: Sequence[str]) -> Dict:
    ff = await footfall(db, store, tr, sources)
    zs = await zones(db, store, tr, sources)
    q = await queue(db, store, tr, sources)
    rev = await revenue(db, store, tr)
    conv = await conversion(db, store, tr, sources)
    all_dwell_total = sum(z["total_dwell_seconds"] for z in zs)
    all_visits = sum(z["visits"] for z in zs)
    breakdown = await source_breakdown(db, store.id, tr)
    return {
        "footfall": ff,
        "zones": zs,
        "queue": q,
        "revenue": rev,
        "conversion": conv,
        "avg_zone_dwell_seconds": round(all_dwell_total / all_visits, 1) if all_visits else None,
        "zone_visits": all_visits,
        "coverage": await coverage(db, store.id, tr),
        "source_breakdown": breakdown,
    }


def counter(items) -> Dict[str, int]:
    return dict(Counter(items))
