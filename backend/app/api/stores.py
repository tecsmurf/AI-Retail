"""Stores, cameras, and zone configuration."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_camera, get_store
from app.database import get_db, utcnow
from app.models.store import Camera, Store, Zone
from app.models.user import User
from app.schemas.store import (
    CameraConfigIn,
    CameraConfigResponse,
    CameraCreate,
    CameraResponse,
    CameraUpdate,
    StoreCreate,
    StoreResponse,
    StoreUpdate,
    ZoneResponse,
)
from app.security import current_user, require_admin
from app.storage import StorageError, get_storage

router = APIRouter(tags=["Stores"])

MAX_FRAME_BYTES = 10 * 1024 * 1024


def camera_response(c: Camera) -> CameraResponse:
    return CameraResponse(
        id=c.id, store_id=c.store_id, camera_code=c.camera_code, name=c.name, camera_type=c.camera_type,
        is_active=c.is_active, resolution_width=c.resolution_width, resolution_height=c.resolution_height,
        fps=c.fps, entry_line=c.entry_line, has_reference_frame=bool(c.reference_frame_key),
        reference_frame_width=c.reference_frame_width, reference_frame_height=c.reference_frame_height,
        config_version=c.config_version or 1,
    )


def zone_response(z: Zone) -> ZoneResponse:
    return ZoneResponse(
        id=z.id, zone_code=z.zone_code, name=z.name, zone_type=z.zone_type, is_revenue_zone=z.is_revenue_zone,
        polygon=z.polygon_points if isinstance(z.polygon_points, list) else None, camera_id=z.camera_id,
        priority=z.priority or 0, color=z.color, display_order=z.display_order or 0,
    )


async def _store_response(db: AsyncSession, store: Store) -> StoreResponse:
    cams = (await db.execute(select(func.count()).where(Camera.store_id == store.id))).scalar() or 0
    zones = (await db.execute(select(func.count()).where(Zone.store_id == store.id))).scalar() or 0
    data = StoreResponse.model_validate(store)
    data.camera_count = cams
    data.zone_count = zones
    return data


@router.get("/api/stores", response_model=List[StoreResponse])
async def list_stores(include_inactive: bool = False, _: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    q = select(Store).order_by(Store.store_code)
    if not include_inactive:
        q = q.where(Store.is_active.is_(True))
    stores = (await db.execute(q)).scalars().all()
    return [await _store_response(db, s) for s in stores]


@router.post("/api/stores", response_model=StoreResponse, status_code=201)
async def create_store(body: StoreCreate, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    if (await db.execute(select(Store).where(Store.store_code == body.store_code))).scalar_one_or_none():
        raise HTTPException(409, "store_code already exists")
    store = Store(**body.model_dump(), is_active=True)
    db.add(store)
    await db.flush()
    return await _store_response(db, store)


@router.get("/api/stores/{store_id}", response_model=StoreResponse)
async def get_store_detail(store: Store = Depends(get_store), _: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await _store_response(db, store)


@router.patch("/api/stores/{store_id}", response_model=StoreResponse)
async def update_store(body: StoreUpdate, store: Store = Depends(get_store), _: User = Depends(require_admin),
                       db: AsyncSession = Depends(get_db)):
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(store, k, v)
    store.updated_at = utcnow()
    await db.flush()
    return await _store_response(db, store)


@router.get("/api/stores/{store_id}/cameras", response_model=List[CameraResponse])
async def list_cameras(store: Store = Depends(get_store), _: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    cams = (await db.execute(select(Camera).where(Camera.store_id == store.id).order_by(Camera.camera_code))).scalars().all()
    return [camera_response(c) for c in cams]


@router.post("/api/stores/{store_id}/cameras", response_model=CameraResponse, status_code=201)
async def create_camera(body: CameraCreate, store: Store = Depends(get_store), _: User = Depends(require_admin),
                        db: AsyncSession = Depends(get_db)):
    dup = (await db.execute(
        select(Camera).where(Camera.store_id == store.id, Camera.camera_code == body.camera_code)
    )).scalar_one_or_none()
    if dup:
        raise HTTPException(409, "camera_code already exists in this store")
    cam = Camera(store_id=store.id, is_active=True, config_version=1, **body.model_dump())
    db.add(cam)
    await db.flush()
    return camera_response(cam)


@router.patch("/api/cameras/{camera_id}", response_model=CameraResponse)
async def update_camera(body: CameraUpdate, camera: Camera = Depends(get_camera), _: User = Depends(require_admin)):
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(camera, k, v)
    return camera_response(camera)


@router.get("/api/stores/{store_id}/zones", response_model=List[ZoneResponse])
async def list_store_zones(store: Store = Depends(get_store), _: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    zones = (await db.execute(select(Zone).where(Zone.store_id == store.id).order_by(Zone.display_order, Zone.name))).scalars().all()
    return [zone_response(z) for z in zones]


@router.get("/api/cameras/{camera_id}/config", response_model=CameraConfigResponse)
async def get_camera_config(camera: Camera = Depends(get_camera), _: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    zones = (await db.execute(select(Zone).where(Zone.camera_id == camera.id).order_by(Zone.display_order))).scalars().all()
    return CameraConfigResponse(camera=camera_response(camera), zones=[zone_response(z) for z in zones])


@router.put("/api/cameras/{camera_id}/config", response_model=CameraConfigResponse)
async def put_camera_config(body: CameraConfigIn, camera: Camera = Depends(get_camera), _: User = Depends(require_admin),
                            db: AsyncSession = Depends(get_db)):
    """Replace this camera's zones and entry line. Polygons are validated
    (>= 3 points, inside [0,1], non-zero area, not self-intersecting). The
    camera's config_version is incremented; jobs record the version they used.
    Existing events keep the zone names they were generated with."""
    if body.entry_line is not None and camera.camera_type not in ("entrance", "other"):
        raise HTTPException(422, "Entry lines are only allowed on entrance cameras")
    existing = {z.zone_code: z for z in (await db.execute(select(Zone).where(Zone.camera_id == camera.id))).scalars().all()}
    other_names = {
        n for (n,) in (await db.execute(
            select(Zone.name).where(Zone.store_id == camera.store_id, Zone.camera_id != camera.id, Zone.camera_id.is_not(None))
        )).all()
    }
    keep = set()
    for order, zin in enumerate(body.zones):
        if zin.name in other_names:
            # Zone names are the analytics key; the same name on two cameras
            # would merge their visits. Allowed only deliberately via distinct names.
            raise HTTPException(422, f"Zone name '{zin.name}' is already used by another camera in this store")
        z = existing.get(zin.zone_code)
        if z is None:
            z = Zone(store_id=camera.store_id, camera_id=camera.id, zone_code=zin.zone_code)
            db.add(z)
        z.name = zin.name
        z.zone_type = zin.zone_type
        z.polygon_points = zin.polygon
        z.priority = zin.priority
        z.is_revenue_zone = zin.is_revenue_zone
        z.color = zin.color
        z.display_order = order
        z.updated_at = utcnow()
        keep.add(zin.zone_code)
    for code, z in existing.items():
        if code not in keep:
            await db.delete(z)
    camera.entry_line = body.entry_line.model_dump() if body.entry_line else None
    camera.config_version = (camera.config_version or 1) + 1
    await db.flush()
    zones = (await db.execute(select(Zone).where(Zone.camera_id == camera.id).order_by(Zone.display_order))).scalars().all()
    return CameraConfigResponse(camera=camera_response(camera), zones=[zone_response(z) for z in zones])


@router.get("/api/cameras/{camera_id}/reference-frame")
async def get_reference_frame(camera: Camera = Depends(get_camera), _: User = Depends(current_user)):
    if not camera.reference_frame_key:
        raise HTTPException(404, "No reference frame yet. Process a video from this camera or upload a still image.")
    try:
        data = get_storage().get_bytes(camera.reference_frame_key)
    except StorageError:
        raise HTTPException(404, "Reference frame missing from storage")
    return Response(content=data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})


@router.post("/api/cameras/{camera_id}/reference-frame", response_model=CameraResponse)
async def upload_reference_frame(
    file: UploadFile = File(...), camera: Camera = Depends(get_camera), _: User = Depends(require_admin)
):
    data = await file.read(MAX_FRAME_BYTES + 1)
    if len(data) > MAX_FRAME_BYTES:
        raise HTTPException(413, "Image too large (max 10 MB)")
    try:
        import cv2
        import numpy as np
    except ImportError:  # API image without OpenCV: accept JPEG as-is
        if not data.startswith(b"\xff\xd8"):
            raise HTTPException(415, "Upload a JPEG image")
        key = f"frames/{camera.id}/uploaded-{uuid.uuid4().hex[:8]}.jpg"
        get_storage().put_bytes(key, data, "image/jpeg")
        camera.reference_frame_key = key
        return camera_response(camera)
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(415, "Not a decodable image")
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    key = f"frames/{camera.id}/uploaded-{uuid.uuid4().hex[:8]}.jpg"
    get_storage().put_bytes(key, buf.tobytes(), "image/jpeg")
    camera.reference_frame_key = key
    camera.reference_frame_height, camera.reference_frame_width = img.shape[:2]
    return camera_response(camera)


__all__ = ["router", "camera_response", "zone_response", "update"]
