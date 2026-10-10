"""API behaviour: health, auth, stores/zones, events, analytics, POS."""

from __future__ import annotations

import pytest

from tests.conftest import ADMIN

SQ = [[0.1, 0.1], [0.4, 0.1], [0.4, 0.4], [0.1, 0.4]]


async def make_store(client, code="s1", **extra):
    r = await client.post("/api/stores", json={"store_code": code, "name": f"Store {code}", **extra})
    assert r.status_code == 201, r.text
    return r.json()


async def make_camera(client, store_id, code="CAM1", ctype="zone"):
    r = await client.post(f"/api/stores/{store_id}/cameras", json={"camera_code": code, "name": code, "camera_type": ctype})
    assert r.status_code == 201, r.text
    return r.json()


# ── health ───────────────────────────────────────────────────────


async def test_health_live_and_ready(anon):
    assert (await anon.get("/health/live")).json() == {"status": "ok"}
    r = await anon.get("/health/ready")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["checks"]["database"]["ok"] and body["checks"]["storage"]["ok"]
    assert body["checks"]["database"]["revision"] == body["checks"]["database"]["expected"]


async def test_ready_reports_unreachable_database(anon, monkeypatch):
    from app.api import system

    async def broken():
        return {"ok": False, "error": "OperationalError"}

    monkeypatch.setattr(system, "_check_database", broken)
    r = await anon.get("/health/ready")
    assert r.status_code == 503 and r.json()["status"] == "not_ready"


# ── auth ─────────────────────────────────────────────────────────


async def test_protected_routes_need_login(anon):
    for path in ("/api/stores", "/api/jobs", "/api/system/status", "/api/analytics/definitions"):
        assert (await anon.get(path)).status_code == 401, path


async def test_login_wrong_password_and_rate_limit(anon, admin):
    for _ in range(10):
        r = await anon.post("/api/auth/login", json={"email": ADMIN[0], "password": "wrong-password"})
        assert r.status_code in (401, 429)
    r = await anon.post("/api/auth/login", json={"email": ADMIN[0], "password": "wrong-password"})
    assert r.status_code == 429


async def test_cookie_session_requires_csrf_header_for_writes(admin):
    assert (await admin.get("/api/auth/me")).json()["role"] == "admin"
    r = await admin.post("/api/stores", json={"store_code": "x1", "name": "X"}, headers={"X-PurpleSol-CSRF": ""})
    assert r.status_code == 403


async def test_session_cookie_flags(anon, admin):
    from tests.conftest import _client

    async with _client() as c:
        r = await c.post("/api/auth/login", json={"email": ADMIN[0], "password": ADMIN[1]})
        cookie = r.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=lax" in cookie


async def test_logout_everywhere_revokes_tokens(admin):
    r = await admin.post("/api/auth/logout-everywhere")
    assert r.status_code in (200, 204)
    assert (await admin.get("/api/auth/me")).status_code == 401


async def test_viewer_cannot_write(viewer):
    assert (await viewer.get("/api/stores")).status_code == 200
    assert (await viewer.post("/api/stores", json={"store_code": "v", "name": "V"})).status_code == 403


# ── stores, cameras, zone configuration ─────────────────────────


