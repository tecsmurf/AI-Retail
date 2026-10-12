"""Video upload (presigned, direct to object storage) and processing jobs.

Upload flow (works from a phone browser):

1. ``POST /api/videos`` with filename, size, store, camera -> returns the
   video record plus upload instructions (a presigned S3 PUT URL, or an API
   URL when STORAGE_BACKEND=local).
2. The browser PUTs the file to that URL (progress events come from XHR).
3. ``POST /api/videos/{id}/complete`` -> the API verifies the object exists
   with the declared size and (by default) queues a processing job.
4. Poll ``GET /api/jobs/{id}``; the worker does the rest. Closing the browser
   at any point after step 3 does not affect processing.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.cv.pipeline import PipelineConfig
from app.database import get_db, utcnow
from app.models.jobs import (
    JOB_QUEUED,
    JOB_RUNNING,
    VIDEO_PENDING,
    VIDEO_UPLOADED,
    ProcessingJob,
    VideoAsset,
)
from app.models.store import Camera, Store, Zone
from app.models.user import User
from app.schemas.jobs import (
    JobCreate,
    JobPage,
    JobResponse,
    PipelineOverrides,
    UploadInstructions,
    VideoComplete,
    VideoCreate,
    VideoCreated,
    VideoResponse,
)
from app.security import client_ip, current_user, rate_limiter, require_admin
from app.services import job_service
from app.storage import StorageError, get_storage, safe_filename

router = APIRouter(tags=["Videos & Jobs"])


# ── Config snapshot ──────────────────────────────────────────────


async def snapshot_config(db: AsyncSession, camera: Camera, overrides: Optional[PipelineOverrides]) -> dict:
    zones = (await db.execute(select(Zone).where(Zone.camera_id == camera.id).order_by(Zone.display_order))).scalars().all()
    pcfg = PipelineConfig(analysis_fps=settings.analysis_fps)
    if overrides:
        o = overrides.model_dump(exclude_none=True)
        for k in ("analysis_fps", "detector_confidence"):
            if k in o:
                setattr(pcfg, k, o[k])
        for k in ("track_activation_threshold", "lost_track_seconds"):
            if k in o:
                setattr(pcfg.tracker, k, o[k])
        for k in ("zone_enter_min_s", "zone_exit_grace_s", "queue_enter_min_s"):
            if k in o:
                setattr(pcfg.engine, k, o[k])
    return {
        "camera_code": camera.camera_code,
        "camera_type": camera.camera_type,
        "camera_config_version": camera.config_version or 1,
        "zones": [
            {"id": str(z.id), "name": z.name, "zone_type": z.zone_type, "polygon": z.polygon_points,
             "priority": z.priority or 0}
            for z in zones if isinstance(z.polygon_points, list) and len(z.polygon_points) >= 3
        ],
        "entry_line": camera.entry_line,
        "pipeline": pcfg.as_dict(),
        "model": settings.yolo_model,
        "imgsz": settings.yolo_imgsz,
    }


async def create_job(db: AsyncSession, video: VideoAsset, user: Optional[User], overrides=None,
                     allow_duplicate: bool = False) -> ProcessingJob:
    active = (await db.execute(
        select(ProcessingJob).where(ProcessingJob.video_id == video.id,
                                    ProcessingJob.status.in_([JOB_QUEUED, JOB_RUNNING]))
    )).scalar_one_or_none()
    if active:
        raise HTTPException(409, f"Video already has an active job ({active.id})")
    camera = await db.get(Camera, video.camera_id)
    config = await snapshot_config(db, camera, overrides)
    config["allow_duplicate"] = allow_duplicate
    job = ProcessingJob(
        store_id=video.store_id, camera_id=video.camera_id, video_id=video.id, status=JOB_QUEUED,
        cancel_requested=False, progress=0.0, stage="queued", attempts=0,
        max_attempts=settings.job_max_attempts, config=config, created_by=user.id if user else None,
    )
    db.add(job)
    await db.flush()
    return job


def job_response(job: ProcessingJob, video: Optional[VideoAsset] = None, camera_code: Optional[str] = None) -> JobResponse:
    r = JobResponse.model_validate(job)
    r.video_filename = video.original_filename if video else None
    r.camera_code = camera_code or (job.config or {}).get("camera_code")
    return r


# ── Videos ───────────────────────────────────────────────────────


@router.post("/api/videos", response_model=VideoCreated, status_code=201)
async def create_video(body: VideoCreate, request: Request, user: User = Depends(require_admin),
                       db: AsyncSession = Depends(get_db)):
    rate_limiter.check(f"upload:{user.id}:{client_ip(request)}", settings.upload_rate_limit_per_hour, 3600)
    ext = os.path.splitext(body.filename)[1].lower()
    if ext not in settings.video_extensions:
        raise HTTPException(415, f"Unsupported file type '{ext}'. Allowed: {', '.join(settings.video_extensions)}")
    if not body.content_type.startswith("video/") and body.content_type != "application/octet-stream":
        raise HTTPException(415, "content_type must be a video/* type")
    if body.size_bytes > settings.max_upload_bytes:
        raise HTTPException(413, f"File is larger than the {settings.max_upload_bytes // (1024**2)} MB limit")
    store = await db.get(Store, body.store_id)
    camera = await db.get(Camera, body.camera_id)
    if not store or not camera or camera.store_id != store.id:
        raise HTTPException(404, "Store or camera not found (camera must belong to the store)")
    video_id = uuid.uuid4()
    key = f"uploads/{store.id}/{video_id}/{safe_filename(body.filename)}"
    video = VideoAsset(
        id=video_id, store_id=store.id, camera_id=camera.id, storage_key=key,
        original_filename=body.filename[:300], content_type=body.content_type, size_bytes=body.size_bytes,
        status=VIDEO_PENDING, recorded_start=body.recorded_start or utcnow(),
        recorded_start_assumed=body.recorded_start is None, created_by=user.id,
    )
    db.add(video)
    await db.flush()
    try:
        up = get_storage().presign_upload(key, body.content_type, str(video_id))
    except StorageError as exc:
        raise HTTPException(503, f"Storage unavailable: {exc}")
    return VideoCreated(
        video=VideoResponse.model_validate(video),
        upload=UploadInstructions(method=up.method, url=up.url, headers=up.headers, direct_to_storage=up.direct),
    )


@router.put("/api/videos/{video_id}/content", status_code=204)
async def upload_content(video_id: uuid.UUID, request: Request, user: User = Depends(require_admin),
                         db: AsyncSession = Depends(get_db)):
    """Upload target when STORAGE_BACKEND=local (development / single host).
    Streams to disk in 1 MB chunks and enforces the declared size."""
    storage = get_storage()
    if storage.name != "local":
        raise HTTPException(400, "Upload directly to object storage using the presigned URL")
    video = await db.get(VideoAsset, video_id)
    if not video:
        raise HTTPException(404, "Video not found")
    if video.status != VIDEO_PENDING:
        raise HTTPException(409, f"Video is already {video.status}")
    limit = min(video.size_bytes or settings.max_upload_bytes, settings.max_upload_bytes)
    written = 0
    tmp = tempfile.NamedTemporaryFile(delete=False, dir=storage.root, suffix=".upload")
    try:
        with tmp:
            async for chunk in request.stream():
                written += len(chunk)
                if written > limit:
                    raise HTTPException(413, "Upload is larger than declared")
                tmp.write(chunk)
        if written != video.size_bytes:
            raise HTTPException(400, f"Received {written} bytes but {video.size_bytes} were declared")
        storage.put_file(video.storage_key, tmp.name)
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
    return Response(status_code=204)


@router.post("/api/videos/{video_id}/complete", response_model=VideoCreated | JobResponse)
async def complete_upload(video_id: uuid.UUID, body: VideoComplete = VideoComplete(), user: User = Depends(require_admin),
                          db: AsyncSession = Depends(get_db)):
    video = await db.get(VideoAsset, video_id)
    if not video:
        raise HTTPException(404, "Video not found")
    if video.status == VIDEO_PENDING:
        size = get_storage().size(video.storage_key)
        if size is None:
            raise HTTPException(409, "The file has not been uploaded yet")
        if video.size_bytes and size != video.size_bytes:
            raise HTTPException(409, f"Uploaded size {size} does not match declared size {video.size_bytes}")
        video.status = VIDEO_UPLOADED
        video.uploaded_at = utcnow()
        video.size_bytes = size
    elif video.status != VIDEO_UPLOADED:
        raise HTTPException(409, f"Video is {video.status}")
    if body.start_processing:
        overrides = PipelineOverrides(**body.pipeline) if body.pipeline else None
        job = await create_job(db, video, user, overrides)
        return job_response(job, video)
    return VideoCreated(video=VideoResponse.model_validate(video),
                        upload=UploadInstructions(method="NONE", url="", headers={}, direct_to_storage=False))


@router.get("/api/videos", response_model=List[VideoResponse])
async def list_videos(store_id: uuid.UUID, limit: int = Query(50, ge=1, le=200), _: User = Depends(current_user),
                      db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        select(VideoAsset).where(VideoAsset.store_id == store_id).order_by(VideoAsset.created_at.desc()).limit(limit)
    )
    return list(rows.scalars().all())


# ── Jobs ─────────────────────────────────────────────────────────


@router.post("/api/jobs", response_model=JobResponse, status_code=201)
async def submit_job(body: JobCreate, request: Request, user: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rate_limiter.check(f"jobs:{user.id}:{client_ip(request)}", settings.upload_rate_limit_per_hour, 3600)
    video = await db.get(VideoAsset, body.video_id)
    if not video:
        raise HTTPException(404, "Video not found")
    if video.status != VIDEO_UPLOADED:
        raise HTTPException(409, f"Video is {video.status}; finish the upload first")
    job = await create_job(db, video, user, body.pipeline, body.allow_duplicate)
    return job_response(job, video)


@router.get("/api/jobs", response_model=JobPage)
async def list_jobs(
    store_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(ProcessingJob, VideoAsset).join(VideoAsset, VideoAsset.id == ProcessingJob.video_id)
    if store_id:
        q = q.where(ProcessingJob.store_id == store_id)
    if status:
        q = q.where(ProcessingJob.status == status)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    rows = (await db.execute(q.order_by(ProcessingJob.created_at.desc()).limit(limit).offset(offset))).all()
    return JobPage(total=total, items=[job_response(j, v) for j, v in rows])


async def _job(db: AsyncSession, job_id: uuid.UUID) -> ProcessingJob:
    job = await db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.get("/api/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: uuid.UUID, _: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    job = await _job(db, job_id)
    return job_response(job, await db.get(VideoAsset, job.video_id))


@router.post("/api/jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: uuid.UUID, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    job = await _job(db, job_id)
    try:
        await job_service.request_cancel(db, job)
    except job_service.JobStateError as exc:
        raise HTTPException(409, str(exc))
    return job_response(job, await db.get(VideoAsset, job.video_id))


@router.post("/api/jobs/{job_id}/retry", response_model=JobResponse)
async def retry_job(job_id: uuid.UUID, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    job = await _job(db, job_id)
    video = await db.get(VideoAsset, job.video_id)
    if video.status != VIDEO_UPLOADED:
        raise HTTPException(409, f"The source video is {video.status}; upload it again")
    try:
        await job_service.retry(db, job)
    except job_service.JobStateError as exc:
        raise HTTPException(409, str(exc))
    return job_response(job, video)


@router.get("/api/jobs/{job_id}/artifacts/{name}")
async def get_artifact(job_id: uuid.UUID, name: str, _: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Inspect detections/tracks: annotated snapshots (JPEG) or tracks.jsonl.gz."""
    job = await _job(db, job_id)
    arts = job.artifacts or {}
    keys = list(arts.get("snapshots", [])) + ([arts["tracks"]] if arts.get("tracks") else [])
    key = next((k for k in keys if k.rsplit("/", 1)[-1] == name), None)
    if not key:
        raise HTTPException(404, "Artifact not found")
    try:
        data = get_storage().get_bytes(key)
    except StorageError:
        raise HTTPException(404, "Artifact missing from storage")
    media = "image/jpeg" if name.endswith(".jpg") else "application/gzip"
    headers = {"Cache-Control": "private, max-age=3600"}
    if media == "application/gzip":
        headers["Content-Disposition"] = f'attachment; filename="{job_id}-{name}"'
    return StreamingResponse(iter([data]), media_type=media, headers=headers)
