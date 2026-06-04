"""Database connection and session management."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


# ── Engine ───────────────────────────────────────────────────────
_db_url = settings.database_url

# Support Neon-style URLs: convert postgres:// to postgresql+asyncpg://
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

# Use aiosqlite for SQLite URLs (dev/demo fallback)
_is_sqlite = _db_url.startswith("sqlite")
_pool_args = {} if _is_sqlite else {"pool_size": 10, "max_overflow": 20, "pool_pre_ping": True}

# For Neon, ensure SSL is used
_connect_args = {}
if "neon.tech" in _db_url:
    _connect_args = {"ssl": True}

engine = create_async_engine(
    _db_url,
    echo=not settings.is_production,
    connect_args=_connect_args,
    **_pool_args,
)

# ── Session Factory ──────────────────────────────────────────────
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Base Model ───────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# ── Dependency ───────────────────────────────────────────────────
async def get_db() -> AsyncSession:
    """FastAPI dependency that yields a database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Lifecycle ────────────────────────────────────────────────────
async def init_db() -> None:
    """Create all tables (for development/demo only)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose engine connections."""
    await engine.dispose()
