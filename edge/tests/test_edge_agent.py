"""Edge box: send queue, settings, camera worker and the agent loop.

Run from ``backend/`` so the shared CV code and test fakes are importable:

    cd backend && PYTHONPATH=.:../edge python -m pytest ../edge/tests -q
"""

from __future__ import annotations

import json
import os
import stat
import time

import pytest

from purplesol_edge.agent import Agent, Settings, load_settings, save_token
from purplesol_edge.camera import CameraWorker, redact
from purplesol_edge.client import ApiError, Unauthorized
from purplesol_edge.outbox import Outbox
from tests.fakes import FakeDetector, queue_then_counter, write_video

QUEUE = [[0.0, 0.5], [0.5, 0.5], [0.5, 1.0], [0.0, 1.0]]
COUNTER = [[0.5, 0.5], [1.0, 0.5], [1.0, 1.0], [0.5, 1.0]]
CAMERA = {
    "camera_id": "11111111-1111-1111-1111-111111111111", "camera_code": "BILL", "camera_type": "billing",
    "zones": [
        {"id": "z1", "name": "Queue", "zone_type": "QUEUE", "polygon": QUEUE, "priority": 0},
        {"id": "z2", "name": "Counter", "zone_type": "BILLING", "polygon": COUNTER, "priority": 0},
    ],
    "entry_line": None,
    "pipeline": {"analysis_fps": 5.0},
}


def test_outbox_survives_restart_and_keeps_order(tmp_path):
    path = str(tmp_path / "outbox.db")
    box = Outbox(path)
    box.push("event", [{"n": 1}, {"n": 2}])
    box.push("occupancy", [{"n": 3}])
    box.close()
    box = Outbox(path)
    assert box.count() == 3
    events = box.peek("event", 10)
    assert [e["n"] for _, e in events] == [1, 2]
    box.delete([events[0][0]])
    assert [e["n"] for _, e in box.peek("event", 10)] == [2] and box.count() == 2
    box.close()


def test_outbox_drops_oldest_beyond_limit(tmp_path):
    box = Outbox(str(tmp_path / "o.db"), max_rows=3)
    box.push("event", [{"n": i} for i in range(5)])
    assert [e["n"] for _, e in box.peek("event", 10)] == [2, 3, 4] and box.dropped == 2
    box.close()


def test_stream_passwords_are_redacted():
    assert redact("rtsp://admin:S3cret!@192.168.1.64:554/Streaming/Channels/102") == \
        "rtsp://admin:***@192.168.1.64:554/Streaming/Channels/102"
    assert redact("rtsp://192.168.1.64/stream") == "rtsp://192.168.1.64/stream"


def test_settings_file_env_overrides_and_token_permissions(tmp_path):
    cfg = tmp_path / "edge.json"
    cfg.write_text(json.dumps({"api_url": "https://api.example.invalid/", "state_dir": str(tmp_path / "state"),
                               "cameras": {"CAM1": "rtsp://u:p@10.0.0.2/1"}}))
    s = load_settings(str(cfg), env={})
    assert s.api_url == "https://api.example.invalid" and s.cameras == {"CAM1": "rtsp://u:p@10.0.0.2/1"} and s.token is None
    save_token(s, "pse_abc")
    assert stat.S_IMODE(os.stat(s.token_path).st_mode) == 0o600
    assert load_settings(str(cfg), env={}).token == "pse_abc"
    s = load_settings(str(cfg), env={"PURPLESOL_API_URL": "http://localhost:8000", "PURPLESOL_EDGE_TOKEN": "pse_env"})
    assert s.api_url == "http://localhost:8000" and s.token == "pse_env"
    cfg.write_text(json.dumps({"cameras": ["rtsp://x"]}))
    with pytest.raises(SystemExit):
        load_settings(str(cfg), env={})


