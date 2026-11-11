"""Setup checklist: each step turns done only when the thing exists."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.database import async_session, utcnow
from app.models.event import Event
from app.models.user import ROLE_ADMIN, ROLE_STORE
from tests.conftest import login_as, make_org, make_user
from tests.test_api import SQ, make_camera, make_store
from tests.test_edge import pair_box


def by_key(status):
    return {s["key"]: s for s in status["steps"]}


async def get_status(client, store_id):
    r = await client.get(f"/api/stores/{store_id}/setup-status")
    assert r.status_code == 200, r.text
    return r.json()


async def test_checklist_follows_the_real_state_of_the_store(admin):
    store = await make_store(admin, "s1")
    st = await get_status(admin, store["id"])
    steps = by_key(st)
    assert st["ready"] is False and (st["done"], st["total"]) == (1, 4)
    assert steps["store"]["done"] and not steps["cameras"]["done"] and not steps["zones"]["done"]
    assert steps["box"]["required"] is False and steps["pos"]["required"] is False

    ent = await make_camera(admin, store["id"], "ENT", "entrance")
    bill = await make_camera(admin, store["id"], "BILL", "billing")
    st = await get_status(admin, store["id"])
    cams = {c["camera_code"]: c for c in st["cameras"]}
    assert by_key(st)["cameras"]["done"] and not by_key(st)["zones"]["done"]
    assert cams["ENT"]["needs"] == ["entry line"] and cams["BILL"]["needs"] == ["queue zone"]
    assert "ENT" in by_key(st)["zones"]["detail"] and "BILL" in by_key(st)["zones"]["detail"]

    # A billing camera needs a queue zone, not just any zone.
    await admin.put(f"/api/cameras/{bill['id']}/config", json={"zones": [
        {"zone_code": "c", "name": "Counter", "zone_type": "BILLING", "polygon": SQ}]})
    assert {c["camera_code"]: c for c in (await get_status(admin, store["id"]))["cameras"]}["BILL"]["needs"] == ["queue zone"]
    await admin.put(f"/api/cameras/{bill['id']}/config", json={"zones": [
        {"zone_code": "q", "name": "Queue", "zone_type": "QUEUE", "polygon": SQ}]})
    await admin.put(f"/api/cameras/{ent['id']}/config", json={
        "zones": [], "entry_line": {"p1": [0.1, 0.5], "p2": [0.9, 0.5], "inside": "right"}})
    st = await get_status(admin, store["id"])
    assert by_key(st)["zones"]["done"] and all(c["needs"] == [] for c in st["cameras"])
    assert st["ready"] is False and not by_key(st)["data"]["done"] and not by_key(st)["box"]["done"]

    # A box that was added but never paired is not "connected".
    r = await admin.post(f"/api/stores/{store['id']}/edge-devices", json={"name": "Spare PC"})
    assert r.status_code == 201
    st = await get_status(admin, store["id"])
    assert not by_key(st)["box"]["done"] and "not paired yet" in by_key(st)["box"]["detail"]
    created, box, _ = await pair_box(admin, store["id"])
    try:
        # Paired and in contact, but no camera is live and nothing has been counted.
        st = await get_status(admin, store["id"])
        assert by_key(st)["box"]["done"] and not any(c["live"] for c in st["cameras"]) and st["ready"] is False
        now = datetime.now(UTC)
        await box.post("/api/edge/heartbeat", json={"cameras": [
            {"camera_id": ent["id"], "status": "online", "last_frame_at": now.isoformat(), "analysed_seconds": 10}]})
        st = await get_status(admin, store["id"])
        cams = {c["camera_code"]: c for c in st["cameras"]}
        assert by_key(st)["box"]["done"] and cams["ENT"]["live"] is True and cams["BILL"]["live"] is False
        # Still no numbers until an event really arrives.
        assert st["ready"] is False
        r = await box.post("/api/edge/events", json={"events": [
            {"key": "Labc123-T1-0001", "camera_id": ent["id"], "event_type": "ENTRY",
             "timestamp": now.isoformat(), "track": "Labc123-T1"}]})
        assert r.json()["inserted"] == 1
    finally:
        await box.aclose()
    st = await get_status(admin, store["id"])
    assert st["ready"] is True and (st["done"], st["total"]) == (4, 4)
    assert "1 events" in by_key(st)["data"]["detail"]
    assert not by_key(st)["pos"]["done"]


async def test_sample_data_does_not_count_as_first_numbers(admin):
    store = await make_store(admin, "s1")
    async with async_session() as db:
        db.add(Event(store_id=uuid.UUID(store["id"]), event_type="ENTRY", customer_id="demo-1", camera_id="CAM1",
                     timestamp=utcnow(), source="sample"))
        await db.commit()
    assert not by_key(await get_status(admin, store["id"]))["data"]["done"]


async def test_checklist_respects_store_access():
    other = await make_org("Other chain", "other")
    await make_user("hq@other.test", "other-password-1", ROLE_ADMIN, org_id=other.id)
    await make_user("admin@test.local", "admin-password-1", ROLE_ADMIN)
    await make_user("sm@test.local", "store-password-1", ROLE_STORE)
    admin = await login_as("admin@test.local", "admin-password-1")
    outsider = await login_as("hq@other.test", "other-password-1")
    manager = await login_as("sm@test.local", "store-password-1")
    try:
        store = await make_store(admin, "s1")
        assert (await admin.get(f"/api/stores/{store['id']}/setup-status")).status_code == 200
        assert (await outsider.get(f"/api/stores/{store['id']}/setup-status")).status_code == 404
        assert (await manager.get(f"/api/stores/{store['id']}/setup-status")).status_code == 404
    finally:
        for c in (admin, outsider, manager):
            await c.aclose()
