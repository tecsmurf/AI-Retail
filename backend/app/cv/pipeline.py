"""End-to-end CV pipeline for one video from one camera.

    video file -> probe -> time-based frame sampling -> YOLO person detection
    -> ByteTrack -> normalized coordinates -> zone assignment
    -> EventEngine (debounced zone/queue/line events) -> PipelineResult

The pipeline is synchronous and CPU/GPU bound; the worker runs it in a
thread. It never touches the database: persistence is the worker's job, which
keeps this module testable and the event output reproducible.
"""

from __future__ import annotations

import gzip
import json
import os
import resource
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

from app.cv.detector import PersonDetector, get_detector
from app.cv.event_engine import EngineConfig, EngineEvent, EntryLine, EventEngine
from app.cv.tracker import PersonTracker, TrackerConfig
from app.cv.video_io import DecodeStats, VideoError, VideoMeta, iter_sampled_frames, probe_video
from app.cv.zone_mapper import ZonePolygon

PIPELINE_VERSION = "2.0.0"


class Cancelled(Exception):
    pass


@dataclass
class PipelineConfig:
    analysis_fps: float = 5.0
    detector_confidence: float = 0.1  # low on purpose: ByteTrack uses low-score boxes
    tracker: TrackerConfig = field(default_factory=TrackerConfig)
    engine: EngineConfig = field(default_factory=EngineConfig)
    max_video_seconds: Optional[float] = None
    snapshot_count: int = 6

    def as_dict(self) -> dict:
        return {
            "analysis_fps": self.analysis_fps,
            "detector_confidence": self.detector_confidence,
            "tracker": self.tracker.as_dict(),
            "engine": self.engine.as_dict(),
            "max_video_seconds": self.max_video_seconds,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> PipelineConfig:
        data = dict(data or {})
        tracker = TrackerConfig(**(data.pop("tracker", None) or {}))
        engine = EngineConfig(**(data.pop("engine", None) or {}))
        allowed = {"analysis_fps", "detector_confidence", "max_video_seconds", "snapshot_count"}
        return cls(tracker=tracker, engine=engine, **{k: v for k, v in data.items() if k in allowed})


@dataclass
class PipelineResult:
    meta: VideoMeta
    events: List[EngineEvent]
    occupancy: List[tuple]
    stats: Dict
    warnings: List[str]
    tracks_artifact: Optional[str] = None
    snapshot_paths: List[str] = field(default_factory=list)


ProgressFn = Callable[[float, Dict], None]


def _rss_mb() -> float:
    # ru_maxrss is KiB on Linux.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def _draw_snapshot(frame, tracked, zones: Sequence[ZonePolygon], entry_line: Optional[EntryLine], path: str) -> None:
    import cv2
    import numpy as np

    img = frame.copy()
    h, w = img.shape[:2]
    for z in zones:
        pts = np.array([[int(x * w), int(y * h)] for x, y in z.polygon], dtype=np.int32)
        cv2.polylines(img, [pts], True, (255, 0, 255), 2)
        cv2.putText(img, z.name, tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)
    if entry_line:
        p1 = (int(entry_line.p1[0] * w), int(entry_line.p1[1] * h))
        p2 = (int(entry_line.p2[0] * w), int(entry_line.p2[1] * h))
        cv2.line(img, p1, p2, (0, 255, 255), 2)
    for tb in tracked:
        x1, y1, x2, y2 = (int(v) for v in tb.bbox)
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.circle(img, ((x1 + x2) // 2, y2), 3, (0, 0, 255), -1)
        cv2.putText(img, f"#{tb.track_id} {tb.confidence:.2f}", (x1, max(12, y1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
    cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 80])


def run_pipeline(
    video_path: str,
    zones: Sequence[ZonePolygon],
    entry_line: Optional[EntryLine],
    config: Optional[PipelineConfig] = None,
    *,
    detector: Optional[PersonDetector] = None,
    progress: Optional[ProgressFn] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
    artifact_dir: Optional[str] = None,
) -> PipelineResult:
    cfg = config or PipelineConfig()
    t_start = time.monotonic()
    meta = probe_video(video_path)
    warnings = list(meta.warnings)
    if cfg.max_video_seconds and meta.duration_s and meta.duration_s > cfg.max_video_seconds:
        raise VideoError(
            "VIDEO_TOO_LONG",
            f"Video is {meta.duration_s:.0f}s long; the limit is {cfg.max_video_seconds:.0f}s",
        )
    analysis_fps = min(cfg.analysis_fps, meta.fps)

    det = detector or get_detector()
    det.load()
    tracker = PersonTracker(frame_rate=analysis_fps, config=cfg.tracker)
    engine = EventEngine(zones, entry_line, cfg.engine)
    decode = DecodeStats()

    tracks_fh = None
    tracks_path = None
    snapshot_paths: List[str] = []
    snapshot_times: List[float] = []
    if artifact_dir:
        os.makedirs(artifact_dir, exist_ok=True)
        tracks_path = os.path.join(artifact_dir, "tracks.jsonl.gz")
        tracks_fh = gzip.open(tracks_path, "wt", encoding="utf-8")
        if meta.duration_s and cfg.snapshot_count > 0:
            step = meta.duration_s / (cfg.snapshot_count + 1)
            snapshot_times = [step * (i + 1) for i in range(cfg.snapshot_count)]

    total_detections = 0
    max_people = 0
    detect_seconds = 0.0
    last_report = 0.0
    try:
        for frame_index, ts, frame in iter_sampled_frames(video_path, meta, analysis_fps, decode):
            if cfg.max_video_seconds and ts > cfg.max_video_seconds:
                raise VideoError("VIDEO_TOO_LONG", f"Video exceeds the {cfg.max_video_seconds:.0f}s limit")
            h, w = frame.shape[:2]
            t0 = time.monotonic()
            detections = det.detect(frame, confidence=cfg.detector_confidence)
            detect_seconds += time.monotonic() - t0
            total_detections += sum(1 for d in detections if d.confidence >= cfg.tracker.track_activation_threshold)
            tracked = tracker.update(detections)
            max_people = max(max_people, len(tracked))
            observations = [
                (tb.track_id, (tb.bbox[0] / w, tb.bbox[1] / h, tb.bbox[2] / w, tb.bbox[3] / h), tb.confidence)
                for tb in tracked
            ]
            engine.update(ts, observations)

            if tracks_fh is not None:
                tracks_fh.write(json.dumps({
                    "t": round(ts, 3), "f": frame_index,
                    "tracks": [[tid, [round(v, 4) for v in box], round(c, 3)] for tid, box, c in observations],
                }) + "\n")
            if snapshot_times and ts >= snapshot_times[0]:
                snapshot_times.pop(0)
                path = os.path.join(artifact_dir, f"snapshot_{len(snapshot_paths) + 1:02d}.jpg")
                _draw_snapshot(frame, tracked, zones, entry_line, path)
                snapshot_paths.append(path)

            now = time.monotonic()
            if should_cancel and now - last_report >= 1.0 and should_cancel():
                raise Cancelled()
            if progress and now - last_report >= 2.0:
                last_report = now
                frac = min(0.99, ts / meta.duration_s) if meta.duration_s else 0.0
                progress(frac, {"t": ts, "tracks": len(tracked), "events": len(engine.events)})
    finally:
        if tracks_fh is not None:
            tracks_fh.close()

    if decode.frames_sampled == 0:
        raise VideoError("UNDECODABLE_VIDEO", "No frames could be decoded")
    if decode.ended_early:
        warnings.append(
            f"decoding stopped at {decode.last_timestamp_s:.1f}s of {meta.duration_s:.1f}s "
            "(truncated or corrupt file); results cover the decoded part only"
        )
    events = engine.finish("video_end")
    elapsed = time.monotonic() - t_start
    if total_detections == 0:
        warnings.append("no people detected in this video")

    counts: Dict[str, int] = {}
    for e in events:
        counts[e.event_type] = counts.get(e.event_type, 0) + 1
    if entry_line is None:
        warnings.append("no entry line configured for this camera: ENTRY/EXIT are not counted")
    if not zones:
        warnings.append("no zones configured for this camera: zone and queue events are not produced")

    stats = {
        "pipeline_version": PIPELINE_VERSION,
        "video": meta.as_dict(),
        "analysis_fps": analysis_fps,
        "frames_decoded": decode.frames_decoded,
        "frames_analyzed": decode.frames_sampled,
        "timestamp_source": decode.timestamp_source,
        "decoded_seconds": round(decode.last_timestamp_s, 2),
        "detections": total_detections,
        "mean_detections_per_frame": round(total_detections / max(1, decode.frames_sampled), 3),
        "max_people_in_frame": max_people,
        "tracks_created": len(tracker.ids_seen),
        "tracks_discarded_short": engine.discarded_short_tracks,
        "events": counts,
        "event_total": len(events),
        "processing_seconds": round(elapsed, 2),
        "detector_seconds": round(detect_seconds, 2),
        "analysis_frames_per_second": round(decode.frames_sampled / elapsed, 2) if elapsed > 0 else None,
        "realtime_factor": round((decode.last_timestamp_s or 0) / elapsed, 2) if elapsed > 0 else None,
        "peak_rss_mb": round(_rss_mb(), 1),
        "device": det.device,
        "model": os.path.basename(det.model_path or det.model_name),
        "model_sha256": det.model_sha256,
    }
    return PipelineResult(
        meta=meta,
        events=events,
        occupancy=engine.occupancy,
        stats=stats,
        warnings=warnings,
        tracks_artifact=tracks_path,
        snapshot_paths=snapshot_paths,
    )
