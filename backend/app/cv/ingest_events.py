"""Import a v1 ``cv_events.jsonl`` file as ``source='legacy_cv'`` (idempotent).

    python -m app.cv.ingest_events [path]

Equivalent to ``python -m app.seed --legacy`` for an arbitrary file.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from app.database import async_session
from app.services.ingest import import_legacy_cv_events


async def run(path: Path) -> dict:
    async with async_session() as db:
        result = await import_legacy_cv_events(db, path)
        await db.commit()
    return result


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "data" / "cv_events.jsonl"
    print(asyncio.run(run(target)))
