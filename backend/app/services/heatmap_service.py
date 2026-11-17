"""Where shoppers stood: per-camera heatmaps from processed videos.

Each finished job stores a sparse grid over its camera picture (feet
positions, person-seconds; see ``heatmap`` in the job results, built in
app/cv/pipeline.py). This sums the grids of every job whose recording
starts inside the requested range, per camera, so the UI can draw them over
each camera's reference picture. Only CV data has positions; other sources
give an empty result.
"""

from __future__ import annotations

import uuid
from typing import Dict, List, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jobs import JOB_COMPLETED, ProcessingJob, VideoAsset
from app.models.store import Camera
from app.services.timerange import TimeRange


async def camera_heatmaps(db: AsyncSession, store_id: uuid.UUID, tr: TimeRange, sources: Sequence[str]) -> Dict:
    if "cv" not in sources:
        return {"cameras": []}
    rows = (
        await db.execute(
            select(ProcessingJob, Camera)
            .join(VideoAsset, VideoAsset.id == ProcessingJob.video_id)
            .join(Camera, Camera.id == ProcessingJob.camera_id)
            .where(
                ProcessingJob.store_id == store_id,
                ProcessingJob.status == JOB_COMPLETED,
                VideoAsset.recorded_start >= tr.start_utc,
                VideoAsset.recorded_start < tr.end_utc,
            )
        )
    ).all()
    per_cam: Dict[uuid.UUID, Dict] = {}
    for job, cam in rows:
        res = job.results or {}
        hm = res.get("heatmap")
        if not hm or res.get("superseded_by"):
            continue
        c = per_cam.setdefault(cam.id, {
            "camera_id": str(cam.id), "camera_code": cam.camera_code, "name": cam.name,
            "has_reference_frame": bool(cam.reference_frame_key),
            "cols": hm["cols"], "rows": hm["rows"], "_cells": {}, "videos": 0, "shoppers": 0, "seconds_analysed": 0.0,
            "_jobs": [],
        })
        if (hm["cols"], hm["rows"]) != (c["cols"], c["rows"]):
            continue  # grid size changed between runs; keep the first one
        for cell, secs in hm["cells"]:
            c["_cells"][cell] = c["_cells"].get(cell, 0.0) + float(secs)
        c["videos"] += 1
        c["shoppers"] += int(res.get("visitors") or 0)
        c["seconds_analysed"] += float(res.get("decoded_seconds") or 0)
        c["_jobs"].append(job.id)

    out: List[Dict] = []
    for c in per_cam.values():
        c.pop("_jobs")
        cells = c.pop("_cells")
        c["person_seconds"] = round(sum(cells.values()), 1)
        c["max_cell_seconds"] = round(max(cells.values()), 2) if cells else 0.0
        c["cells"] = [[k, round(v, 2)] for k, v in sorted(cells.items())]
        c["seconds_analysed"] = round(c["seconds_analysed"], 1)
        out.append(c)
    out.sort(key=lambda c: c["camera_code"])
    return {"cameras": out}
