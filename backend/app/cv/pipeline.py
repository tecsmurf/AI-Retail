"""Video processing pipeline — orchestrates detection, tracking, zone mapping, and event generation."""

from __future__ import annotations
import asyncio
from datetime import datetime
from typing import AsyncGenerator, Dict, List, Optional
import numpy as np
from app.cv.detector import PersonDetector, Detection
from app.cv.tracker import ByteTracker, Track
from app.cv.zone_mapper import ZoneMapper, ZonePolygon


class VideoProcessor:
    """End-to-end video processing pipeline."""

    def __init__(self, store_id: str, camera_id: str, zone_mapper: ZoneMapper = None):
        self.store_id = store_id
        self.camera_id = camera_id
        self.detector = PersonDetector()
        self.tracker = ByteTracker()
        self.zone_mapper = zone_mapper or ZoneMapper()
        self.customer_zones: Dict[int, Optional[str]] = {}
        self.customer_entry_time: Dict[int, datetime] = {}
        self.events: List[Dict] = []

    def process_frame(self, frame: np.ndarray, timestamp: datetime = None) -> List[Dict]:
        """Process a single frame and generate events."""
        if timestamp is None:
            timestamp = datetime.utcnow()

        detections = self.detector.detect(frame)
        tracks = self.tracker.update(detections)
        frame_events = []

        for track in tracks:
            x, y = track.bottom_center
            current_zone = self.zone_mapper.get_zone(x, y)
            prev_zone = self.customer_zones.get(track.track_id)
            cust_id = f"CUST_{track.track_id:04d}"

            # New customer
            if track.track_id not in self.customer_entry_time:
                self.customer_entry_time[track.track_id] = timestamp
                frame_events.append({
                    "event_type": "ENTRY",
                    "customer_id": cust_id,
                    "store_code": self.store_id,
                    "camera_id": self.camera_id,
                    "timestamp": timestamp.isoformat(),
                    "bbox": track.bbox,
                    "confidence": track.confidence,
                })

            # Zone transition
            current_name = current_zone.name if current_zone else None
            if current_name != prev_zone:
                if prev_zone:
                    frame_events.append({
                        "event_type": "ZONE_EXIT",
                        "customer_id": cust_id,
                        "store_code": self.store_id,
                        "zone_name": prev_zone,
                        "timestamp": timestamp.isoformat(),
                    })
                if current_name:
                    frame_events.append({
                        "event_type": "ZONE_ENTER",
                        "customer_id": cust_id,
                        "store_code": self.store_id,
                        "zone_name": current_name,
                        "zone_type": current_zone.zone_type if current_zone else None,
                        "timestamp": timestamp.isoformat(),
                    })
                self.customer_zones[track.track_id] = current_name

        self.events.extend(frame_events)
        return frame_events

    def process_video(self, video_path: str, sample_rate: int = 5):
        """Process an entire video file."""
        try:
            import cv2
        except ImportError:
            print("OpenCV not available")
            return self.events

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        frame_count = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if frame_count % sample_rate == 0:
                ts = datetime.utcnow()
                self.process_frame(frame, ts)
            frame_count += 1

        cap.release()
        return self.events
