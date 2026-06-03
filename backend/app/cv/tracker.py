"""
ByteTrack Multi-Object Tracker.

Provides persistent customer IDs across frames for
journey reconstruction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.cv.detector import Detection


@dataclass
class Track:
    """A tracked object (customer)."""
    track_id: int
    bbox: Tuple[float, float, float, float]
    confidence: float
    age: int = 0  # frames since track was created
    hits: int = 0  # total successful detections
    time_since_update: int = 0
    state: str = "active"  # active, lost, removed

    @property
    def center(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def bottom_center(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, y2)


class ByteTracker:
    """
    Simplified ByteTrack implementation for person tracking.
    Uses IoU-based association with two-stage matching.
    """

    def __init__(
        self,
        track_thresh: float = 0.5,
        match_thresh: float = 0.8,
        track_buffer: int = 30,
    ) -> None:
        self.track_thresh = track_thresh
        self.match_thresh = match_thresh
        self.track_buffer = track_buffer
        self._next_id = 1
        self.tracks: List[Track] = []
        self.lost_tracks: List[Track] = []
        self.removed_tracks: List[Track] = []
        self.frame_count = 0

    def update(self, detections: List[Detection]) -> List[Track]:
        """
        Update tracker with new detections.

        Args:
            detections: List of Detection objects from the detector

        Returns:
            List of active Track objects with assigned IDs
        """
        self.frame_count += 1

        # Split detections into high and low confidence
        high_dets = [d for d in detections if d.confidence >= self.track_thresh]
        low_dets = [d for d in detections if d.confidence < self.track_thresh]

        # Predict track positions (simple: use last known position)
        for track in self.tracks:
            track.time_since_update += 1

        # Stage 1: Match high-confidence detections with tracks
        matched, unmatched_tracks, unmatched_dets = self._match(
            self.tracks, high_dets
        )

        # Update matched tracks
        for track_idx, det_idx in matched:
            track = self.tracks[track_idx]
            det = high_dets[det_idx]
            track.bbox = det.bbox
            track.confidence = det.confidence
            track.hits += 1
            track.time_since_update = 0
            track.age += 1

        # Stage 2: Match remaining tracks with low-confidence detections
        remaining_tracks = [self.tracks[i] for i in unmatched_tracks]
        matched2, still_unmatched, _ = self._match(
            remaining_tracks, low_dets
        )
        for track_idx, det_idx in matched2:
            track = remaining_tracks[track_idx]
            det = low_dets[det_idx]
            track.bbox = det.bbox
            track.confidence = det.confidence
            track.hits += 1
            track.time_since_update = 0
            track.age += 1

        # Handle unmatched tracks → lost
        for idx in still_unmatched:
            track = remaining_tracks[idx]
            if track.time_since_update > self.track_buffer:
                track.state = "removed"
                self.removed_tracks.append(track)
            else:
                track.state = "lost"
                self.lost_tracks.append(track)

        # Create new tracks from unmatched high-confidence detections
        for det_idx in unmatched_dets:
            det = high_dets[det_idx]
            new_track = Track(
                track_id=self._next_id,
                bbox=det.bbox,
                confidence=det.confidence,
                hits=1,
            )
            self._next_id += 1
            self.tracks.append(new_track)

        # Clean up
        self.tracks = [t for t in self.tracks if t.state == "active"]

        # Re-activate lost tracks if matched
        new_lost = []
        for lt in self.lost_tracks:
            if lt.time_since_update > self.track_buffer:
                lt.state = "removed"
                self.removed_tracks.append(lt)
            else:
                new_lost.append(lt)
        self.lost_tracks = new_lost

        return [t for t in self.tracks if t.hits >= 2]

    def _match(
        self,
        tracks: List[Track],
        detections: List[Detection],
    ) -> Tuple[List[Tuple[int, int]], List[int], List[int]]:
        """
        Match tracks to detections using IoU.
        Returns: (matched_pairs, unmatched_track_indices, unmatched_det_indices)
        """
        if not tracks or not detections:
            return (
                [],
                list(range(len(tracks))),
                list(range(len(detections))),
            )

        # Compute IoU matrix
        iou_matrix = np.zeros((len(tracks), len(detections)))
        for i, track in enumerate(tracks):
            for j, det in enumerate(detections):
                iou_matrix[i, j] = self._iou(track.bbox, det.bbox)

        # Greedy matching
        matched = []
        used_tracks = set()
        used_dets = set()

        while True:
            if iou_matrix.size == 0:
                break
            max_val = iou_matrix.max()
            if max_val < (1 - self.match_thresh):
                break
            idx = np.unravel_index(iou_matrix.argmax(), iou_matrix.shape)
            i, j = int(idx[0]), int(idx[1])
            if i in used_tracks or j in used_dets:
                iou_matrix[i, j] = 0
                continue
            matched.append((i, j))
            used_tracks.add(i)
            used_dets.add(j)
            iou_matrix[i, :] = 0
            iou_matrix[:, j] = 0

        unmatched_tracks = [i for i in range(len(tracks)) if i not in used_tracks]
        unmatched_dets = [j for j in range(len(detections)) if j not in used_dets]

        return matched, unmatched_tracks, unmatched_dets

    @staticmethod
    def _iou(
        box1: Tuple[float, float, float, float],
        box2: Tuple[float, float, float, float],
    ) -> float:
        """Compute IoU between two bounding boxes."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        inter = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - inter

        return inter / union if union > 0 else 0
