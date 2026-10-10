"""Test configuration.

The database defaults to a temporary SQLite file migrated with Alembic. Set
TEST_DATABASE_URL (e.g. postgresql+asyncpg://...) to run the same suite on
PostgreSQL; that database is migrated and its tables are emptied between tests.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="purplesol-tests-"))
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{_TMP / 'test.db'}"
os.environ["APP_ENV"] = "test"
os.environ["SECRET_KEY"] = "test-secret-key-0123456789abcdef0123456789"
os.environ["STORAGE_BACKEND"] = "local"
os.environ["STORAGE_LOCAL_DIR"] = str(_TMP / "storage")
os.environ["WORKER_TMP_DIR"] = str(_TMP / "worker")
os.environ["INGEST_API_KEY"] = "test-ingest-key"
os.environ.pop("ADMIN_EMAIL", None)
os.environ.pop("ADMIN_PASSWORD", None)

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app import migrate  # noqa: E402
from app.database import Base, async_session, engine  # noqa: E402
from app.models.user import ROLE_ADMIN, ROLE_VIEWER, User  # noqa: E402
from app.security import hash_password, rate_limiter  # noqa: E402
from app.storage import reset_storage  # noqa: E402

ADMIN = ("admin@example.com", "admin-password-123")
VIEWER = ("viewer@example.com", "viewer-password-123")
DATA_DIR = Path(__file__).parent / "data"


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    migrate.upgrade(os.environ["DATABASE_URL"])
    yield


@pytest_asyncio.fixture(autouse=True)
async def clean_state():
    rate_limiter.reset()
    reset_storage()
    yield
    async with async_session() as db:
        for table in reversed(Base.metadata.sorted_tables):
            await db.execute(delete(table))
        await db.commit()
    await engine.dispose()


async def make_user(email: str, password: str, role: str) -> User:
    async with async_session() as db:
        user = User(email=email, password_hash=hash_password(password), role=role, is_active=True)
        db.add(user)
        await db.commit()
        return user


def _client() -> AsyncClient:
    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def anon():
    async with _client() as c:
        yield c


async def _login(email: str, password: str, role: str) -> AsyncClient:
    await make_user(email, password, role)
    c = _client()
    r = await c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    c.headers["X-PurpleSol-CSRF"] = "1"
    return c


@pytest_asyncio.fixture
async def admin():
    c = await _login(*ADMIN, ROLE_ADMIN)
    try:
        yield c
    finally:
        await c.aclose()


@pytest_asyncio.fixture
async def viewer():
    c = await _login(*VIEWER, ROLE_VIEWER)
    try:
        yield c
    finally:
        await c.aclose()
