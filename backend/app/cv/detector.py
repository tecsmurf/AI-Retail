"""
Person Detector — YOLO11 / RT-DETR based person detection.

Provides real-time person detection with bounding boxes,
confidence scores, and track-ready outputs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from app.config import settings


@dataclass
class Detection:
    """Single person detection result."""
    bbox: Tuple[float, float, float, float]  # x1, y1, x2, y2
    confidence: float
    class_id: int = 0  # 0 = person in COCO
    track_id: Optional[int] = None

    @property
    def center(self) -> Tuple[float, float]:
        """Center point of bounding box."""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def bottom_center(self) -> Tuple[float, float]:
        """Bottom-center point (foot position for zone mapping)."""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, y2)

    @property
    def area(self) -> float:
        x1, y1, x2, y2 = self.bbox
        return (x2 - x1) * (y2 - y1)


class PersonDetector:
    """YOLO11-based person detection engine."""

    def __init__(
        self,
        model_path: str = None,
        confidence: float = None,
        device: str = "auto",
    ) -> None:
        self.model_path = model_path or settings.yolo_model
        self.confidence = confidence or settings.yolo_confidence
        self.device = device
        self._model = None

    def _load_model(self):
        """Lazy-load the YOLO model."""
        if self._model is None:
            try:
                from ultralytics import YOLO
                self._model = YOLO(self.model_path)
                print(f"✓ YOLO model loaded: {self.model_path}")
            except ImportError:
                print("⚠ ultralytics not installed, using mock detector")
                self._model = "mock"

    def detect(self, frame: np.ndarray) -> List[Detection]:
        """
        Detect persons in a single frame.

        Args:
            frame: BGR image as numpy array (H, W, 3)

        Returns:
            List of Detection objects for persons only
        """
        self._load_model()

        if self._model == "mock":
            return []

        results = self._model(
            frame,
            conf=self.confidence,
            classes=[0],  # person class only
            verbose=False,
        )

        detections = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0])
                det = Detection(
                    bbox=(float(x1), float(y1), float(x2), float(y2)),
                    confidence=conf,
                    class_id=0,
                )
                detections.append(det)

        return detections

    def detect_batch(
        self, frames: List[np.ndarray]
    ) -> List[List[Detection]]:
        """Detect persons in multiple frames."""
        return [self.detect(frame) for frame in frames]
