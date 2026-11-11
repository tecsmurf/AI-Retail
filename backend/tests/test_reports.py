"""CSV reports: same numbers as the dashboard, scoped like the dashboard."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.database import async_session
from app.models.org import AuditLog
from app.models.user import ROLE_ADMIN, ROLE_STORE
from tests.conftest import login_as, make_org, make_user
from tests.test_api import make_camera, make_store
from tests.test_edge import pair_box


def parse(resp):
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"] and resp.headers["cache-control"] == "no-store"
    text = resp.content.decode("utf-8")
    assert text.startswith("﻿")
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    data = [r for r in rows[1:] if not r[0].startswith("#")]
    notes = [r[0] for r in rows[1:] if r[0].startswith("#")]
    return rows[0], [dict(zip(rows[0], r, strict=True)) for r in data], notes


async def live_entry(admin, store_id, camera_id, key="Labc123-T1"):
    """One real entry, delivered the way a box delivers it."""
    _, box, _ = await pair_box(admin, store_id)
    now = datetime.now(UTC) - timedelta(minutes=1)
    try:
        r = await box.post("/api/edge/events", json={"events": [
            {"key": f"{key}-0001", "camera_id": camera_id, "event_type": "ENTRY", "timestamp": now.isoformat(), "track": key},
            {"key": f"{key}-0002", "camera_id": camera_id, "event_type": "ZONE_ENTER", "timestamp": now.isoformat(),
             "track": key, "zone_name": "=Promo", "zone_type": "SHELF"},
            {"key": f"{key}-0003", "camera_id": camera_id, "event_type": "ZONE_EXIT",
             "timestamp": (now + timedelta(seconds=20)).isoformat(), "track": key, "zone_name": "=Promo",
             "zone_type": "SHELF", "dwell_seconds": 20},
        ]})
        assert r.json()["inserted"] == 3, r.text
    finally:
        await box.aclose()
    return now


async def test_daily_and_zone_reports_match_the_dashboard(admin):
    store = await make_store(admin, "s1")
    ent = await make_camera(admin, store["id"], "ENT", "entrance")
    now = await live_entry(admin, store["id"], ent["id"])
    day = {"start": (now.date() - timedelta(days=1)).isoformat(), "end": (now.date() + timedelta(days=1)).isoformat()}

    header, rows, notes = parse(await admin.get(f"/api/reports/{store['id']}/daily.csv", params=day))
    assert header[:4] == ["date", "store_code", "entries", "exits"] and len(rows) == 3
    assert sum(int(r["entries"] or 0) for r in rows) == 1 and {r["store_code"] for r in rows} == {"s1"}
    # Days nobody watched have empty counts, not zeros.
    assert sorted(r["entries"] for r in rows) == ["", "", "1"]
    # No POS mapping: revenue and conversion are empty, not zero.
    assert all(r["transactions"] == "" and r["revenue"] == "" and r["conversion_pct"] == "" for r in rows)
    assert any("not measured" in n for n in notes) and any("edge" in n for n in notes)
    ov = (await admin.get(f"/api/analytics/{store['id']}/overview", params=day)).json()
    assert ov["footfall"]["entries"] == 1

    header, rows, _ = parse(await admin.get(f"/api/reports/{store['id']}/zones.csv", params=day))
    # A name a spreadsheet would treat as a formula is quoted.
    assert len(rows) == 1 and rows[0]["zone"] == "'=Promo" and rows[0]["visits"] == "1"
    assert float(rows[0]["avg_dwell_s"]) == 20

    too_long = {"start": "2026-01-01", "end": "2026-06-30"}
    assert (await admin.get(f"/api/reports/{store['id']}/daily.csv", params=too_long)).status_code == 422

    async with async_session() as db:
        exports = (await db.execute(select(AuditLog).where(AuditLog.action == "report.export"))).scalars().all()
    assert {e.details.get("report") for e in exports} == {"daily", "zones"}


async def test_reports_only_cover_stores_the_caller_may_see(anon):
    other = await make_org("Other chain", "other")
    await make_user("hq@other.test", "other-password-1", ROLE_ADMIN, org_id=other.id)
    await make_user("admin@test.local", "admin-password-1", ROLE_ADMIN)
    admin = await login_as("admin@test.local", "admin-password-1")
    outsider = await login_as("hq@other.test", "other-password-1")
    try:
        s1 = await make_store(admin, "s1")
        s2 = await make_store(admin, "s2")
        r = await admin.post("/api/users", json={"email": "sm@test.local", "password": "store-password-1",
                                                 "role": ROLE_STORE, "store_ids": [s1["id"]]})
        assert r.status_code == 201, r.text
        manager = await login_as("sm@test.local", "store-password-1")
        try:
            _, rows, _ = parse(await admin.get("/api/reports/stores.csv"))
            assert [r["store_code"] for r in rows] == ["s1", "s2"]
            _, rows, _ = parse(await manager.get("/api/reports/stores.csv"))
            assert [r["store_code"] for r in rows] == ["s1"]
            assert (await manager.get(f"/api/reports/{s1['id']}/daily.csv")).status_code == 200
            for path in (f"/api/reports/{s2['id']}/daily.csv", f"/api/reports/{s2['id']}/zones.csv"):
                assert (await manager.get(path)).status_code == 404
            _, rows, _ = parse(await outsider.get("/api/reports/stores.csv"))
            assert rows == []
            for client in (outsider,):
                assert (await client.get(f"/api/reports/{s1['id']}/daily.csv")).status_code == 404
                assert (await client.get(f"/api/reports/{s1['id']}/zones.csv")).status_code == 404
        finally:
            await manager.aclose()
        for path in ("/api/reports/stores.csv", f"/api/reports/{s1['id']}/daily.csv"):
            assert (await anon.get(path)).status_code == 401
    finally:
        await admin.aclose()
        await outsider.aclose()
