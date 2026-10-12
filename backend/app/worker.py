"""Video-processing worker.

Run with ``python -m app.worker``. Deploy it as its own service (it needs the
CV dependencies and more memory than the API). Any number of workers can run
against the same database; each claims one job at a time.

Durability guarantees
* Job state lives in PostgreSQL; source videos and artifacts in object
  storage. A worker restart never loses queued work.
* Running jobs heartbeat every few seconds. If a worker dies, another worker
  (or the same one after restart) re-queues the job once its heartbeat is
  older than JOB_STALE_AFTER_SECONDS, up to JOB_MAX_ATTEMPTS attempts.
* On SIGTERM (redeploy) the current job is stopped and immediately re-queued
  without consuming an attempt.
* Results are written in one transaction: the job's previous partial output
  is deleted and replaced, so retries never duplicate events.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import signal
import socket
import tempfile
import threading
import time
import traceback
import uuid
from datetime import timedelta
from typing import Dict, List, Optional

import structlog
from sqlalchemy import delete, insert, select

from app.config import settings
from app.database import async_session, utcnow
from app.logging_setup import configure_logging
from app.models.event import CustomerJourney, Event
from app.models.jobs import (
    JOB_CANCELLED,
    JOB_COMPLETED,
    JOB_QUEUED,
    JOB_RUNNING,
    VIDEO_DELETED,
    VIDEO_UPLOADED,
    OccupancySample,
    ProcessingJob,
    VideoAsset,
    WorkerHeartbeat,
)
from app.models.store import Camera
from app.services import job_service, journey_service
from app.storage import StorageError, get_storage

log = structlog.get_logger("worker")


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _rss_mb() -> Optional[float]:
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024.0, 1)
    except OSError:
        return None
    return None


def build_event_rows(job: ProcessingJob, camera: Camera, video: VideoAsset, events) -> List[Dict]:
    base = video.recorded_start
    rows = []
    for e in events:
        box = e.box
        rows.append({
            "id": uuid.uuid4(),
            "store_id": job.store_id,
            "event_type": e.event_type,
            "customer_id": f"{camera.camera_code}-{video.id.hex[:6]}-T{e.track_id}",
            "camera_id": camera.camera_code,
            "zone_id": e.zone_id,
            "zone_name": e.zone_name,
            "zone_type": e.zone_type,
            "timestamp": base + timedelta(seconds=e.t),
            "source": "cv",
            "event_key": e.key(str(job.id)),
            "job_id": job.id,
            "track_id": e.track_id,
            "video_offset_seconds": round(e.t, 3),
            "confidence": e.confidence,
            "bbox_x": round(box[0], 4) if box else None,
            "bbox_y": round(box[1], 4) if box else None,
            "bbox_w": round(box[2] - box[0], 4) if box else None,
            "bbox_h": round(box[3] - box[1], 4) if box else None,
            "is_staff": False,
            "queue_wait_seconds": e.queue_wait_seconds,
            "queue_abandoned": e.queue_abandoned,
            "dwell_seconds": e.dwell_seconds,
            "metadata_json": e.meta or None,
            "created_at": utcnow(),
        })
    return rows


class Worker:
    def __init__(self, worker_id: Optional[str] = None, detector_factory=None) -> None:
        # detector_factory returns a loaded-on-demand detector; tests inject a fake.
        self.detector_factory = detector_factory
        self.worker_id = worker_id or f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self.stopping = threading.Event()
        self.current_job: Optional[uuid.UUID] = None
        self.jobs_completed = 0
        self.jobs_failed = 0
        self.model_loaded = False
        self.model_error: Optional[str] = None
        self.device: Optional[str] = None
        self._last_stale_check = 0.0
        self._last_retention = 0.0

    # ── heartbeats ───────────────────────────────────────────────

    async def write_heartbeat(self) -> None:
        async with async_session() as db:
            hb = await db.get(WorkerHeartbeat, self.worker_id)
            if hb is None:
                hb = WorkerHeartbeat(worker_id=self.worker_id, hostname=socket.gethostname(), started_at=utcnow(),
                                     jobs_completed=0, jobs_failed=0, model_loaded=False)
                db.add(hb)
            hb.last_seen_at = utcnow()
            hb.current_job_id = self.current_job
            hb.model_loaded = self.model_loaded
            hb.model_error = self.model_error
            hb.device = self.device
            hb.rss_mb = _rss_mb()
            hb.jobs_completed = self.jobs_completed
            hb.jobs_failed = self.jobs_failed
            hb.version = settings.app_version
            await db.commit()

    async def heartbeat_loop(self) -> None:
        while not self.stopping.is_set():
            try:
                await self.write_heartbeat()
            except Exception as exc:  # noqa: BLE001
                log.warning("heartbeat_failed", error=str(exc))
            await asyncio.sleep(settings.worker_heartbeat_seconds)

    # ── main loop ────────────────────────────────────────────────

    def _detector(self):
        if self.detector_factory is not None:
            return self.detector_factory()
        from app.cv.detector import get_detector

        return get_detector()

    def load_model(self) -> None:
        try:
            det = self._detector()
            det.load()
            self.model_loaded = True
            self.model_error = None
            self.device = det.device
            log.info("model_loaded", model=det.model_path, sha256=det.model_sha256, device=det.device)
        except Exception as exc:  # noqa: BLE001
            self.model_loaded = False
            self.model_error = str(exc)[:500]
            log.error("model_load_failed", error=str(exc))

    async def run(self, once: bool = False) -> None:
        log.info("worker_starting", worker_id=self.worker_id)
        await asyncio.to_thread(self.load_model)
        hb_task = asyncio.create_task(self.heartbeat_loop())
        try:
            while not self.stopping.is_set():
                await self.maintenance()
                if not self.model_loaded:
                    # Do not claim jobs we cannot run; retry loading periodically.
                    await asyncio.sleep(30)
                    await asyncio.to_thread(self.load_model)
                    continue
                async with async_session() as db:
                    job = await job_service.claim_next(db, self.worker_id)
                if job is None:
                    if once:
                        break
                    await asyncio.sleep(settings.worker_poll_seconds)
                    continue
                await self.process(job.id)
                if once:
                    break
        finally:
            self.stopping.set()
            hb_task.cancel()
            try:
                await self.write_heartbeat()
            except Exception:  # noqa: BLE001
                pass

    async def maintenance(self) -> None:
        now = time.monotonic()
        if now - self._last_stale_check > 30:
            self._last_stale_check = now
            async with async_session() as db:
                recovered = await job_service.requeue_stale(db)
            if recovered:
                log.warning("stale_jobs_recovered", jobs=[str(j) for j in recovered])
        if now - self._last_retention > 3600:
            self._last_retention = now
            try:
                await self.apply_retention()
            except Exception as exc:  # noqa: BLE001
                log.warning("retention_failed", error=str(exc))

    async def apply_retention(self) -> None:
        """Delete source videos older than VIDEO_RETENTION_DAYS that no queued
        or running job needs. Events, journeys and job records are kept."""
        if settings.video_retention_days <= 0:
            return
        cutoff = utcnow() - timedelta(days=settings.video_retention_days)
        async with async_session() as db:
            busy = select(ProcessingJob.video_id).where(ProcessingJob.status.in_([JOB_QUEUED, JOB_RUNNING]))
            videos = (
                await db.execute(
                    select(VideoAsset).where(
                        VideoAsset.status == VIDEO_UPLOADED,
                        VideoAsset.uploaded_at < cutoff,
                        VideoAsset.id.not_in(busy),
                    )
                )
            ).scalars().all()
            storage = get_storage()
            for v in videos:
                storage.delete(v.storage_key)
                v.status = VIDEO_DELETED
                v.deleted_at = utcnow()
                log.info("video_retention_deleted", video_id=str(v.id), store_id=str(v.store_id))
            await db.commit()

    # ── one job ──────────────────────────────────────────────────

    async def process(self, job_id: uuid.UUID) -> None:
        from app.cv.detector import ModelLoadError
        from app.cv.event_engine import EntryLine
        from app.cv.pipeline import Cancelled, PipelineConfig, run_pipeline
        from app.cv.video_io import VideoError, extract_frame_jpeg
        from app.cv.zone_mapper import ZonePolygon

        self.current_job = job_id
        bound = log.bind(job_id=str(job_id))
        workdir = tempfile.mkdtemp(prefix=f"job-{job_id.hex[:8]}-", dir=self._tmp_root())
        cancel_flag = threading.Event()
        reason = {"why": None}
        state = {"progress": 0.0, "stage": "downloading"}
        started = time.monotonic()
        try:
            async with async_session() as db:
                job = await db.get(ProcessingJob, job_id)
                video = await db.get(VideoAsset, job.video_id)
                camera = await db.get(Camera, job.camera_id)
                bound = bound.bind(store_id=str(job.store_id), camera=camera.camera_code, attempt=job.attempts)
                bound.info("job_started")
                cfg_snapshot = dict(job.config or {})
            if video.status != VIDEO_UPLOADED:
                raise VideoError("VIDEO_UNAVAILABLE", f"Source video is {video.status}", retryable=False)

            # Download (object storage -> local temp file).
            await self._heartbeat(job_id, 0.0, "downloading")
            local = os.path.join(workdir, "source" + os.path.splitext(video.storage_key)[1])
            await asyncio.to_thread(get_storage().download_to, video.storage_key, local)
            digest = await asyncio.to_thread(_sha256, local)

            # Refuse to double count the same footage on the same camera.
            async with async_session() as db:
                dup = (
                    await db.execute(
                        select(ProcessingJob.id, VideoAsset.id)
                        .join(VideoAsset, VideoAsset.id == ProcessingJob.video_id)
                        .where(
                            ProcessingJob.camera_id == camera.id,
                            ProcessingJob.status == JOB_COMPLETED,
                            ProcessingJob.video_id != video.id,
                            VideoAsset.probe["sha256"].as_string() == digest,
                        )
                    )
                ).first()
            if dup and not cfg_snapshot.get("allow_duplicate"):
                raise VideoError(
                    "DUPLICATE_VIDEO",
                    f"This exact file was already processed for camera {camera.camera_code} (job {dup[0]}). "
                    "Processing it again would double count. Retry with allow_duplicate to override.",
                )

            zones = [
                ZonePolygon(z["name"], z["zone_type"], [tuple(p) for p in z["polygon"]], z.get("priority", 0), z.get("id"))
                for z in cfg_snapshot.get("zones", [])
            ]
            entry_line = EntryLine.from_dict(cfg_snapshot.get("entry_line"))
            pcfg = PipelineConfig.from_dict(cfg_snapshot.get("pipeline"))
            pcfg.max_video_seconds = pcfg.max_video_seconds or settings.max_video_seconds

            def on_progress(frac: float, info: dict) -> None:
                state["progress"] = 0.05 + 0.85 * frac
                state["stage"] = "analyzing"

            def should_cancel() -> bool:
                # Checked by the pipeline between frames, so a redeploy (SIGTERM)
                # stops the job promptly instead of at the next heartbeat.
                if self.stopping.is_set() and not cancel_flag.is_set():
                    reason["why"] = "shutdown"
                    cancel_flag.set()
                return cancel_flag.is_set()

            artifact_dir = os.path.join(workdir, "artifacts")
            task = asyncio.create_task(
                asyncio.to_thread(
                    run_pipeline, local, zones, entry_line, pcfg,
                    detector=self._detector(), progress=on_progress, should_cancel=should_cancel,
                    artifact_dir=artifact_dir,
                )
            )
            state["stage"] = "analyzing"
            while not task.done():
                await asyncio.wait({task}, timeout=settings.worker_heartbeat_seconds)
                if self.stopping.is_set():
                    reason["why"] = "shutdown"
                    cancel_flag.set()
                elif time.monotonic() - started > settings.job_timeout_seconds:
                    reason["why"] = "timeout"
                    cancel_flag.set()
                alive = await self._heartbeat(job_id, state["progress"], state["stage"])
                if not alive and not cancel_flag.is_set():
                    reason["why"] = "cancel"
                    cancel_flag.set()
            result = task.result()

            # Persist results.
            await self._heartbeat(job_id, 0.92, "saving")
            artifacts = await asyncio.to_thread(self._upload_artifacts, job_id, result)
            ref_key = None
            if not camera.reference_frame_key:
                jpeg, w, h = await asyncio.to_thread(extract_frame_jpeg, local, 1.0)
                ref_key = f"frames/{camera.id}/{video.id}.jpg"
                await asyncio.to_thread(get_storage().put_bytes, ref_key, jpeg, "image/jpeg")
            counts = await self._persist(job_id, video.id, camera, result, digest, artifacts, ref_key)
            self.jobs_completed += 1
            bound.info("job_completed", events=counts["events"], journeys=counts["journeys"],
                       seconds=round(time.monotonic() - started, 1), **{
                           k: result.stats.get(k) for k in ("frames_analyzed", "tracks_created", "realtime_factor")})
        except Cancelled:
            await self._handle_cancel(job_id, reason["why"], bound)
        except VideoError as exc:
            await self._fail(job_id, exc.code, str(exc), exc.retryable, bound)
        except ModelLoadError as exc:
            self.model_loaded = False
            self.model_error = str(exc)[:500]
            await self._fail(job_id, "MODEL_LOAD_FAILED", str(exc), True, bound)
        except (StorageError, OSError) as exc:
            await self._fail(job_id, "STORAGE_ERROR", f"{type(exc).__name__}: {exc}", True, bound)
        except Exception as exc:  # noqa: BLE001
            bound.error("job_crashed", error=str(exc), traceback=traceback.format_exc()[-4000:])
            await self._fail(job_id, "INTERNAL_ERROR", f"{type(exc).__name__}: {exc}", True, bound)
        finally:
            self.current_job = None
            shutil.rmtree(workdir, ignore_errors=True)

    def _tmp_root(self) -> str:
        os.makedirs(settings.worker_tmp_dir, exist_ok=True)
        return settings.worker_tmp_dir

    async def _heartbeat(self, job_id: uuid.UUID, progress: float, stage: str) -> bool:
        async with async_session() as db:
            return await job_service.heartbeat(db, job_id, self.worker_id, progress, stage)

    def _upload_artifacts(self, job_id: uuid.UUID, result) -> Dict:
        storage = get_storage()
        out: Dict = {"snapshots": []}
        if result.tracks_artifact and os.path.exists(result.tracks_artifact):
            key = f"artifacts/{job_id}/tracks.jsonl.gz"
            storage.put_file(key, result.tracks_artifact, "application/gzip")
            out["tracks"] = key
        for path in result.snapshot_paths:
            key = f"artifacts/{job_id}/{os.path.basename(path)}"
            storage.put_file(key, path, "image/jpeg")
            out["snapshots"].append(key)
        return out

    async def _persist(self, job_id, video_id, camera, result, digest, artifacts, ref_key) -> Dict:
        async with async_session() as db:
            job = await db.get(ProcessingJob, job_id)
            video = await db.get(VideoAsset, video_id)
            if job.status != JOB_RUNNING or job.locked_by != self.worker_id:
                raise RuntimeError("job was taken over by another worker before results were saved")
            # Idempotent: remove anything a previous attempt of this job wrote.
            await db.execute(delete(Event).where(Event.job_id == job_id))
            await db.execute(delete(CustomerJourney).where(CustomerJourney.job_id == job_id))
            await db.execute(delete(OccupancySample).where(OccupancySample.job_id == job_id))
            # Supersede earlier completed jobs for the same video (re-processing
            # with new zones/config must replace, not add to, earlier counts).
            previous = (
                await db.execute(
                    select(ProcessingJob).where(
                        ProcessingJob.video_id == video_id,
                        ProcessingJob.id != job_id,
                        ProcessingJob.status == JOB_COMPLETED,
                    )
                )
            ).scalars().all()
            for p in previous:
                await db.execute(delete(Event).where(Event.job_id == p.id))
                await db.execute(delete(CustomerJourney).where(CustomerJourney.job_id == p.id))
                await db.execute(delete(OccupancySample).where(OccupancySample.job_id == p.id))
                p.results = {**(p.results or {}), "superseded_by": str(job_id)}

            rows = build_event_rows(job, camera, video, result.events)
            for i in range(0, len(rows), 1000):
                await db.execute(insert(Event), rows[i:i + 1000])
            occ = [
                {"store_id": job.store_id, "job_id": job_id, "camera_code": camera.camera_code, "zone_name": z,
                 "zone_type": zt, "timestamp": video.recorded_start + timedelta(seconds=t), "count": n}
                for t, z, zt, n in result.occupancy
            ]
            for i in range(0, len(occ), 2000):
                await db.execute(insert(OccupancySample), occ[i:i + 2000])
            await db.flush()
            journeys = await journey_service.rebuild_for_job(db, job.store_id, job_id)

            overlap = await self._overlap_warning(db, job, video, result.meta.duration_s)
            warnings = list(result.warnings) + ([overlap] if overlap else [])
            video.probe = {**result.meta.as_dict(), "sha256": digest}
            job.results = {**result.stats, "warnings": warnings, "journeys": journeys,
                           "recorded_start_assumed": video.recorded_start_assumed}
            job.artifacts = artifacts
            job.model_name = result.stats.get("model")
            job.model_sha256 = result.stats.get("model_sha256")
            job.pipeline_version = result.stats.get("pipeline_version")
            job.status = JOB_COMPLETED
            job.progress = 1.0
            job.stage = "done"
            job.finished_at = utcnow()
            job.locked_by = None
            cam = await db.get(Camera, camera.id)
            if ref_key and not cam.reference_frame_key:
                cam.reference_frame_key = ref_key
                cam.reference_frame_width = result.meta.width
                cam.reference_frame_height = result.meta.height
            if not cam.resolution_width:
                cam.resolution_width = result.meta.width
                cam.resolution_height = result.meta.height
                cam.fps = round(result.meta.fps, 3)
            await db.commit()
            return {"events": len(rows), "journeys": journeys}

    async def _overlap_warning(self, db, job, video, duration) -> Optional[str]:
        if not video.recorded_start or not duration:
            return None
        end = video.recorded_start + timedelta(seconds=duration)
        others = (
            await db.execute(
                select(VideoAsset).join(ProcessingJob, ProcessingJob.video_id == VideoAsset.id).where(
                    ProcessingJob.camera_id == job.camera_id,
                    ProcessingJob.status == JOB_COMPLETED,
                    VideoAsset.id != video.id,
                )
            )
        ).scalars().all()
        for o in others:
            o_dur = (o.probe or {}).get("duration_s") or 0
            if o.recorded_start and o.recorded_start < end and o.recorded_start + timedelta(seconds=o_dur) > video.recorded_start:
                return (f"recording time overlaps video {o.id} ({o.original_filename}) on the same camera; "
                        "counts for the overlapping period may be duplicated")
        return None

    async def _fail(self, job_id, code, message, retryable, bound) -> None:
        async with async_session() as db:
            job = await db.get(ProcessingJob, job_id)
            status = await job_service.mark_failed(db, job, code, message, retryable)
        if status != JOB_QUEUED:
            self.jobs_failed += 1
        bound.warning("job_failed", code=code, error=message[:500], retryable=retryable, new_status=status)

    async def _handle_cancel(self, job_id, why, bound) -> None:
        async with async_session() as db:
            job = await db.get(ProcessingJob, job_id)
            if why == "shutdown":
                # Hand the job back without consuming an attempt.
                job.status = JOB_QUEUED
                job.attempts = max(0, job.attempts - 1)
                job.stage = "requeued_on_shutdown"
                job.locked_by = None
            elif why == "timeout":
                await job_service.mark_failed(
                    db, job, "JOB_TIMEOUT", f"Processing exceeded {settings.job_timeout_seconds}s", False
                )
                bound.warning("job_timeout")
                return
            else:
                job.status = JOB_CANCELLED
                job.stage = "cancelled"
                job.finished_at = utcnow()
                job.locked_by = None
            await db.commit()
        bound.info("job_stopped", reason=why)


def main() -> None:
    configure_logging()
    worker = Worker()

    def _stop(*_):
        log.info("shutdown_signal", worker_id=worker.worker_id)
        worker.stopping.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    asyncio.run(worker.run())


if __name__ == "__main__":
    main()
