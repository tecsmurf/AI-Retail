"""Setup checklist for one store: what is done, what is still missing.

Everything here is read from the database as it is now. A step is only shown
as done when the thing it names exists: a camera, a paired box that checked in,
a drawn line, an event that really arrived.
"""

from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_store
from app.api.edge import online_window
from app.database import get_db, utcnow
from app.models.edge import EDGE_ACTIVE, EDGE_PENDING, EdgeDevice
from app.models.event import REAL_SOURCES, Event
from app.models.pos import POSTransaction
from app.models.store import Camera, Store, Zone
from app.services.timerange import store_tz, to_local

router = APIRouter(tags=["Setup"])


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def camera_needs(camera_type: str, has_entry_line: bool, zone_types: List[str]) -> List[str]:
    """What a camera still lacks before it can produce numbers."""
    if camera_type == "entrance":
        return [] if has_entry_line else ["entry line"]
    if camera_type == "billing":
        return [] if "QUEUE" in zone_types else ["queue zone"]
    if camera_type == "zone":
        return [] if zone_types else ["zones"]
    # "other": anything drawn makes it useful.
    return [] if has_entry_line or zone_types else ["zones or an entry line"]


@router.get("/api/stores/{store_id}/setup-status")
async def setup_status(store: Store = Depends(get_store), db: AsyncSession = Depends(get_db)):
    cameras = list((await db.execute(
        select(Camera).where(Camera.store_id == store.id, Camera.is_active.is_(True)).order_by(Camera.camera_code)
    )).scalars().all())
    zone_types: Dict[object, List[str]] = {}
    for cam_id, ztype in (await db.execute(
        select(Zone.camera_id, Zone.zone_type).where(Zone.store_id == store.id, Zone.camera_id.is_not(None))
    )).all():
        zone_types.setdefault(cam_id, []).append(ztype)

    devices = list((await db.execute(
        select(EdgeDevice).where(EdgeDevice.store_id == store.id, EdgeDevice.status.in_((EDGE_ACTIVE, EDGE_PENDING)))
    )).scalars().all())
    now = utcnow()
    online = [d for d in devices
              if d.status == EDGE_ACTIVE and d.last_seen_at is not None and now - d.last_seen_at <= online_window()]
    live_cameras = {cam_id for d in online for cam_id, r in (d.camera_status or {}).items()
                    if (r or {}).get("status") == "online"}

    cam_rows = []
    for c in cameras:
        types = zone_types.get(c.id, [])
        cam_rows.append({
            "camera_id": str(c.id), "camera_code": c.camera_code, "name": c.name, "camera_type": c.camera_type,
            "has_entry_line": bool(c.entry_line), "zones": len(types),
            "has_still_image": bool(c.reference_frame_key),
            "live": str(c.id) in live_cameras,
            "needs": camera_needs(c.camera_type, bool(c.entry_line), types),
        })

    first_event, last_event, event_count = (await db.execute(
        select(func.min(Event.timestamp), func.max(Event.timestamp), func.count(Event.id))
        .where(Event.store_id == store.id, Event.source.in_(REAL_SOURCES))
    )).one()
    pos_rows = 0
    if store.pos_store_code:
        pos_rows = (await db.execute(
            select(func.count(POSTransaction.id))
            .where(POSTransaction.org_id == store.org_id, POSTransaction.store_id == store.pos_store_code)
        )).scalar_one()

    entrances = sum(1 for c in cameras if c.camera_type == "entrance")
    undrawn = [c["camera_code"] for c in cam_rows if c["needs"]]
    paired = [d for d in devices if d.status == EDGE_ACTIVE]
    tz = store_tz(store.timezone)

    if not cameras:
        cameras_detail = "Add the cameras you want analysed."
    elif not entrances:
        cameras_detail = f"{_plural(len(cameras), 'camera')}. None is an entrance camera, so people coming in are not counted."
    else:
        cameras_detail = f"{_plural(len(cameras), 'camera')}, {entrances} at an entrance."

    if online and live_cameras:
        box_detail = f"{_plural(len(live_cameras), 'camera')} live through the box in the store."
    elif online:
        box_detail = "The box is connected, but no camera is live yet. Check the stream addresses on the box."
    elif paired:
        box_detail = "The box is paired but has not checked in recently. Check that the store PC is on and online."
    elif devices:
        box_detail = "A box was added but is not paired yet. Enter its pairing code on the store PC."
    else:
        box_detail = "Needed for live numbers. Without it you can upload recordings."

    if not cameras:
        zones_detail = "Add cameras first."
    elif undrawn:
        zones_detail = f"Still to draw: {', '.join(undrawn)}."
    else:
        zones_detail = "Every camera has what it needs."

    if event_count:
        first_local = to_local(first_event, tz).strftime("%d %b %Y")
        last_local = to_local(last_event, tz).strftime("%d %b %Y, %H:%M")
        data_detail = f"{event_count:,} events from this store's cameras since {first_local}. Latest: {last_local} store time."
    else:
        data_detail = "Nothing has arrived yet. Start the box, or upload a recording under Videos."

    if not store.pos_store_code:
        pos_detail = "Set the POS store code and import sales to see revenue next to footfall."
    elif not pos_rows:
        pos_detail = f"POS store code {store.pos_store_code} is set, but no sales were imported for it."
    else:
        pos_detail = f"{pos_rows:,} sales lines imported for POS store code {store.pos_store_code}."

    steps = [
        {"key": "store", "title": "Store created", "done": True, "required": True,
         "detail": f"{store.name} ({store.store_code}), time zone {store.timezone}."},
        {"key": "cameras", "title": "Cameras added", "done": bool(cameras), "required": True, "detail": cameras_detail},
        {"key": "box", "title": "In-store box connected", "done": bool(online), "required": False, "detail": box_detail},
        {"key": "zones", "title": "Entry line and zones drawn", "done": bool(cameras) and not undrawn,
         "required": True, "detail": zones_detail},
        {"key": "data", "title": "First real numbers", "done": bool(event_count), "required": True, "detail": data_detail},
        {"key": "pos", "title": "Sales data linked", "done": bool(pos_rows), "required": False, "detail": pos_detail},
    ]
    required = [s for s in steps if s["required"]]
    return {
        "store_id": str(store.id),
        "ready": all(s["done"] for s in required),
        "done": sum(1 for s in required if s["done"]),
        "total": len(required),
        "steps": steps,
        "cameras": cam_rows,
        "has_entrance_camera": bool(entrances),
        "boxes": len(devices),
        "box_online": bool(online),
    }
