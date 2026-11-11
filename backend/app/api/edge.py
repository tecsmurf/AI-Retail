"""In-store edge boxes.

Dashboard side (admin session): add a box to a store, get a one-time pairing
code, see whether the box and its cameras are online, revoke it, ask for a
fresh still image.

Box side (``Authorization: Bearer pse_...``): pair with the code, fetch the
camera and zone configuration, send heartbeats, events, queue-length samples
and still images. The box never sends video, and the cloud never stores the
recorder's address or password: stream URLs live only in the box's own file.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access import Scope, require_org_admin, store_in_scope
from app.api.deps import get_store
from app.api.stores import set_reference_frame
from app.api.videos import snapshot_config
from app.config import settings
from app.database import get_db, utcnow
from app.models.edge import EDGE_ACTIVE, EDGE_PENDING, EDGE_REVOKED, EdgeCoverage, EdgeDevice
from app.models.event import EVENT_TYPES
from app.models.jobs import OccupancySample
from app.models.store import Camera, Store
from app.security import client_ip, rate_limiter
from app.services import audit, journey_service
from app.services.ingest import insert_events
from app.storage import get_storage

router = APIRouter(tags=["Edge boxes"])

# No 0/O, 1/I/L: the code is read off a screen and typed on the box.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 10
TOKEN_PREFIX = "pse_"
MAX_EVENTS = 2000
MAX_OCCUPANCY = 5000
MAX_SNAPSHOT_BYTES = 5 * 1024 * 1024
FUTURE_TOLERANCE = timedelta(minutes=10)
CAMERA_STATES = ("online", "connecting", "offline", "error", "unconfigured")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def normalise_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def new_pairing_code() -> tuple[str, str]:
    """(code as shown to the user, hash to store)."""
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
    return f"{raw[:5]}-{raw[5:]}", _sha(raw)


def online_window() -> timedelta:
    return timedelta(seconds=max(settings.edge_heartbeat_seconds * 3, 90))


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() + "Z" if dt else None


def _naive_utc(dt: datetime) -> datetime:
    return dt.astimezone(UTC).replace(tzinfo=None) if dt.tzinfo else dt


# ── Dashboard side ───────────────────────────────────────────────


class DeviceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


def device_response(d: EdgeDevice, cameras: List[Camera], code: Optional[str] = None) -> dict:
    now = utcnow()
    online = d.status == EDGE_ACTIVE and d.last_seen_at is not None and now - d.last_seen_at <= online_window()
    reported: Dict[str, dict] = d.camera_status or {}
    cams = []
    for c in cameras:
        r = reported.get(str(c.id)) or {}
        state = r.get("status") or "unknown"
        cams.append({
            "camera_id": str(c.id), "camera_code": c.camera_code, "name": c.name, "camera_type": c.camera_type,
            # A camera can only be live while its box is.
            "status": state if online else ("unknown" if not reported else "offline"),
            "reported_status": state,
            "message": r.get("message"),
            "fps": r.get("fps"),
            "last_frame_at": r.get("last_frame_at"),
            "width": r.get("width"), "height": r.get("height"),
        })
    return {
        "id": str(d.id), "store_id": str(d.store_id), "name": d.name, "status": d.status, "online": online,
        "hostname": d.hostname, "agent_version": d.agent_version,
        "last_seen_at": _iso(d.last_seen_at),
        "last_seen_seconds_ago": round((now - d.last_seen_at).total_seconds()) if d.last_seen_at else None,
        "paired_at": _iso(d.paired_at), "created_at": _iso(d.created_at), "revoked_at": _iso(d.revoked_at),
        "events_received": d.events_received or 0, "last_event_at": _iso(d.last_event_at),
        "stats": d.stats or {},
        "cameras": cams if d.status == EDGE_ACTIVE else [],
        "pairing_code": code,
        "pairing_expires_at": _iso(d.pairing_expires_at) if d.status == EDGE_PENDING else None,
        "pairing_expired": d.status == EDGE_PENDING and (d.pairing_expires_at is None or d.pairing_expires_at < now),
    }


async def _store_cameras(db: AsyncSession, store_id: uuid.UUID) -> List[Camera]:
    return list((await db.execute(
        select(Camera).where(Camera.store_id == store_id, Camera.is_active.is_(True)).order_by(Camera.camera_code)
    )).scalars().all())


async def _device(db: AsyncSession, scope: Scope, device_id: uuid.UUID) -> EdgeDevice:
    device = await db.get(EdgeDevice, device_id)
    if not device or device.org_id != scope.org_id:
        raise HTTPException(404, "Box not found")
    await store_in_scope(db, scope, device.store_id)
    return device


@router.get("/api/stores/{store_id}/edge-devices")
async def list_devices(store: Store = Depends(get_store), db: AsyncSession = Depends(get_db)):
    """Boxes of a store with live status (revoked boxes are left out)."""
    devices = (await db.execute(
        select(EdgeDevice).where(EdgeDevice.store_id == store.id, EdgeDevice.status != EDGE_REVOKED)
        .order_by(EdgeDevice.created_at)
    )).scalars().all()
    cameras = await _store_cameras(db, store.id)
    return {
        "items": [device_response(d, cameras) for d in devices],
        "heartbeat_seconds": settings.edge_heartbeat_seconds,
        "online_window_seconds": int(online_window().total_seconds()),
    }


@router.post("/api/stores/{store_id}/edge-devices", status_code=201)
async def create_device(body: DeviceCreate, request: Request, store: Store = Depends(get_store),
                        scope: Scope = Depends(require_org_admin), db: AsyncSession = Depends(get_db)):
    """Register a box for this store. The pairing code is returned once."""
    code, code_hash = new_pairing_code()
    device = EdgeDevice(
        org_id=store.org_id, store_id=store.id, name=body.name.strip(), status=EDGE_PENDING,
        pairing_code_hash=code_hash, events_received=0, created_by=scope.user.id,
        pairing_expires_at=utcnow() + timedelta(minutes=settings.edge_pairing_minutes),
    )
    db.add(device)
    await db.flush()
    audit.record(db, "edge.create", user=scope.user, target_type="edge_device", target_id=device.id,
                 details={"name": device.name, "store_code": store.store_code}, request=request)
    return device_response(device, [], code)


@router.post("/api/edge-devices/{device_id}/pairing-code")
async def renew_pairing_code(device_id: uuid.UUID, request: Request, scope: Scope = Depends(require_org_admin),
                             db: AsyncSession = Depends(get_db)):
    """New pairing code. Use it when the code expired or the box was replaced:
    the previous box (if any) stops being accepted immediately."""
    device = await _device(db, scope, device_id)
    if device.status == EDGE_REVOKED:
        raise HTTPException(409, "This box was removed. Add a new one.")
    code, code_hash = new_pairing_code()
    device.status = EDGE_PENDING
    device.token_hash = None
    device.pairing_code_hash = code_hash
    device.pairing_expires_at = utcnow() + timedelta(minutes=settings.edge_pairing_minutes)
    audit.record(db, "edge.pairing_code", user=scope.user, target_type="edge_device", target_id=device.id,
                 details={"name": device.name}, request=request)
    return device_response(device, [], code)


@router.post("/api/edge-devices/{device_id}/revoke")
async def revoke_device(device_id: uuid.UUID, request: Request, scope: Scope = Depends(require_org_admin),
                        db: AsyncSession = Depends(get_db)):
    """Remove a box: its token stops working at once. Data it already sent is kept."""
    device = await _device(db, scope, device_id)
    device.status = EDGE_REVOKED
    device.token_hash = None
    device.pairing_code_hash = None
    device.revoked_at = utcnow()
    audit.record(db, "edge.revoke", user=scope.user, target_type="edge_device", target_id=device.id,
                 details={"name": device.name}, request=request)
    return device_response(device, [])


@router.post("/api/edge-devices/{device_id}/snapshot-request/{camera_id}", status_code=202)
async def request_snapshot(device_id: uuid.UUID, camera_id: uuid.UUID, scope: Scope = Depends(require_org_admin),
                           db: AsyncSession = Depends(get_db)):
    """Ask the box for a fresh still image of a camera (delivered with its next heartbeat)."""
    device = await _device(db, scope, device_id)
    if device.status != EDGE_ACTIVE:
        raise HTTPException(409, "The box is not paired")
    camera = await db.get(Camera, camera_id)
    if not camera or camera.store_id != device.store_id:
        raise HTTPException(404, "Camera not found")
    wanted = list(device.snapshot_requests or [])
    if str(camera.id) not in wanted:
        wanted.append(str(camera.id))
    device.snapshot_requests = wanted
    return {"requested": True, "expect_within_seconds": settings.edge_heartbeat_seconds * 2}


# ── Box side ─────────────────────────────────────────────────────


async def current_device(request: Request, db: AsyncSession = Depends(get_db)) -> EdgeDevice:
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if not token.startswith(TOKEN_PREFIX):
        raise HTTPException(401, "Box token required")
    device = (await db.execute(
        select(EdgeDevice).where(EdgeDevice.token_hash == _sha(token), EdgeDevice.status == EDGE_ACTIVE)
    )).scalar_one_or_none()
    if device is None:
        raise HTTPException(401, "This box is not paired (or was removed). Pair it again.")
    request.state.user_id = f"edge:{device.id}"
    return device


class PairRequest(BaseModel):
    code: str = Field(..., min_length=8, max_length=32)
    hostname: Optional[str] = Field(None, max_length=200)
    agent_version: Optional[str] = Field(None, max_length=50)


@router.post("/api/edge/pair")
async def pair(body: PairRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Exchange a pairing code for the box's token (returned once)."""
    rate_limiter.check(f"edge-pair:{client_ip(request)}", 10, 600)
    code = normalise_code(body.code)
    device = None
    if len(code) == CODE_LENGTH:
        device = (await db.execute(
            select(EdgeDevice).where(EdgeDevice.pairing_code_hash == _sha(code), EdgeDevice.status == EDGE_PENDING)
        )).scalar_one_or_none()
    if device is None or device.pairing_expires_at is None or device.pairing_expires_at < utcnow():
        raise HTTPException(400, "Pairing code is wrong or has expired. Create a new code in the dashboard.")
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    device.token_hash = _sha(token)
    device.pairing_code_hash = None
    device.pairing_expires_at = None
    device.status = EDGE_ACTIVE
    device.paired_at = utcnow()
    device.last_seen_at = utcnow()
    device.last_ip = client_ip(request)[:64]
    device.hostname = (body.hostname or "")[:200] or None
    device.agent_version = (body.agent_version or "")[:50] or None
    device.camera_status = None
    store = await db.get(Store, device.store_id)
    audit.record(db, "edge.paired", actor=f"edge:{device.name}", org_id=device.org_id, target_type="edge_device",
                 target_id=device.id, details={"hostname": device.hostname, "store_code": store.store_code},
                 request=request)
    return {"token": token, "device_id": str(device.id), "name": device.name,
            "store": {"id": str(store.id), "store_code": store.store_code, "name": store.name}}


