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
    # 1 = a track is reported from its first detection. With 2, a single
    # missed detection right after a person appears postpones the track, and
    # people who cross the entry line within their first few frames were not
    # counted (15% simulated detection misses: 10/65 entries lost at 2,
    # 1/65 at 1; see docs/CV_VALIDATION.md). One-frame false positives are
    # still dropped by the event engine's min_track_samples.
    minimum_consecutive_frames: int = 1

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
        """Track one frame. Returns the *detected* box of every track that was
        matched in this frame.

        supervision's ``update_with_detections`` maps tracks back to
        detections by IoU > 0.5 between the detection and the Kalman-filtered
        track box. When a person changes speed or size quickly (walking up to
        the camera, stopping after a fast approach) the filtered box lags and
        the IoU drops below 0.5: the tracker keeps the identity internally but
        reports nothing, for seconds at a time. On the one-by-one clip this hid
        people for up to 4 s right where they crossed the entry line. Here each
        track is joined to the exact detection ByteTrack associated with it:
        ByteTrack copies that detection's score onto the track, so the score
        identifies it (IoU only breaks ties between equal scores).
        """
        if detections:
            tensors = np.array([[*d.bbox, d.confidence] for d in detections], dtype=np.float32)
        else:
            tensors = np.zeros((0, 5), dtype=np.float32)
        tracks = self._tracker.update_with_tensors(tensors=tensors)
        frame_id = self._tracker.frame_id
        out: List[TrackedBox] = []
        used: set = set()
        for track in tracks:
            if track.frame_id != frame_id or track.external_track_id < 0:
                continue
            idx = self._detection_for(track, tensors, used)
            if idx is None:
                continue
            used.add(idx)
            tid = int(track.external_track_id)
            self.ids_seen.add(tid)
            box = tuple(float(v) for v in tensors[idx, :4])
            out.append(TrackedBox(tid, box, float(tensors[idx, 4])))
        return out

    @staticmethod
    def _detection_for(track, tensors: np.ndarray, used: set):
        candidates = [i for i in np.flatnonzero(tensors[:, 4] == np.float32(track.score)) if i not in used]
        if not candidates:
            return None
        if len(candidates) == 1:
            return int(candidates[0])
        tb = np.asarray(track.tlbr, dtype=np.float32)

        def iou(i: int) -> float:
            b = tensors[i, :4]
            ix = max(0.0, min(b[2], tb[2]) - max(b[0], tb[0]))
            iy = max(0.0, min(b[3], tb[3]) - max(b[1], tb[1]))
            inter = ix * iy
            union = (b[2] - b[0]) * (b[3] - b[1]) + (tb[2] - tb[0]) * (tb[3] - tb[1]) - inter
            return inter / union if union > 0 else 0.0

        return int(max(candidates, key=iou))

    def reset(self) -> None:
        self._tracker.reset()
        self.ids_seen.clear()
