"""Online track stitching: join tracker fragments that belong to one person.

ByteTrack matches detections to tracks by box overlap (IoU). At the low
analysis rates the worker uses (5 fps), a person who walks fast, is hidden
for a moment behind a shelf or another shopper, or is missed for a few frames
can come back with no overlap with their predicted box. ByteTrack then starts
a new id, and the visitor is counted twice (and can produce a second ENTRY).

The stitcher sits between the tracker and the event engine. When a new
tracker id appears, it looks for a *visitor* whose track was lost a moment
ago and whose motion predicts the new position, and reuses that visitor's id.
The event engine keeps per-track state for ``track_end_grace_s`` after a
track goes missing, so a stitched visitor continues the same zone visit,
dwell clock and line-crossing state instead of starting a new one.

Guards against joining two different people:

* the gap must be short (``max_gap_s``, below the engine's grace time);
* the new box must be near the constant-velocity prediction, measured in
  box heights so it works at any distance from the camera;
* box sizes must be similar;
* a track that was lost at the frame edge left the view and is never joined;
* if two lost visitors fit almost equally well, nothing is joined.

Everything is in normalized coordinates and pure Python, so it is unit
tested with synthetic tracks (tests/test_cv_logic.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

Box = Tuple[float, float, float, float]  # normalized x1, y1, x2, y2
Observation = Tuple[int, Box, float]


@dataclass
class StitchConfig:
    enabled: bool = True
    # Longest gap that is joined. Must stay below EngineConfig.track_end_grace_s
    # so the engine still holds the visitor's state when the fragment returns.
    max_gap_s: float = 2.0
    # Distance from the predicted bottom-centre, in heights of the lost box.
    max_distance_box_heights: float = 0.75
    # Allowed growth/shrink of box height between the fragments.
    max_height_ratio: float = 1.5
    # Boxes whose last position touched this margin left the view.
    edge_margin: float = 0.02
    # Second-best candidate must be this much worse, or the join is skipped.
    ambiguity_ratio: float = 1.5
    # Cap on the velocity used for prediction (frame heights per second).
    max_speed: float = 0.6

    def as_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class _Visitor:
    visitor_id: int
    raw_id: int
    last_t: float
    last_box: Box
    velocity: Tuple[float, float] = (0.0, 0.0)  # of the bottom-centre, per second
    history: List[Tuple[float, Tuple[float, float]]] = field(default_factory=list)


def _ref(box: Box) -> Tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, box[3])


def _height(box: Box) -> float:
    return max(1e-6, box[3] - box[1])


def _at_edge(box: Box, margin: float) -> bool:
    x1, y1, x2, y2 = box
    return x1 <= margin or y1 <= margin or x2 >= 1.0 - margin or y2 >= 1.0 - margin


class TrackStitcher:
    def __init__(self, config: Optional[StitchConfig] = None) -> None:
        self.cfg = config or StitchConfig()
        self._visitors: Dict[int, _Visitor] = {}
        self._raw_to_visitor: Dict[int, int] = {}
        self._next_id = 1
        self.stitches = 0
        self.raw_ids_seen: set = set()

    def _new_visitor(self, raw_id: int, t: float, box: Box) -> int:
        vid = self._next_id
        self._next_id += 1
        self._visitors[vid] = _Visitor(vid, raw_id, t, box)
        self._raw_to_visitor[raw_id] = vid
        return vid

    def _predict(self, v: _Visitor, t: float) -> Tuple[float, float]:
        dt = t - v.last_t
        x, y = _ref(v.last_box)
        vx, vy = v.velocity
        speed = (vx * vx + vy * vy) ** 0.5
        if speed > self.cfg.max_speed:
            vx, vy = vx * self.cfg.max_speed / speed, vy * self.cfg.max_speed / speed
        return (x + vx * dt, y + vy * dt)

    def _match(self, t: float, box: Box, busy: set) -> Optional[int]:
        cfg = self.cfg
        scored = []
        nx, ny = _ref(box)
        for v in self._visitors.values():
            if v.visitor_id in busy:
                continue
            gap = t - v.last_t
            if gap <= 0 or gap > cfg.max_gap_s:
                continue
            if _at_edge(v.last_box, cfg.edge_margin):
                continue
            h_old, h_new = _height(v.last_box), _height(box)
            if max(h_old, h_new) / min(h_old, h_new) > cfg.max_height_ratio:
                continue
            px, py = self._predict(v, t)
            # Distance in box heights; the allowed radius grows a little with
            # the gap because the prediction gets less certain.
            dist = ((nx - px) ** 2 + (ny - py) ** 2) ** 0.5 / h_old
            limit = cfg.max_distance_box_heights * (1.0 + 0.25 * gap)
            if dist <= limit:
                scored.append((dist, v.visitor_id))
        if not scored:
            return None
        scored.sort()
        if len(scored) > 1 and scored[1][0] < scored[0][0] * cfg.ambiguity_ratio + 1e-6:
            return None
        return scored[0][1]

    def update(self, t: float, observations: Sequence[Observation]) -> List[Observation]:
        """Map tracker ids to visitor ids for one analysed frame."""
        if not self.cfg.enabled:
            for raw, _, _ in observations:
                self.raw_ids_seen.add(raw)
            return list(observations)

        out: List[Observation] = []
        busy = set()
        # Known raw ids first, so a returning fragment keeps priority over a
        # brand-new id that might otherwise claim its visitor.
        known = [o for o in observations if o[0] in self._raw_to_visitor]
        new = [o for o in observations if o[0] not in self._raw_to_visitor]
        for raw, box, conf in known:
            vid = self._raw_to_visitor[raw]
            v = self._visitors[vid]
            if v.raw_id != raw:
                # Its visitor was taken over by a stitched fragment that is
                # also still alive: these are two people after all.
                if v.last_t >= t or vid in busy:
                    vid = self._new_visitor(raw, t, box)
                    v = self._visitors[vid]
                else:
                    v.raw_id = raw
            busy.add(vid)
            out.append((vid, box, conf))
        for raw, box, conf in new:
            self.raw_ids_seen.add(raw)
            vid = self._match(t, box, busy)
            if vid is None:
                vid = self._new_visitor(raw, t, box)
            else:
                self.stitches += 1
                self._visitors[vid].raw_id = raw
                self._raw_to_visitor[raw] = vid
            busy.add(vid)
            out.append((vid, box, conf))

        for vid, box, _ in out:
            self._observe(self._visitors[vid], t, box)
        for raw, _, _ in known:
            self.raw_ids_seen.add(raw)
        self._prune(t)
        return out

    def _observe(self, v: _Visitor, t: float, box: Box) -> None:
        v.history.append((t, _ref(box)))
        if len(v.history) > 6:
            v.history.pop(0)
        # Velocity over the recent window is steadier than frame-to-frame.
        t0, (x0, y0) = v.history[0]
        if t > t0:
            x1, y1 = _ref(box)
            v.velocity = ((x1 - x0) / (t - t0), (y1 - y0) / (t - t0))
        v.last_t = t
        v.last_box = box

    def _prune(self, t: float) -> None:
        # Forget long-gone visitors so the candidate search stays small. The
        # horizon is longer than both max_gap_s and ByteTrack's lost buffer.
        horizon = max(self.cfg.max_gap_s * 2, 5.0)
        for vid in [vid for vid, v in self._visitors.items() if t - v.last_t > horizon]:
            del self._visitors[vid]
        for raw in [r for r, vid in self._raw_to_visitor.items() if vid not in self._visitors]:
            del self._raw_to_visitor[raw]

    @property
    def visitor_count(self) -> int:
        """Distinct people (visitor ids) issued so far."""
        return self._next_id - 1
