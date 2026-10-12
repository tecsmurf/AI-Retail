"""Seed reference data: stores, cameras, store-level zones, and optionally
the bundled sample datasets.

    python -m app.seed                 # stores, cameras, zones (idempotent)
    python -m app.seed --sample        # + sample events (source=sample) and the POS CSV
    python -m app.seed --legacy        # + v1 cv_events.jsonl (source=legacy_cv)

Running it again never duplicates anything. Sample and legacy records are
excluded from analytics unless the dashboard is switched to "all data".
The zones below are the v1 store-level zone list (no camera, no polygon);
camera zones with polygons are drawn in the dashboard's zone editor.
The POS CSV's store code (ST1008) does not match either store, so its rows
are imported but stay unassigned until an admin maps a store to it.
"""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from sqlalchemy import select

from app.database import async_session
from app.models.store import Camera, Store, Zone
from app.services import pos_service
from app.services.ingest import import_legacy_cv_events, import_sample_events

REPO_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("PURPLESOL_DATA_DIR", REPO_DIR / "purple"))
LEGACY_FILE = Path(__file__).resolve().parents[1] / "data" / "cv_events.jsonl"

STORES = [
    {
        "store_code": "store_1076",
        "name": "Purplle Beauty Store 1 — Mumbai",
        "city": "Mumbai",
        "address": "Mumbai, Maharashtra",
        "timezone": "Asia/Kolkata",
    },
    {
        "store_code": "store_1077",
        "name": "Purplle Beauty Store 2 — Mumbai",
        "city": "Mumbai",
        "address": "Mumbai, Maharashtra",
        "timezone": "Asia/Kolkata",
    },
]

CAMERAS = {
    "store_1076": [
        {"camera_code": "CAM1", "name": "Zone Camera 1", "camera_type": "zone"},
        {"camera_code": "CAM2", "name": "Zone Camera 2", "camera_type": "zone"},
        {"camera_code": "CAM3", "name": "Entry Camera", "camera_type": "entrance"},
        {"camera_code": "CAM5", "name": "Billing Camera", "camera_type": "billing"},
    ],
    "store_1077": [
        {"camera_code": "CAM1", "name": "Entry Camera 1", "camera_type": "entrance"},
        {"camera_code": "CAM2", "name": "Entry Camera 2", "camera_type": "entrance"},
        {"camera_code": "CAM3", "name": "Billing Camera", "camera_type": "billing"},
        {"camera_code": "CAM4", "name": "Zone Camera", "camera_type": "zone"},
    ],
}

