"""Chain-level comparison: the same metrics.py numbers, one row per store.

Nothing here computes a metric of its own; each row is assembled from
``app.services.metrics`` for that store, over the same local dates in the
store's own time zone. Rollups add counts and never average rates across
stores: a chain-wide rate is recomputed from the summed counts of the stores
where it is measurable.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Dict, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import Scope
from app.models.anomaly import Anomaly
from app.models.org import Region
from app.models.store import Store
from app.services import metrics
from app.services.timerange import resolve_range

UNASSIGNED = "No region"


async def _store_row(db: AsyncSession, store: Store, region_name: Optional[str], start: Optional[date],
                     end: Optional[date], sources: Sequence[str], open_anomalies: int) -> Dict:
    tr = resolve_range(store.timezone, start, end)
    ff = await metrics.footfall(db, store, tr, sources)
    zs = await metrics.zones(db, store, tr, sources)
    q = await metrics.queue(db, store, tr, sources)
    rev = await metrics.revenue(db, store, tr)
    cov = await metrics.coverage(db, store.id, tr)
    breakdown = await metrics.source_breakdown(db, store.id, tr)
    entries = ff["entries"]
    tx = rev["transactions"]
    visits = sum(z["visits"] for z in zs)
    dwell = sum(z["total_dwell_seconds"] for z in zs)
    events = sum(n for s, n in breakdown.items() if s in sources)
    live_seconds = float(cov.get("live_seconds") or 0)
    flags: List[str] = []
    if not cov["cameras"] and live_seconds == 0 and events == 0:
        flags.append("no_data")
    elif entries == 0 and not cov["has_entrance_footage"] and not cov.get("has_live_entrance"):
        flags.append("no_entrance_data")
    if not store.pos_store_code:
        flags.append("no_pos_mapping")
    if open_anomalies:
        flags.append("open_anomalies")
    return {
        "store_id": str(store.id),
        "store_code": store.store_code,
        "name": store.name,
        "city": store.city,
        "region_id": str(store.region_id) if store.region_id else None,
        "region": region_name,
        "timezone": store.timezone,
        "entries": entries,
        "exits": ff["exits"],
        "avg_daily_entries": ff["avg_daily_entries"],
        "peak_hour": ff["peak_hour"],
        "zone_visits": visits,
        "avg_zone_dwell_seconds": round(dwell / visits, 1) if visits else None,
        "queue_visits": q["queue_visits"],
        "avg_queue_wait_seconds": q["avg_wait_seconds"],
        "median_queue_wait_seconds": q["median_wait_seconds"],
        "abandonment_rate": q["abandonment_rate"],
        "transactions": tx,
        "revenue": rev["total_revenue"],
        "avg_order_value": rev["avg_order_value"],
        # Same rule as metrics.conversion: needs POS mapping, entries and orders.
        "conversion_rate": round(tx / entries * 100, 1) if (tx and entries) else None,
        "processed_video_hours": round(cov["processed_video_seconds"] / 3600, 2),
        "live_hours": round(live_seconds / 3600, 2),
        "open_anomalies": open_anomalies,
        "flags": flags,
    }


def _rollup(name: str, rows: List[Dict]) -> Dict:
    entries = sum(r["entries"] for r in rows)
    measurable = [r for r in rows if r["conversion_rate"] is not None]
    conv_entries = sum(r["entries"] for r in measurable)
    conv_tx = sum(r["transactions"] for r in measurable)
    with_pos = [r for r in rows if r["transactions"] is not None]
    waited = [r for r in rows if r["avg_queue_wait_seconds"] is not None and r["queue_visits"]]
    wait_n = sum(r["queue_visits"] for r in waited)
    return {
        "name": name,
        "stores": len(rows),
        "stores_with_data": sum(1 for r in rows if "no_data" not in r["flags"]),
        "entries": entries,
        "transactions": sum(r["transactions"] for r in with_pos) if with_pos else None,
        "revenue": round(sum(r["revenue"] or 0 for r in with_pos), 2) if with_pos else None,
        "conversion_rate": round(conv_tx / conv_entries * 100, 1) if conv_entries else None,
        "conversion_stores": len(measurable),
        "queue_visits": sum(r["queue_visits"] for r in rows),
        "avg_queue_wait_seconds": (
            round(sum(r["avg_queue_wait_seconds"] * r["queue_visits"] for r in waited) / wait_n, 1) if wait_n else None
        ),
    }


async def org_overview(db: AsyncSession, scope: Scope, start: Optional[date], end: Optional[date],
                       sources: Sequence[str], region_id: Optional[uuid.UUID] = None) -> Dict:
    q = scope.filter_stores(select(Store).where(Store.is_active.is_(True))).order_by(Store.store_code)
    if region_id:
        q = q.where(Store.region_id == region_id)
    stores = list((await db.execute(q)).scalars().all())
    region_names = {
        r.id: r.name
        for r in (await db.execute(select(Region).where(Region.org_id == scope.org_id))).scalars().all()
    }
    open_by_store: Dict[uuid.UUID, int] = {}
    if stores:
        open_by_store = dict((await db.execute(
            select(Anomaly.store_id, func.count())
            .where(Anomaly.store_id.in_([s.id for s in stores]), Anomaly.is_resolved.is_(False))
            .group_by(Anomaly.store_id)
        )).all())
    rows = [
        await _store_row(db, s, region_names.get(s.region_id), start, end, sources, open_by_store.get(s.id, 0))
        for s in stores
    ]
    by_region: Dict[str, List[Dict]] = {}
    for r in rows:
        by_region.setdefault(r["region"] or UNASSIGNED, []).append(r)
    # The dates are the same local calendar dates in every store's own time zone.
    ref = resolve_range(stores[0].timezone if stores else "UTC", start, end)
    notes = [
        "Each store's numbers cover the same calendar dates in that store's own time zone.",
        "Conversion is transactions per entry and is only shown for stores with a POS mapping, entries and orders "
        "in the range. Group rates use only those stores.",
    ]
    return {
        "range": {"start": ref.start_date.isoformat(), "end": ref.end_date.isoformat(), "days": ref.days},
        "data": list(sources),
        "stores": rows,
        "total": _rollup("All stores", rows),
        "regions": [_rollup(name, rs) for name, rs in sorted(by_region.items(), key=lambda kv: (kv[0] == UNASSIGNED, kv[0]))],
        "notes": notes,
    }
