"""Upload -> durable job -> worker -> events -> analytics, plus job lifecycle."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, update

from app.database import async_session, utcnow
from app.models.event import Event
from app.models.jobs import ProcessingJob
from app.services import job_service
from app.worker import Worker
from tests.fakes import FakeDetector, queue_then_counter, write_video
from tests.test_api import make_camera, make_store

ZONES = [
    {"zone_code": "Q", "name": "Queue", "zone_type": "QUEUE", "polygon": [[0, 0.5], [0.5, 0.5], [0.5, 1], [0, 1]]},
    {"zone_code": "C", "name": "Counter", "zone_type": "BILLING", "polygon": [[0.5, 0.5], [1, 0.5], [1, 1], [0.5, 1]]},
]


async def upload(client, store_id, camera_id, path, recorded_start="2026-03-08T18:00:00+05:30", start=True):
    data = Path(path).read_bytes()
    r = await client.post("/api/videos", json={
        "store_id": store_id, "camera_id": camera_id, "filename": "clip.mp4", "size_bytes": len(data),
        "content_type": "video/mp4", "recorded_start": recorded_start,
    })
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["upload"]["direct_to_storage"] is False
    r = await client.put(created["upload"]["url"], content=data, headers={"Content-Type": "video/mp4"})
    assert r.status_code == 204, r.text
    r = await client.post(f"/api/videos/{created['video']['id']}/complete", json={"start_processing": start})
    assert r.status_code == 200, r.text
    return created["video"]["id"], r.json()


@pytest.fixture
def clip(tmp_path):
    p = tmp_path / "clip.mp4"
    write_video(str(p), 15, 10, queue_then_counter)
    return str(p)


async def setup_camera(admin):
    store = await make_store(admin)
    cam = await make_camera(admin, store["id"], "CAM5", "billing")
    assert (await admin.put(f"/api/cameras/{cam['id']}/config", json={"zones": ZONES})).status_code == 200
    return store, cam


async def run_worker_once():
    await Worker(worker_id="test-worker", detector_factory=FakeDetector).run(once=True)


async def test_upload_process_and_analytics_end_to_end(admin, clip):
    store, cam = await setup_camera(admin)
    video_id, job = await upload(admin, store["id"], cam["id"], clip)
    assert job["status"] == "queued" and job["config"]["camera_config_version"] == 2

    await run_worker_once()

    job = (await admin.get(f"/api/jobs/{job['id']}")).json()
    assert job["status"] == "completed", job
    assert job["results"]["tracks_created"] == 1
    assert job["results"]["events"]["QUEUE_COMPLETED"] == 1
    assert job["model_name"] == "fake-detector" and job["pipeline_version"]
    snap = job["artifacts"]["snapshots"][0].rsplit("/", 1)[-1]
    r = await admin.get(f"/api/jobs/{job['id']}/artifacts/{snap}")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"

    # Recording started 18:00 IST on 8 March -> events on that local day.
    q = (await admin.get(f"/api/analytics/{store['id']}/queue",
                         params={"start": "2026-03-08", "end": "2026-03-08"})).json()
    assert q["queue_visits"] == 1 and q["completed"] == 1 and q["abandoned"] == 0
    assert q["median_wait_seconds"] == pytest.approx(8.5, abs=1.0)
    cams = (await admin.get(f"/api/stores/{store['id']}/cameras")).json()
    assert cams[0]["has_reference_frame"] and cams[0]["resolution_width"] == 640
    assert (await admin.get(f"/api/cameras/{cam['id']}/reference-frame")).status_code == 200
    status = (await admin.get("/api/system/status")).json()
    assert status["workers"][0]["worker_id"] == "test-worker"


async def test_reprocessing_replaces_previous_results(admin, clip):
    store, cam = await setup_camera(admin)
    video_id, job1 = await upload(admin, store["id"], cam["id"], clip)
    await run_worker_once()
    r = await admin.post("/api/jobs", json={"video_id": video_id})
    assert r.status_code == 201, r.text
    await run_worker_once()
    async with async_session() as db:
        jobs = {j.id: j for j in (await db.execute(select(ProcessingJob))).scalars().all()}
        per_job = dict((await db.execute(select(Event.job_id, func.count()).group_by(Event.job_id))).all())
    assert len(per_job) == 1  # only the newest job's events remain
    old = next(j for j in jobs.values() if str(j.id) == job1["id"])
    assert old.results["superseded_by"]


async def test_duplicate_file_on_same_camera_is_refused(admin, clip):
    store, cam = await setup_camera(admin)
    await upload(admin, store["id"], cam["id"], clip)
    await run_worker_once()
    _, job2 = await upload(admin, store["id"], cam["id"], clip, recorded_start="2026-03-09T18:00:00+05:30")
    await run_worker_once()
    job2 = (await admin.get(f"/api/jobs/{job2['id']}")).json()
    assert job2["status"] == "failed" and job2["error_code"] == "DUPLICATE_VIDEO"


async def test_corrupt_upload_fails_without_retry(admin, tmp_path):
    store, cam = await setup_camera(admin)
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video" * 1000)
    _, job = await upload(admin, store["id"], cam["id"], str(bad))
    await run_worker_once()
    job = (await admin.get(f"/api/jobs/{job['id']}")).json()
    assert job["status"] == "failed" and job["error_code"] in ("INVALID_VIDEO", "UNDECODABLE_VIDEO")
    assert job["attempts"] == 1
    alerts = (await admin.get(f"/api/analytics/{store['id']}/alerts")).json()["items"]
    assert alerts and alerts[0]["alert_type"] == "PROCESSING_FAILED"


async def test_upload_validation(admin):
    store, cam = await setup_camera(admin)
    base = {"store_id": store["id"], "camera_id": cam["id"], "size_bytes": 10, "content_type": "video/mp4"}
    assert (await admin.post("/api/videos", json={**base, "filename": "x.exe"})).status_code == 415
    assert (await admin.post("/api/videos", json={**base, "filename": "x.mp4", "size_bytes": 10**13})).status_code == 413
    assert (await admin.post("/api/videos", json={**base, "filename": "x.mp4",
                                                  "recorded_start": "2026-03-08T10:00:00"})).status_code == 422
    r = await admin.post("/api/videos", json={**base, "filename": "x.mp4"})
    vid = r.json()["video"]["id"]
    assert r.json()["video"]["recorded_start_assumed"] is True
    # Wrong size and not-yet-uploaded are refused.
    assert (await admin.put(f"/api/videos/{vid}/content", content=b"0" * 20)).status_code == 413
    assert (await admin.post(f"/api/videos/{vid}/complete", json={})).status_code == 409


async def test_cancel_queued_job_and_retry(admin, clip):
    store, cam = await setup_camera(admin)
    _, job = await upload(admin, store["id"], cam["id"], clip)
    r = await admin.post(f"/api/jobs/{job['id']}/cancel")
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    await run_worker_once()  # nothing to claim
    assert (await admin.get(f"/api/jobs/{job['id']}")).json()["status"] == "cancelled"
    r = await admin.post(f"/api/jobs/{job['id']}/retry")
    assert r.status_code == 200 and r.json()["status"] == "queued"
    await run_worker_once()
    assert (await admin.get(f"/api/jobs/{job['id']}")).json()["status"] == "completed"


async def test_stale_running_job_is_requeued_then_fails_after_max_attempts(admin, clip):
    store, cam = await setup_camera(admin)
    _, job = await upload(admin, store["id"], cam["id"], clip)
    stale = update(ProcessingJob).values(heartbeat_at=utcnow() - timedelta(hours=1))
    async with async_session() as db:
        claimed = await job_service.claim_next(db, "dead-worker")
        assert str(claimed.id) == job["id"]
        await db.execute(stale)
        await db.commit()
    async with async_session() as db:
        assert await job_service.requeue_stale(db) == [claimed.id]
    async with async_session() as db:
        j = await db.get(ProcessingJob, claimed.id)
        assert j.status == "queued" and j.error_code == "WORKER_LOST"
        j.attempts = j.max_attempts - 1
        await db.commit()
    async with async_session() as db:
        await job_service.claim_next(db, "dead-worker")
        await db.execute(stale)
        await db.commit()
    async with async_session() as db:
        await job_service.requeue_stale(db)
    async with async_session() as db:
        j = await db.get(ProcessingJob, claimed.id)
        assert j.status == "failed" and j.attempts == j.max_attempts


async def test_claim_is_exclusive(admin, clip):
    store, cam = await setup_camera(admin)
    await upload(admin, store["id"], cam["id"], clip)
    async with async_session() as a, async_session() as b:
        first = await job_service.claim_next(a, "w1")
        second = await job_service.claim_next(b, "w2")
    assert first is not None and second is None


async def test_shutdown_requeues_without_consuming_attempt(admin, clip):
    store, cam = await setup_camera(admin)
    _, job = await upload(admin, store["id"], cam["id"], clip)

    class StoppingDetector(FakeDetector):
        def detect(self, frame, confidence=None):
            worker.stopping.set()
            return super().detect(frame, confidence)

    worker = Worker(worker_id="w-stop", detector_factory=StoppingDetector)
    async with async_session() as db:
        claimed = await job_service.claim_next(db, "w-stop")
    await worker.process(claimed.id)
    j = (await admin.get(f"/api/jobs/{job['id']}")).json()
    assert j["status"] == "queued" and j["attempts"] == 0
