"""Database connection and session management.

Timestamps are stored as *naive UTC* datetimes everywhere (SQLite cannot keep
time zones). Use :func:`utcnow` instead of ``datetime.utcnow`` and convert to a
store's local time zone only at the analytics / presentation boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import AsyncIterator

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def utcnow() -> datetime:
    """Current time as a naive UTC datetime (the storage convention)."""
    return datetime.now(UTC).replace(tzinfo=None)


def normalize_database_url(url: str) -> str:
    """Accept the URL styles that hosting providers hand out.

    Neon/Railway/Heroku give ``postgres://`` or ``postgresql://`` URLs, often
    with ``sslmode=require``; asyncpg needs ``postgresql+asyncpg://`` and an
    ``ssl`` argument instead of ``sslmode``.
    """
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


def engine_kwargs(url: str) -> dict:
    parsed = make_url(url)
    kwargs: dict = {"echo": settings.db_echo}
    if parsed.drivername.startswith("sqlite"):
        kwargs["connect_args"] = {"timeout": 30}
        return kwargs
    connect_args: dict = {}
    query = dict(parsed.query)
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)
    if sslmode in ("require", "verify-ca", "verify-full") or "neon.tech" in (parsed.host or ""):
        connect_args["ssl"] = True
    kwargs.update(
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=300,
        connect_args=connect_args,
    )
    return kwargs


def build_engine(url: str | None = None):
    url = normalize_database_url(url or settings.database_url)
    parsed = make_url(url)
    # asyncpg rejects libpq-only query parameters; strip them from the URL.
    if not parsed.drivername.startswith("sqlite"):
        query = {k: v for k, v in parsed.query.items() if k not in ("sslmode", "channel_binding")}
        parsed = parsed.set(query=query)
    return create_async_engine(parsed, **engine_kwargs(url))


engine = build_engine()
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, committed on success."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all() -> None:
    """Create all tables directly (tests / throwaway databases only)."""
    import app.models  # noqa: F401  (register models)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()
