"""Multi-object tracking with ByteTrack (supervision implementation).

ByteTrack associates high-confidence detections first, then uses
low-confidence detections (>= 0.1) to keep existing tracks alive through
partial occlusion, with a Kalman motion model. Lost tracks are kept for
``lost_track_seconds`` and can be re-acquired with the same id.

A new ``PersonTracker`` is created for every job, so ids never leak across
videos, cameras, or stores.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np

from app.cv.detector import Detection


@dataclass
class TrackerConfig:
    # Detections above this score can be matched in the first association
    # stage; new tracks need score > activation + 0.1 (ByteTrack rule).
    track_activation_threshold: float = 0.3
    lost_track_seconds: float = 3.0
    minimum_matching_threshold: float = 0.8
    minimum_consecutive_frames: int = 2

    def as_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class TrackedBox:
    track_id: int
    bbox: Tuple[float, float, float, float]  # pixels
    confidence: float


class PersonTracker:
    def __init__(self, frame_rate: float, config: TrackerConfig | None = None) -> None:
        import supervision as sv

        self.config = config or TrackerConfig()
        self.frame_rate = max(1.0, float(frame_rate))
        # supervision scales the buffer by frame_rate / 30.
        buffer_frames = int(round(self.config.lost_track_seconds * 30))
        self._tracker = sv.ByteTrack(
            track_activation_threshold=self.config.track_activation_threshold,
            lost_track_buffer=buffer_frames,
            minimum_matching_threshold=self.config.minimum_matching_threshold,
            frame_rate=int(round(self.frame_rate)),
            minimum_consecutive_frames=self.config.minimum_consecutive_frames,
        )
        self._sv = sv
        self.ids_seen: set = set()

    def update(self, detections: Sequence[Detection]) -> List[TrackedBox]:
        sv = self._sv
        if detections:
            xyxy = np.array([d.bbox for d in detections], dtype=np.float32)
            conf = np.array([d.confidence for d in detections], dtype=np.float32)
            dets = sv.Detections(xyxy=xyxy, confidence=conf, class_id=np.zeros(len(detections), dtype=int))
        else:
            dets = sv.Detections.empty()
        tracked = self._tracker.update_with_detections(dets)
        out: List[TrackedBox] = []
        if tracked.tracker_id is None:
            return out
        for box, conf, tid in zip(tracked.xyxy, tracked.confidence, tracked.tracker_id):
            tid = int(tid)
            self.ids_seen.add(tid)
            out.append(TrackedBox(tid, tuple(float(v) for v in box), float(conf)))
        return out

    def reset(self) -> None:
        self._tracker.reset()
        self.ids_seen.clear()
