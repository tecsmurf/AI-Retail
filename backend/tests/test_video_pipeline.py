"""Video decoding/validation and the full pipeline on synthetic footage."""

from __future__ import annotations

import os
import subprocess

import pytest

from app.cv.event_engine import EntryLine
from app.cv.pipeline import PipelineConfig, run_pipeline
from app.cv.video_io import VideoError, probe_video
from app.cv.zone_mapper import ZonePolygon
from tests.fakes import FakeDetector, queue_then_counter, write_video

QUEUE = ZonePolygon("Queue", "QUEUE", [(0, 0.5), (0.5, 0.5), (0.5, 1), (0, 1)])
COUNTER = ZonePolygon("Counter", "BILLING", [(0.5, 0.5), (1, 0.5), (1, 1), (0.5, 1)])


def test_probe_rejects_empty_and_corrupt_files(tmp_path):
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    with pytest.raises(VideoError) as e:
        probe_video(str(empty))
    assert e.value.code == "EMPTY_VIDEO"
    junk = tmp_path / "junk.mp4"
    junk.write_bytes(os.urandom(4096))
    with pytest.raises(VideoError) as e:
        probe_video(str(junk))
    assert e.value.code in ("INVALID_VIDEO", "UNDECODABLE_VIDEO")


def test_probe_reads_metadata(tmp_path):
    p = tmp_path / "v.mp4"
    write_video(str(p), 3, 10, lambda t: None)
    meta = probe_video(str(p))
    assert (meta.width, meta.height) == (640, 360)
    assert meta.fps == pytest.approx(10, abs=0.1)
    assert meta.duration_s == pytest.approx(3, abs=0.2)


@pytest.mark.skipif(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0, reason="needs ffmpeg")
def test_truncated_video_processes_what_decodes(tmp_path):
    p = tmp_path / "v.mp4"
    write_video(str(p), 10, 10, queue_then_counter)
    full = p.read_bytes()
    cut = tmp_path / "cut.mp4"
    cut.write_bytes(full[: len(full) // 2])
    try:
        meta = probe_video(str(cut))
    except VideoError as e:  # moov atom at the end: the file is unusable, reported as such
        assert e.code in ("INVALID_VIDEO", "UNDECODABLE_VIDEO")
        return
    res = run_pipeline(str(cut), [QUEUE, COUNTER], None, PipelineConfig(), detector=FakeDetector())
    assert res.stats["decoded_seconds"] <= meta.duration_s + 0.5


def test_pipeline_end_to_end_queue_to_counter(tmp_path):
    p = tmp_path / "v.mp4"
    write_video(str(p), 15, 10, queue_then_counter)
    res = run_pipeline(str(p), [QUEUE, COUNTER], None, PipelineConfig(), detector=FakeDetector(),
                       artifact_dir=str(tmp_path / "art"))
    types = [e.event_type for e in res.events]
    assert types.count("QUEUE_ENTER") == 1 and types.count("QUEUE_COMPLETED") == 1
    wait = next(e for e in res.events if e.event_type == "QUEUE_EXIT").queue_wait_seconds
    assert wait == pytest.approx(8.5, abs=1.0)  # until the box's foot point leaves the queue polygon
    assert res.stats["tracks_created"] == 1
    assert os.path.exists(res.tracks_artifact) and res.snapshot_paths


def test_pipeline_entry_line(tmp_path):
    p = tmp_path / "v.mp4"
    # Walks downward across a horizontal line at y=0.5 (180 px).
    write_video(str(p), 6, 10, lambda t: (320, int(100 + 40 * t)))
    line = EntryLine((0.1, 0.5), (0.9, 0.5), "right")
    res = run_pipeline(str(p), [], line, PipelineConfig(), detector=FakeDetector())
    assert [e.event_type for e in res.events] == ["ENTRY"]


def test_pipeline_cancellation(tmp_path):
    from app.cv.pipeline import Cancelled

    p = tmp_path / "v.mp4"
    write_video(str(p), 5, 10, queue_then_counter)
    with pytest.raises(Cancelled):
        run_pipeline(str(p), [QUEUE], None, PipelineConfig(), detector=FakeDetector(), should_cancel=lambda: True)


@pytest.mark.cv
def test_real_detector_returns_no_people_on_blank_frame():
    np = pytest.importorskip("numpy")
    pytest.importorskip("ultralytics")
    from app.cv.detector import PersonDetector

    det = PersonDetector()
    assert det.detect(np.zeros((360, 640, 3), dtype=np.uint8)) == []
    assert det.model_sha256 and len(det.model_sha256) == 64
