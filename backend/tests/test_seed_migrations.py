"""Seed idempotency and migration integrity."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import func, select

from app import seed
from app.database import async_session
from app.models.event import Event
from app.models.pos import POSTransaction


async def _counts():
    async with async_session() as db:
        by_source = dict((await db.execute(select(Event.source, func.count()).group_by(Event.source))).all())
        pos = (await db.execute(select(func.count()).select_from(POSTransaction))).scalar()
        gender = (await db.execute(select(func.count()).where(Event.gender.is_not(None)))).scalar()
    return by_source, pos, gender


@pytest.mark.skipif(not (seed.DATA_DIR / "sample_eventsbe42122.jsonl").exists(), reason="sample data not present")
async def test_seed_is_idempotent_and_tags_sources():
    first = await seed.run(sample=True, legacy=True)
    assert first["reference"]["stores"] == 2
    by_source, pos, gender = await _counts()
    assert by_source["sample"] == 19  # 10 plain + 3 queue records x 3 events
    assert by_source["legacy_cv"] == 494
    assert pos == 101
    assert gender == 0  # demographic predictions in the sample file are not stored
    second = await seed.run(sample=True, legacy=True)
    assert second["reference"] == {"stores": 0, "cameras": 0, "zones": 0}
    assert await _counts() == (by_source, pos, gender)


async def test_real_data_excludes_sample_and_legacy(admin):
    if not (seed.DATA_DIR / "sample_eventsbe42122.jsonl").exists():
        pytest.skip("sample data not present")
    await seed.run(sample=True, legacy=True)
    stores = (await admin.get("/api/stores")).json()
    sid = next(s["id"] for s in stores if s["store_code"] == "store_1076")
    real = (await admin.get(f"/api/analytics/{sid}/footfall", params={"start": "2026-03-08", "end": "2026-03-08"})).json()
    every = (await admin.get(f"/api/analytics/{sid}/footfall",
                             params={"start": "2026-03-08", "end": "2026-03-08", "data": "all"})).json()
    assert real["entries"] == 0 and every["entries"] > 0


def test_models_match_migrations():
    """Alembic head must produce exactly the ORM schema (no un-migrated model changes)."""
    from alembic.autogenerate import compare_metadata
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    import app.models  # noqa: F401
    from app.database import Base

    url = os.environ["DATABASE_URL"].replace("+aiosqlite", "").replace("+asyncpg", "+psycopg2")
    if "psycopg2" in url:
        pytest.importorskip("psycopg2")
    engine = create_engine(url)
    with engine.connect() as conn:
        diffs = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": False}), Base.metadata)
    engine.dispose()
    assert diffs == []


def test_downgrade_upgrade_roundtrip(tmp_path):
    from alembic import command

    from app.migrate import alembic_config, upgrade

    url = f"sqlite+aiosqlite:///{tmp_path / 'rt.db'}"
    upgrade(url)
    command.downgrade(alembic_config(url), "0001")
    command.upgrade(alembic_config(url), "head")
    command.downgrade(alembic_config(url), "base")


