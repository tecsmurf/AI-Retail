"""One camera stream -> anonymous events.

Each camera runs in its own thread: connect to the recorder's stream, sample
frames at the analysis rate, detect and track people with the same pipeline
the cloud worker uses for recordings (``app.cv``), and put the resulting
events and queue-length samples in the outbox. Frames are analysed in memory
and then discarded; nothing is written to disk except an occasional still
image that the dashboard asked for.

A live stream is read by a small reader thread that keeps only the newest
frame, so a slow box analyses fewer frames instead of falling behind. A file
path (used for testing and for ``check-camera``) is read frame by frame.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
import uuid
from datetime import UTC, datetime
from typing import List, Optional, Tuple

from app.cv.event_engine import EntryLine, EventEngine
from app.cv.pipeline import PipelineConfig
from app.cv.stitcher import TrackStitcher
from app.cv.tracker import PersonTracker
from app.cv.zone_mapper import ZonePolygon
from purplesol_edge.outbox import Outbox

log = logging.getLogger("purplesol_edge.camera")

STALL_SECONDS = 15.0          # no new frame for this long = the stream is dead, reconnect
BACKOFF_START, BACKOFF_MAX = 2.0, 60.0
OCCUPANCY_STEP = 5            # queue-length samples are snapped to 5 s boundaries
SNAPSHOT_MAX_WIDTH = 1280
LIVE_SCHEMES = ("rtsp://", "rtsps://", "http://", "https://", "rtmp://")


def redact(url: str) -> str:
    """Hide the password of a stream address before it is logged or shown."""
    return re.sub(r"(://[^:/@\s]*):[^@\s]*@", r"\1:***@", url or "")


def is_live(url: str) -> bool:
    return url.lower().startswith(LIVE_SCHEMES)


def utc_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).isoformat()


def open_capture(url: str):
    import cv2

    if is_live(url):
        # TCP is far more reliable than UDP on store networks; the timeout
        # (microseconds) makes a dead recorder fail instead of hanging.
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp|timeout;15000000")
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap
    return cv2.VideoCapture(url)


def encode_still(frame) -> bytes:
    import cv2

    h, w = frame.shape[:2]
    if w > SNAPSHOT_MAX_WIDTH:
        frame = cv2.resize(frame, (SNAPSHOT_MAX_WIDTH, int(h * SNAPSHOT_MAX_WIDTH / w)))
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        raise RuntimeError("could not encode the still image")
    return buf.tobytes()


class _LatestFrame(threading.Thread):
    """Reads a live stream as fast as it arrives and keeps only the newest frame."""

    def __init__(self, cap) -> None:
        super().__init__(daemon=True)
        self.cap = cap
        self.lock = threading.Lock()
        self.frame = None
        self.frame_time = 0.0
        self.seq = 0
        self.ended = False
        self.stop_flag = threading.Event()

    def run(self) -> None:
        while not self.stop_flag.is_set():
            ok, frame = self.cap.read()
            if not ok or frame is None:
                self.ended = True
                return
            with self.lock:
                self.frame, self.frame_time, self.seq = frame, time.time(), self.seq + 1

    def take(self, after_seq: int) -> Tuple[Optional[object], float, int]:
        with self.lock:
            if self.seq == after_seq:
                return None, 0.0, after_seq
            return self.frame, self.frame_time, self.seq


class CameraWorker(threading.Thread):
    def __init__(self, camera: dict, url: str, outbox: Outbox, detector, *, loop_file: bool = False) -> None:
        super().__init__(daemon=True, name=f"camera-{camera['camera_code']}")
        self.camera = camera
        self.camera_id = camera["camera_id"]
        self.code = camera["camera_code"]
        self.url = url
        self.outbox = outbox
        self.detector = detector
        self.loop_file = loop_file
        self.cfg = PipelineConfig.from_dict(camera.get("pipeline"))
        self.zones = [
            ZonePolygon(name=z["name"], zone_type=z["zone_type"], polygon=z["polygon"], priority=z.get("priority", 0),
                        zone_id=z.get("id"))
            for z in camera.get("zones", [])
        ]
        self.entry_line = EntryLine.from_dict(camera.get("entry_line"))
        self.stop_flag = threading.Event()
        self._lock = threading.Lock()
        # health, read by the heartbeat
        self.status = "connecting"
        self.message: Optional[str] = None
        self.fps: Optional[float] = None
        self.last_frame_at: Optional[float] = None
        self.width: Optional[int] = None
        self.height: Optional[int] = None
        self._analysed = 0.0
        self._want_still = False
        self._still: Optional[bytes] = None
        self.frames_analysed = 0
        self.events_emitted = 0
        self.sessions = 0

    # ── called from the main loop ────────────────────────────────

    def health(self) -> dict:
        with self._lock:
            analysed, self._analysed = self._analysed, 0.0
            return {
                "camera_id": self.camera_id, "status": self.status, "message": self.message,
                "fps": round(self.fps, 2) if self.fps is not None else None,
                "last_frame_at": utc_iso(self.last_frame_at) if self.last_frame_at else None,
                "width": self.width, "height": self.height, "analysed_seconds": round(min(analysed, 3600.0), 1),
            }

    def request_still(self) -> None:
        self._want_still = True

    def take_still(self) -> Optional[bytes]:
        with self._lock:
            still, self._still = self._still, None
            return still

    def stop(self) -> None:
        self.stop_flag.set()

    # ── stream loop ──────────────────────────────────────────────

    def _set(self, status: str, message: Optional[str] = None) -> None:
        with self._lock:
            self.status, self.message = status, message

    def run(self) -> None:
        backoff = BACKOFF_START
        while not self.stop_flag.is_set():
            started = time.monotonic()
            try:
                self._session()
            except Exception as exc:  # noqa: BLE001 - one camera must never take the box down
                log.exception("camera %s failed", self.code)
                self._set("error", f"{type(exc).__name__}: {str(exc)[:200]}")
            if not is_live(self.url) and not self.loop_file:
                return
            if time.monotonic() - started > 60:
                backoff = BACKOFF_START  # it worked for a while: retry quickly
            if self.stop_flag.wait(backoff):
                return
            backoff = min(BACKOFF_MAX, backoff * 2)

    def _session(self) -> None:
        """One connection to the stream, from connect to disconnect."""
        self._set("connecting")
        cap = open_capture(self.url)
        if not cap.isOpened():
            cap.release()
            self._set("offline", "Cannot open the stream. Check the address, user name and password, and that the recorder is on.")
            log.warning("camera %s: cannot open %s", self.code, redact(self.url))
            return
        self.sessions += 1
        session = uuid.uuid4().hex[:6]
        live = is_live(self.url)
        import cv2

        native_fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        if not 1.0 <= native_fps <= 120.0:
            native_fps = 25.0
        analysis_fps = min(self.cfg.analysis_fps, native_fps)
        tracker = PersonTracker(frame_rate=analysis_fps, config=self.cfg.tracker)
        stitcher = TrackStitcher(self.cfg.stitch)
        engine = EventEngine(self.zones, self.entry_line, self.cfg.engine)
        interval = 1.0 / analysis_fps
        reader = None
        if live:
            reader = _LatestFrame(cap)
            reader.start()
        # Stream time 0 corresponds to this wall-clock moment.
        epoch = time.time()
        last_t = None
        last_seq = 0
        last_new_frame = time.monotonic()
        step = max(1, round(native_fps / analysis_fps))
        index = 0
        recent: List[float] = []
        log.info("camera %s connected (%s, %.1f fps analysed)", self.code, redact(self.url), analysis_fps)
        try:
            while not self.stop_flag.is_set():
                if live:
                    frame, frame_time, seq = reader.take(last_seq)
                    if frame is None:
                        if reader.ended:
                            self._set("offline", "The stream ended. Reconnecting.")
                            return
                        if time.monotonic() - last_new_frame > STALL_SECONDS:
                            self._set("offline", "No picture from the camera for 15 seconds. Reconnecting.")
                            return
                        time.sleep(0.01)
                        continue
                    last_seq, last_new_frame = seq, time.monotonic()
                    t = frame_time - epoch
                    if last_t is not None and t - last_t < interval * 0.9:
                        time.sleep(0.005)
                        continue
                else:
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        return
                    index += 1
                    if (index - 1) % step:
                        continue
                    t = (index - 1) / native_fps
                self._analyse(frame, t, epoch, session, tracker, stitcher, engine)
                with self._lock:
                    if last_t is not None:
                        self._analysed += min(t - last_t, 2.0)  # gaps are not coverage
                        recent.append(t - last_t)
                        recent[:] = recent[-25:]
                        self.fps = len(recent) / sum(recent) if sum(recent) > 0 else None
                    self.status, self.message = "online", None
                    self.last_frame_at = epoch + t
                    self.height, self.width = frame.shape[:2]
                last_t = t
        finally:
            if reader is not None:
                reader.stop_flag.set()
            # Close open visits so their dwell and wait times are not lost.
            if last_t is not None:
                engine.finish("stream_end")
                self._drain(engine, epoch, session)
            cap.release()
            if reader is not None:
                reader.join(timeout=2)

    def _analyse(self, frame, t: float, epoch: float, session: str, tracker, stitcher, engine) -> None:
        h, w = frame.shape[:2]
        detections = self.detector.detect(frame, confidence=self.cfg.detector_confidence)
        tracked = tracker.update(detections)
        observations = [
            (tb.track_id, (tb.bbox[0] / w, tb.bbox[1] / h, tb.bbox[2] / w, tb.bbox[3] / h), tb.confidence)
            for tb in tracked
        ]
        observations = stitcher.update(t, observations)
        engine.update(t, observations)
        self.frames_analysed += 1
        self._drain(engine, epoch, session)
        if self._want_still:
            self._want_still = False
            still = encode_still(frame)
            with self._lock:
                self._still = still

    def _drain(self, engine: EventEngine, epoch: float, session: str) -> None:
        """Move finished events and samples from the engine to the outbox."""
        events, engine.events = engine.events, []
        samples, engine.occupancy = engine.occupancy, []
        if events:
            rows = []
            for e in events:
                track = f"L{session}-T{e.track_id}"
                rows.append({
                    # Time is part of the key: a re-acquired track id restarts its sequence.
                    "key": f"{track}-{int(e.t * 10):x}-{e.seq}-{e.event_type}"[:64],
                    "camera_id": self.camera_id, "event_type": e.event_type,
                    "timestamp": utc_iso(epoch + e.t), "track": track,
                    "zone_id": e.zone_id, "zone_name": e.zone_name, "zone_type": e.zone_type,
                    "dwell_seconds": round(e.dwell_seconds, 2) if e.dwell_seconds is not None else None,
                    "queue_wait_seconds": round(e.queue_wait_seconds, 2) if e.queue_wait_seconds is not None else None,
                    "queue_abandoned": e.queue_abandoned,
                    "confidence": round(e.confidence, 3) if e.confidence is not None else None,
                    "box": [round(v, 4) for v in e.box] if e.box else None,
                })
            self.outbox.push("event", rows)
            self.events_emitted += len(rows)
        if samples:
            rows = []
            for t, zone, ztype, count in samples:
                ts = int(epoch + t)
                ts -= ts % OCCUPANCY_STEP
                rows.append({"camera_id": self.camera_id, "zone_name": zone, "zone_type": ztype,
                             "timestamp": utc_iso(ts), "count": int(count)})
            self.outbox.push("occupancy", rows)


def probe(url: str, seconds: float = 5.0) -> dict:
    """Open a stream briefly and report what arrives (for ``check-camera``)."""
    import cv2

    cap = open_capture(url)
    if not cap.isOpened():
        cap.release()
        return {"ok": False, "message": "Cannot open the stream. Check the address, user name and password."}
    frames, first, started = 0, None, time.monotonic()
    while time.monotonic() - started < seconds:
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        frames += 1
        if first is None:
            first = frame
    elapsed = time.monotonic() - started
    reported = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    if first is None:
        return {"ok": False, "message": "The stream opened but no picture arrived."}
    h, w = first.shape[:2]
    return {"ok": True, "width": w, "height": h, "frames": frames, "seconds": round(elapsed, 1),
            "measured_fps": round(frames / elapsed, 1) if elapsed > 0 else None,
            "reported_fps": round(reported, 1) if reported else None, "still": encode_still(first)}


__all__ = ["CameraWorker", "probe", "redact", "is_live"]
