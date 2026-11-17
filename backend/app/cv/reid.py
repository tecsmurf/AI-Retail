"""Anonymous appearance descriptors for joining track fragments of one shopper.

A descriptor is a short vector computed from the whole-body crop of a tracked
person: mostly what they are wearing and their build, as seen from a CCTV
camera. It is used only to decide "is this fragment the same person as that
one, a moment ago, in this store". There is no face model, nothing is matched
against a list of known people, and descriptors are kept in memory for the
job only (the linker turns them into visit numbers and they are dropped).
See docs/DECISIONS.md D19 and docs/REID.md.

Two encoders:

* ``LmbnEncoder`` (default): LightMBN-n, a small person re-identification
  network (OSNet backbone, 3,584-d output), run with TorchScript on CPU. The
  weights file ``lmbn_n_duke.torchscript`` is committed next to the YOLO
  weights. ~30 ms per crop on 4 vCPU.
* ``ColourEncoder``: hand-made clothing-colour histograms (upper and lower
  body, HSV). No model and almost free, but much weaker. Used when the
  network cannot be loaded, and as a baseline in evaluations.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import List, Optional, Sequence, Tuple

import numpy as np

log = logging.getLogger(__name__)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_REID_MODEL = "lmbn_n_duke.torchscript"

PixelBox = Tuple[float, float, float, float]


def _l2(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-12)


def _crop(frame: np.ndarray, box: PixelBox) -> Optional[np.ndarray]:
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = box
    x1, y1 = max(0, int(round(x1))), max(0, int(round(y1)))
    x2, y2 = min(w, int(round(x2))), min(h, int(round(y2)))
    if x2 - x1 < 4 or y2 - y1 < 8:
        return None
    return frame[y1:y2, x1:x2]


class AppearanceEncoder:
    name = "base"
    dim = 0

    def load(self) -> None:  # pragma: no cover - trivial
        pass

    def embed(self, frame: np.ndarray, boxes: Sequence[PixelBox]) -> np.ndarray:
        """Return one L2-normalised row per box (zeros for unusable crops)."""
        raise NotImplementedError


class ColourEncoder(AppearanceEncoder):
    """Upper/lower-body HSV histograms (hue x saturation, plus value)."""

    name = "colour-hsv"
    H_BINS, S_BINS, V_BINS = 12, 4, 6
    dim = 2 * (12 * 4 + 6)

    def embed(self, frame: np.ndarray, boxes: Sequence[PixelBox]) -> np.ndarray:
        import cv2

        out = np.zeros((len(boxes), self.dim), dtype=np.float32)
        for i, box in enumerate(boxes):
            crop = _crop(frame, box)
            if crop is None:
                continue
            hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
            ch, cw = hsv.shape[:2]
            # Trim the borders (background) and the head; split torso/legs.
            x0, x1 = int(cw * 0.2), max(int(cw * 0.8), int(cw * 0.2) + 1)
            parts = (hsv[int(ch * 0.15):int(ch * 0.5), x0:x1], hsv[int(ch * 0.5):int(ch * 0.95), x0:x1])
            feats = []
            for part in parts:
                if part.size == 0:
                    feats.append(np.zeros(self.dim // 2, dtype=np.float32))
                    continue
                hs = cv2.calcHist([part], [0, 1], None, [self.H_BINS, self.S_BINS], [0, 180, 0, 256]).ravel()
                v = cv2.calcHist([part], [2], None, [self.V_BINS], [0, 256]).ravel()
                f = np.concatenate([hs / max(hs.sum(), 1.0), 0.5 * v / max(v.sum(), 1.0)])
                feats.append(np.sqrt(f).astype(np.float32))  # Hellinger
            out[i] = np.concatenate(feats)
        return _l2(out)


class LmbnEncoder(AppearanceEncoder):
    name = "lmbn_n"
    dim = 3584
    INPUT_HW = (384, 128)
    MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def __init__(self, model_path: Optional[str] = None, batch_size: int = 16) -> None:
        self.model_path = model_path or os.environ.get("REID_MODEL") or DEFAULT_REID_MODEL
        if not os.path.isabs(self.model_path):
            self.model_path = os.path.join(BACKEND_DIR, self.model_path)
        self.batch_size = batch_size
        self._model = None
        self._lock = threading.Lock()

    def load(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            import torch

            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"re-identification model not found: {self.model_path}")
            model = torch.jit.load(self.model_path, map_location="cpu")
            model.eval()
            self._model = model

    def _prep(self, crop: np.ndarray) -> np.ndarray:
        import cv2

        h, w = self.INPUT_HW
        img = cv2.resize(crop, (w, h), interpolation=cv2.INTER_LINEAR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        img = (img - self.MEAN) / self.STD
        return img.transpose(2, 0, 1)

    def embed(self, frame: np.ndarray, boxes: Sequence[PixelBox]) -> np.ndarray:
        import torch

        self.load()
        out = np.zeros((len(boxes), self.dim), dtype=np.float32)
        idx: List[int] = []
        batch: List[np.ndarray] = []
        for i, box in enumerate(boxes):
            crop = _crop(frame, box)
            if crop is not None:
                idx.append(i)
                batch.append(self._prep(crop))
        for s in range(0, len(batch), self.batch_size):
            x = torch.from_numpy(np.stack(batch[s:s + self.batch_size]))
            with torch.inference_mode():
                y = self._model(x).float().numpy()
            for j, row in enumerate(y):
                out[idx[s + j]] = row
        return _l2(out)


_encoder: Optional[AppearanceEncoder] = None
_encoder_lock = threading.Lock()


def get_encoder(kind: Optional[str] = None) -> AppearanceEncoder:
    """Shared encoder for the process (``REID_ENCODER`` = lmbn | colour)."""
    global _encoder
    kind = (kind or os.environ.get("REID_ENCODER") or "lmbn").lower()
    with _encoder_lock:
        if _encoder is not None and (_encoder.name.startswith(kind[:4])):
            return _encoder
        if kind.startswith("col"):
            _encoder = ColourEncoder()
        else:
            enc = LmbnEncoder()
            try:
                enc.load()
                _encoder = enc
            except Exception as exc:  # noqa: BLE001 - fall back, never fail the job
                log.warning("re-identification model unavailable (%s); using colour histograms", exc)
                _encoder = ColourEncoder()
        return _encoder
