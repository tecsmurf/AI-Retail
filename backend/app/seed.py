"""
Seed script — populate database with store data, zones, cameras,
sample events from provided assets, and POS transactions.
"""

from __future__ import annotations

import asyncio
import csv
import json
import uuid
from datetime import datetime, date, time
from pathlib import Path

from app.database import async_session, init_db
from app.models.store import Store, Camera, Zone
from app.models.event import Event
from app.models.pos import POSTransaction


# ── Store Definitions ────────────────────────────────────────────

STORES = [
    {
        "store_code": "store_1076",
        "name": "Purplle Beauty Store 1 — Mumbai",
        "city": "Mumbai",
        "address": "Mumbai, Maharashtra",
    },
    {
        "store_code": "store_1077",
        "name": "Purplle Beauty Store 2 — Mumbai",
        "city": "Mumbai",
        "address": "Mumbai, Maharashtra",
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


async def seed_stores(session) -> dict:
    """Seed stores and return store_code -> store_id mapping."""
    store_map = {}
    for store_data in STORES:
        store = Store(**store_data)
        session.add(store)
        await session.flush()
        store_map[store_data["store_code"]] = store.id
        print(f"  ✓ Store: {store.name} ({store.store_code})")
    return store_map


async def seed_cameras(session, store_map: dict) -> None:
    """Seed cameras for each store."""
    for store_code, cameras in CAMERAS.items():
        store_id = store_map.get(store_code)
        if not store_id:
            continue
        for cam_data in cameras:
            camera = Camera(store_id=store_id, **cam_data)
            session.add(camera)
        print(f"  ✓ Cameras for {store_code}: {len(cameras)}")


async def seed_zones(session, store_map: dict) -> None:
    """Seed zones for each store."""
    for store_code, zones in ZONES.items():
        store_id = store_map.get(store_code)
        if not store_id:
            continue
        for i, zone_data in enumerate(zones):
            zone = Zone(store_id=store_id, display_order=i, **zone_data)
            session.add(zone)
        print(f"  ✓ Zones for {store_code}: {len(zones)}")


async def seed_sample_events(session, store_map: dict) -> None:
    """Seed events from sample_events.jsonl."""
    data_dir = Path(__file__).parent.parent / "purple"
    events_file = data_dir / "sample_eventsbe42122.jsonl"

    if not events_file.exists():
        # Try alternate paths
        for candidate in [
            Path("c:/Users/adity/OneDrive/Desktop/purple sol/purple/sample_eventsbe42122.jsonl"),
        ]:
            if candidate.exists():
                events_file = candidate
                break
        else:
            print("  ⚠ sample_events.jsonl not found, skipping")
            return

    count = 0
    with open(events_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)

            # Map event type
            event_type = data.get("event_type", "").upper()
            if event_type == "ZONE_ENTERED":
                event_type = "ZONE_ENTER"
            elif event_type == "ZONE_EXITED":
                event_type = "ZONE_EXIT"

            # Resolve store
            store_code = data.get("store_code") or data.get("store_id", "")
            if store_code.startswith("ST"):
                store_code = f"store_{store_code[2:]}"
            store_id = store_map.get(store_code)
            if not store_id:
                # Default to first store
                store_id = list(store_map.values())[0]

            # Get timestamp
            ts = data.get("event_timestamp") or data.get("event_time") or data.get("queue_join_ts")
            if ts:
                timestamp = datetime.fromisoformat(ts)
            else:
                timestamp = datetime.utcnow()

            # Customer ID
            customer_id = str(
                data.get("id_token")
                or data.get("track_id")
                or f"CUST_{count}"
            )

            event = Event(
                store_id=store_id,
                event_type=event_type,
                customer_id=customer_id,
                camera_id=data.get("camera_id"),
                zone_id=data.get("zone_id"),
                zone_name=data.get("zone_name"),
                zone_type=data.get("zone_type"),
                timestamp=timestamp,
                hotspot_x=data.get("zone_hotspot_x"),
                hotspot_y=data.get("zone_hotspot_y"),
                gender=data.get("gender_pred") or data.get("gender"),
                age=data.get("age_pred") or data.get("age"),
                age_bucket=data.get("age_bucket"),
                is_staff=data.get("is_staff", False),
                queue_wait_seconds=data.get("wait_seconds"),
                queue_position=data.get("queue_position_at_join"),
                queue_abandoned=data.get("abandoned"),
                group_id=data.get("group_id"),
                group_size=data.get("group_size"),
            )
            session.add(event)
            count += 1

    print(f"  ✓ Events loaded: {count}")


async def seed_pos_transactions(session, store_map: dict) -> None:
    """Seed POS transactions from CSV."""
    data_dir = Path(__file__).parent.parent / "purple"
    csv_file = data_dir / "POS - sample transactionsb1e826f.csv"

    if not csv_file.exists():
        for candidate in [
            Path("c:/Users/adity/OneDrive/Desktop/purple sol/purple/POS - sample transactionsb1e826f.csv"),
        ]:
            if candidate.exists():
                csv_file = candidate
                break
        else:
            print("  ⚠ POS CSV not found, skipping")
            return

    count = 0
    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                order_date = datetime.strptime(row["order_date"], "%d-%m-%Y").date()
                order_time = datetime.strptime(row["order_time"], "%H:%M:%S").time()
            except ValueError:
                continue

            txn = POSTransaction(
                order_id=int(row["order_id"]),
                store_id=row["store_id"],
                order_date=order_date,
                order_time=order_time,
                product_id=row["product_id"],
                brand_name=row["brand_name"],
                total_amount=float(row["total_amount"]),
            )
            session.add(txn)
            count += 1

    print(f"  ✓ POS transactions loaded: {count}")


async def seed_demo_data(session, store_map: dict) -> None:
    """
    Generate additional realistic demo events to make the dashboard look alive.
    Creates footfall patterns, zone visits, and journeys for both stores.
    """
    import random

    random.seed(42)

    zones_s1 = ["Salm", "TFS", "Minimalist", "Aqualogica", "Foxtale",
                 "Juicy Chemistry", "Faces Canada", "Mars + NY Bae",
                 "Men's Section", "L'Oreal", "Beauty", "Makeup Unit"]
    zones_s2 = ["Left Wall", "Right Wall", "Center Display 1",
                 "Center Display 2", "Makeup Area"]

    store_zones = {
        "store_1076": zones_s1,
        "store_1077": zones_s2,
    }

    genders = ["M", "F"]
    age_buckets = ["18-24", "25-34", "35-44", "45-54"]

    count = 0
    for store_code, store_id in store_map.items():
        zones = store_zones.get(store_code, zones_s1)

        # Generate 150 customer journeys per store
        for i in range(150):
            customer_id = f"DEMO_{store_code}_{i:04d}"
            gender = random.choice(genders)
            age = random.randint(18, 55)
            age_bucket = (
                "18-24" if age < 25
                else "25-34" if age < 35
                else "35-44" if age < 45
                else "45-54"
            )

            # Random hour (9 AM to 9 PM)
            hour = random.randint(9, 21)
            minute = random.randint(0, 59)
            base_time = datetime(2026, 3, 8, hour, minute, 0)

            # ENTRY event
            entry = Event(
                store_id=store_id,
                event_type="ENTRY",
                customer_id=customer_id,
                camera_id="CAM1",
                timestamp=base_time,
                gender=gender,
                age=age,
                age_bucket=age_bucket,
                is_staff=False,
            )
            session.add(entry)
            count += 1

            # Visit 1-4 zones
            num_zones = random.randint(1, min(4, len(zones)))
            visited = random.sample(zones, num_zones)
            current_time = base_time

            for z_name in visited:
                # Zone enter
                current_time = current_time.replace(
                    second=0, microsecond=0
                ) + __import__("datetime").timedelta(
                    seconds=random.randint(30, 120)
                )
                enter = Event(
                    store_id=store_id,
                    event_type="ZONE_ENTER",
                    customer_id=customer_id,
                    zone_name=z_name,
                    zone_type="SHELF",
                    timestamp=current_time,
                    gender=gender,
                    age=age,
                    age_bucket=age_bucket,
                )
                session.add(enter)
                count += 1

                # Dwell time (20s to 180s)
                dwell = random.randint(20, 180)
                current_time += __import__("datetime").timedelta(seconds=dwell)

                # Zone exit
                exit_ev = Event(
                    store_id=store_id,
                    event_type="ZONE_EXIT",
                    customer_id=customer_id,
                    zone_name=z_name,
                    zone_type="SHELF",
                    timestamp=current_time,
                    dwell_seconds=float(dwell),
                    gender=gender,
                    age=age,
                    age_bucket=age_bucket,
                )
                session.add(exit_ev)
                count += 1

            # 30% chance of checkout
            if random.random() < 0.30:
                current_time += __import__("datetime").timedelta(
                    seconds=random.randint(30, 90)
                )
                queue_wait = random.randint(5, 60)

                checkout = Event(
                    store_id=store_id,
                    event_type="QUEUE_COMPLETED",
                    customer_id=customer_id,
                    zone_name="Billing",
                    zone_type="BILLING",
                    timestamp=current_time,
                    queue_wait_seconds=float(queue_wait),
                    queue_position=random.randint(1, 5),
                    queue_abandoned=False,
                    gender=gender,
                    age=age,
                    age_bucket=age_bucket,
                )
                session.add(checkout)
                count += 1

            # EXIT event
            current_time += __import__("datetime").timedelta(
                seconds=random.randint(10, 60)
            )
            exit_event = Event(
                store_id=store_id,
                event_type="EXIT",
                customer_id=customer_id,
                camera_id="CAM1",
                timestamp=current_time,
                gender=gender,
                age=age,
                age_bucket=age_bucket,
            )
            session.add(exit_event)
            count += 1

    print(f"  ✓ Demo events generated: {count}")


async def main():
    """Run the seed script."""
    print("\n🌱 Seeding PurpleSol database...\n")

    await init_db()
    print("  ✓ Tables created\n")

    async with async_session() as session:
        # Check if already seeded
        from sqlalchemy import select, func
        result = await session.execute(select(func.count(Store.id)))
        existing = result.scalar()
        if existing and existing > 0:
            print("  ℹ Database already has data. Skipping seed.\n")
            return

        print("── Stores & Infrastructure ──")
        store_map = await seed_stores(session)
        await seed_cameras(session, store_map)
        await seed_zones(session, store_map)

        print("\n── Event Data ──")
        await seed_sample_events(session, store_map)
        await seed_demo_data(session, store_map)

        print("\n── POS Data ──")
        await seed_pos_transactions(session, store_map)

        await session.commit()
        print("\n✅ Seed complete!\n")


if __name__ == "__main__":
    asyncio.run(main())