@pytest.mark.cv
def test_camera_worker_turns_a_stream_into_events(tmp_path):
    video = str(tmp_path / "bill.mp4")
    write_video(video, 16, 25, queue_then_counter)
    outbox = Outbox(str(tmp_path / "o.db"))
    worker = CameraWorker(CAMERA, video, outbox, FakeDetector())
    worker.request_still()
    before = time.time()
    worker.run()  # a file ends, so run() returns
    events = [e for _, e in outbox.peek("event", 100)]
    types = [e["event_type"] for e in events]
    assert types.count("QUEUE_ENTER") == 1 and types.count("QUEUE_EXIT") == 1 and "QUEUE_COMPLETED" in types
    wait = next(e for e in events if e["event_type"] == "QUEUE_EXIT")["queue_wait_seconds"]
    # Stands still for 6 s, then crosses the queue zone's right edge at about 8.5 s.
    assert 7.5 <= wait <= 9.5
    # Keys are unique, tracks are labelled per connection, nothing identifies a person.
    assert len({e["key"] for e in events}) == len(events)
    assert all(e["track"].startswith("L") and e["camera_id"] == CAMERA["camera_id"] for e in events)
    assert set(events[0]) == {"key", "camera_id", "event_type", "timestamp", "track", "zone_id", "zone_name", "zone_type",
                              "dwell_seconds", "queue_wait_seconds", "queue_abandoned", "confidence", "box"}
    samples = [s for _, s in outbox.peek("occupancy", 100)]
    assert samples and all(int(s["timestamp"][17:19]) % 5 == 0 for s in samples)
    assert max(s["count"] for s in samples if s["zone_name"] == "Queue") == 1
    health = worker.health()
    assert health["status"] == "online" and (health["width"], health["height"]) == (640, 360)
    assert 14.0 <= health["analysed_seconds"] <= 16.5 and worker.health()["analysed_seconds"] == 0
    assert health["last_frame_at"] >= "2020" and worker.frames_analysed >= 75
    still = worker.take_still()
    assert still and still.startswith(b"\xff\xd8") and worker.take_still() is None
    assert time.time() - before < 60
    outbox.close()


@pytest.mark.cv
def test_unreachable_stream_reports_offline(tmp_path):
    outbox = Outbox(str(tmp_path / "o.db"))
    worker = CameraWorker(CAMERA, str(tmp_path / "missing.mp4"), outbox, FakeDetector())
    worker.run()
    health = worker.health()
    assert health["status"] == "offline" and "Cannot open the stream" in health["message"]
    assert outbox.count() == 0
    outbox.close()


class FakeClient:
    def __init__(self):
        self.sent, self.beats, self.stills = [], [], []
        self.fail = None
        self.config_version = "v1"
        self.snapshot_requests = []

    def config(self):
        return {"cameras": [CAMERA, {**CAMERA, "camera_id": "22222222-2222-2222-2222-222222222222", "camera_code": "ENT"}],
                "config_version": self.config_version, "heartbeat_seconds": 30}

    def heartbeat(self, payload):
        if self.fail:
            raise self.fail
        self.beats.append(payload)
        return {"config_changed": payload["config_version"] != self.config_version,
                "snapshot_requests": self.snapshot_requests}

    def send(self, events, occupancy):
        if self.fail:
            raise self.fail
        self.sent.append((events, occupancy))
        return {"inserted": len(events)}

    def snapshot(self, camera_id, jpeg):
        self.stills.append((camera_id, jpeg))


class StubWorker:
    def __init__(self, camera, url, outbox, detector):
        self.camera, self.url, self.code = camera, url, camera["camera_code"]
        self.started = self.stopped = self.want_still = False
        self.still = None
        self.analysed = 30.0

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def join(self, timeout=None):
        pass

    def health(self):
        analysed, self.analysed = self.analysed, 0.0
        return {"camera_id": self.camera["camera_id"], "status": "online", "analysed_seconds": analysed}

    def add_analysed(self, seconds):
        self.analysed += seconds

    def request_still(self):
        self.want_still = True

    def take_still(self):
        still, self.still = self.still, None
        return still


