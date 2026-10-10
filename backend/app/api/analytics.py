"""Analytics endpoints. Every number comes from app.services.metrics.

Common query parameters: ``start``/``end`` (store-local dates, inclusive;
default: the last 7 days) and ``data`` (``real`` by default; ``all`` adds the
bundled sample, demo and legacy v1 records, which the UI labels as such).
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RangeParams, get_store
from app.database import get_db
from app.models.anomaly import Alert, Anomaly
from app.models.store import Store
from app.models.user import User
from app.security import current_user, require_admin
from app.services import anomaly_service, journey_service, metrics
from app.services.insights import build_insights

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


def _envelope(store: Store, tr, sources, body: dict) -> dict:
    return {"store_id": str(store.id), "range": tr.as_dict(), "data": list(sources), **body}


@router.get("/definitions")
async def definitions(_: User = Depends(current_user)):
    return metrics.DEFINITIONS


@router.get("/{store_id}/data-extent")
async def data_extent(store: Store = Depends(get_store), _: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Where data exists (per source), so the UI can jump to it."""
    return {"store_id": str(store.id), "timezone": store.timezone, "sources": await metrics.data_extent(db, store)}


@router.get("/{store_id}/overview")
async def overview(rp: RangeParams = Depends(), store: Store = Depends(get_store), _: User = Depends(current_user),
                   db: AsyncSession = Depends(get_db)):
    tr, sources = rp.resolve(store)
    body = await metrics.overview(db, store, tr, sources)
    alerts = await anomaly_service.list_alerts(db, store.id, unread_only=True)
    body["active_alerts"] = len(alerts)
    return _envelope(store, tr, sources, body)


@router.get("/{store_id}/footfall")
async def footfall(rp: RangeParams = Depends(), store: Store = Depends(get_store), _: User = Depends(current_user),
                   db: AsyncSession = Depends(get_db)):
    tr, sources = rp.resolve(store)
    return _envelope(store, tr, sources, await metrics.footfall(db, store, tr, sources))


@router.get("/{store_id}/zones")
async def zones(rp: RangeParams = Depends(), store: Store = Depends(get_store), _: User = Depends(current_user),
                db: AsyncSession = Depends(get_db)):
    tr, sources = rp.resolve(store)
    return _envelope(store, tr, sources, {"zones": await metrics.zones(db, store, tr, sources)})


@router.get("/{store_id}/queue")
async def queue(rp: RangeParams = Depends(), store: Store = Depends(get_store), _: User = Depends(current_user),
                db: AsyncSession = Depends(get_db)):
    tr, sources = rp.resolve(store)
    return _envelope(store, tr, sources, await metrics.queue(db, store, tr, sources))


@router.get("/{store_id}/revenue")
async def revenue(rp: RangeParams = Depends(), store: Store = Depends(get_store), _: User = Depends(current_user),
                  db: AsyncSession = Depends(get_db)):
    tr, sources = rp.resolve(store)
    return _envelope(store, tr, sources, await metrics.revenue(db, store, tr))


@router.get("/{store_id}/conversion")
async def conversion(rp: RangeParams = Depends(), store: Store = Depends(get_store), _: User = Depends(current_user),
                     db: AsyncSession = Depends(get_db)):
    tr, sources = rp.resolve(store)
    return _envelope(store, tr, sources, await metrics.conversion(db, store, tr, sources))


