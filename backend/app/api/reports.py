"""CSV exports for HQ and store managers.

Every file uses the same definitions as the dashboard (docs/METRICS.md) and
says which data sources it covers. Empty cells mean "not measured" (no POS
data, no queue camera), never zero. Exports are recorded in the audit log.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date, timedelta
from typing import Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import Scope, get_scope, store_in_scope
from app.api.deps import RangeParams
from app.database import get_db
from app.services import audit, metrics, org_metrics
from app.services.timerange import parse_sources, resolve_range

router = APIRouter(prefix="/api/reports", tags=["Reports"])

MAX_DAILY_DAYS = 92


def _cell(v):
    """Empty for "not measured"; text that a spreadsheet would run as a formula is quoted."""
    if v is None:
        return ""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def _csv(filename: str, header: List[str], rows: Iterable[List], notes: List[str]) -> Response:
    buf = io.StringIO()
    # BOM so Excel opens non-English store names correctly.
    buf.write("\ufeff")
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow([_cell(v) for v in r])
    for n in notes:
        w.writerow([f"# {n}"])
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


def _safe(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in s)[:60]


@router.get("/stores.csv")
async def stores_csv(
    request: Request, start: Optional[date] = Query(None), end: Optional[date] = Query(None), data: str = Query("real"),
    region_id: Optional[uuid.UUID] = None, scope: Scope = Depends(get_scope), db: AsyncSession = Depends(get_db),
):
    """All visible stores side by side (the HQ comparison)."""
    body = await org_metrics.org_overview(db, scope, start, end, parse_sources(data), region_id)
    rng = body["range"] or {"start": str(start or ""), "end": str(end or "")}
    header = ["store_code", "store", "city", "region", "entries", "exits", "avg_daily_entries", "peak_hour",
              "zone_visits", "avg_zone_dwell_s", "queue_visits", "avg_queue_wait_s", "median_queue_wait_s",
              "queue_abandonment_pct", "transactions", "revenue", "avg_order_value", "conversion_pct",
              "uploaded_video_h", "live_camera_h", "open_anomalies", "flags"]
    rows = [[s["store_code"], s["name"], s["city"], s["region"], s["entries"], s["exits"], s["avg_daily_entries"],
             s["peak_hour"], s["zone_visits"], s["avg_zone_dwell_seconds"], s["queue_visits"],
             s["avg_queue_wait_seconds"], s["median_queue_wait_seconds"], s["abandonment_rate"], s["transactions"],
             s["revenue"], s["avg_order_value"], s["conversion_rate"], s["processed_video_hours"], s["live_hours"],
             s["open_anomalies"], " ".join(s["flags"])] for s in body["stores"]]
    audit.record(db, "report.export", user=scope.user, target_type="report", target_id="stores",
                 details={"start": rng["start"], "end": rng["end"], "stores": len(rows)}, request=request)
    notes = [f"Dates {rng['start']} to {rng['end']}, each store in its own time zone. Sources: {','.join(body['data'])}.",
             "Empty cells are not measured (for example no POS data), not zero.", *body["notes"][1:]]
    return _csv(f"purplesol-stores-{rng['start']}-{rng['end']}.csv", header, rows, notes)


@router.get("/{store_id}/daily.csv")
async def daily_csv(
    store_id: uuid.UUID, request: Request, rp: RangeParams = Depends(), scope: Scope = Depends(get_scope),
    db: AsyncSession = Depends(get_db),
):
    """One row per local day for one store."""
    store = await store_in_scope(db, scope, store_id)
    tr, sources = rp.resolve(store)
    if tr.days > MAX_DAILY_DAYS:
        raise HTTPException(422, f"Daily export is limited to {MAX_DAILY_DAYS} days")
    header = ["date", "store_code", "entries", "exits", "zone_visits", "avg_zone_dwell_s", "queue_visits",
              "avg_queue_wait_s", "median_queue_wait_s", "transactions", "revenue", "conversion_pct",
              "uploaded_video_min", "live_camera_min"]
    rows = []
    day = tr.start_date
    while day <= tr.end_date:
        dtr = resolve_range(store.timezone, day, day)
        ov = await metrics.overview(db, store, dtr, sources)
        ff, q, rev, conv, cov = ov["footfall"], ov["queue"], ov["revenue"], ov["conversion"], ov["coverage"]
        # A day nobody watched has no counts at all; writing 0 would read as an empty store.
        watched = (cov["processed_video_seconds"] or cov.get("live_seconds", 0)
                   or any(ov.get("source_breakdown", {}).values()))
        counts = [ff["entries"], ff["exits"], ov["zone_visits"]] if watched else [None, None, None]
        rows.append([day.isoformat(), store.store_code, *counts,
                     ov["avg_zone_dwell_seconds"], q["queue_visits"] if watched else None,
                     q["avg_wait_seconds"], q["median_wait_seconds"],
                     rev.get("transactions") if rev["available"] else None,
                     rev.get("total_revenue") if rev["available"] else None, conv["conversion_rate"],
                     round(cov["processed_video_seconds"] / 60, 1), round(cov.get("live_seconds", 0) / 60, 1)])
        day += timedelta(days=1)
    audit.record(db, "report.export", user=scope.user, target_type="store", target_id=store.id,
                 details={"report": "daily", "start": tr.start_date.isoformat(), "end": tr.end_date.isoformat()}, request=request)
    notes = [f"{store.name}, {tr.start_date} to {tr.end_date}, time zone {store.timezone}. Sources: {','.join(sources)}.",
             "Minutes of uploaded video and live camera time show how much footage stands behind each day. "
             "A day with no footage and no events has empty counts.",
             "Empty cells are not measured, not zero. Conversion = POS transactions / entries (an estimate)."]
    return _csv(f"purplesol-{_safe(store.store_code)}-daily-{tr.start_date}-{tr.end_date}.csv", header, rows, notes)


@router.get("/{store_id}/zones.csv")
async def zones_csv(
    store_id: uuid.UUID, request: Request, rp: RangeParams = Depends(), scope: Scope = Depends(get_scope),
    db: AsyncSession = Depends(get_db),
):
    store = await store_in_scope(db, scope, store_id)
    tr, sources = rp.resolve(store)
    zones = await metrics.zones(db, store, tr, sources)
    header = ["rank", "zone", "zone_type", "visits", "unique_tracks", "avg_dwell_s", "median_dwell_s", "p90_dwell_s",
              "max_dwell_s", "total_dwell_s", "cameras"]
    rows = [[z["rank"], z["zone_name"], z["zone_type"], z["visits"], z["unique_tracks"], z["avg_dwell_seconds"],
             z["median_dwell_seconds"], z["p90_dwell_seconds"], z["max_dwell_seconds"], z["total_dwell_seconds"],
             " ".join(z["cameras"])] for z in zones]
    audit.record(db, "report.export", user=scope.user, target_type="store", target_id=store.id,
                 details={"report": "zones", "start": tr.start_date.isoformat(), "end": tr.end_date.isoformat()}, request=request)
    notes = [f"{store.name}, {tr.start_date} to {tr.end_date}, time zone {store.timezone}. Sources: {','.join(sources)}.",
             "A visit is one anonymous track staying in the zone; tracks are not linked across cameras."]
    return _csv(f"purplesol-{_safe(store.store_code)}-zones-{tr.start_date}-{tr.end_date}.csv", header, rows, notes)