async def build_config(db: AsyncSession, device: EdgeDevice) -> dict:
    store = await db.get(Store, device.store_id)
    cameras = await _store_cameras(db, store.id)
    cams = []
    for c in cameras:
        cfg = await snapshot_config(db, c, None)
        cfg["pipeline"]["analysis_fps"] = settings.edge_analysis_fps
        cams.append({"camera_id": str(c.id), "name": c.name, "has_reference_frame": bool(c.reference_frame_key), **cfg})
    version = hashlib.sha256(json.dumps(
        [{k: v for k, v in c.items() if k != "has_reference_frame"} for c in cams], sort_keys=True, default=str,
    ).encode()).hexdigest()[:16]
    return {
        "device_id": str(device.id),
        "store": {"id": str(store.id), "store_code": store.store_code, "name": store.name, "timezone": store.timezone},
        "cameras": cams,
        "config_version": version,
        "heartbeat_seconds": settings.edge_heartbeat_seconds,
        "max_events_per_request": MAX_EVENTS,
    }


@router.get("/api/edge/config")
async def get_config(device: EdgeDevice = Depends(current_device), db: AsyncSession = Depends(get_db)):
    """Cameras, zones, entry lines and pipeline settings for this box's store.
    Stream addresses are not part of it: they are configured on the box."""
    return await build_config(db, device)


