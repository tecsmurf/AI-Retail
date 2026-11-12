"""Self-service sign-up: a new customer gets their own empty company."""

from __future__ import annotations

from app.config import settings
from tests.conftest import _client, login_as
from tests.test_api import make_camera, make_store

PW = "a-long-enough-password"
NEW = {"company_name": "Sharma Kirana Stores", "full_name": "Priya Sharma", "email": "Priya@Example.in", "password": PW}


async def signup(body=None):
    c = _client()
    r = await c.post("/api/auth/signup", json=body or NEW)
    c.headers["X-PurpleSol-CSRF"] = "1"
    return c, r


async def test_signup_creates_isolated_company_and_signs_in(admin):
    other = await make_store(admin, "s1")
    await make_camera(admin, other["id"])
    assert (await admin.get("/api/auth/options")).json() == {"signup_enabled": True}

    c, r = await signup()
    try:
        assert r.status_code == 201, r.text
        me = r.json()
        assert me["email"] == "priya@example.in" and me["role"] == "admin" and me["is_admin"]
        assert me["org_name"] == "Sharma Kirana Stores" and me["full_name"] == "Priya Sharma"
        # Signed in by the cookie, and sees nothing of the other company.
        assert (await c.get("/api/auth/me")).json()["id"] == me["id"]
        assert (await c.get("/api/stores")).json() == []
        assert (await c.get(f"/api/stores/{other['id']}")).status_code == 404
        assert [u["email"] for u in (await c.get("/api/users")).json()] == ["priya@example.in"]
        # Request metrics describe the whole service: not for a customer's admin.
        assert (await c.get("/api/system/metrics")).status_code == 403

        # They can set up their own store and add a store manager.
        mine = await c.post("/api/stores", json={"store_code": "s1", "name": "Andheri", "timezone": "Asia/Kolkata"})
        assert mine.status_code == 201, mine.text  # the same store code as another company is fine
        r = await c.post("/api/users", json={"email": "manager@example.in", "password": PW, "role": "store_manager",
                                             "store_ids": [mine.json()["id"]]})
        assert r.status_code == 201, r.text
        m = await login_as("manager@example.in", PW)
        try:
            assert [s["name"] for s in (await m.get("/api/stores")).json()] == ["Andheri"]
        finally:
            await m.aclose()
        # The first company still cannot see the new one.
        assert [s["name"] for s in (await admin.get("/api/stores")).json()] == [other["name"]]
        actions = [a["action"] for a in (await c.get("/api/org/audit")).json()["items"]]
        assert "auth.signup" in actions
        assert "auth.signup" not in [a["action"] for a in (await admin.get("/api/org/audit")).json()["items"]]
    finally:
        await c.aclose()


async def test_signup_rejects_duplicate_email_and_weak_password(admin):
    for body, status in (({**NEW, "email": "ADMIN@example.com"}, 409), ({**NEW, "password": "short"}, 422),
                         ({**NEW, "email": "not-an-email"}, 422), ({**NEW, "company_name": " "}, 422)):
        c, r = await signup(body)
        await c.aclose()
        assert r.status_code == status, (body, r.text)


async def test_signup_is_rate_limited_and_can_be_turned_off(anon, monkeypatch):
    monkeypatch.setattr(settings, "signup_rate_limit_per_hour", 2)
    for i in range(2):
        c, r = await signup({**NEW, "email": f"user{i}@example.in"})
        await c.aclose()
        assert r.status_code == 201
    c, r = await signup({**NEW, "email": "user9@example.in"})
    await c.aclose()
    assert r.status_code == 429
    monkeypatch.setattr(settings, "signup_enabled", False)
    assert (await anon.get("/api/auth/options")).json() == {"signup_enabled": False}
    c, r = await signup({**NEW, "email": "later@example.in"})
    await c.aclose()
    assert r.status_code == 403


async def test_profile_update(admin):
    r = await admin.patch("/api/auth/me", json={"full_name": "  Head Office  "})
    assert r.status_code == 200 and r.json()["full_name"] == "Head Office"
    assert (await admin.get("/api/auth/me")).json()["full_name"] == "Head Office"