async def test_store_camera_zone_config_roundtrip(admin):
    store = await make_store(admin)
    cam = await make_camera(admin, store["id"], "CAM1", "billing")
    body = {"zones": [
        {"zone_code": "Q", "name": "Queue", "zone_type": "QUEUE", "polygon": SQ},
        {"zone_code": "C", "name": "Counter", "zone_type": "BILLING",
         "polygon": [[0.5, 0.5], [0.9, 0.5], [0.9, 0.9], [0.5, 0.9]]},
    ]}
    r = await admin.put(f"/api/cameras/{cam['id']}/config", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["camera"]["config_version"] == 2
    assert [z["name"] for z in out["zones"]] == ["Queue", "Counter"]
    # Replacing drops zones not in the new list.
    r = await admin.put(f"/api/cameras/{cam['id']}/config", json={"zones": body["zones"][:1]})
    assert len(r.json()["zones"]) == 1


@pytest.mark.parametrize("polygon", [
    [[0, 0], [1, 1]],
    [[0, 0], [1.5, 0], [1, 1]],
    [[0, 0], [1, 1], [1, 0], [0, 1]],
])
async def test_invalid_polygons_rejected(admin, polygon):
    store = await make_store(admin)
    cam = await make_camera(admin, store["id"])
    r = await admin.put(f"/api/cameras/{cam['id']}/config",
                        json={"zones": [{"zone_code": "Z", "name": "Z", "zone_type": "SHELF", "polygon": polygon}]})
    assert r.status_code == 422


async def test_entry_line_only_on_entrance_cameras(admin):
    store = await make_store(admin)
    zone_cam = await make_camera(admin, store["id"], "CAM1", "zone")
    entry_cam = await make_camera(admin, store["id"], "CAM2", "entrance")
    line = {"p1": [0.1, 0.5], "p2": [0.9, 0.5], "inside": "right"}
    assert (await admin.put(f"/api/cameras/{zone_cam['id']}/config", json={"zones": [], "entry_line": line})).status_code == 422
    r = await admin.put(f"/api/cameras/{entry_cam['id']}/config", json={"zones": [], "entry_line": line})
    assert r.status_code == 200 and r.json()["camera"]["entry_line"]["inside"] == "right"


async def test_zone_names_unique_across_cameras(admin):
    store = await make_store(admin)
    a = await make_camera(admin, store["id"], "CAM1")
    b = await make_camera(admin, store["id"], "CAM2")
    zone = {"zone_code": "Z", "name": "Lipstick", "zone_type": "SHELF", "polygon": SQ}
    assert (await admin.put(f"/api/cameras/{a['id']}/config", json={"zones": [zone]})).status_code == 200
    assert (await admin.put(f"/api/cameras/{b['id']}/config", json={"zones": [zone]})).status_code == 422


async def test_duplicate_codes_conflict(admin):
    store = await make_store(admin)
    assert (await admin.post("/api/stores", json={"store_code": "s1", "name": "dup"})).status_code == 409
    await make_camera(admin, store["id"])
    r = await admin.post(f"/api/stores/{store['id']}/cameras", json={"camera_code": "CAM1", "name": "x"})
    assert r.status_code == 409


# ── events ───────────────────────────────────────────────────────


def ev(i, etype="ENTRY", ts="2026-03-08T10:00:00+05:30", **kw):
    return {"event_type": etype, "customer_id": f"c{i}", "store_code": "s1", "timestamp": ts, **kw}


async def test_event_ingest_is_idempotent(admin, anon):
    await make_store(admin)
    batch = [ev(i, event_key=f"key-{i:06d}") for i in range(5)]
    r = await anon.post("/api/events/batch", json=batch, headers={"X-API-Key": "test-ingest-key"})
    assert r.status_code == 201 and r.json()["inserted"] == 5
    r = await anon.post("/api/events/batch", json=batch, headers={"X-API-Key": "test-ingest-key"})
    assert r.json()["inserted"] == 0 and r.json()["duplicates"] == 5
    # Without keys, exact duplicates are still dropped (content key).
    r = await anon.post("/api/events/batch", json=[ev(9), ev(9)], headers={"X-API-Key": "test-ingest-key"})
    assert r.json()["inserted"] == 1


async def test_event_ingest_auth_and_validation(admin, anon):
    await make_store(admin)
    assert (await anon.post("/api/events", json=ev(1), headers={"X-API-Key": "wrong"})).status_code == 401
    r = await admin.post("/api/events", json=ev(1, ts="2026-03-08T10:00:00"))
    assert r.status_code == 422  # timestamp without offset
    r = await admin.post("/api/events", json={**ev(1), "store_code": "nope"})
    assert r.status_code == 422


# ── analytics ────────────────────────────────────────────────────


async def test_analytics_use_store_local_days_and_real_data_only(admin):
    store = await make_store(admin)
    sid = store["id"]
    events = [
        # 23:30 IST on 8 March is 18:00 UTC: must land on 8 March local.
        ev(1, "ENTRY", "2026-03-08T23:30:00+05:30", event_key="k-entry-1"),
        ev(2, "ENTRY", "2026-03-09T00:30:00+05:30", event_key="k-entry-2"),
        ev(3, "ZONE_EXIT", "2026-03-08T12:00:00+05:30", zone_name="Shelf", zone_type="SHELF",
           dwell_seconds=40, event_key="k-zone-3"),
    ]
    assert (await admin.post("/api/events/batch", json=events)).status_code == 201
    r = await admin.get(f"/api/analytics/{sid}/footfall", params={"start": "2026-03-08", "end": "2026-03-08"})
    assert r.status_code == 200, r.text
    assert r.json()["entries"] == 1
    assert r.json()["hourly"][23]["entries"] == 1
    assert r.json()["peak_hour_entries"] == 1
    r = await admin.get(f"/api/analytics/{sid}/zones", params={"start": "2026-03-08", "end": "2026-03-09"})
    zones = r.json()["zones"]
    assert zones[0]["zone_name"] == "Shelf" and zones[0]["visits"] == 1 and zones[0]["avg_dwell_seconds"] == 40


async def test_overview_and_extent_on_empty_store(admin):
    store = await make_store(admin)
    r = await admin.get(f"/api/analytics/{store['id']}/overview")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["footfall"]["entries"] == 0
    assert body["conversion"]["conversion_rate"] is None
    r = await admin.get(f"/api/analytics/{store['id']}/data-extent")
    assert r.status_code == 200
    r = await admin.get(f"/api/analytics/{store['id']}/insights")
    assert r.status_code == 200 and r.json()["insights"] == []


async def test_demographics_are_not_invented(admin):
    store = await make_store(admin)
    assert (await admin.get(f"/api/analytics/{store['id']}/demographics")).json()["available"] is False


async def test_bad_range_rejected(admin):
    store = await make_store(admin)
    r = await admin.get(f"/api/analytics/{store['id']}/footfall", params={"start": "2026-03-09", "end": "2026-03-01"})
    assert r.status_code == 422


# ── POS ──────────────────────────────────────────────────────────

POS_CSV = (
    "order_id,order_date,order_time,store_id,product_id,brand_name,total_amount\n"
    "1,08-03-2026,12:15:05,P1,111,Brand,100.50\n"
    "1,08-03-2026,12:15:05,P1,222,Brand,50\n"
    "2,08-03-2026,18:00:00,P1,111,Brand,20\n"
)


async def test_pos_import_idempotent_and_revenue_mapping(admin):
    store = await make_store(admin, pos_store_code="P1")
    files = {"file": ("pos.csv", POS_CSV, "text/csv")}
    r = await admin.post("/api/pos/import", files=files)
    assert r.status_code == 200, r.text
    assert r.json()["inserted"] == 3
    r = await admin.post("/api/pos/import", files=files)
    assert r.json()["inserted"] == 0 and r.json()["duplicates_skipped"] == 3
    r = await admin.get(f"/api/analytics/{store['id']}/revenue", params={"start": "2026-03-08", "end": "2026-03-08"})
    body = r.json()
    assert body["total_revenue"] == pytest.approx(170.5)
    assert body["transactions"] == 2


async def test_pos_unassigned_codes_listed(admin):
    await make_store(admin)
    await admin.post("/api/pos/import", files={"file": ("pos.csv", POS_CSV, "text/csv")})
    items = (await admin.get("/api/pos/unassigned")).json()["items"]
    assert items[0]["pos_store_code"] == "P1" and items[0]["orders"] == 2


async def test_pos_import_rejects_missing_columns(admin):
    r = await admin.post("/api/pos/import", files={"file": ("pos.csv", "a,b\n1,2\n", "text/csv")})
    assert r.status_code == 422
