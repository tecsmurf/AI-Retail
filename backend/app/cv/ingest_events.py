"""
Ingest CV-processed events from cv_events.jsonl into PostgreSQL.

This script reads the 494 real events generated from CCTV footage
and inserts them into the events table alongside any existing data.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.database import async_session, init_db
from app.models.event import Event


async def ingest_cv_events():
    """Load CV events from JSONL into PostgreSQL."""
    events_file = Path("data/cv_events.jsonl")
    if not events_file.exists():
        print("  No cv_events.jsonl found. Run process_videos first.")
        return

    print("\n" + "=" * 60)
    print("  PurpleSol - CV Event Database Ingestion")
    print("=" * 60)

    await init_db()
    print("  Database connected\n")

    events = []
    with open(events_file, "r") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    print(f"  Events to ingest: {len(events)}")

    # We need store_id (UUID) mapping - for now we'll query existing stores
    async with async_session() as session:
        from sqlalchemy import select
        from app.models.store import Store

        result = await session.execute(select(Store))
        stores = result.scalars().all()
        store_map = {s.store_code: s.id for s in stores}

        if not store_map:
            print("  No stores found in database. Run seed.py first.")
            print("  Creating stores...")
            # Auto-create stores if missing
            for code, name in [
                ("store_1076", "Purplle Beauty Store 1 - Mumbai"),
                ("store_1077", "Purplle Beauty Store 2 - Mumbai"),
            ]:
                store = Store(store_code=code, name=name, city="Mumbai")
                session.add(store)
            await session.flush()

            result = await session.execute(select(Store))
            stores = result.scalars().all()
            store_map = {s.store_code: s.id for s in stores}
            await session.commit()
            print(f"  Created {len(store_map)} stores")

        print(f"  Store mapping: {list(store_map.keys())}")

        # Ingest events
        count = 0
        type_counts = defaultdict(int)

        for ev in events:
            store_code = ev.get("store_code", "")
            store_id = store_map.get(store_code)
            if not store_id:
                continue

            timestamp = datetime.fromisoformat(ev["timestamp"])

            event = Event(
                store_id=store_id,
                event_type=ev["event_type"],
                customer_id=ev["customer_id"],
                camera_id=ev.get("camera_id"),
                zone_name=ev.get("zone_name"),
                zone_type=ev.get("zone_type"),
                timestamp=timestamp,
                dwell_seconds=ev.get("dwell_seconds"),
                queue_wait_seconds=ev.get("queue_wait_seconds"),
                queue_abandoned=ev.get("queue_abandoned"),
                is_staff=False,
            )
            session.add(event)
            count += 1
            type_counts[ev["event_type"]] += 1

        await session.commit()

    print(f"\n  Ingested: {count} events")
    print(f"\n  Breakdown:")
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {t:20s}: {c}")
    print(f"\n{'=' * 60}")
    print("  Done!")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(ingest_cv_events())
