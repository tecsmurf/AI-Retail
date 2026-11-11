"""Edge box command line.

    python -m purplesol_edge pair ABCDE-FGHJK     # once, with the code from the dashboard
    python -m purplesol_edge cameras              # cameras of this store and which have a stream address
    python -m purplesol_edge check-camera CAM1    # try one stream and report what arrives
    python -m purplesol_edge run                  # analyse the streams and send events (keep running)

Settings come from a JSON file (``edge.json`` by default, see
``edge.example.json``) and can be overridden by environment variables:

    PURPLESOL_EDGE_CONFIG   path of the settings file
    PURPLESOL_API_URL       address of the cloud API
    PURPLESOL_EDGE_STATE    folder for the token and the send queue
    PURPLESOL_EDGE_TOKEN    token (instead of the token file)

Stream addresses contain the recorder's user name and password. They are read
from the settings file on this box and are never sent to the cloud or logged.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import socket
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from purplesol_edge import __version__
from purplesol_edge.client import ApiClient, ApiError, Unauthorized
from purplesol_edge.outbox import Outbox

log = logging.getLogger("purplesol_edge")

EXIT_NOT_PAIRED = 3
SEND_EVERY_SECONDS = 2.0
OFFLINE_LOG_EVERY_SECONDS = 60.0
EVENT_BATCH = 500
SAMPLE_BATCH = 1000


@dataclass
class Settings:
    api_url: str = ""
    state_dir: str = "./state"
    # camera code -> stream address (rtsp://user:password@recorder/...)
    cameras: Dict[str, str] = field(default_factory=dict)
    token: Optional[str] = None
    model: Optional[str] = None
    device: Optional[str] = None

    @property
    def token_path(self) -> Path:
        return Path(self.state_dir) / "token"

    @property
    def outbox_path(self) -> Path:
        return Path(self.state_dir) / "outbox.db"


def load_settings(path: Optional[str] = None, env: Optional[dict] = None) -> Settings:
    env = os.environ if env is None else env
    path = path or env.get("PURPLESOL_EDGE_CONFIG") or "edge.json"
    data: dict = {}
    if Path(path).exists():
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except ValueError as exc:
            sys.exit(f"{path} is not valid JSON: {exc}")
        if not isinstance(data, dict):
            sys.exit(f"{path} must contain a JSON object")
    cameras = data.get("cameras") or {}
    if not isinstance(cameras, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in cameras.items()):
        sys.exit('"cameras" must map camera codes to stream addresses, e.g. {"CAM1": "rtsp://..."}')
    s = Settings(
        api_url=str(data.get("api_url") or ""), state_dir=str(data.get("state_dir") or "./state"),
        cameras=cameras, model=data.get("model"), device=data.get("device"),
    )
    s.api_url = (env.get("PURPLESOL_API_URL") or s.api_url).rstrip("/")
    s.state_dir = env.get("PURPLESOL_EDGE_STATE") or s.state_dir
    s.token = env.get("PURPLESOL_EDGE_TOKEN") or None
    if not s.token and s.token_path.exists():
        s.token = s.token_path.read_text(encoding="utf-8").strip() or None
    return s


def save_token(settings: Settings, token: str) -> None:
    Path(settings.state_dir).mkdir(parents=True, exist_ok=True)
    path = settings.token_path
    # Create with owner-only permissions from the start.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(token + "\n")
    os.chmod(path, 0o600)


def _client(settings: Settings, need_token: bool = True) -> ApiClient:
    if not settings.api_url:
        sys.exit('Set "api_url" in edge.json (or PURPLESOL_API_URL) to the address of the cloud API.')
    if need_token and not settings.token:
        print("This box is not paired yet. Run: python -m purplesol_edge pair CODE", file=sys.stderr)
        sys.exit(EXIT_NOT_PAIRED)
    return ApiClient(settings.api_url, settings.token)


class LockedDetector:
    """One model shared by all camera threads; inference runs one frame at a time."""

    def __init__(self, detector) -> None:
        self._detector = detector
        self._lock = threading.Lock()

    def detect(self, frame, confidence=None):
        with self._lock:
            return self._detector.detect(frame, confidence=confidence)


def build_detector(settings: Settings):
    from app.cv.detector import PersonDetector

    det = PersonDetector(model_path=settings.model, device=settings.device)
    det.load()
    log.info("model %s loaded on %s", os.path.basename(det.model_path or ""), det.device)
    return LockedDetector(det)


# ── commands ─────────────────────────────────────────────────────


def cmd_pair(settings: Settings, code: str) -> int:
    client = _client(settings, need_token=False)
    try:
        res = client.pair(code, socket.gethostname())
    except ApiError as exc:
        print(f"Pairing failed: {exc.message}", file=sys.stderr)
        return 1
    save_token(settings, res["token"])
    print(f"Paired as \"{res['name']}\" for store {res['store']['name']} ({res['store']['store_code']}).")
    print(f"Token saved to {settings.token_path}. Next: python -m purplesol_edge cameras")
    return 0


def cmd_cameras(settings: Settings) -> int:
    from purplesol_edge.camera import redact

    try:
        cfg = _client(settings).config()
    except Unauthorized as exc:
        print(f"{exc.message}", file=sys.stderr)
        return EXIT_NOT_PAIRED
    except ApiError as exc:
        print(f"Could not load the configuration: {exc.message}", file=sys.stderr)
        return 1
    print(f"Store: {cfg['store']['name']} ({cfg['store']['store_code']})")
    known = set()
    for cam in cfg["cameras"]:
        known.add(cam["camera_code"])
        url = settings.cameras.get(cam["camera_code"])
        extras = f"{len(cam['zones'])} zones" + (", entry line" if cam.get("entry_line") else "")
        print(f"  {cam['camera_code']:10} {cam['camera_type']:9} {extras:24} "
              f"{redact(url) if url else 'NO STREAM ADDRESS in edge.json'}")
    for code in sorted(set(settings.cameras) - known):
        print(f"  {code:10} is in edge.json but not in the dashboard: add the camera there or fix the code")
    return 0


def cmd_check(settings: Settings, code: str, save: Optional[str]) -> int:
    from purplesol_edge.camera import probe, redact

    url = settings.cameras.get(code)
    if not url:
        print(f'No stream address for "{code}" in edge.json.', file=sys.stderr)
        return 1
    print(f"Opening {redact(url)} ...")
    res = probe(url)
    if not res["ok"]:
        print(res["message"], file=sys.stderr)
        return 1
    print(f"OK: {res['width']}x{res['height']}, {res['frames']} frames in {res['seconds']} s "
          f"({res['measured_fps']} fps measured, {res['reported_fps']} reported)")
    if save:
        Path(save).write_bytes(res["still"])
        print(f"Still image saved to {save} (stays on this box)")
    return 0


class Agent:
    def __init__(self, settings: Settings, client: ApiClient, outbox: Outbox, detector, worker_factory=None) -> None:
        from purplesol_edge.camera import CameraWorker

        self.settings = settings
        self.client = client
        self.outbox = outbox
        self.detector = detector
        self.worker_factory = worker_factory or CameraWorker
        self.workers: Dict[str, object] = {}   # camera_id -> CameraWorker
        self.worker_cfg: Dict[str, str] = {}   # camera_id -> config fingerprint
        self.config: Optional[dict] = None
        self.stopping = threading.Event()
        self.heartbeat_seconds = 30.0
        self.sent_events = 0
        self.last_error: Optional[str] = None
        self._offline_logged = 0.0

    # configuration ------------------------------------------------

    def apply_config(self, cfg: dict) -> None:
        """Start, restart or stop camera threads so they match the cloud configuration."""
        self.config = cfg
        self.heartbeat_seconds = float(cfg.get("heartbeat_seconds") or 30)
        wanted = {}
        for cam in cfg["cameras"]:
            url = self.settings.cameras.get(cam["camera_code"])
            if url:
                fingerprint = json.dumps({k: v for k, v in cam.items() if k != "has_reference_frame"}, sort_keys=True) + url
                wanted[cam["camera_id"]] = (cam, url, fingerprint)
        for cam_id in list(self.workers):
            if cam_id not in wanted or wanted[cam_id][2] != self.worker_cfg[cam_id]:
                self.workers.pop(cam_id).stop()
                self.worker_cfg.pop(cam_id)
        for cam_id, (cam, url, fingerprint) in wanted.items():
            if cam_id not in self.workers:
                worker = self.worker_factory(cam, url, self.outbox, self.detector)
                self.workers[cam_id] = worker
                self.worker_cfg[cam_id] = fingerprint
                worker.start()
                log.info("camera %s started", cam["camera_code"])

    # sending ------------------------------------------------------

    def flush(self) -> bool:
        """Send one batch from the outbox. Returns True when something was sent."""
        events = self.outbox.peek("event", EVENT_BATCH)
        samples = self.outbox.peek("occupancy", SAMPLE_BATCH)
        if not events and not samples:
            return False
        ids = [i for i, _ in events] + [i for i, _ in samples]
        try:
            res = self.client.send([e for _, e in events], [s for _, s in samples])
        except Unauthorized:
            raise
        except ApiError as exc:
            if exc.status in (413, 422):
                # The cloud will never accept this batch; keeping it would block the queue forever.
                log.error("the cloud rejected a batch of %d items (%s); dropping it", len(ids), exc.message)
                self.outbox.delete(ids)
                return True
            self._offline(exc.message)
            return False
        self.outbox.delete(ids)
        self.sent_events += res.get("inserted", 0)
        self._online()
        return True

    def _offline(self, message: str) -> None:
        """Note that the cloud cannot be reached, without filling the log during a long outage."""
        now = time.monotonic()
        if self.last_error is None or now - self._offline_logged >= OFFLINE_LOG_EVERY_SECONDS:
            self._offline_logged = now
            log.warning("cloud not reachable (%s); cameras keep running, %d items wait in the queue",
                        message, self.outbox.count())
        self.last_error = message

    def _online(self) -> None:
        if self.last_error is not None:
            log.info("cloud reachable again; sending %d waiting items", self.outbox.count())
        self.last_error = None

    def heartbeat(self) -> None:
        cameras = [w.health() for w in self.workers.values()]
        running = set(self.workers)
        for cam in (self.config or {}).get("cameras", []):
            if cam["camera_id"] not in running:
                cameras.append({"camera_id": cam["camera_id"], "status": "unconfigured",
                                "message": "No stream address for this camera in the box's edge.json."})
        try:
            res = self.client.heartbeat({
                "agent_version": __version__, "hostname": socket.gethostname(),
                "config_version": (self.config or {}).get("config_version"), "cameras": cameras,
                "stats": {"queued": self.outbox.count(), "sent_events": self.sent_events,
                          "dropped": self.outbox.dropped},
            })
        except ApiError:
            # Not delivered: keep the analysed time so the next check-in reports it.
            for cam in cameras:
                worker = self.workers.get(cam["camera_id"])
                if worker is not None and cam.get("analysed_seconds"):
                    worker.add_analysed(cam["analysed_seconds"])
            raise
        self._online()
        if res.get("config_changed"):
            log.info("configuration changed in the dashboard; reloading")
            self.apply_config(self.client.config())
        for cam_id in res.get("snapshot_requests", []):
            worker = self.workers.get(cam_id)
            if worker is not None:
                worker.request_still()

    def upload_stills(self) -> None:
        for cam_id, worker in self.workers.items():
            still = worker.take_still()
            if still:
                try:
                    self.client.snapshot(cam_id, still)
                    log.info("still image of %s sent", worker.code)
                except Unauthorized:
                    raise
                except ApiError as exc:
                    log.warning("could not send the still image of %s: %s", worker.code, exc.message)

    # main loop ----------------------------------------------------

    def run(self) -> int:
        next_beat = 0.0
        while not self.stopping.is_set():
            try:
                if self.config is None:
                    self.apply_config(self.client.config())
                if time.monotonic() >= next_beat:
                    next_beat = time.monotonic() + self.heartbeat_seconds
                    self.heartbeat()
                self.upload_stills()
                while self.flush() and not self.stopping.is_set():
                    pass
            except Unauthorized as exc:
                log.error("%s", exc.message)
                self.shutdown()
                return EXIT_NOT_PAIRED
            except ApiError as exc:
                # Offline: cameras keep analysing, the queue keeps the results.
                self._offline(exc.message)
            self.stopping.wait(SEND_EVERY_SECONDS)
        self.shutdown()
        return 0

    def shutdown(self) -> None:
        for worker in self.workers.values():
            worker.stop()
        for worker in self.workers.values():
            worker.join(timeout=5)
        try:
            while self.flush():
                pass
        except ApiError:
            pass


def cmd_run(settings: Settings) -> int:
    client = _client(settings)
    Path(settings.state_dir).mkdir(parents=True, exist_ok=True)
    outbox = Outbox(str(settings.outbox_path))
    log.info("edge box %s starting; %d items waiting in the queue", __version__, outbox.count())
    agent = Agent(settings, client, outbox, build_detector(settings))
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: agent.stopping.set())
    try:
        return agent.run()
    finally:
        outbox.close()


def main(argv: Optional[list] = None) -> None:
    parser = argparse.ArgumentParser(prog="purplesol_edge", description="In-store edge box")
    parser.add_argument("--config", help="settings file (default: edge.json or PURPLESOL_EDGE_CONFIG)")
    parser.add_argument("--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pair", help="connect this box to a store with the code from the dashboard")
    p.add_argument("code")
    sub.add_parser("cameras", help="list the store's cameras and their stream addresses")
    c = sub.add_parser("check-camera", help="try one camera stream")
    c.add_argument("code")
    c.add_argument("--save", metavar="FILE", help="save one still image to this file on the box")
    sub.add_parser("run", help="analyse the streams and send events")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings(args.config)
    if args.cmd == "pair":
        code = cmd_pair(settings, args.code)
    elif args.cmd == "cameras":
        code = cmd_cameras(settings)
    elif args.cmd == "check-camera":
        code = cmd_check(settings, args.code, args.save)
    else:
        code = cmd_run(settings)
    sys.exit(code)
