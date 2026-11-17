"""Store-wide visits: one anonymous id per shopper across cameras and files.

Each processed video already joins its own track fragments into shoppers
(app/cv/linker.py, inside the pipeline). This service does the same across
all videos of one store that were recorded at about the same time: the
entrance camera, the aisle cameras and the billing camera, or two
consecutive files from one camera.

1. After a job finishes, the worker saves one mean appearance descriptor per
   track fragment (float16, ``reid/{job_id}.npz`` in object storage) with
   the fragment's wall-clock start and end and its camera. Nothing else: no
   image, no face, no name.
2. ``relink_store`` finds every finished job of the store whose recording
   overlaps this one (allowing ``REID_CROSS_CAMERA_MAX_GAP_S`` for walking
   between cameras, and chaining overlaps), links all their fragments, and
   rewrites the events' ``customer_id`` to a store visit id such as
   ``V2611171030-0007``. Journeys for those jobs are rebuilt from the events,
   so a journey now runs across cameras.
3. Descriptor files are deleted ``REID_DESCRIPTOR_HOURS`` (default 24) after
   the job finished (``purge_expired_descriptors``). Visits are never linked
   across days and nobody is recognised on a later visit.

If a descriptor file is missing (expired, or the job ran before this
existed), that job keeps its own per-video ids.
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.cv.linker import Fragment, LinkConfig, link_fragments
from app.database import utcnow
from app.models.event import CustomerJourney, Event
from app.models.jobs import JOB_COMPLETED, ProcessingJob, VideoAsset
from app.models.store import Camera
from app.services import journey_service
from app.storage import StorageError, get_storage

log = logging.getLogger(__name__)

DESCRIPTOR_ARTIFACT = "reid"


def descriptor_key(job_id: uuid.UUID) -> str:
    return f"reid/{job_id}.npz"


def pack_fragments(fragments: Sequence[Fragment]) -> Optional[bytes]:
    """One row per fragment that has a descriptor: track id, start, end
    (seconds from the start of the video) and the mean descriptor."""
    rows = [(f.key, f.t_start, f.t_end, f.prototype()) for f in fragments]
    rows = [r for r in rows if r[3] is not None]
    if not rows:
        return None
    buf = io.BytesIO()
    np.savez_compressed(
        buf,
        track=np.array([int(r[0]) for r in rows], dtype=np.int64),
        t0=np.array([r[1] for r in rows], dtype=np.float64),
        t1=np.array([r[2] for r in rows], dtype=np.float64),
        desc=np.stack([r[3] for r in rows]).astype(np.float16),
    )
    return buf.getvalue()


def unpack_fragments(data: bytes) -> List[Tuple[int, float, float, np.ndarray]]:
    with np.load(io.BytesIO(data), allow_pickle=False) as z:
        desc = z["desc"].astype(np.float32)
        return [(int(t), float(a), float(b), desc[i]) for i, (t, a, b) in enumerate(zip(z["track"], z["t0"], z["t1"]))]


def _video_span(video: VideoAsset) -> Optional[Tuple[datetime, datetime]]:
    duration = (video.probe or {}).get("duration_s")
    if not video.recorded_start or not duration:
        return None
    return video.recorded_start, video.recorded_start + timedelta(seconds=float(duration))


def visit_id(cluster_start: datetime, n: int) -> str:
    return f"V{cluster_start:%y%m%d%H%M}-{n:04d}"


async def relink_store(db: AsyncSession, store_id: uuid.UUID, job_id: uuid.UUID) -> Dict:
    """Link shoppers across every job recorded around ``job_id``'s video.

    Runs inside the caller's transaction; does not commit."""
    slack = timedelta(seconds=settings.reid_cross_camera_max_gap_s)
    rows = (
        await db.execute(
            select(ProcessingJob, VideoAsset, Camera)
            .join(VideoAsset, VideoAsset.id == ProcessingJob.video_id)
            .join(Camera, Camera.id == ProcessingJob.camera_id)
            .where(ProcessingJob.store_id == store_id,
                   (ProcessingJob.status == JOB_COMPLETED) | (ProcessingJob.id == job_id))
        )
    ).all()
    spans = {}
    for job, video, camera in rows:
        if not (job.artifacts or {}).get(DESCRIPTOR_ARTIFACT):
            continue
        if (job.results or {}).get("superseded_by"):
            continue
        span = _video_span(video)
        if span:
            spans[job.id] = (span, job, camera)
    if job_id not in spans:
        return {"linked": False, "reason": "no descriptors for this job"}

    # Grow the cluster: every job whose recording (plus walking slack)
    # touches the cluster's time range joins it.
    lo, hi = spans[job_id][0]
    members = {job_id}
    changed = True
    while changed:
        changed = False
        for jid, ((s, e), _, _) in spans.items():
            if jid not in members and s - slack <= hi and e + slack >= lo:
                members.add(jid)
                lo, hi = min(lo, s), max(hi, e)
                changed = True

    storage = get_storage()
    fragments: List[Fragment] = []
    loaded = []
    for jid in sorted(members, key=lambda j: spans[j][0][0]):
        (start, _), job, camera = spans[jid]
        try:
            data = storage.get_bytes(job.artifacts[DESCRIPTOR_ARTIFACT])
        except StorageError:
            continue
        loaded.append(jid)
        offset = (start - lo).total_seconds()
        for track, t0, t1, desc in unpack_fragments(data):
            fragments.append(Fragment(key=(jid, track), camera=camera.camera_code,
                                      t_start=offset + t0, t_end=offset + t1, descriptors=[desc]))
    if not fragments:
        return {"linked": False, "reason": "descriptor files missing"}

    cfg = LinkConfig(cross_camera_max_gap_s=settings.reid_cross_camera_max_gap_s)
    result = link_fragments(fragments, cfg)

    events = (
        await db.execute(select(Event.id, Event.job_id, Event.track_id).where(Event.job_id.in_(loaded)))
    ).all()
    updates = []
    for ev_id, ev_job, track in events:
        n = result.shopper_of.get((ev_job, track))
        if n is not None:
            updates.append({"id": ev_id, "customer_id": visit_id(lo, n)})
    for i in range(0, len(updates), 1000):
        await db.execute(update(Event), updates[i:i + 1000])
    await db.flush()

    # Journeys of these jobs now follow store visits, across cameras.
    await db.execute(delete(CustomerJourney).where(CustomerJourney.job_id.in_(loaded)))
    evs = (await db.execute(select(Event).where(Event.job_id.in_(loaded)))).scalars().all()
    journeys = journey_service.build_journeys(store_id, None, evs, "cv")
    db.add_all(journeys)
    await db.flush()
    cameras = {spans[j][2].camera_code for j in loaded}
    return {
        "linked": True,
        "jobs": len(loaded),
        "cameras": len(cameras),
        "fragments": len(fragments),
        "visits": result.shoppers,
        "cross_camera_links": result.cross_camera_links,
        "journeys": len(journeys),
        "window_start": lo.isoformat(),
        "window_end": hi.isoformat(),
    }


async def purge_expired_descriptors(db: AsyncSession) -> int:
    """Delete descriptor files of jobs that finished more than
    REID_DESCRIPTOR_HOURS ago. Returns the number of files deleted."""
    cutoff = utcnow() - timedelta(hours=settings.reid_descriptor_hours)
    jobs = (
        await db.execute(select(ProcessingJob).where(ProcessingJob.finished_at < cutoff))
    ).scalars().all()
    storage = get_storage()
    n = 0
    for job in jobs:
        key = (job.artifacts or {}).get(DESCRIPTOR_ARTIFACT)
        if not key:
            continue
        try:
            storage.delete(key)
        except StorageError as exc:
            log.warning("descriptor_delete_failed job=%s error=%s", job.id, exc)
            continue
        job.artifacts = {k: v for k, v in job.artifacts.items() if k != DESCRIPTOR_ARTIFACT}
        n += 1
    await db.commit()
    return n
