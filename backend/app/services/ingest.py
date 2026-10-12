"""Idempotent event insertion and file importers for bundled datasets.

Every row carries an ``event_key``; (store_id, event_key) is unique, so
re-running an import inserts nothing new. Demographic fields present in the
bundled sample file (gender/age predictions) are deliberately not stored.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import utcnow
from app.models.event import Event
from app.models.store import Store
from app.services.timerange import store_tz, to_utc_naive


async def insert_events(db: AsyncSession, rows: List[Dict]) -> int:
    """Insert event rows, skipping (store_id, event_key) duplicates. Returns inserted count."""
    if not rows:
        return 0
    insert_fn = postgresql.insert if db.bind.dialect.name == "postgresql" else sqlite.insert
    inserted = 0
    for i in range(0, len(rows), 500):
        chunk = rows[i:i + 500]
        # A multi-row VALUES needs identical keys in every row.
        keys = set().union(*chunk) | {"id", "created_at"}
        chunk = [{k: r.get(k) for k in keys} for r in chunk]
        for r in chunk:
            r["id"] = r["id"] or uuid.uuid4()
            r["created_at"] = r["created_at"] or utcnow()
        stmt = insert_fn(Event).values(chunk).on_conflict_do_nothing(index_elements=["store_id", "event_key"])
        res = await db.execute(stmt)
        inserted += res.rowcount if res.rowcount is not None and res.rowcount >= 0 else len(chunk)
    return inserted


def _line_key(prefix: str, line: str) -> str:
    return f"{prefix}-" + hashlib.sha256(line.encode()).hexdigest()[:40]


def _lines(path: Path) -> Iterable[str]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield line.strip()


async def _store_map(db: AsyncSession) -> Dict[str, Store]:
    return {s.store_code: s for s in (await db.execute(select(Store))).scalars().all()}


def _sample_store_code(d: dict) -> str:
    code = d.get("store_code") or d.get("store_id") or ""
    return f"store_{code[2:]}" if code.startswith("ST") else code


async def import_sample_events(db: AsyncSession, path: Path) -> Dict:
    """Import the bundled sample_events JSONL as ``source='sample'``.

    The file's timestamps have no offset; they are read as store-local time.
    Queue records become QUEUE_ENTER (join), QUEUE_EXIT (with the recorded
    wait) and QUEUE_COMPLETED/QUEUE_ABANDONED at the exit time.
    """
    stores = await _store_map(db)
    rows: List[Dict] = []
    skipped = 0
    for line in _lines(path):
        d = json.loads(line)
        store = stores.get(_sample_store_code(d))
        if store is None:
            skipped += 1
            continue
        tz = store_tz(store.timezone)

        def ts(value: str, tz=tz) -> datetime:
            return to_utc_naive(datetime.fromisoformat(value), tz)

        base = {
            "store_id": store.id, "source": "sample",
            "customer_id": str(d.get("id_token") or d.get("track_id")),
            "camera_id": d.get("camera_id"), "zone_id": d.get("zone_id"), "zone_name": d.get("zone_name"),
            "zone_type": d.get("zone_type"), "is_staff": bool(d.get("is_staff", False)),
            "group_id": d.get("group_id"), "group_size": d.get("group_size"),
        }
        etype = (d.get("event_type") or "").lower()
        if etype in ("entry", "exit"):
            rows.append({**base, "event_type": etype.upper(), "timestamp": ts(d["event_timestamp"]),
                         "event_key": _line_key("sample", line)})
        elif etype in ("zone_entered", "zone_exited"):
            rows.append({**base, "event_type": "ZONE_ENTER" if etype == "zone_entered" else "ZONE_EXIT",
                         "timestamp": ts(d["event_time"]), "event_key": _line_key("sample", line)})
        elif etype in ("queue_completed", "queue_abandoned"):
            join, exit_ = ts(d["queue_join_ts"]), ts(d["queue_exit_ts"])
            wait = d.get("wait_seconds")
            queue_base = {**base, "zone_type": "QUEUE", "queue_position": d.get("queue_position_at_join")}
            rows.append({**queue_base, "event_type": "QUEUE_ENTER", "timestamp": join,
                         "event_key": _line_key("sample-qe", line)})
            rows.append({**queue_base, "event_type": "QUEUE_EXIT", "timestamp": exit_, "queue_wait_seconds": wait,
                         "event_key": _line_key("sample-qx", line)})
            rows.append({**queue_base, "event_type": etype.upper(), "timestamp": exit_, "queue_wait_seconds": wait,
                         "queue_abandoned": etype == "queue_abandoned", "event_key": _line_key("sample", line)})
        else:
            skipped += 1
    inserted = await insert_events(db, rows)
    return {"file": path.name, "rows": len(rows), "inserted": inserted, "duplicates": len(rows) - inserted,
            "skipped": skipped}


async def import_legacy_cv_events(db: AsyncSession, path: Path) -> Dict:
    """Import v1 ``cv_events.jsonl`` as ``source='legacy_cv'``.

    These came from the v1 tracker, whose ENTRY/QUEUE_COMPLETED logic was
    wrong (see docs/PROJECT_AUDIT.md). They are kept for reference only and
    are excluded from default analytics. Timestamps are kept as written.
    """
    stores = await _store_map(db)
    rows: List[Dict] = []
    skipped = 0
    for line in _lines(path):
        d = json.loads(line)
        store = stores.get(d.get("store_code", ""))
        if store is None:
            skipped += 1
            continue
        rows.append({
            "store_id": store.id, "source": "legacy_cv", "event_type": d["event_type"],
            "customer_id": d["customer_id"], "camera_id": d.get("camera_id"), "zone_name": d.get("zone_name"),
            "zone_type": d.get("zone_type"), "timestamp": datetime.fromisoformat(d["timestamp"]),
            "confidence": d.get("confidence"), "dwell_seconds": d.get("dwell_seconds"),
            "queue_wait_seconds": d.get("queue_wait_seconds"), "queue_abandoned": d.get("queue_abandoned"),
            "is_staff": False, "event_key": _line_key("legacy", line),
        })
    inserted = await insert_events(db, rows)
    return {"file": path.name, "rows": len(rows), "inserted": inserted, "duplicates": len(rows) - inserted,
            "skipped": skipped}
