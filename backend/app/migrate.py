"""Apply database migrations safely.

Usage::

    python -m app.migrate            # upgrade to the latest schema
    python -m app.migrate --check    # exit 1 if the database is not at head

A database created by PurpleSol v1 (tables exist, no ``alembic_version``) is
stamped at the v1 baseline first, so the upgrade preserves its data. Nothing
here drops or truncates data.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.config import settings
from app.database import build_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent


def alembic_config(url: str | None = None) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["database_url"] = url or settings.database_url
    return cfg


def head_revision() -> str:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


async def current_state(url: str | None = None) -> tuple[str | None, bool]:
    """Return (current alembic revision, whether v1 tables exist)."""
    engine = build_engine(url)
    try:
        async with engine.connect() as conn:

            def _inspect(sync_conn):
                tables = set(inspect(sync_conn).get_table_names())
                rev = MigrationContext.configure(sync_conn).get_current_revision()
                return rev, "stores" in tables

            return await conn.run_sync(_inspect)
    finally:
        await engine.dispose()


def upgrade(url: str | None = None) -> str:
    cfg = alembic_config(url)
    rev, has_tables = asyncio.run(current_state(url))
    if rev is None and has_tables:
        print("Existing v1 database without migration history: stamping baseline 0001")
        command.stamp(cfg, "0001")
    command.upgrade(cfg, "head")
    return head_revision()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="only verify the schema is current")
    args = parser.parse_args()
    if args.check:
        rev, _ = asyncio.run(current_state())
        head = head_revision()
        print(f"current={rev} head={head}")
        return 0 if rev == head else 1
    print(f"Database at revision {upgrade()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
