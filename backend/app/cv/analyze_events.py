"""
Ingest CV-generated events into the dashboard demo data.

Reads cv_events.jsonl and produces updated dashboard statistics
that reflect REAL data from the CCTV footage.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def analyze_cv_events():
    """Analyze the CV-generated events and produce dashboard metrics."""
    events_file = Path("c:/Users/adity/OneDrive/Desktop/purple sol/backend/data/cv_events.jsonl")

    if not events_file.exists():
        print("No cv_events.jsonl found. Run process_videos first.")
        return

    events = []
    with open(events_file, "r") as f:
        for line in f:
            if line.strip():
                events.append(json.loads(line))

    print(f"\n{'=' * 60}")
    print(f"  PurpleSol — CV Event Analysis")
    print(f"{'=' * 60}")
    print(f"\n  Total events: {len(events)}")

    # ── Per-store metrics ─────────────────────────────────────────
    stores = defaultdict(list)
    for e in events:
        stores[e["store_code"]].append(e)

    for store_code, store_events in sorted(stores.items()):
        print(f"\n  ──── {store_code} ────")

        # Event type counts
        type_counts = defaultdict(int)
        for e in store_events:
            type_counts[e["event_type"]] += 1

        print(f"  Events: {len(store_events)}")
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            print(f"    {t:20s}: {c}")

        # Unique customers
        customers = set()
        for e in store_events:
            customers.add(e["customer_id"])
        print(f"  Unique tracks: {len(customers)}")

        # Zone visits
        zone_visits = defaultdict(int)
        zone_dwell = defaultdict(list)
        for e in store_events:
            if e["event_type"] == "ZONE_ENTER":
                zn = e.get("zone_name", "Unknown")
                zone_visits[zn] += 1
            if e["event_type"] == "ZONE_EXIT":
                zn = e.get("zone_name", "Unknown")
                dwell = e.get("dwell_seconds", 0)
                if dwell > 0:
                    zone_dwell[zn].append(dwell)

        if zone_visits:
            print(f"\n  Zone visits:")
            for z, c in sorted(zone_visits.items(), key=lambda x: -x[1]):
                avg_dwell = 0
                if z in zone_dwell and zone_dwell[z]:
                    avg_dwell = sum(zone_dwell[z]) / len(zone_dwell[z])
                print(f"    {z:20s}: {c:3d} visits | avg dwell: {avg_dwell:.1f}s")

        # Queue metrics
        queue_waits = []
        for e in store_events:
            if e["event_type"] == "QUEUE_COMPLETED":
                wait = e.get("queue_wait_seconds", 0)
                if wait > 0:
                    queue_waits.append(wait)

        if queue_waits:
            print(f"\n  Queue metrics:")
            print(f"    Customers served: {len(queue_waits)}")
            print(f"    Avg wait: {sum(queue_waits)/len(queue_waits):.1f}s")
            print(f"    Max wait: {max(queue_waits):.1f}s")
            print(f"    Min wait: {min(queue_waits):.1f}s")

        # Entries/exits = footfall
        entries = type_counts.get("ENTRY", 0)
        exits = type_counts.get("EXIT", 0)
        billing = type_counts.get("QUEUE_COMPLETED", 0)
        conv_rate = (billing / entries * 100) if entries > 0 else 0
        print(f"\n  Footfall:")
        print(f"    Entries: {entries}")
        print(f"    Exits: {exits}")
        print(f"    Billing completed: {billing}")
        print(f"    Conversion rate: {conv_rate:.1f}%")

    # ── Generate updated demo-data.ts ──────────────────────────────
    print(f"\n{'─' * 60}")
    print("  Generating updated dashboard data...")

    # Aggregate across stores
    all_entries = sum(1 for e in events if e["event_type"] == "ENTRY")
    all_billing = sum(1 for e in events if e["event_type"] == "QUEUE_COMPLETED")
    all_zone_enters = sum(1 for e in events if e["event_type"] == "ZONE_ENTER")

    # Zone aggregation
    zone_data = defaultdict(lambda: {"visits": 0, "dwell": []})
    for e in events:
        if e["event_type"] == "ZONE_ENTER":
            zn = e.get("zone_name", "Unknown")
            zone_data[zn]["visits"] += 1
        if e["event_type"] == "ZONE_EXIT":
            zn = e.get("zone_name", "Unknown")
            dwell = e.get("dwell_seconds", 0)
            if dwell > 0:
                zone_data[zn]["dwell"].append(dwell)

    # Queue aggregation
    queue_waits_all = []
    for e in events:
        if e["event_type"] == "QUEUE_COMPLETED":
            w = e.get("queue_wait_seconds", 0)
            if w > 0:
                queue_waits_all.append(w)

    conv_rate = (all_billing / all_entries * 100) if all_entries > 0 else 0

    print(f"\n  Real metrics for dashboard:")
    print(f"    Total visitors (ENTRY): {all_entries}")
    print(f"    Zone visits: {all_zone_enters}")
    print(f"    Billing completed: {all_billing}")
    print(f"    Conversion rate: {conv_rate:.1f}%")
    if queue_waits_all:
        print(f"    Avg queue wait: {sum(queue_waits_all)/len(queue_waits_all):.1f}s")

    print(f"\n{'=' * 60}")
    print(f"  Done! Use these metrics to update the dashboard.")
    print(f"{'=' * 60}\n")

    return {
        "total_visitors": all_entries,
        "zone_visitors": all_zone_enters,
        "billing_completed": all_billing,
        "conversion_rate": conv_rate,
        "queue_waits": queue_waits_all,
        "zone_data": dict(zone_data),
    }


if __name__ == "__main__":
    analyze_cv_events()