ZONES = {
    "store_1076": [
        {"zone_code": "S1_ENTRANCE", "name": "Entrance", "zone_type": "ENTRANCE", "is_revenue_zone": False, "color": "#4CAF50"},
        {"zone_code": "S1_SALM", "name": "Salm", "zone_type": "SHELF", "is_revenue_zone": True, "color": "#E91E63"},
        {"zone_code": "S1_TFS", "name": "TFS", "zone_type": "SHELF", "is_revenue_zone": True, "color": "#9C27B0"},
        {"zone_code": "S1_MINIMALIST", "name": "Minimalist", "zone_type": "SHELF", "is_revenue_zone": True, "color": "#2196F3"},
        {"zone_code": "S1_AQUALOGICA", "name": "Aqualogica", "zone_type": "SHELF", "is_revenue_zone": True, "color": "#00BCD4"},
        {"zone_code": "S1_FOXTALE", "name": "Foxtale", "zone_type": "SHELF", "is_revenue_zone": True, "color": "#FF9800"},
        {"zone_code": "S1_JC", "name": "Juicy Chemistry", "zone_type": "SHELF", "is_revenue_zone": True, "color": "#FFEB3B"},
        {"zone_code": "S1_FACES", "name": "Faces Canada", "zone_type": "SHELF", "is_revenue_zone": True, "color": "#F44336"},
        {"zone_code": "S1_MARS", "name": "Mars + NY Bae", "zone_type": "SHELF", "is_revenue_zone": True, "color": "#795548"},
        {"zone_code": "S1_MENS", "name": "Men's Section", "zone_type": "SHELF", "is_revenue_zone": True, "color": "#607D8B"},
        {"zone_code": "S1_LOREAL", "name": "L'Oreal", "zone_type": "SHELF", "is_revenue_zone": True, "color": "#FF5722"},
        {"zone_code": "S1_BEAUTY", "name": "Beauty", "zone_type": "SHELF", "is_revenue_zone": True, "color": "#E040FB"},
        {"zone_code": "S1_MAKEUP", "name": "Makeup Unit", "zone_type": "DISPLAY", "is_revenue_zone": True, "color": "#CE93D8"},
        {"zone_code": "S1_FRAGRANCE", "name": "Fragrance & Nail", "zone_type": "DISPLAY", "is_revenue_zone": True, "color": "#B39DDB"},
        {"zone_code": "S1_BILLING", "name": "Cash Counter", "zone_type": "BILLING", "is_revenue_zone": True, "color": "#4CAF50"},
    ],
    "store_1077": [
        {"zone_code": "S2_ENTRANCE", "name": "Entrance", "zone_type": "ENTRANCE", "is_revenue_zone": False, "color": "#4CAF50"},
        {"zone_code": "S2_LEFT_WALL", "name": "Left Wall", "zone_type": "SHELF", "is_revenue_zone": True, "color": "#E91E63"},
        {"zone_code": "S2_RIGHT_WALL", "name": "Right Wall", "zone_type": "SHELF", "is_revenue_zone": True, "color": "#9C27B0"},
        {"zone_code": "S2_CENTER_1", "name": "Center Display 1", "zone_type": "DISPLAY", "is_revenue_zone": True, "color": "#2196F3"},
        {"zone_code": "S2_CENTER_2", "name": "Center Display 2", "zone_type": "DISPLAY", "is_revenue_zone": True, "color": "#00BCD4"},
        {"zone_code": "S2_MAKEUP", "name": "Makeup Area", "zone_type": "DISPLAY", "is_revenue_zone": True, "color": "#FF9800"},
        {"zone_code": "S2_BILLING", "name": "Billing Area", "zone_type": "BILLING", "is_revenue_zone": True, "color": "#4CAF50"},
    ],
}


async def seed_reference(db) -> dict:
    created = {"stores": 0, "cameras": 0, "zones": 0}
    stores = {s.store_code: s for s in (await db.execute(select(Store))).scalars().all()}
    for data in STORES:
        if data["store_code"] not in stores:
            store = Store(**data, is_active=True)
            db.add(store)
            await db.flush()
            stores[store.store_code] = store
            created["stores"] += 1
    for code, cams in CAMERAS.items():
        store = stores[code]
        have = {c for (c,) in (await db.execute(select(Camera.camera_code).where(Camera.store_id == store.id))).all()}
        for cam in cams:
            if cam["camera_code"] not in have:
                db.add(Camera(store_id=store.id, is_active=True, config_version=1, **cam))
                created["cameras"] += 1
    for code, zones in ZONES.items():
        store = stores[code]
        have = {z for (z,) in (await db.execute(select(Zone.zone_code).where(Zone.store_id == store.id))).all()}
        for order, zone in enumerate(zones):
            if zone["zone_code"] not in have:
                db.add(Zone(store_id=store.id, display_order=order, **zone))
                created["zones"] += 1
    await db.flush()
    return created


async def run(sample: bool, legacy: bool) -> dict:
    report = {}
    async with async_session() as db:
        report["reference"] = await seed_reference(db)
        if sample:
            events_file = DATA_DIR / "sample_eventsbe42122.jsonl"
            pos_file = DATA_DIR / "POS - sample transactionsb1e826f.csv"
            if events_file.exists():
                report["sample_events"] = await import_sample_events(db, events_file)
            else:
                report["sample_events"] = f"not found: {events_file}"
            if pos_file.exists():
                report["pos"] = await pos_service.import_csv(db, pos_file.read_text(encoding="utf-8-sig"), source="sample")
            else:
                report["pos"] = f"not found: {pos_file}"
        if legacy:
            report["legacy_cv"] = (
                await import_legacy_cv_events(db, LEGACY_FILE) if LEGACY_FILE.exists() else f"not found: {LEGACY_FILE}"
            )
        await db.commit()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed PurpleSol reference data (idempotent)")
    parser.add_argument("--sample", action="store_true", help="import the bundled sample events and POS CSV")
    parser.add_argument("--legacy", action="store_true", help="import v1 cv_events.jsonl as legacy_cv")
    args = parser.parse_args()
    report = asyncio.run(run(args.sample, args.legacy))
    for k, v in report.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
