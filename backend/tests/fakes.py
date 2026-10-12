"""Synthetic video and a deterministic stand-in detector for pipeline tests.

The fake detector "sees" bright rectangles, so the decode -> track -> event ->
persist path runs end to end without downloading or running a model. Real
model behaviour is covered separately (tests marked ``cv``) and in
docs/CV_VALIDATION.md.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

import numpy as np

from app.cv.detector import Detection

W, H = 640, 360


def write_video(path: str, seconds: float, fps: float, position: Callable[[float], Optional[Tuple[int, int]]]) -> None:
    """position(t) -> bottom-centre pixel of a 40x100 white box, or None (no person)."""
    import cv2

    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    assert out.isOpened()
    for i in range(int(seconds * fps)):
        frame = np.full((H, W, 3), 30, dtype=np.uint8)
        p = position(i / fps)
        if p is not None:
            x, y = p
            cv2.rectangle(frame, (x - 20, y - 100), (x + 20, y), (255, 255, 255), -1)
        out.write(frame)
    out.release()


class FakeDetector:
    device = "cpu"
    model_name = "fake"
    model_path = "fake-detector"
    model_sha256 = "0" * 64

    def load(self) -> None:
        pass

    def detect(self, frame: np.ndarray, confidence: Optional[float] = None) -> List[Detection]:
        mask = frame.min(axis=2) > 200
        if not mask.any():
            return []
        ys, xs = np.nonzero(mask)
        return [Detection((float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())), 0.9)]


def queue_then_counter(t: float):
    """Waits in the queue (left half) for 6 s, walks to the counter (right half)."""
    if t < 6:
        return (160, 300)
    if t < 11:  # ~0.3 box widths per analysed frame at 5 fps
        return (int(160 + 320 * (t - 6) / 5), 300)
    return (480, 300)