class CameraHealth(BaseModel):
    camera_id: uuid.UUID
    status: str = Field(..., max_length=20)
    message: Optional[str] = Field(None, max_length=300)
    fps: Optional[float] = Field(None, ge=0, le=240)
    last_frame_at: Optional[datetime] = None
    width: Optional[int] = Field(None, ge=0, le=20000)
    height: Optional[int] = Field(None, ge=0, le=20000)
    # Seconds of stream analysed since the previous heartbeat.
    analysed_seconds: float = Field(0.0, ge=0, le=3600)


class Heartbeat(BaseModel):
    agent_version: Optional[str] = Field(None, max_length=50)
    hostname: Optional[str] = Field(None, max_length=200)
    config_version: Optional[str] = Field(None, max_length=32)
    cameras: List[CameraHealth] = Field(default_factory=list, max_length=64)
    stats: Dict[str, float | int | str | None] = Field(default_factory=dict)


@router.post("/api/edge/heartbeat")
async def heartbeat(body: Heartbeat, request: Request, device: EdgeDevice = Depends(current_device),
                    db: AsyncSession = Depends(get_db)):
    now = utcnow()
    own = {c.id for c in await _store_cameras(db, device.store_id)}
    status: Dict[str, dict] = {}
    hour = now.replace(minute=0, second=0, microsecond=0)
    for cam in body.cameras:
        if cam.camera_id not in own:
            continue
        status[str(cam.camera_id)] = {
            "status": cam.status if cam.status in CAMERA_STATES else "error",
            "message": cam.message, "fps": cam.fps,
            "last_frame_at": _iso(_naive_utc(cam.last_frame_at)) if cam.last_frame_at else None,
            "width": cam.width, "height": cam.height,
        }
        if cam.analysed_seconds > 0:
            row = await db.get(EdgeCoverage, (cam.camera_id, hour))
            if row is None:
                db.add(EdgeCoverage(camera_id=cam.camera_id, hour=hour, store_id=device.store_id,
                                    seconds=cam.analysed_seconds))
            else:
                # An hour cannot hold more than an hour of stream.
                row.seconds = min(3600.0, row.seconds + cam.analysed_seconds)
    device.camera_status = status
    device.last_seen_at = now
    device.last_ip = client_ip(request)[:64]
    if body.agent_version:
        device.agent_version = body.agent_version
    if body.hostname:
        device.hostname = body.hostname
    device.stats = {k: v for k, v in list(body.stats.items())[:20]}
    # A still image is only ever sent because an administrator asked for it.
    wanted = [c for c in (device.snapshot_requests or []) if uuid.UUID(c) in own]
    config = await build_config(db, device)
    return {
        "server_time": _iso(now),
        "config_version": config["config_version"],
        "config_changed": body.config_version != config["config_version"],
        "snapshot_requests": wanted,
        "heartbeat_seconds": settings.edge_heartbeat_seconds,
    }


