"""Chains: organisations are isolated, roles limit which stores a user sees,
team and region management, the HQ comparison and the audit log."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest_asyncio

from app.models.user import ROLE_ADMIN
from tests.conftest import login_as, make_org, make_user
from tests.test_api import make_camera, make_store

PW = "a-long-password-1"
POS_HEADER = "order_id,order_date,order_time,store_id,product_id,brand_name,total_amount\n"


@pytest_asyncio.fixture
async def other_admin():
    """Admin of a second, unrelated organisation."""
    org = await make_org("Other Chain", "other")
    await make_user("boss@other.example", PW, ROLE_ADMIN, org_id=org.id)
    c = await login_as("boss@other.example", PW)
    try:
        yield c
    finally:
        await c.aclose()


async def add_user(admin, email, role, **grants):
    r = await admin.post("/api/users", json={"email": email, "password": PW, "role": role, **grants})
    assert r.status_code == 201, r.text
    return r.json()


def entry(store_code, key, ts="2026-03-10T06:00:00Z"):
    return {"store_code": store_code, "event_type": "ENTRY", "customer_id": key, "timestamp": ts,
            "event_key": f"entry-key-{key}"}


# ── organisations are isolated ───────────────────────────────────


async def test_me_describes_org_and_permissions(admin):
    me = (await admin.get("/api/auth/me")).json()
    assert me["org_name"] == "Default organisation" and me["all_stores"] and me["is_admin"] and me["can_upload"]


async def test_other_organisation_sees_nothing(admin, other_admin):
    store = await make_store(admin, "s1")
    cam = await make_camera(admin, store["id"])
    assert (await other_admin.get("/api/stores")).json() == []
    for path in (
        f"/api/stores/{store['id']}",
        f"/api/stores/{store['id']}/cameras",
        f"/api/stores/{store['id']}/zones",
        f"/api/cameras/{cam['id']}/config",
        f"/api/analytics/{store['id']}/overview",
        f"/api/analytics/{store['id']}/journeys",
        f"/api/events?store_id={store['id']}",
        f"/api/videos?store_id={store['id']}",
        f"/api/jobs?store_id={store['id']}",
    ):
        assert (await other_admin.get(path)).status_code == 404, path
    # Writes are refused the same way, even for an admin of the other organisation.
    assert (await other_admin.patch(f"/api/stores/{store['id']}", json={"name": "Mine"})).status_code == 404
    assert (await other_admin.patch(f"/api/cameras/{cam['id']}", json={"name": "Mine"})).status_code == 404
    r = await other_admin.post("/api/videos", json={
        "filename": "a.mp4", "size_bytes": 10, "content_type": "video/mp4", "store_id": store["id"], "camera_id": cam["id"]})
    assert r.status_code == 404
    assert (await admin.get(f"/api/stores/{store['id']}")).json()["name"] == "Store s1"


async def test_same_store_code_in_two_organisations(admin, other_admin):
    a = await make_store(admin, "s1")
    b = await make_store(other_admin, "s1")
    assert a["id"] != b["id"]
    assert (await admin.post("/api/stores", json={"store_code": "s1", "name": "dup"})).status_code == 409
    # Admin sessions ingest into their own organisation's store with that code.
    assert (await admin.post("/api/events", json=entry("s1", "a-1"))).status_code == 201
    assert (await other_admin.post("/api/events/batch", json=[entry("s1", "b-1"), entry("s1", "b-2")])).status_code == 201
    params = {"start": "2026-03-10", "end": "2026-03-10"}
    assert (await admin.get(f"/api/analytics/{a['id']}/footfall", params=params)).json()["entries"] == 1
    assert (await other_admin.get(f"/api/analytics/{b['id']}/footfall", params=params)).json()["entries"] == 2


async def test_api_key_ingest_selects_organisation_by_header(admin, other_admin, anon):
    await make_store(admin, "s1")
    b = await make_store(other_admin, "s9")
    key = {"X-API-Key": "test-ingest-key"}
    # No header: default organisation, where s9 does not exist.
    assert (await anon.post("/api/events", json=entry("s9", "k1"), headers=key)).status_code == 422
    r = await anon.post("/api/events", json=entry("s9", "k1"), headers={**key, "X-PurpleSol-Org": "other"})
    assert r.status_code == 201 and r.json()["inserted"] == 1
    assert (await anon.post("/api/events", json=entry("s9", "k2"), headers={**key, "X-PurpleSol-Org": "nope"})).status_code == 404
    params = {"start": "2026-03-10", "end": "2026-03-10"}
    assert (await other_admin.get(f"/api/analytics/{b['id']}/footfall", params=params)).json()["entries"] == 1


async def test_pos_rows_are_per_organisation(admin, other_admin):
    a = await make_store(admin, "s1", pos_store_code="ST1")
    b = await make_store(other_admin, "s1", pos_store_code="ST1")
    csv = POS_HEADER + "1,10-03-2026,12:00:00,ST1,P1,Brand,100\n2,10-03-2026,12:05:00,ST9,P1,Brand,50\n"
    r = await admin.post("/api/pos/import", files={"file": ("pos.csv", csv, "text/csv")})
    assert r.json()["inserted"] == 2
    params = {"start": "2026-03-10", "end": "2026-03-10"}
    assert (await admin.get(f"/api/analytics/{a['id']}/revenue", params=params)).json()["total_revenue"] == 100
    assert (await other_admin.get(f"/api/analytics/{b['id']}/revenue", params=params)).json()["total_revenue"] == 0
    assert [u["pos_store_code"] for u in (await admin.get("/api/pos/unassigned")).json()["items"]] == ["ST9"]
    assert (await other_admin.get("/api/pos/unassigned")).json()["items"] == []
    # The same order ids can be imported by the other organisation.
    r = await other_admin.post("/api/pos/import", files={"file": ("pos.csv", csv, "text/csv")})
    assert r.json()["inserted"] == 2 and r.json()["duplicates_skipped"] == 0
    assert (await admin.get(f"/api/analytics/{a['id']}/revenue", params=params)).json()["total_revenue"] == 100


# ── roles ────────────────────────────────────────────────────────


async def test_store_manager_sees_only_assigned_stores(admin):
    s1, s2 = await make_store(admin, "s1"), await make_store(admin, "s2")
    c1, c2 = await make_camera(admin, s1["id"]), await make_camera(admin, s2["id"])
    await add_user(admin, "sm@example.com", "store_manager", store_ids=[s1["id"]])
    sm = await login_as("sm@example.com", PW)
    try:
        me = (await sm.get("/api/auth/me")).json()
        assert me["all_stores"] is False and me["store_ids"] == [s1["id"]] and me["can_upload"] and not me["is_admin"]
        assert [s["id"] for s in (await sm.get("/api/stores")).json()] == [s1["id"]]
        assert (await sm.get(f"/api/analytics/{s1['id']}/overview")).status_code == 200
        assert (await sm.get(f"/api/analytics/{s2['id']}/overview")).status_code == 404
        assert (await sm.get(f"/api/cameras/{c2['id']}/config")).status_code == 404
        # May upload recordings for their own store only; cannot change setup or team.
        video = {"filename": "a.mp4", "size_bytes": 10, "content_type": "video/mp4"}
        r = await sm.post("/api/videos", json={**video, "store_id": s1["id"], "camera_id": c1["id"]})
        assert r.status_code == 201, r.text
        r = await sm.post("/api/videos", json={**video, "store_id": s2["id"], "camera_id": c2["id"]})
        assert r.status_code == 404
        assert (await sm.patch(f"/api/stores/{s1['id']}", json={"name": "x"})).status_code == 403
        assert (await sm.put(f"/api/cameras/{c1['id']}/config", json={"zones": []})).status_code == 403
        assert (await sm.get("/api/users")).status_code == 403
        assert (await sm.get("/api/org/audit")).status_code == 403
        assert (await sm.post("/api/org/regions", json={"name": "x"})).status_code == 403
        jobs = (await sm.get("/api/jobs")).json()
        assert jobs["total"] == 0
    finally:
        await sm.aclose()


async def test_regional_manager_sees_stores_of_their_regions(admin):
    north = (await admin.post("/api/org/regions", json={"name": "North"})).json()
    south = (await admin.post("/api/org/regions", json={"name": "South"})).json()
    n1 = await make_store(admin, "n1", region_id=north["id"])
    n2 = await make_store(admin, "n2", region_id=north["id"])
    s1 = await make_store(admin, "s1", region_id=south["id"])
    await add_user(admin, "rm@example.com", "regional_manager", region_ids=[north["id"]])
    rm = await login_as("rm@example.com", PW)
    try:
        assert {s["id"] for s in (await rm.get("/api/stores")).json()} == {n1["id"], n2["id"]}
        assert (await rm.get(f"/api/stores/{s1['id']}")).status_code == 404
        ov = (await rm.get("/api/org/overview")).json()
        assert [r["store_code"] for r in ov["stores"]] == ["n1", "n2"] and ov["total"]["stores"] == 2
        assert [r["name"] for r in (await rm.get("/api/org/regions")).json()["items"]] == ["North"]
        # A store moved into the region becomes visible without touching the user.
        assert (await admin.patch(f"/api/stores/{s1['id']}", json={"region_id": north["id"]})).status_code == 200
        assert len((await rm.get("/api/stores")).json()) == 3
    finally:
        await rm.aclose()


async def test_viewer_reads_everything_but_cannot_upload(admin, viewer):
    s1 = await make_store(admin, "s1")
    c1 = await make_camera(admin, s1["id"])
    assert len((await viewer.get("/api/stores")).json()) == 1
    r = await viewer.post("/api/videos", json={
        "filename": "a.mp4", "size_bytes": 10, "content_type": "video/mp4", "store_id": s1["id"], "camera_id": c1["id"]})
    assert r.status_code == 403
    assert (await viewer.get("/api/org/overview")).status_code == 200


# ── team management ──────────────────────────────────────────────


async def test_team_management(admin, other_admin):
    s1 = await make_store(admin, "s1")
    foreign = await make_store(other_admin, "f1")
    # Grants must point at the caller's own organisation.
    r = await admin.post("/api/users", json={"email": "x@example.com", "password": PW, "role": "store_manager",
                                             "store_ids": [foreign["id"]]})
    assert r.status_code == 422
    u = await add_user(admin, "sm@example.com", "store_manager", store_ids=[s1["id"]], full_name="Sam M")
    assert u["store_ids"] == [s1["id"]] and u["full_name"] == "Sam M"
    assert (await admin.post("/api/users", json={"email": "SM@example.com", "password": PW})).status_code == 409
    # Emails are unique across organisations.
    assert (await other_admin.post("/api/users", json={"email": "sm@example.com", "password": PW})).status_code == 409
    # Promote to HQ viewer: explicit grants are dropped.
    r = await admin.patch(f"/api/users/{u['id']}", json={"role": "viewer"})
    assert r.status_code == 200 and r.json()["store_ids"] == [] and r.json()["role"] == "viewer"
    assert [x["email"] for x in (await admin.get("/api/users")).json()] == ["admin@example.com", "sm@example.com"]
    # Another organisation cannot see or touch the user.
    assert (await other_admin.patch(f"/api/users/{u['id']}", json={"role": "admin"})).status_code == 404
    assert (await other_admin.post(f"/api/users/{u['id']}/password", json={"new_password": PW + "x"})).status_code == 404
    assert all(x["email"] != "sm@example.com" for x in (await other_admin.get("/api/users")).json())


async def test_admin_password_reset_signs_user_out(admin):
    u = await add_user(admin, "v@example.com", "viewer")
    v = await login_as("v@example.com", PW)
    try:
        assert (await admin.post(f"/api/users/{u['id']}/password", json={"new_password": "brand-new-password"})).status_code == 204
        assert (await v.get("/api/auth/me")).status_code == 401
        again = await login_as("v@example.com", "brand-new-password")
        await again.aclose()
    finally:
        await v.aclose()


async def test_cannot_remove_own_or_last_admin(admin):
    me = (await admin.get("/api/auth/me")).json()
    assert (await admin.patch(f"/api/users/{me['id']}", json={"role": "viewer"})).status_code == 400
    assert (await admin.patch(f"/api/users/{me['id']}", json={"is_active": False})).status_code == 400
    assert (await admin.post(f"/api/users/{me['id']}/deactivate")).status_code == 400
    second = await add_user(admin, "a2@example.com", "admin")
    assert (await admin.patch(f"/api/users/{second['id']}", json={"is_active": False})).status_code == 200
    assert (await admin.patch(f"/api/users/{second['id']}", json={"is_active": True, "full_name": "Second"})).json()["is_active"]


# ── regions ──────────────────────────────────────────────────────


async def test_regions_crud_and_delete_keeps_stores(admin, other_admin):
    r = (await admin.post("/api/org/regions", json={"name": "West"})).json()
    assert (await admin.post("/api/org/regions", json={"name": "west"})).status_code == 409
    assert (await other_admin.post("/api/org/regions", json={"name": "West"})).status_code == 201
    s = await make_store(admin, "s1", region_id=r["id"])
    assert s["region_id"] == r["id"]
    assert (await admin.get("/api/org/regions")).json()["items"] == [{"id": r["id"], "name": "West", "store_count": 1}]
    assert (await admin.patch(f"/api/org/regions/{r['id']}", json={"name": "Mumbai West"})).json()["name"] == "Mumbai West"
    # Another organisation's region cannot be used or changed.
    assert (await other_admin.patch(f"/api/org/regions/{r['id']}", json={"name": "x"})).status_code == 404
    assert (await other_admin.post("/api/stores", json={"store_code": "o1", "name": "o", "region_id": r["id"]})).status_code == 422
    assert (await admin.delete(f"/api/org/regions/{r['id']}")).status_code == 204
    assert (await admin.get(f"/api/stores/{s['id']}")).json()["region_id"] is None


# ── HQ comparison ────────────────────────────────────────────────


async def test_org_overview_rows_rollups_and_flags(admin, other_admin):
    north = (await admin.post("/api/org/regions", json={"name": "North"})).json()
    a = await make_store(admin, "a1", region_id=north["id"], pos_store_code="STA")
    await make_store(admin, "b1")
    await make_store(other_admin, "z1")
    events = [entry("a1", f"e{i}", "2026-03-10T06:00:00Z") for i in range(4)]
    assert (await admin.post("/api/events/batch", json=events)).json()["inserted"] == 4
    csv = POS_HEADER + "1,10-03-2026,12:00:00,STA,P1,Brand,300\n2,10-03-2026,13:00:00,STA,P1,Brand,100\n"
    await admin.post("/api/pos/import", files={"file": ("pos.csv", csv, "text/csv")})
    ov = (await admin.get("/api/org/overview", params={"start": "2026-03-10", "end": "2026-03-10"})).json()
    rows = {r["store_code"]: r for r in ov["stores"]}
    assert set(rows) == {"a1", "b1"}
    assert rows["a1"]["entries"] == 4 and rows["a1"]["transactions"] == 2 and rows["a1"]["revenue"] == 400
    assert rows["a1"]["conversion_rate"] == 50.0 and rows["a1"]["region"] == "North" and rows["a1"]["flags"] == []
    assert rows["b1"]["entries"] == 0 and rows["b1"]["conversion_rate"] is None and rows["b1"]["revenue"] is None
    assert set(rows["b1"]["flags"]) == {"no_data", "no_pos_mapping"}
    assert ov["total"]["stores"] == 2 and ov["total"]["stores_with_data"] == 1 and ov["total"]["entries"] == 4
    assert ov["total"]["conversion_rate"] == 50.0 and ov["total"]["revenue"] == 400
    assert [r["name"] for r in ov["regions"]] == ["North", "No region"]
    # The single-store page reports the same numbers.
    single = (await admin.get(f"/api/analytics/{a['id']}/conversion", params={"start": "2026-03-10", "end": "2026-03-10"})).json()
    assert single["conversion_rate"] == rows["a1"]["conversion_rate"]
    only = (await admin.get("/api/org/overview", params={"region_id": north["id"]})).json()
    assert [r["store_code"] for r in only["stores"]] == ["a1"]


# ── audit log ────────────────────────────────────────────────────


async def test_audit_log_records_changes_per_organisation(admin, other_admin):
    s = await make_store(admin, "s1")
    await admin.patch(f"/api/stores/{s['id']}", json={"name": "Renamed"})
    await add_user(admin, "v@example.com", "viewer")
    await make_store(other_admin, "o1")
    log = (await admin.get("/api/org/audit")).json()
    actions = [e["action"] for e in log["items"]]
    assert {"auth.login", "store.create", "store.update", "user.create"} <= set(actions)
    assert all(e["actor"] == "admin@example.com" for e in log["items"])
    created = next(e for e in log["items"] if e["action"] == "user.create")
    assert created["details"] == {"email": "v@example.com", "role": "viewer"} and "password" not in str(created)
    only_users = (await admin.get("/api/org/audit", params={"action": "user."})).json()
    assert [e["action"] for e in only_users["items"]] == ["user.create"]
    theirs = [e["action"] for e in (await other_admin.get("/api/org/audit")).json()["items"]]
    assert sorted(theirs) == ["auth.login", "store.create"]
    assert datetime.fromisoformat(created["created_at"].replace("Z", "+00:00")) <= datetime.now(UTC)


async def test_system_status_is_scoped_and_metrics_are_operator_only(admin, other_admin):
    assert (await admin.get("/api/system/metrics")).status_code == 200
    assert (await other_admin.get("/api/system/metrics")).status_code == 403
    assert (await other_admin.get("/api/system/status")).json()["queue"]["queue_depth"] == 0
