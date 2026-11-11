"""In-store edge boxes: pairing, configuration, heartbeats, live events,
queue samples, still images, revocation and organisation isolation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest_asyncio
from sqlalchemy import select

from app.database import async_session
from app.models.edge import EdgeDevice
from app.models.user import ROLE_ADMIN
from tests.conftest import _client, login_as, make_org, make_user
from tests.test_api import SQ, make_camera, make_store

# Smallest valid baseline JPEG header that carries a size (SOI + SOF0 16x8).
JPEG = b"\xff\xd8" + b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + \
    b"\xff\xc0\x00\x0b\x08\x00\x08\x00\x10\x01\x01\x11\x00" + b"\xff\xd9"


def iso(dt: datetime) -> str:
    return dt.replace(tzinfo=UTC).isoformat()


async def setup_store(admin, code="s1"):
    store = await make_store(admin, code)
    ent = await make_camera(admin, store["id"], "ENT", "entrance")
    bill = await make_camera(admin, store["id"], "BILL", "billing")
    r = await admin.put(f"/api/cameras/{bill['id']}/config", json={"zones": [
        {"zone_code": "q", "name": "Queue", "zone_type": "QUEUE", "polygon": SQ},
        {"zone_code": "c", "name": "Counter", "zone_type": "BILLING",
         "polygon": [[0.6, 0.6], [0.9, 0.6], [0.9, 0.9], [0.6, 0.9]]},
    ]})
    assert r.status_code == 200, r.text
    r = await admin.put(f"/api/cameras/{ent['id']}/config", json={
        "zones": [], "entry_line": {"p1": [0.1, 0.5], "p2": [0.9, 0.5], "inside": "right"}})
    assert r.status_code == 200, r.text
    return store, ent, bill


async def pair_box(admin, store_id, name="Back office PC"):
    r = await admin.post(f"/api/stores/{store_id}/edge-devices", json={"name": name})
    assert r.status_code == 201, r.text
    created = r.json()
    box = _client()
    r = await box.post("/api/edge/pair", json={"code": created["pairing_code"].lower(), "hostname": "pc-1",
                                              "agent_version": "0.1.0"})
    assert r.status_code == 200, r.text
    box.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return created, box, r.json()


@pytest_asyncio.fixture
async def paired(admin):
    store, ent, bill = await setup_store(admin)
    created, box, _ = await pair_box(admin, store["id"])
    try:
        yield store, ent, bill, created, box
    finally:
        await box.aclose()


async def test_pairing_code_is_single_use_and_only_hashes_are_stored(admin, anon):
    store, _, _ = await setup_store(admin)
    created, box, paired = await pair_box(admin, store["id"])
    await box.aclose()
    code = created["pairing_code"]
    assert len(code) == 11 and code[5] == "-" and created["status"] == "pending"
    assert paired["store"]["store_code"] == "s1" and paired["token"].startswith("pse_")
    # The same code cannot be used twice; wrong codes are refused.
    assert (await anon.post("/api/edge/pair", json={"code": code})).status_code == 400
    assert (await anon.post("/api/edge/pair", json={"code": "AAAAA-AAAAA"})).status_code == 400
    async with async_session() as db:
        d = (await db.execute(select(EdgeDevice))).scalar_one()
        assert d.status == "active" and d.pairing_code_hash is None
        assert d.token_hash and paired["token"] not in (d.token_hash, d.name) and len(d.token_hash) == 64
    listed = (await admin.get(f"/api/stores/{store['id']}/edge-devices")).json()["items"]
    assert listed[0]["online"] is True and listed[0]["pairing_code"] is None and listed[0]["hostname"] == "pc-1"
    actions = [e["action"] for e in (await admin.get("/api/org/audit", params={"action": "edge."})).json()["items"]]
    assert sorted(actions) == ["edge.create", "edge.paired"]


async def test_expired_code_and_rate_limit(admin, anon):
    store, _, _ = await setup_store(admin)
    created = (await admin.post(f"/api/stores/{store['id']}/edge-devices", json={"name": "b"})).json()
    async with async_session() as db:
        d = (await db.execute(select(EdgeDevice))).scalar_one()
        d.pairing_expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
        await db.commit()
    assert (await anon.post("/api/edge/pair", json={"code": created["pairing_code"]})).status_code == 400
    listed = (await admin.get(f"/api/stores/{store['id']}/edge-devices")).json()["items"]
    assert listed[0]["pairing_expired"] is True
    codes = [(await anon.post("/api/edge/pair", json={"code": "ZZZZZ-ZZZZZ"})).status_code for _ in range(10)]
    assert 429 in codes


async def test_box_routes_need_a_valid_token(anon, admin):
    assert (await anon.get("/api/edge/config")).status_code == 401
    assert (await anon.get("/api/edge/config", headers={"Authorization": "Bearer pse_nope"})).status_code == 401
    # A user session is not a box token.
    assert (await admin.post("/api/edge/heartbeat", json={})).status_code == 401


async def test_config_has_zones_and_lines_but_no_stream_addresses(paired):
    store, ent, bill, _, box = paired
    cfg = (await box.get("/api/edge/config")).json()
    assert cfg["store"]["store_code"] == "s1" and cfg["heartbeat_seconds"] == 30
    cams = {c["camera_code"]: c for c in cfg["cameras"]}
    assert set(cams) == {"ENT", "BILL"}
    assert cams["ENT"]["entry_line"]["inside"] == "right" and cams["ENT"]["camera_id"] == ent["id"]
    assert [z["name"] for z in cams["BILL"]["zones"]] == ["Queue", "Counter"]
    assert cams["BILL"]["pipeline"]["analysis_fps"] == 5.0
    assert "rtsp" not in str(cfg).lower() and "password" not in str(cfg).lower()


async def test_heartbeat_reports_health_coverage_and_config_changes(admin, paired):
    store, ent, bill, created, box = paired
    cfg = (await box.get("/api/edge/config")).json()
    now = datetime.now(UTC)
    beat = {"agent_version": "0.1.0", "config_version": cfg["config_version"], "stats": {"outbox": 0}, "cameras": [
        {"camera_id": ent["id"], "status": "online", "fps": 5.0, "last_frame_at": now.isoformat(), "width": 1280,
         "height": 720, "analysed_seconds": 30},
        {"camera_id": bill["id"], "status": "offline", "message": "Cannot open the stream", "analysed_seconds": 0},
    ]}
    r = (await box.post("/api/edge/heartbeat", json=beat)).json()
    assert r["config_changed"] is False
    # No picture is asked for unless an administrator presses the button.
    assert r["snapshot_requests"] == []
    assert (await box.put(f"/api/edge/cameras/{ent['id']}/snapshot", content=JPEG)).status_code == 409
    await box.post("/api/edge/heartbeat", json=beat)
    dev = (await admin.get(f"/api/stores/{store['id']}/edge-devices")).json()["items"][0]
    cams = {c["camera_code"]: c for c in dev["cameras"]}
    assert cams["ENT"]["status"] == "online" and cams["ENT"]["width"] == 1280
    assert cams["BILL"]["status"] == "offline" and cams["BILL"]["message"] == "Cannot open the stream"
    # A day either side: the store's local date differs from the UTC date for part of every day.
    day = {"start": (now.date() - timedelta(days=1)).isoformat(), "end": (now.date() + timedelta(days=1)).isoformat()}
    ov = (await admin.get(f"/api/analytics/{store['id']}/overview", params=day)).json()
    cov = ov["coverage"]
    assert cov["cameras"]["ENT"]["live_seconds"] == 60 and cov["live_seconds"] == 60
    assert cov["has_live_entrance"] is True and cov["has_entrance_footage"] is False
    # Editing zones changes the configuration version the box must reload.
    await admin.put(f"/api/cameras/{bill['id']}/config", json={"zones": []})
    assert (await box.post("/api/edge/heartbeat", json=beat)).json()["config_changed"] is True
    # A box that stops reporting goes offline, and so do its cameras.
    async with async_session() as db:
        d = (await db.execute(select(EdgeDevice))).scalar_one()
        d.last_seen_at = d.last_seen_at - timedelta(minutes=10)
        await db.commit()
    dev = (await admin.get(f"/api/stores/{store['id']}/edge-devices")).json()["items"][0]
    assert dev["online"] is False and {c["status"] for c in dev["cameras"]} == {"offline"}


async def test_live_events_are_idempotent_and_feed_analytics(admin, paired):
    store, ent, bill, _, box = paired
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0) - timedelta(minutes=5)
    events = [
        {"key": "Labc123-T1-0001", "camera_id": ent["id"], "event_type": "ENTRY", "timestamp": iso(now), "track": "Labc123-T1",
         "confidence": 0.9, "box": [0.4, 0.2, 0.5, 0.6]},
        {"key": "Labc123-T2-0001", "camera_id": bill["id"], "event_type": "QUEUE_ENTER", "timestamp": iso(now),
         "track": "Labc123-T2", "zone_name": "Queue", "zone_type": "QUEUE"},
        {"key": "Labc123-T2-0002", "camera_id": bill["id"], "event_type": "QUEUE_EXIT",
         "timestamp": iso(now + timedelta(seconds=40)), "track": "Labc123-T2", "zone_name": "Queue", "zone_type": "QUEUE",
         "queue_wait_seconds": 40},
        # Refused: far in the future, unknown type, another store's camera id.
        {"key": "Labc123-T3-0001", "camera_id": ent["id"], "event_type": "ENTRY",
         "timestamp": iso(now + timedelta(hours=3)), "track": "Labc123-T3"},
        {"key": "Labc123-T4-0001", "camera_id": ent["id"], "event_type": "FACE_MATCH", "timestamp": iso(now), "track": "x"},
        {"key": "Labc123-T5-0001", "camera_id": "00000000-0000-0000-0000-00000000dead", "event_type": "ENTRY",
         "timestamp": iso(now), "track": "y"},
    ]
    snapped = now.replace(second=now.second - now.second % 5)
    occupancy = [{"camera_id": bill["id"], "zone_name": "Queue", "zone_type": "QUEUE", "timestamp": iso(snapped), "count": 3}]
    r = (await box.post("/api/edge/events", json={"events": events, "occupancy": occupancy})).json()
    assert r == {"received": 6, "inserted": 3, "duplicates": 0, "skipped": 3, "samples": 1}
    again = (await box.post("/api/edge/events", json={"events": events, "occupancy": occupancy})).json()
    assert again["inserted"] == 0 and again["duplicates"] == 3 and again["samples"] == 0
    day = {"start": (now.date() - timedelta(days=1)).isoformat(), "end": (now.date() + timedelta(days=1)).isoformat()}
    ov = (await admin.get(f"/api/analytics/{store['id']}/overview", params=day)).json()
    assert ov["footfall"]["entries"] == 1 and ov["source_breakdown"] == {"edge": 3}
    assert ov["queue"]["queue_visits"] == 1 and ov["queue"]["avg_wait_seconds"] == 40
    assert ov["queue"]["max_queue_length"] == 3
    # Live data is real data, and can be filtered on its own.
    only_cv = (await admin.get(f"/api/analytics/{store['id']}/queue", params={**day, "data": "cv"})).json()
    assert only_cv["queue_visits"] == 0 and only_cv["max_queue_length"] is None
    listed = (await admin.get("/api/events", params={"store_id": store["id"], "source": "edge"})).json()
    assert listed["total"] == 3 and {e["customer_id"] for e in listed["items"]} == {"ENT-Labc123-T1", "BILL-Labc123-T2"}
    assert all(e["event_key"].startswith("edge-") for e in listed["items"])
    journeys = (await admin.get(f"/api/analytics/{store['id']}/journeys", params=day)).json()
    assert journeys["total"] == 2 and {j["source"] for j in journeys["items"]} == {"edge"}
    queued = next(j for j in journeys["items"] if j["customer_id"] == "BILL-Labc123-T2")
    assert [s["event_type"] for s in queued["steps"]] == ["QUEUE_ENTER", "QUEUE_EXIT"] and queued["made_purchase"] is False
    dev = (await admin.get(f"/api/stores/{store['id']}/edge-devices")).json()["items"][0]
    assert dev["events_received"] == 3


async def test_later_batch_extends_the_same_journey(admin, paired):
    store, ent, bill, _, box = paired
    now = datetime.now(UTC).replace(tzinfo=None, microsecond=0) - timedelta(minutes=5)
    base = {"camera_id": bill["id"], "track": "Lsess01-T7", "zone_name": "Queue", "zone_type": "QUEUE"}
    await box.post("/api/edge/events", json={"events": [
        {**base, "key": "Lsess01-T7-0001", "event_type": "QUEUE_ENTER", "timestamp": iso(now)}]})
    await box.post("/api/edge/events", json={"events": [
        {**base, "key": "Lsess01-T7-0002", "event_type": "QUEUE_EXIT", "timestamp": iso(now + timedelta(seconds=20)),
         "queue_wait_seconds": 20}]})
    day = {"start": (now.date() - timedelta(days=1)).isoformat(), "end": (now.date() + timedelta(days=1)).isoformat()}
    journeys = (await admin.get(f"/api/analytics/{store['id']}/journeys", params=day)).json()
    assert journeys["total"] == 1 and len(journeys["items"][0]["steps"]) == 2


async def test_batch_size_limit(paired):
    _, ent, _, _, box = paired
    now = iso(datetime.now(UTC).replace(tzinfo=None))
    events = [{"key": f"Lbig0001-T{i}-0001", "camera_id": ent["id"], "event_type": "ENTRY", "timestamp": now,
               "track": f"Lbig0001-T{i}"} for i in range(2001)]
    assert (await box.post("/api/edge/events", json={"events": events})).status_code == 413


async def test_snapshot_becomes_the_cameras_still_image(admin, paired):
    store, ent, bill, created, box = paired
    assert (await admin.post(f"/api/edge-devices/{created['id']}/snapshot-request/{bill['id']}")).status_code == 202
    beat = {"cameras": [{"camera_id": bill["id"], "status": "online"}]}
    assert bill["id"] in (await box.post("/api/edge/heartbeat", json=beat)).json()["snapshot_requests"]
    assert (await box.put(f"/api/edge/cameras/{bill['id']}/snapshot", content=b"not a jpeg")).status_code == 415
    assert (await box.put(f"/api/edge/cameras/{bill['id']}/snapshot", content=JPEG)).status_code == 204
    cams = {c["id"]: c for c in (await admin.get(f"/api/stores/{store['id']}/cameras")).json()}
    cam = cams[bill["id"]]
    assert cam["has_reference_frame"] and (cam["reference_frame_width"], cam["reference_frame_height"]) == (16, 8)
    first_version = cam["reference_frame_version"]
    assert (await admin.get(f"/api/cameras/{bill['id']}/reference-frame")).content == JPEG
    # The request is cleared; a newer still replaces the old file.
    assert bill["id"] not in (await box.post("/api/edge/heartbeat", json=beat)).json()["snapshot_requests"]
    from app.models.store import Camera
    from app.storage import get_storage

    async with async_session() as db:
        old_key = (await db.execute(select(Camera.reference_frame_key).where(Camera.camera_code == "BILL"))).scalar_one()
    # A second picture is refused until an administrator asks again.
    assert (await box.put(f"/api/edge/cameras/{bill['id']}/snapshot", content=JPEG)).status_code == 409
    assert (await admin.post(f"/api/edge-devices/{created['id']}/snapshot-request/{bill['id']}")).status_code == 202
    assert (await box.put(f"/api/edge/cameras/{bill['id']}/snapshot", content=JPEG)).status_code == 204
    assert get_storage().size(old_key) is None
    cams = {c["id"]: c for c in (await admin.get(f"/api/stores/{store['id']}/cameras")).json()}
    assert cams[bill["id"]]["reference_frame_version"] != first_version


async def test_revoke_and_re_pair(admin, paired):
    store, ent, _, created, box = paired
    r = await admin.post(f"/api/edge-devices/{created['id']}/pairing-code")
    assert r.status_code == 200 and r.json()["status"] == "pending" and r.json()["pairing_code"]
    # The old token stops working as soon as a new code is issued.
    assert (await box.get("/api/edge/config")).status_code == 401
    box2 = _client()
    token = (await box2.post("/api/edge/pair", json={"code": r.json()["pairing_code"]})).json()["token"]
    box2.headers["Authorization"] = f"Bearer {token}"
    try:
        assert (await box2.get("/api/edge/config")).status_code == 200
        assert (await admin.post(f"/api/edge-devices/{created['id']}/revoke")).json()["status"] == "revoked"
        assert (await box2.post("/api/edge/heartbeat", json={})).status_code == 401
        assert (await admin.get(f"/api/stores/{store['id']}/edge-devices")).json()["items"] == []
        assert (await admin.post(f"/api/edge-devices/{created['id']}/pairing-code")).status_code == 409
    finally:
        await box2.aclose()


async def test_boxes_are_isolated_between_organisations_and_roles(admin, viewer, paired):
    store, ent, _, created, box = paired
    org = await make_org("Other Chain", "other")
    await make_user("boss@other.example", "a-long-password-1", ROLE_ADMIN, org_id=org.id)
    other = await login_as("boss@other.example", "a-long-password-1")
    try:
        other_store = await make_store(other, "o1")
        other_cam = await make_camera(other, other_store["id"], "ENT", "entrance")
        assert (await other.get(f"/api/stores/{store['id']}/edge-devices")).status_code == 404
        assert (await other.post(f"/api/stores/{store['id']}/edge-devices", json={"name": "x"})).status_code == 404
        assert (await other.post(f"/api/edge-devices/{created['id']}/revoke")).status_code == 404
        # The box cannot write to another organisation's camera.
        assert (await box.put(f"/api/edge/cameras/{other_cam['id']}/snapshot", content=JPEG)).status_code == 404
        now = iso(datetime.now(UTC).replace(tzinfo=None))
        r = await box.post("/api/edge/events", json={"events": [
            {"key": "Lzzz0001-T1-0001", "camera_id": other_cam["id"], "event_type": "ENTRY", "timestamp": now, "track": "t"}]})
        assert r.json()["inserted"] == 0 and r.json()["skipped"] == 1
    finally:
        await other.aclose()
    # Viewers can see box status but cannot add or remove boxes.
    assert (await viewer.get(f"/api/stores/{store['id']}/edge-devices")).status_code == 200
    assert (await viewer.post(f"/api/stores/{store['id']}/edge-devices", json={"name": "x"})).status_code == 403
    assert (await viewer.post(f"/api/edge-devices/{created['id']}/revoke")).status_code == 403