def make_agent(tmp_path, client):
    settings = Settings(api_url="http://x", state_dir=str(tmp_path), cameras={"BILL": "rtsp://u:p@10.0.0.2/1"})
    outbox = Outbox(str(tmp_path / "o.db"))
    return Agent(settings, client, outbox, detector=None, worker_factory=StubWorker), outbox


def test_agent_starts_configured_cameras_and_reports_the_rest(tmp_path):
    client = FakeClient()
    agent, outbox = make_agent(tmp_path, client)
    agent.apply_config(client.config())
    assert list(agent.workers) == [CAMERA["camera_id"]] and agent.workers[CAMERA["camera_id"]].started
    client.snapshot_requests = [CAMERA["camera_id"]]
    agent.heartbeat()
    beat = client.beats[-1]
    by_id = {c["camera_id"]: c for c in beat["cameras"]}
    assert by_id[CAMERA["camera_id"]]["status"] == "online"
    assert by_id["22222222-2222-2222-2222-222222222222"]["status"] == "unconfigured"
    assert "rtsp" not in json.dumps(beat)  # stream addresses never leave the box
    worker = agent.workers[CAMERA["camera_id"]]
    assert worker.want_still
    worker.still = b"\xff\xd8jpeg"
    agent.upload_stills()
    assert client.stills == [(CAMERA["camera_id"], b"\xff\xd8jpeg")]
    # A configuration change restarts only the cameras whose settings changed.
    client.config_version = "v2"
    agent.heartbeat()
    assert agent.config["config_version"] == "v2" and agent.workers[CAMERA["camera_id"]] is worker
    outbox.close()


def test_agent_keeps_events_while_offline_and_drops_rejected_batches(tmp_path):
    client = FakeClient()
    agent, outbox = make_agent(tmp_path, client)
    outbox.push("event", [{"key": "k1"}, {"key": "k2"}])
    outbox.push("occupancy", [{"count": 1}])
    client.fail = ApiError(0, "cannot reach the cloud")
    assert agent.flush() is False and outbox.count() == 3  # nothing lost while offline
    client.fail = None
    assert agent.flush() is True and outbox.count() == 0
    assert client.sent == [([{"key": "k1"}, {"key": "k2"}], [{"count": 1}])] and agent.sent_events == 2
    outbox.push("event", [{"key": "bad"}])
    client.fail = ApiError(422, "invalid")
    assert agent.flush() is True and outbox.count() == 0  # a batch the cloud will never accept is dropped
    outbox.push("event", [{"key": "k3"}])
    client.fail = Unauthorized(401, "revoked")
    with pytest.raises(Unauthorized):
        agent.flush()
    assert outbox.count() == 1  # kept for after re-pairing
    outbox.close()


def test_analysed_time_is_reported_after_a_failed_check_in(tmp_path, caplog):
    client = FakeClient()
    agent, outbox = make_agent(tmp_path, client)
    agent.apply_config(client.config())
    client.fail = ApiError(0, "cannot reach the cloud")
    with caplog.at_level("WARNING", logger="purplesol_edge"):
        for _ in range(3):
            with pytest.raises(ApiError):
                agent.heartbeat()
            agent._offline("cannot reach the cloud")
    # A long outage is logged once, not on every attempt.
    assert sum("cloud not reachable" in r.message for r in caplog.records) == 1
    client.fail = None
    agent.heartbeat()
    assert client.beats[-1]["cameras"][0]["analysed_seconds"] == 30.0 and agent.last_error is None
    agent.heartbeat()
    assert client.beats[-1]["cameras"][0]["analysed_seconds"] == 0.0
    outbox.close()


def test_agent_exits_with_code_3_when_the_token_is_revoked(tmp_path):
    client = FakeClient()
    agent, outbox = make_agent(tmp_path, client)

    def revoked():
        raise Unauthorized(401, "This box is not paired (or was removed). Pair it again.")

    client.config = revoked
    assert agent.run() == 3
    outbox.close()