class EdgeEvent(BaseModel):
    key: str = Field(..., min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    camera_id: uuid.UUID
    event_type: str = Field(..., max_length=50)
    timestamp: datetime
    track: str = Field(..., min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    zone_id: Optional[str] = Field(None, max_length=100)
    zone_name: Optional[str] = Field(None, max_length=200)
    zone_type: Optional[str] = Field(None, max_length=50)
    dwell_seconds: Optional[float] = Field(None, ge=0)
    queue_wait_seconds: Optional[float] = Field(None, ge=0)
    queue_abandoned: Optional[bool] = None
    confidence: Optional[float] = Field(None, ge=0, le=1)
    box: Optional[List[float]] = Field(None, min_length=4, max_length=4)


class EdgeOccupancy(BaseModel):
    camera_id: uuid.UUID
    zone_name: str = Field(..., max_length=200)
    zone_type: str = Field(..., max_length=50)
    timestamp: datetime
    count: int = Field(..., ge=0, le=10000)


class EdgeBatch(BaseModel):
    events: List[EdgeEvent] = Field(default_factory=list)
    occupancy: List[EdgeOccupancy] = Field(default_factory=list)


@router.post("/api/edge/events")
async def receive_events(body: EdgeBatch, device: EdgeDevice = Depends(current_device),
                         db: AsyncSession = Depends(get_db)):
    """Events and queue-length samples from live streams. Safe to resend:
    events are unique on their key, samples on camera, zone and time."""
    if len(body.events) > MAX_EVENTS or len(body.occupancy) > MAX_OCCUPANCY:
        raise HTTPException(413, f"At most {MAX_EVENTS} events and {MAX_OCCUPANCY} samples per request")
    cameras = {c.id: c for c in await _store_cameras(db, device.store_id)}
    limit = utcnow() + FUTURE_TOLERANCE
    prefix = f"edge-{device.id.hex[:12]}-"
    rows = []
    skipped = 0
    touched = set()
    for e in body.events:
        cam = cameras.get(e.camera_id)
        ts = _naive_utc(e.timestamp)
        if cam is None or e.event_type not in EVENT_TYPES or ts > limit:
            skipped += 1
            continue
        customer = f"{cam.camera_code}-{e.track}"[:100]
        touched.add(customer)
        box = e.box
        rows.append({
            "store_id": device.store_id, "event_type": e.event_type, "customer_id": customer,
            "camera_id": cam.camera_code, "zone_id": e.zone_id, "zone_name": e.zone_name, "zone_type": e.zone_type,
            "timestamp": ts, "source": "edge", "event_key": prefix + e.key, "confidence": e.confidence,
            "bbox_x": round(box[0], 4) if box else None, "bbox_y": round(box[1], 4) if box else None,
            "bbox_w": round(box[2] - box[0], 4) if box else None, "bbox_h": round(box[3] - box[1], 4) if box else None,
            "is_staff": False, "dwell_seconds": e.dwell_seconds, "queue_wait_seconds": e.queue_wait_seconds,
            "queue_abandoned": e.queue_abandoned, "metadata_json": {"edge_device": str(device.id)},
        })
    inserted = await insert_events(db, rows)
    if inserted:
        await journey_service.rebuild_for_customers(db, device.store_id, touched, "edge")
        device.events_received = (device.events_received or 0) + inserted
        device.last_event_at = utcnow()

    samples = 0
    wanted = []
    for o in body.occupancy:
        cam = cameras.get(o.camera_id)
        ts = _naive_utc(o.timestamp).replace(microsecond=0)
        if cam is None or ts > limit:
            skipped += 1
            continue
        wanted.append((cam.camera_code, o.zone_name, ts, o.zone_type, o.count))
    if wanted:
        times = [w[2] for w in wanted]
        existing = {
            (c, z, t) for c, z, t in (await db.execute(
                select(OccupancySample.camera_code, OccupancySample.zone_name, OccupancySample.timestamp).where(
                    OccupancySample.store_id == device.store_id, OccupancySample.job_id.is_(None),
                    OccupancySample.timestamp >= min(times), OccupancySample.timestamp <= max(times))
            )).all()
        }
        for code, zone, ts, ztype, count in wanted:
            if (code, zone, ts) in existing:
                continue
            existing.add((code, zone, ts))
            db.add(OccupancySample(store_id=device.store_id, job_id=None, camera_code=code, zone_name=zone,
                                   zone_type=ztype, timestamp=ts, count=count))
            samples += 1
    device.last_seen_at = utcnow()
    return {"received": len(body.events), "inserted": inserted, "duplicates": len(rows) - inserted,
            "skipped": skipped, "samples": samples}


def jpeg_size(data: bytes) -> Optional[tuple[int, int]]:
    """(width, height) from a JPEG's start-of-frame marker, without decoding it."""
    if not data.startswith(b"\xff\xd8"):
        return None
    i, n = 2, len(data)
    while i + 9 < n:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(data[i + 7:i + 9], "big"), int.from_bytes(data[i + 5:i + 7], "big")
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        i += 2 + int.from_bytes(data[i + 2:i + 4], "big")
    return None


@router.put("/api/edge/cameras/{camera_id}/snapshot", status_code=204)
async def upload_snapshot(camera_id: uuid.UUID, request: Request, device: EdgeDevice = Depends(current_device),
                          db: AsyncSession = Depends(get_db)):
    """One still image (JPEG) of a camera, used to draw its zones in the
    dashboard. Replaces the previous still; it is the only picture the box
    sends, and it is only accepted while an administrator's request is open."""
    camera = await db.get(Camera, camera_id)
    if not camera or camera.store_id != device.store_id:
        raise HTTPException(404, "Camera not found")
    if str(camera.id) not in (device.snapshot_requests or []):
        raise HTTPException(409, "No still image was asked for")
    data = b""
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_SNAPSHOT_BYTES:
            raise HTTPException(413, "Image too large (max 5 MB)")
    size = jpeg_size(data)
    if size is None:
        raise HTTPException(415, "Send a JPEG image")
    key = f"frames/{camera.id}/live-{uuid.uuid4().hex[:8]}.jpg"
    get_storage().put_bytes(key, data, "image/jpeg")
    set_reference_frame(camera, key)
    camera.reference_frame_width, camera.reference_frame_height = size
    device.snapshot_requests = [c for c in (device.snapshot_requests or []) if c != str(camera.id)]
    return Response(status_code=204)
