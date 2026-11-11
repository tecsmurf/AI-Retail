"""What is deleted, and when: recordings with their annotated frames, audit
IP addresses, and a camera's still image on request."""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select, update

from app.config import settings
from app.database import async_session, utcnow
from app.models.jobs import VIDEO_DELETED, VideoAsset
from app.models.org import AuditLog
from app.storage import StorageError, get_storage
from app.worker import Worker
from tests.fakes import FakeDetector
from tests.test_api import make_camera, make_store
from tests.test_edge import JPEG
from tests.test_jobs_worker import clip, run_worker_once, setup_camera, upload  # noqa: F401 - clip is a fixture


def stored(key: str) -> bool:
    try:
        get_storage().get_bytes(key)
        return True
    except StorageError:
        return False


async def test_old_recordings_are_deleted_with_their_annotated_frames(admin, clip):  # noqa: F811
    store, cam = await setup_camera(admin)
    video_id, job = await upload(admin, store["id"], cam["id"], clip)
    await run_worker_once()
    job = (await admin.get(f"/api/jobs/{job['id']}")).json()
    snapshots, tracks = job["artifacts"]["snapshots"], job["artifacts"]["tracks"]
    async with async_session() as db:
        video = (await db.execute(select(VideoAsset))).scalar_one()
        video_key = video.storage_key
    assert snapshots and all(stored(k) for k in [*snapshots, tracks, video_key])

    worker = Worker(worker_id="test-worker", detector_factory=FakeDetector)
    await worker.apply_retention()
    assert stored(video_key) and stored(snapshots[0])  # not old enough yet

    async with async_session() as db:
        await db.execute(update(VideoAsset).values(
            uploaded_at=utcnow() - timedelta(days=settings.video_retention_days + 1)))
        await db.commit()
    await worker.apply_retention()
    assert not stored(video_key) and not any(stored(k) for k in snapshots)
    assert stored(tracks)  # numbers only, kept
    async with async_session() as db:
        assert (await db.execute(select(VideoAsset.status))).scalar_one() == VIDEO_DELETED
    job = (await admin.get(f"/api/jobs/{job['id']}")).json()
    assert job["artifacts"]["snapshots"] == [] and job["status"] == "completed"
    # The counts made from the recording are still there.
    assert job["results"]["events"]["QUEUE_COMPLETED"] == 1


async def test_audit_ip_addresses_are_blanked_after_the_retention_period(admin):
    await make_store(admin)  # writes audit entries with an IP address
    async with async_session() as db:
        rows = (await db.execute(select(AuditLog))).scalars().all()
        assert rows and all(r.ip for r in rows)
        old = rows[0].id
        await db.execute(update(AuditLog).where(AuditLog.id == old).values(
            created_at=utcnow() - timedelta(days=settings.audit_ip_retention_days + 1)))
        await db.commit()
    await Worker(worker_id="test-worker", detector_factory=FakeDetector).apply_retention()
    async with async_session() as db:
        rows = {r.id: r for r in (await db.execute(select(AuditLog))).scalars().all()}
    assert rows[old].ip is None and rows[old].action  # entry kept, address gone
    assert all(r.ip for i, r in rows.items() if i != old)
    status = (await admin.get("/api/system/status")).json()
    assert status["config"]["audit_ip_retention_days"] == 90 and status["config"]["video_retention_days"] == 30


async def test_admin_can_remove_a_cameras_still_image(admin, viewer):
    store = await make_store(admin)
    cam = await make_camera(admin, store["id"], "ENT", "entrance")
    assert (await admin.delete(f"/api/cameras/{cam['id']}/reference-frame")).status_code == 404
    r = await admin.post(f"/api/cameras/{cam['id']}/reference-frame", files={"file": ("still.jpg", JPEG, "image/jpeg")})
    if r.status_code == 415:  # OpenCV refuses the tiny header-only test image: store it directly
        from app.models.store import Camera
        key = f"frames/{cam['id']}/test.jpg"
        get_storage().put_bytes(key, JPEG, "image/jpeg")
        async with async_session() as db:
            await db.execute(update(Camera).values(reference_frame_key=key, reference_frame_width=16, reference_frame_height=8))
            await db.commit()
    async with async_session() as db:
        from app.models.store import Camera
        key = (await db.execute(select(Camera.reference_frame_key))).scalar_one()
    assert key and stored(key)
    got = await admin.get(f"/api/cameras/{cam['id']}/reference-frame")
    assert got.status_code == 200 and got.headers["cache-control"] == "private, no-cache"
    again = await admin.get(f"/api/cameras/{cam['id']}/reference-frame", headers={"If-None-Match": got.headers["etag"]})
    assert again.status_code == 304

    assert (await viewer.delete(f"/api/cameras/{cam['id']}/reference-frame")).status_code == 403
    r = await admin.delete(f"/api/cameras/{cam['id']}/reference-frame")
    assert r.status_code == 200 and r.json()["has_reference_frame"] is False and r.json()["reference_frame_version"] is None
    assert not stored(key)
    assert (await admin.get(f"/api/cameras/{cam['id']}/reference-frame")).status_code == 404
    async with async_session() as db:
        actions = (await db.execute(select(AuditLog.action))).scalars().all()
    assert "camera.reference_frame_removed" in actions
