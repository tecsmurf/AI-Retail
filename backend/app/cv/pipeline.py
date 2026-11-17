"""End-to-end CV pipeline for one video from one camera.

    video file -> probe -> time-based frame sampling -> YOLO person detection
    -> ByteTrack -> normalized coordinates -> track stitching -> zone assignment
    -> EventEngine (debounced zone/queue/line events)
    -> appearance descriptors (about 1 per person per second, app/cv/reid.py)
    -> shopper linking (app/cv/linker.py) -> PipelineResult

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
from app.cv.linker import Fragment, LinkConfig, link_fragments
from app.cv.reid import AppearanceEncoder, get_encoder
from app.cv.stitcher import StitchConfig, TrackStitcher
from app.cv.tracker import PersonTracker, TrackerConfig
from app.cv.video_io import DecodeStats, VideoError, VideoMeta, iter_sampled_frames, probe_video
from app.cv.zone_mapper import ZonePolygon

PIPELINE_VERSION = "2.3.0"


class Cancelled(Exception):
    pass


@dataclass
class ReidConfig:
    enabled: bool = True
    encoder: str = "lmbn"  # lmbn | colour
    # One descriptor per person per this many seconds (CPU cost scales with it).
    interval_s: float = 1.0
    # Skip crops that another person covers by more than this share of the
    # box: a mixed crop describes two people.
    max_covered: float = 0.2
    min_height_px: int = 48
    max_per_track: int = 60
    # Skip boxes cut off by the frame edge: half a person describes badly.
    edge_margin: float = 0.01
    # ...unless the person has no clean view at all; then up to
    # ``max_fallback_per_track`` such crops are used instead.
    fallback_max_covered: float = 0.5
    max_fallback_per_track: int = 5

    def as_dict(self) -> dict:
        return dict(self.__dict__)


def _covered_share(i: int, boxes: Sequence[tuple]) -> float:
    x1, y1, x2, y2 = boxes[i]
    area = max(1e-9, (x2 - x1) * (y2 - y1))
    worst = 0.0
    for j, (a1, b1, a2, b2) in enumerate(boxes):
        if j == i:
            continue
        iw = min(x2, a2) - max(x1, a1)
        ih = min(y2, b2) - max(y1, b1)
        if iw > 0 and ih > 0:
            worst = max(worst, iw * ih / area)
    return worst


@dataclass
class PipelineConfig:
    analysis_fps: float = 5.0
    detector_confidence: float = 0.1  # low on purpose: ByteTrack uses low-score boxes
    tracker: TrackerConfig = field(default_factory=TrackerConfig)
    engine: EngineConfig = field(default_factory=EngineConfig)
    stitch: StitchConfig = field(default_factory=StitchConfig)
    reid: ReidConfig = field(default_factory=ReidConfig)
    link: LinkConfig = field(default_factory=LinkConfig)
    max_video_seconds: Optional[float] = None
    snapshot_count: int = 6
    # Heatmap grid over the camera picture (feet positions, person-seconds).
    heatmap_cols: int = 64
    heatmap_rows: int = 36

    def as_dict(self) -> dict:
        return {
            "analysis_fps": self.analysis_fps,
            "detector_confidence": self.detector_confidence,
            "tracker": self.tracker.as_dict(),
            "engine": self.engine.as_dict(),
            "stitch": self.stitch.as_dict(),
            "reid": self.reid.as_dict(),
            "link": self.link.as_dict(),
            "max_video_seconds": self.max_video_seconds,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> PipelineConfig:
        data = dict(data or {})
        tracker = TrackerConfig(**(data.pop("tracker", None) or {}))
        engine = EngineConfig(**(data.pop("engine", None) or {}))
        stitch = StitchConfig(**(data.pop("stitch", None) or {}))
        reid = ReidConfig(**(data.pop("reid", None) or {}))
        link = LinkConfig(**(data.pop("link", None) or {}))
        allowed = {"analysis_fps", "detector_confidence", "max_video_seconds", "snapshot_count",
                   "heatmap_cols", "heatmap_rows"}
        return cls(tracker=tracker, engine=engine, stitch=stitch, reid=reid, link=link,
                   **{k: v for k, v in data.items() if k in allowed})


@dataclass
class PipelineResult:
    meta: VideoMeta
    events: List[EngineEvent]
    occupancy: List[tuple]
    stats: Dict
    warnings: List[str]
    tracks_artifact: Optional[str] = None
    snapshot_paths: List[str] = field(default_factory=list)
    # Confirmed track fragments with their appearance descriptors, for
    # linking across cameras. In memory only; never written to storage.
    fragments: List[Fragment] = field(default_factory=list)


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
    encoder: Optional[AppearanceEncoder] = None,
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
    stitcher = TrackStitcher(cfg.stitch)
    engine = EventEngine(zones, entry_line, cfg.engine)
    decode = DecodeStats()
    enc: Optional[AppearanceEncoder] = None
    if cfg.reid.enabled:
        enc = encoder or get_encoder(cfg.reid.encoder)
        enc.load()
    # visitor id -> [first_t, last_t, first_box, last_box]
    spans: Dict[int, list] = {}
    descriptors: Dict[int, List] = {}
    fallback: Dict[int, List] = {}
    last_desc_t: Dict[int, float] = {}
    last_fallback_t: Dict[int, float] = {}
    reid_seconds = 0.0
    crops_embedded = 0
    heat: Dict[int, float] = {}
    sample_s = 1.0 / analysis_fps

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
            observations = stitcher.update(ts, observations)
            engine.update(ts, observations)

            for vid, box, _ in observations:
                fx = min(max((box[0] + box[2]) / 2.0, 0.0), 0.999999)
                fy = min(max(box[3], 0.0), 0.999999)
                cell = int(fy * cfg.heatmap_rows) * cfg.heatmap_cols + int(fx * cfg.heatmap_cols)
                heat[cell] = heat.get(cell, 0.0) + sample_s
                sp = spans.get(vid)
                if sp is None:
                    spans[vid] = [ts, ts, box, box]
                else:
                    sp[1], sp[3] = ts, box
            if enc is not None and observations:
                px = [(b[0] * w, b[1] * h, b[2] * w, b[3] * h) for _, b, _ in observations]
                pick, pick_good = [], []
                for i, (vid, nb, _) in enumerate(observations):
                    if px[i][3] - px[i][1] < cfg.reid.min_height_px:
                        continue
                    em = cfg.reid.edge_margin
                    cut = nb[0] <= em or nb[1] <= em or nb[2] >= 1 - em or nb[3] >= 1 - em
                    covered = _covered_share(i, px)
                    if not cut and covered <= cfg.reid.max_covered:
                        if (len(descriptors.get(vid, ())) < cfg.reid.max_per_track
                                and ts - last_desc_t.get(vid, -1e9) >= cfg.reid.interval_s):
                            pick.append(i)
                            pick_good.append(True)
                    elif (not descriptors.get(vid) and covered <= cfg.reid.fallback_max_covered
                          and ts - last_fallback_t.get(vid, -1e9) >= cfg.reid.interval_s
                          and len(fallback.get(vid, ())) < cfg.reid.max_fallback_per_track):
                        # No clean view of this person yet: keep a few
                        # cut-off or partly covered crops in reserve.
                        pick.append(i)
                        pick_good.append(False)
                if pick:
                    t1 = time.monotonic()
                    vecs = enc.embed(frame, [px[i] for i in pick])
                    reid_seconds += time.monotonic() - t1
                    for i, good, vec in zip(pick, pick_good, vecs):
                        if not vec.any():
                            continue
                        vid = observations[i][0]
                        (descriptors if good else fallback).setdefault(vid, []).append(vec)
                        (last_desc_t if good else last_fallback_t)[vid] = ts
                        crops_embedded += 1

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

    # Join fragments of the same shopper (people hidden behind others for
    # longer than the stitcher's 2 s, or leaving and coming back).
    fragments = [
        Fragment(key=vid, camera="", t_start=spans[vid][0], t_end=spans[vid][1],
                 descriptors=descriptors.get(vid) or fallback.get(vid, []), first_box=spans[vid][2], last_box=spans[vid][3])
        for vid in sorted(engine.confirmed_track_ids) if vid in spans
    ]
    link = link_fragments(fragments, cfg.link if enc is not None else LinkConfig(enabled=False))
    for e in events:
        e.shopper_id = link.shopper_of.get(e.track_id)
    if artifact_dir:
        with open(os.path.join(artifact_dir, "shoppers.json"), "w", encoding="utf-8") as fh:
            json.dump({str(k): v for k, v in sorted(link.shopper_of.items())}, fh)
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
        "track_stitches": stitcher.stitches,
        # Distinct people: confirmed track fragments (short flickers are not
        # people) joined into shoppers by appearance re-identification.
        "visitors": link.shoppers,
        "track_fragments": len(fragments),
        "tracks_discarded_short": engine.discarded_short_tracks,
        # Where people stood on this camera's picture: person-seconds per cell
        # of a cols x rows grid (feet position), sparse [cell, seconds] pairs.
        "heatmap": {
            "cols": cfg.heatmap_cols,
            "rows": cfg.heatmap_rows,
            "cells": [[c, round(v, 2)] for c, v in sorted(heat.items())],
        },
        "reid": {
            "encoder": enc.name if enc is not None else None,
            "descriptors": crops_embedded,
            "seconds": round(reid_seconds, 2),
            "same_camera_links": link.same_camera_links,
            "thresholds": link.thresholds,
            "skipped_ambiguous": link.skipped_ambiguous,
        },
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
        fragments=fragments,
    )
