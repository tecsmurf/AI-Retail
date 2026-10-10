"""Video probing and bounded-memory frame sampling.

Frames are decoded one at a time with OpenCV (FFmpeg backend) and sampled by
*timestamp*, not by "every Nth frame", so variable frame rates and odd
container FPS values still give an evenly spaced analysis rate. Skipped frames
are only ``grab()``-ed (demuxed and decoded, never converted/copied), and at
most one frame is held in memory.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Iterator, List, Optional, Tuple

import numpy as np


class VideoError(Exception):
    """Raised for unusable input. ``retryable`` is False for bad files."""

    def __init__(self, code: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass
class VideoMeta:
    path: str
    size_bytes: int
    width: int
    height: int
    fps: float  # average frame rate
    duration_s: Optional[float]
    frame_count: Optional[int]  # as reported by the container (may be wrong)
    codec: Optional[str] = None
    rotation: int = 0
    variable_frame_rate: bool = False
    probe_tool: str = "opencv"
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        # The local path is a worker temp file: not useful to clients and it
        # leaks host layout, so it is left out of stored/returned metadata.
        d = asdict(self)
        d.pop("path", None)
        return d


def _parse_rate(rate: Optional[str]) -> Optional[float]:
    if not rate or rate in ("0/0", "N/A"):
        return None
    try:
        if "/" in rate:
            num, den = rate.split("/")
            den_f = float(den)
            return float(num) / den_f if den_f else None
        return float(rate)
    except ValueError:
        return None


def _ffprobe(path: str) -> Optional[dict]:
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=codec_name,width,height,avg_frame_rate,r_frame_rate,nb_frames,duration:"
             "stream_side_data=rotation:stream_tags=rotate:format=duration",
             "-of", "json", path],
            capture_output=True, text=True, timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return {"error": out.stderr.strip()[:500]}
    try:
        return json.loads(out.stdout or "{}")
    except json.JSONDecodeError:
        return None


def probe_video(path: str) -> VideoMeta:
    """Read metadata; raise VideoError for missing/empty/undecodable files."""
    import cv2

    if not os.path.exists(path):
        raise VideoError("VIDEO_NOT_FOUND", "Video file not found", retryable=True)
    size = os.path.getsize(path)
    if size == 0:
        raise VideoError("EMPTY_VIDEO", "The uploaded file is empty")

    warnings: List[str] = []
    info = _ffprobe(path)
    if info and "error" in info:
        raise VideoError("INVALID_VIDEO", f"Not a readable video: {info['error'] or 'ffprobe failed'}")

    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            raise VideoError("INVALID_VIDEO", "OpenCV could not open the video (corrupt file or unsupported codec)")
        ok, frame = cap.read()
        if not ok or frame is None:
            raise VideoError("UNDECODABLE_VIDEO", "Could not decode the first frame (unsupported codec or corrupt file)")
        height, width = frame.shape[:2]
        cv_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        cv_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    finally:
        cap.release()

    fps = None
    duration = None
    frame_count = None
    codec = None
    rotation = 0
    vfr = False
    tool = "opencv"
    streams = (info or {}).get("streams") or []
    if streams:
        tool = "ffprobe"
        s = streams[0]
        codec = s.get("codec_name")
        avg = _parse_rate(s.get("avg_frame_rate"))
        real = _parse_rate(s.get("r_frame_rate"))
        fps = avg or real
        if avg and real and abs(avg - real) / max(avg, real) > 0.02:
            vfr = True
            warnings.append(f"variable frame rate (avg {avg:.2f} fps, nominal {real:.2f} fps)")
        try:
            duration = float(s.get("duration") or (info.get("format") or {}).get("duration"))
        except (TypeError, ValueError):
            duration = None
        try:
            frame_count = int(s["nb_frames"]) if s.get("nb_frames") not in (None, "N/A") else None
        except ValueError:
            frame_count = None
        for sd in s.get("side_data_list") or []:
            if "rotation" in sd:
                rotation = int(sd["rotation"])
        if not rotation and (s.get("tags") or {}).get("rotate"):
            rotation = int(s["tags"]["rotate"])
    if not fps or fps <= 0 or fps > 240:
        if cv_fps and 0 < cv_fps <= 240:
            fps = cv_fps
        else:
            warnings.append("frame rate missing or invalid in metadata; assuming 25 fps")
            fps = 25.0
    if frame_count is None and cv_frames > 0:
        frame_count = cv_frames
    if duration is None and frame_count:
        duration = frame_count / fps
    if duration is None:
        warnings.append("duration unknown; progress will be approximate")
    if rotation:
        warnings.append(f"rotation metadata {rotation} deg; frames are auto-rotated by the decoder")

    return VideoMeta(
        path=path, size_bytes=size, width=int(width), height=int(height), fps=float(fps),
        duration_s=duration, frame_count=frame_count, codec=codec, rotation=rotation,
        variable_frame_rate=vfr, probe_tool=tool, warnings=warnings,
    )


@dataclass
class DecodeStats:
    frames_decoded: int = 0
    frames_sampled: int = 0
    last_timestamp_s: float = 0.0
    timestamp_source: str = "container"
    ended_early: bool = False


def iter_sampled_frames(
    path: str, meta: VideoMeta, analysis_fps: float, stats: DecodeStats
) -> Iterator[Tuple[int, float, np.ndarray]]:
    """Yield (frame_index, timestamp_seconds, BGR frame) at ~analysis_fps.

    Timestamps come from the container (CAP_PROP_POS_MSEC) when they are
    monotonic, otherwise from frame_index / fps.
    """
    import cv2

    if analysis_fps <= 0:
        raise ValueError("analysis_fps must be positive")
    interval = 1.0 / analysis_fps
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise VideoError("INVALID_VIDEO", "Could not open video for decoding")
    next_t = 0.0
    index = -1
    last_ts = -1.0
    use_container_ts = True
    try:
        while True:
            if not cap.grab():
                break
            index += 1
            stats.frames_decoded += 1
            ts = None
            if use_container_ts:
                pos = cap.get(cv2.CAP_PROP_POS_MSEC)
                if pos is not None and pos > 0 and pos / 1000.0 > last_ts:
                    ts = pos / 1000.0
                elif index > 0:
                    use_container_ts = False
                    stats.timestamp_source = "frame_index"
            if ts is None:
                ts = index / meta.fps
            # POS_MSEC of the first frame is 0 with most demuxers.
            if index == 0:
                ts = 0.0
            last_ts = ts
            stats.last_timestamp_s = ts
            if ts + 1e-6 < next_t:
                continue
            ok, frame = cap.retrieve()
            if not ok or frame is None:
                continue
            stats.frames_sampled += 1
            next_t += interval
            while next_t <= ts:
                next_t += interval
            yield index, ts, frame
    finally:
        cap.release()
    if meta.duration_s and stats.last_timestamp_s < meta.duration_s * 0.95 - 1.0:
        stats.ended_early = True


def extract_frame_jpeg(path: str, at_seconds: float = 1.0, quality: int = 85) -> Tuple[bytes, int, int]:
    """Grab a single frame as JPEG (for the zone editor's reference image)."""
    import cv2

    cap = cv2.VideoCapture(path)
    try:
        if at_seconds > 0:
            cap.set(cv2.CAP_PROP_POS_MSEC, at_seconds * 1000.0)
        ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()
        if not ok or frame is None:
            raise VideoError("UNDECODABLE_VIDEO", "Could not decode a reference frame")
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise VideoError("ENCODE_FAILED", "Could not encode reference frame")
        h, w = frame.shape[:2]
        return buf.tobytes(), w, h
    finally:
        cap.release()
