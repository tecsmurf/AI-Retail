"""
Process actual CCTV footage from Store 1 and Store 2.

This script:
1. Loads each video file
2. Runs YOLO11 person detection
3. Tracks persons with ByteTrack
4. Maps positions to zones using camera-specific zone polygons
5. Generates business events (ENTRY, EXIT, ZONE_ENTER, ZONE_EXIT, etc.)
6. Saves events to a JSONL file for database ingestion

Usage:
    python -m app.cv.process_videos
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import cv2
import numpy as np

from app.cv.detector import PersonDetector, Detection
from app.cv.tracker import ByteTracker, Track
from app.cv.zone_mapper import ZoneMapper, ZonePolygon


# ── Zone Configurations Per Camera ───────────────────────────────
# These polygons are defined in pixel coordinates relative to each
# camera's frame. They are estimated from the store layouts and
# would be calibrated precisely during real deployment.

def get_store1_cam1_zones() -> List[ZonePolygon]:
    """Store 1, CAM 1 — Zone camera (upper area brands)."""
    return [
        ZonePolygon("Salm", "SHELF",
                    [(50, 30), (200, 30), (200, 200), (50, 200)],
                    color="#E91E63"),
        ZonePolygon("TFS", "SHELF",
                    [(220, 30), (380, 30), (380, 200), (220, 200)],
                    color="#9C27B0"),
        ZonePolygon("Minimalist", "SHELF",
                    [(500, 30), (680, 30), (680, 200), (500, 200)],
                    color="#2196F3"),
        ZonePolygon("Aqualogica", "SHELF",
                    [(700, 30), (880, 30), (880, 200), (700, 200)],
                    color="#00BCD4"),
        ZonePolygon("Foxtale", "SHELF",
                    [(900, 30), (1060, 30), (1060, 200), (900, 200)],
                    color="#FF9800"),
        ZonePolygon("Juicy Chemistry", "SHELF",
                    [(1080, 30), (1250, 30), (1250, 200), (1080, 200)],
                    color="#FFEB3B"),
        ZonePolygon("Fragrance & Nail", "DISPLAY",
                    [(350, 280), (520, 280), (520, 480), (350, 480)],
                    color="#B39DDB"),
        ZonePolygon("Makeup Unit", "DISPLAY",
                    [(580, 280), (880, 280), (880, 500), (580, 500)],
                    color="#CE93D8"),
    ]


def get_store1_cam2_zones() -> List[ZonePolygon]:
    """Store 1, CAM 2 — Zone camera (lower area brands)."""
    return [
        ZonePolygon("Faces Canada", "SHELF",
                    [(100, 500), (350, 500), (350, 700), (100, 700)],
                    color="#F44336"),
        ZonePolygon("Mars + NY Bae", "SHELF",
                    [(380, 500), (560, 500), (560, 700), (380, 700)],
                    color="#795548"),
        ZonePolygon("Men's Section", "SHELF",
                    [(580, 500), (760, 500), (760, 700), (580, 700)],
                    color="#607D8B"),
        ZonePolygon("L'Oreal", "SHELF",
                    [(800, 500), (1050, 500), (1050, 700), (800, 700)],
                    color="#FF5722"),
        ZonePolygon("Beauty", "SHELF",
                    [(1070, 500), (1250, 500), (1250, 700), (1070, 700)],
                    color="#E040FB"),
    ]


def get_store1_cam3_zones() -> List[ZonePolygon]:
    """Store 1, CAM 3 — Entry camera."""
    return [
        ZonePolygon("Entrance", "ENTRANCE",
                    [(0, 0), (1280, 0), (1280, 720), (0, 720)],
                    is_revenue_zone=False, color="#4CAF50"),
    ]


def get_store1_cam5_zones() -> List[ZonePolygon]:
    """Store 1, CAM 5 — Billing camera."""
    return [
        ZonePolygon("Cash Counter", "BILLING",
                    [(0, 0), (1280, 0), (1280, 720), (0, 720)],
                    color="#4CAF50"),
    ]


def get_store2_entry_zones() -> List[ZonePolygon]:
    """Store 2, entry cameras."""
    return [
        ZonePolygon("Entrance", "ENTRANCE",
                    [(0, 0), (1280, 0), (1280, 720), (0, 720)],
                    is_revenue_zone=False, color="#4CAF50"),
    ]


def get_store2_billing_zones() -> List[ZonePolygon]:
    """Store 2, billing camera."""
    return [
        ZonePolygon("Billing Area", "BILLING",
                    [(0, 0), (1280, 0), (1280, 720), (0, 720)],
                    color="#4CAF50"),
    ]


def get_store2_zone_zones() -> List[ZonePolygon]:
    """Store 2, zone camera."""
    return [
        ZonePolygon("Left Wall", "SHELF",
                    [(20, 100), (200, 100), (200, 600), (20, 600)],
                    color="#E91E63"),
        ZonePolygon("Right Wall", "SHELF",
                    [(1080, 100), (1260, 100), (1260, 600), (1080, 600)],
                    color="#9C27B0"),
        ZonePolygon("Center Display 1", "DISPLAY",
                    [(300, 300), (550, 300), (550, 550), (300, 550)],
                    color="#2196F3"),
        ZonePolygon("Center Display 2", "DISPLAY",
                    [(600, 300), (850, 300), (850, 550), (600, 550)],
                    color="#00BCD4"),
        ZonePolygon("Makeup Area", "DISPLAY",
                    [(650, 200), (950, 200), (950, 420), (650, 420)],
                    color="#FF9800"),
    ]


# ── Video Processing Configuration ───────────────────────────────

VIDEO_CONFIGS = {
    # Store 1
    "store1_cam1_zone": {
        "store_code": "store_1076",
        "camera_id": "CAM1",
        "camera_type": "zone",
        "zones_fn": get_store1_cam1_zones,
    },
    "store1_cam2_zone": {
        "store_code": "store_1076",
        "camera_id": "CAM2",
        "camera_type": "zone",
        "zones_fn": get_store1_cam2_zones,
    },
    "store1_cam3_entry": {
        "store_code": "store_1076",
        "camera_id": "CAM3",
        "camera_type": "entrance",
        "zones_fn": get_store1_cam3_zones,
    },
    "store1_cam5_billing": {
        "store_code": "store_1076",
        "camera_id": "CAM5",
        "camera_type": "billing",
        "zones_fn": get_store1_cam5_zones,
    },
    # Store 2
    "store2_entry1": {
        "store_code": "store_1077",
        "camera_id": "CAM1",
        "camera_type": "entrance",
        "zones_fn": get_store2_entry_zones,
    },
    "store2_entry2": {
        "store_code": "store_1077",
        "camera_id": "CAM2",
        "camera_type": "entrance",
        "zones_fn": get_store2_entry_zones,
    },
    "store2_billing": {
        "store_code": "store_1077",
        "camera_id": "CAM3",
        "camera_type": "billing",
        "zones_fn": get_store2_billing_zones,
    },
    "store2_zone": {
        "store_code": "store_1077",
        "camera_id": "CAM4",
        "camera_type": "zone",
        "zones_fn": get_store2_zone_zones,
    },
}

# Map file names to configs
FILE_TO_CONFIG = {
    "CAM 1 - zone.mp4": "store1_cam1_zone",
    "CAM 2 - zone.mp4": "store1_cam2_zone",
    "CAM 3 - entry.mp4": "store1_cam3_entry",
    "CAM 5 - billing.mp4": "store1_cam5_billing",
    "entry 1.mp4": "store2_entry1",
    "entry 2.mp4": "store2_entry2",
    "billing_area.mp4": "store2_billing",
    "zone.mp4": "store2_zone",
}


class CCTVProcessor:
    """Process CCTV footage and generate business events."""

    def __init__(
        self,
        store_code: str,
        camera_id: str,
        camera_type: str,
        zones: List[ZonePolygon],
        confidence: float = 0.4,
        sample_rate: int = 10,  # Process every Nth frame
    ):
        self.store_code = store_code
        self.camera_id = camera_id
        self.camera_type = camera_type
        self.zone_mapper = ZoneMapper(zones)
        self.confidence = confidence
        self.sample_rate = sample_rate

        self.detector = PersonDetector(confidence=confidence)
        self.tracker = ByteTracker(track_thresh=0.4, track_buffer=60)

        # State tracking
        self.customer_zones: Dict[int, Optional[str]] = {}
        self.customer_first_seen: Dict[int, datetime] = {}
        self.customer_zone_enter_time: Dict[int, datetime] = {}
        self.active_tracks: set = set()
        self.events: List[Dict] = []

    def process_video(self, video_path: str, base_timestamp: datetime = None) -> List[Dict]:
        """
        Process a video file and generate events.

        Args:
            video_path: Path to the video file
            base_timestamp: Starting timestamp for event generation

        Returns:
            List of business event dicts
        """
        if base_timestamp is None:
            base_timestamp = datetime(2026, 3, 8, 10, 0, 0)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"  ✗ Cannot open video: {video_path}")
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_secs = total_frames / fps

        print(f"  ├─ FPS: {fps:.1f}, Frames: {total_frames}, Duration: {duration_secs:.0f}s")
        print(f"  ├─ Processing every {self.sample_rate}th frame ({total_frames // self.sample_rate} iterations)")
        print(f"  ├─ Zones: {[z.name for z in self.zone_mapper.zones]}")

        frame_count = 0
        processed_count = 0
        start_time = time.time()

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % self.sample_rate == 0:
                # Calculate video timestamp
                video_seconds = frame_count / fps
                current_ts = base_timestamp + timedelta(seconds=video_seconds)

                # Detect + track
                detections = self.detector.detect(frame)
                tracks = self.tracker.update(detections)

                # Generate events from tracks
                self._process_tracks(tracks, current_ts, frame.shape)

                processed_count += 1

                # Progress reporting
                if processed_count % 100 == 0:
                    elapsed = time.time() - start_time
                    progress = frame_count / total_frames * 100
                    fps_actual = processed_count / elapsed if elapsed > 0 else 0
                    print(f"  ├─ Progress: {progress:.1f}% | "
                          f"Events: {len(self.events)} | "
                          f"Active tracks: {len(tracks)} | "
                          f"{fps_actual:.1f} frames/s")

            frame_count += 1

        cap.release()

        # Generate EXIT events for remaining tracks
        final_ts = base_timestamp + timedelta(seconds=duration_secs)
        for track_id in list(self.active_tracks):
            self._emit_exit(track_id, final_ts)

        elapsed = time.time() - start_time
        print(f"  └─ Done: {len(self.events)} events in {elapsed:.1f}s")

        return self.events

    def _process_tracks(
        self, tracks: List[Track], timestamp: datetime, frame_shape: Tuple
    ):
        """Process current tracks and generate events."""
        h, w = frame_shape[:2]
        current_track_ids = set()

        for track in tracks:
            track_id = track.track_id
            current_track_ids.add(track_id)

            # Normalize bottom-center to frame coordinates
            bx, by = track.bottom_center

            # Check zone
            zone = self.zone_mapper.get_zone(bx, by)
            current_zone = zone.name if zone else None
            prev_zone = self.customer_zones.get(track_id)

            customer_id = f"{self.store_code}_{self.camera_id}_T{track_id:04d}"

            # New track = new customer
            if track_id not in self.active_tracks:
                self.active_tracks.add(track_id)
                self.customer_first_seen[track_id] = timestamp

                if self.camera_type == "entrance":
                    self._emit_event("ENTRY", customer_id, timestamp, track, zone)

            # Zone transition
            if current_zone != prev_zone:
                # Exit previous zone
                if prev_zone is not None:
                    dwell = 0.0
                    enter_time = self.customer_zone_enter_time.get(track_id)
                    if enter_time:
                        dwell = (timestamp - enter_time).total_seconds()
                    self._emit_event("ZONE_EXIT", customer_id, timestamp, track,
                                     zone_name=prev_zone, dwell_seconds=dwell)

                # Enter new zone
                if current_zone is not None:
                    self.customer_zone_enter_time[track_id] = timestamp
                    zone_type = zone.zone_type if zone else "SHELF"

                    if zone_type == "BILLING":
                        self._emit_event("QUEUE_ENTER", customer_id, timestamp,
                                         track, zone_name=current_zone)
                    else:
                        self._emit_event("ZONE_ENTER", customer_id, timestamp,
                                         track, zone_name=current_zone,
                                         zone_type=zone_type)

                self.customer_zones[track_id] = current_zone

        # Detect exits (tracks that disappeared)
        lost_tracks = self.active_tracks - current_track_ids
        for lost_id in lost_tracks:
            customer_id = f"{self.store_code}_{self.camera_id}_T{lost_id:04d}"

            # Emit zone exit if in a zone
            prev_zone = self.customer_zones.get(lost_id)
            if prev_zone:
                dwell = 0.0
                enter_time = self.customer_zone_enter_time.get(lost_id)
                if enter_time:
                    dwell = (timestamp - enter_time).total_seconds()
                self._emit_event("ZONE_EXIT", customer_id, timestamp,
                                 zone_name=prev_zone, dwell_seconds=dwell)

            # Emit exit for entrance/billing cameras
            if self.camera_type in ("entrance", "billing"):
                first_seen = self.customer_first_seen.get(lost_id, timestamp)
                total_time = (timestamp - first_seen).total_seconds()

                if self.camera_type == "billing":
                    self._emit_event("QUEUE_COMPLETED", customer_id, timestamp,
                                     zone_name="Billing",
                                     queue_wait=total_time)
                else:
                    self._emit_event("EXIT", customer_id, timestamp)

            self.active_tracks.discard(lost_id)
            self.customer_zones.pop(lost_id, None)
            self.customer_zone_enter_time.pop(lost_id, None)

    def _emit_exit(self, track_id: int, timestamp: datetime):
        """Emit EXIT event for a track."""
        customer_id = f"{self.store_code}_{self.camera_id}_T{track_id:04d}"
        prev_zone = self.customer_zones.get(track_id)
        if prev_zone:
            self._emit_event("ZONE_EXIT", customer_id, timestamp,
                             zone_name=prev_zone)
        self.active_tracks.discard(track_id)

    def _emit_event(
        self,
        event_type: str,
        customer_id: str,
        timestamp: datetime,
        track: Track = None,
        zone: ZonePolygon = None,
        zone_name: str = None,
        zone_type: str = None,
        dwell_seconds: float = None,
        queue_wait: float = None,
    ):
        """Create and store a business event."""
        event = {
            "event_type": event_type,
            "customer_id": customer_id,
            "store_code": self.store_code,
            "camera_id": self.camera_id,
            "timestamp": timestamp.isoformat(),
        }

        if zone:
            event["zone_name"] = zone.name
            event["zone_type"] = zone.zone_type
        elif zone_name:
            event["zone_name"] = zone_name
            if zone_type:
                event["zone_type"] = zone_type

        if track:
            event["confidence"] = round(track.confidence, 3)
            event["bbox_x"] = round(track.bbox[0], 1)
            event["bbox_y"] = round(track.bbox[1], 1)
            event["bbox_w"] = round(track.bbox[2] - track.bbox[0], 1)
            event["bbox_h"] = round(track.bbox[3] - track.bbox[1], 1)

        if dwell_seconds is not None and dwell_seconds > 0:
            event["dwell_seconds"] = round(dwell_seconds, 1)

        if queue_wait is not None and queue_wait > 0:
            event["queue_wait_seconds"] = round(queue_wait, 1)
            event["queue_abandoned"] = False

        self.events.append(event)


def find_video_files() -> List[Tuple[str, str]]:
    """Find all CCTV video files and their config keys."""
    base_paths = [
        Path("c:/Users/adity/OneDrive/Desktop/purple sol/purple"),
    ]

    videos = []
    for base in base_paths:
        if not base.exists():
            continue
        for mp4 in base.rglob("*.mp4"):
            filename = mp4.name
            if filename in FILE_TO_CONFIG:
                config_key = FILE_TO_CONFIG[filename]
                videos.append((str(mp4), config_key))

    return videos


def main():
    """Process all CCTV footage and generate events."""
    print("\n" + "=" * 60)
    print("  PurpleSol — CCTV Footage Processing")
    print("=" * 60)

    videos = find_video_files()
    if not videos:
        print("\n  ✗ No video files found!")
        print("  Looking in: purple/ directory")
        return

    print(f"\n  Found {len(videos)} video files:\n")
    for path, config_key in videos:
        config = VIDEO_CONFIGS[config_key]
        print(f"  • {Path(path).name}")
        print(f"    Store: {config['store_code']} | "
              f"Camera: {config['camera_id']} | "
              f"Type: {config['camera_type']}")

    # Output file
    output_dir = Path("c:/Users/adity/OneDrive/Desktop/purple sol/backend/data")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "cv_events.jsonl"

    all_events = []
    base_ts = datetime(2026, 3, 8, 10, 0, 0)

    print(f"\n{'─' * 60}")
    print("  Processing videos...\n")

    for video_path, config_key in videos:
        config = VIDEO_CONFIGS[config_key]
        filename = Path(video_path).name
        print(f"\n  📹 {filename}")
        print(f"  ├─ Store: {config['store_code']}, Camera: {config['camera_id']}")

        zones = config["zones_fn"]()
        processor = CCTVProcessor(
            store_code=config["store_code"],
            camera_id=config["camera_id"],
            camera_type=config["camera_type"],
            zones=zones,
            confidence=0.4,
            sample_rate=15,  # Every 15th frame for speed
        )

        events = processor.process_video(video_path, base_ts)
        all_events.extend(events)

    # Save all events
    print(f"\n{'─' * 60}")
    print(f"\n  📊 Total events generated: {len(all_events)}")

    with open(output_file, "w") as f:
        for event in all_events:
            f.write(json.dumps(event) + "\n")

    print(f"  💾 Saved to: {output_file}")

    # Event type breakdown
    event_types: Dict[str, int] = {}
    for e in all_events:
        et = e["event_type"]
        event_types[et] = event_types.get(et, 0) + 1

    print(f"\n  Event breakdown:")
    for et, count in sorted(event_types.items(), key=lambda x: -x[1]):
        print(f"    {et:20s}: {count:,}")

    # Store breakdown
    store_counts: Dict[str, int] = {}
    for e in all_events:
        sc = e["store_code"]
        store_counts[sc] = store_counts.get(sc, 0) + 1

    print(f"\n  Store breakdown:")
    for sc, count in sorted(store_counts.items()):
        print(f"    {sc}: {count:,} events")

    print(f"\n{'=' * 60}")
    print("  ✅ Processing complete!")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
