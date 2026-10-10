"""Person detection with Ultralytics YOLO11.

* The model is loaded once per process and reused (``get_detector``).
* Only COCO class 0 (person) is returned.
* Boxes are in source-frame pixels (Ultralytics undoes its own letterbox
  resize), clipped to the frame and validated, then normalized to [0, 1].
* Device: CUDA when available, else CPU (``CV_DEVICE`` overrides).
"""

from __future__ import annotations

import hashlib
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from app.config import settings

PERSON_CLASS_ID = 0
BACKEND_DIR = Path(__file__).resolve().parents[2]


class ModelLoadError(RuntimeError):
    pass


@dataclass
class Detection:
    """Single person detection. ``bbox`` is in pixels (x1, y1, x2, y2)."""

    bbox: Tuple[float, float, float, float]
    confidence: float
    class_id: int = PERSON_CLASS_ID

    @property
    def center(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @property
    def bottom_center(self) -> Tuple[float, float]:
        x1, _, x2, y2 = self.bbox
        return ((x1 + x2) / 2, y2)

    @property
    def area(self) -> float:
        x1, y1, x2, y2 = self.bbox
        return (x2 - x1) * (y2 - y1)


def resolve_model_path(name: str) -> str:
    """Model files are looked up as given, then next to the backend package."""
    candidates = [Path(name), BACKEND_DIR / name, BACKEND_DIR / "models" / name]
    for c in candidates:
        if c.exists():
            return str(c)
    raise ModelLoadError(
        f"Model file '{name}' not found (looked in {', '.join(str(c) for c in candidates)}). "
        "The worker image bundles yolo11n.pt; set YOLO_MODEL to a path that exists."
    )


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def select_device(requested: str = "auto") -> str:
    if requested and requested != "auto":
        return requested
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda:0"
    except ImportError:  # pragma: no cover
        pass
    return "cpu"


def clip_and_validate(
    boxes: np.ndarray, confs: np.ndarray, width: int, height: int, min_size_px: float = 2.0
) -> List[Detection]:
    """Clip pixel boxes to the frame and drop NaN/degenerate boxes."""
    dets: List[Detection] = []
    for (x1, y1, x2, y2), conf in zip(boxes, confs):
        if not np.all(np.isfinite([x1, y1, x2, y2, conf])):
            continue
        x1, x2 = sorted((float(x1), float(x2)))
        y1, y2 = sorted((float(y1), float(y2)))
        x1, x2 = max(0.0, x1), min(float(width), x2)
        y1, y2 = max(0.0, y1), min(float(height), y2)
        if x2 - x1 < min_size_px or y2 - y1 < min_size_px:
            continue
        dets.append(Detection((x1, y1, x2, y2), float(conf)))
    return dets


class PersonDetector:
    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence: Optional[float] = None,
        iou: Optional[float] = None,
        imgsz: Optional[int] = None,
        device: Optional[str] = None,
    ) -> None:
        self.model_name = model_path or settings.yolo_model
        self.confidence = settings.yolo_confidence if confidence is None else confidence
        self.iou = settings.yolo_iou if iou is None else iou
        self.imgsz = imgsz or settings.yolo_imgsz
        self.device = select_device(device or settings.cv_device)
        self.model_path: Optional[str] = None
        self.model_sha256: Optional[str] = None
        self._model = None
        self._lock = threading.Lock()

    def load(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            path = resolve_model_path(self.model_name)
            try:
                from ultralytics import YOLO

                model = YOLO(path)
                # Warm up once so the first real frame is not penalized.
                model.predict(np.zeros((64, 64, 3), dtype=np.uint8), verbose=False, device=self.device)
            except Exception as exc:  # noqa: BLE001
                raise ModelLoadError(f"Failed to load model {path}: {exc}") from exc
            self.model_path = path
            self.model_sha256 = file_sha256(path)
            self._model = model

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def detect(self, frame: np.ndarray, confidence: Optional[float] = None) -> List[Detection]:
        """Detect people in one BGR frame (H, W, 3)."""
        if frame is None or frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("frame must be an HxWx3 BGR image")
        self.load()
        import torch

        conf = self.confidence if confidence is None else confidence
        with torch.inference_mode():
            results = self._model.predict(
                frame,
                conf=conf,
                iou=self.iou,
                imgsz=self.imgsz,
                classes=[PERSON_CLASS_ID],
                device=self.device,
                half=self.device.startswith("cuda"),
                verbose=False,
            )
        h, w = frame.shape[:2]
        result = results[0]
        if result.boxes is None or len(result.boxes) == 0:
            return []
        cls = result.boxes.cls.cpu().numpy().astype(int)
        keep = cls == PERSON_CLASS_ID
        boxes = result.boxes.xyxy.cpu().numpy()[keep]
        confs = result.boxes.conf.cpu().numpy()[keep]
        return clip_and_validate(boxes, confs, w, h)


_detectors: dict = {}
_detectors_lock = threading.Lock()


def get_detector(model_name: Optional[str] = None, imgsz: Optional[int] = None) -> PersonDetector:
    """Process-wide cache: one loaded model per (name, imgsz)."""
    key = (model_name or settings.yolo_model, imgsz or settings.yolo_imgsz, os.getpid())
    with _detectors_lock:
        det = _detectors.get(key)
        if det is None:
            det = PersonDetector(model_path=key[0], imgsz=key[1])
            _detectors[key] = det
        return det