@router.get("/{store_id}/pos-correlation")
async def pos_correlation(
    rp: RangeParams = Depends(),
    min_counter_dwell_s: float = Query(10.0, ge=0, le=3600),
    grace_s: float = Query(120.0, ge=0, le=3600),
    store: Store = Depends(get_store), _: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    tr, sources = rp.resolve(store)
    body = await metrics.pos_correlation(db, store, tr, sources, min_counter_dwell_s, grace_s)
    return _envelope(store, tr, sources, body)


@router.get("/{store_id}/journeys")
async def journeys(
    rp: RangeParams = Depends(),
    journey_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    store: Store = Depends(get_store), _: User = Depends(current_user), db: AsyncSession = Depends(get_db),
):
    tr, sources = rp.resolve(store)
    page = await journey_service.list_journeys(db, store.id, tr, sources, journey_type, limit, offset)
    items = [
        {
            "id": str(j.id), "customer_id": j.customer_id, "camera_id": j.camera_id, "job_id": str(j.job_id) if j.job_id else None,
            "source": j.source, "entry_time": j.entry_time.isoformat() + "Z",
            "exit_time": j.exit_time.isoformat() + "Z" if j.exit_time else None,
            "duration_seconds": j.duration_seconds, "zones_visited": j.zones_visited or [], "zone_count": j.zone_count,
            "total_dwell_seconds": j.total_dwell_seconds, "visited_billing": j.visited_billing,
            "made_purchase": j.made_purchase, "observed_entry": j.observed_entry, "observed_exit": j.observed_exit,
            "journey_type": j.journey_type,
            "steps": [
                {"sequence": s.sequence, "event_type": s.event_type, "zone_name": s.zone_name,
                 "timestamp": s.timestamp.isoformat() + "Z", "dwell_seconds": s.dwell_seconds}
                for s in j.journey_events
            ],
        }
        for j in page["items"]
    ]
    return _envelope(store, tr, sources, {"total": page["total"], "limit": limit, "offset": offset, "items": items})


@router.get("/{store_id}/journeys/analytics")
async def journey_analytics(rp: RangeParams = Depends(), store: Store = Depends(get_store), _: User = Depends(current_user),
                            db: AsyncSession = Depends(get_db)):
    tr, sources = rp.resolve(store)
    return _envelope(store, tr, sources, await journey_service.journey_analytics(db, store.id, tr, sources))


@router.get("/{store_id}/anomalies")
async def anomalies(rp: RangeParams = Depends(), store: Store = Depends(get_store), _: User = Depends(current_user),
                    db: AsyncSession = Depends(get_db)):
    tr, sources = rp.resolve(store)
    rows = await anomaly_service.list_anomalies(db, store.id, tr)
    return _envelope(store, tr, sources, {"items": [_anomaly(a) for a in rows]})


@router.post("/{store_id}/detect-anomalies")
async def detect_anomalies(rp: RangeParams = Depends(), store: Store = Depends(get_store), _: User = Depends(require_admin),
                           db: AsyncSession = Depends(get_db)):
    tr, sources = rp.resolve(store)
    return await anomaly_service.detect(db, store, tr, sources)


@router.post("/{store_id}/anomalies/{anomaly_id}/resolve")
async def resolve_anomaly(anomaly_id: uuid.UUID, store: Store = Depends(get_store), _: User = Depends(require_admin),
                          db: AsyncSession = Depends(get_db)):
    a = await db.get(Anomaly, anomaly_id)
    if not a or a.store_id != store.id:
        raise HTTPException(404, "Anomaly not found")
    await anomaly_service.resolve_anomaly(db, a)
    return _anomaly(a)


@router.get("/{store_id}/alerts")
async def alerts(unread_only: bool = False, limit: int = Query(50, ge=1, le=200), store: Store = Depends(get_store),
                 _: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = await anomaly_service.list_alerts(db, store.id, unread_only, limit)
    return {"items": [_alert(a) for a in rows]}


@router.post("/{store_id}/alerts/{alert_id}/read")
async def mark_alert_read(alert_id: uuid.UUID, store: Store = Depends(get_store), _: User = Depends(current_user),
                          db: AsyncSession = Depends(get_db)):
    a = await db.get(Alert, alert_id)
    if not a or a.store_id != store.id:
        raise HTTPException(404, "Alert not found")
    a.is_read = True
    return _alert(a)


@router.get("/{store_id}/insights")
async def insights(rp: RangeParams = Depends(), store: Store = Depends(get_store), _: User = Depends(current_user),
                   db: AsyncSession = Depends(get_db)):
    tr, sources = rp.resolve(store)
    ov = await metrics.overview(db, store, tr, sources)
    ja = await journey_service.journey_analytics(db, store.id, tr, sources)
    return _envelope(store, tr, sources, build_insights(ov, ja))


@router.get("/{store_id}/demographics")
async def demographics(store: Store = Depends(get_store), _: User = Depends(current_user)):
    """Not provided: there is no validated, privacy-reviewed age/gender model
    in the pipeline. Returned explicitly so clients do not invent values."""
    return {
        "available": False,
        "reason": "Demographic estimation is not implemented or validated. PurpleSol reports anonymous aggregate movement only.",
    }


def _anomaly(a: Anomaly) -> dict:
    return {
        "id": str(a.id), "anomaly_type": a.anomaly_type, "severity": a.severity, "zone_name": a.zone_name,
        "description": a.description, "metric_value": a.metric_value, "threshold_value": a.threshold_value,
        "detected_at": a.detected_at.isoformat() + "Z", "is_resolved": a.is_resolved,
        "resolved_at": a.resolved_at.isoformat() + "Z" if a.resolved_at else None,
    }


def _alert(a: Alert) -> dict:
    return {
        "id": str(a.id), "alert_type": a.alert_type, "title": a.title, "message": a.message,
        "severity": a.severity, "is_read": a.is_read, "created_at": a.created_at.isoformat() + "Z",
        "anomaly_id": str(a.anomaly_id) if a.anomaly_id else None,
    }


__all__: List[str] = ["router"]
