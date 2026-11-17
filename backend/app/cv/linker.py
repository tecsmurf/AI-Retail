"""Join track fragments into shoppers (anonymous visits).

The tracker and stitcher keep a person's id while they stay in view or vanish
for up to 2 s. In a busy aisle people pass behind each other for longer than
that, and each time they come back with a new id, so one shopper is counted
two or three times. A shopper who walks from one camera to the next is a new
id on every camera.

The linker runs after a video (or a set of videos from one store) has been
tracked. Each fragment carries a few appearance descriptors (app/cv/reid.py).
Fragments are joined into chains, one chain per shopper, with these rules:

* a person cannot be in two places at once: fragments that overlap in time
  are never joined (on one camera, or across cameras unless the cameras are
  marked as overlapping);
* the gap must be plausible: up to ``max_gap_s`` on the same camera, or within
  the camera pair's transit window (``transit``) across cameras;
* the appearance distance must be under the threshold for that case;
* if a fragment has two candidates that fit almost equally well, nothing is
  joined (better to count one shopper twice than to merge two people).

Joining is greedy, cheapest pair first, each fragment having at most one
successor and one predecessor, so every chain is a time-ordered path. Same
camera links are made first; chains are then linked across cameras.

Pure Python + NumPy, unit-tested with synthetic descriptors
(tests/test_linker.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Hashable, List, Optional, Sequence, Tuple

import numpy as np

Box = Tuple[float, float, float, float]


@dataclass
class Fragment:
    key: Hashable
    camera: str
    t_start: float  # seconds on a clock shared by all fragments being linked
    t_end: float
    descriptors: List[np.ndarray] = field(default_factory=list)
    first_box: Optional[Box] = None
    last_box: Optional[Box] = None

    def prototype(self) -> Optional[np.ndarray]:
        if not self.descriptors:
            return None
        m = np.mean(np.stack(self.descriptors), axis=0)
        n = float(np.linalg.norm(m))
        return m / n if n > 0 else None


@dataclass
class LinkConfig:
    enabled: bool = True
    # Same camera: longest gap between the end of one fragment and the start
    # of the next that can still be the same shopper.
    max_gap_s: float = 90.0
    # Cosine distance between mean descriptors (0 = identical, 1 = unrelated).
    # Defaults are for the LightMBN encoder; see docs/REID.md for how they
    # were chosen and the colour fallback's values.
    max_distance: float = 0.40
    cross_camera_max_distance: float = 0.40
    # Each second of gap adds this to the distance, so a near gap wins a tie.
    gap_penalty_per_s: float = 0.0005
    # A link is skipped if the runner-up for either end is within this margin.
    ambiguity_margin: float = 0.02
    # Fragments with fewer descriptors than this are never joined.
    min_descriptors: int = 1
    # Default transit window between two different cameras (seconds).
    cross_camera_min_gap_s: float = 0.0
    cross_camera_max_gap_s: float = 120.0
    # Overlap tolerated between consecutive fragments (tracker jitter).
    overlap_tolerance_s: float = 0.3
    # Self-calibration. Fragments seen at the same time for at least
    # ``negative_min_overlap_s`` are certainly different people; how close
    # their descriptors are shows how well the encoder separates people on
    # this footage. The threshold is lowered to ``adaptive_factor`` x the
    # 5th percentile of those distances (dark or grainy video makes everyone
    # look alike, and then almost nothing is joined).
    adaptive: bool = True
    adaptive_factor: float = 0.9
    negative_min_overlap_s: float = 1.0
    adaptive_min_pairs: int = 8

    def as_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class LinkResult:
    shopper_of: Dict[Hashable, int]  # fragment key -> shopper number (1..N)
    shoppers: int
    same_camera_links: int
    cross_camera_links: int
    skipped_ambiguous: int
    # Distance thresholds actually used (after self-calibration).
    thresholds: Dict[str, float] = field(default_factory=dict)


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(1.0 - np.clip(np.dot(a, b), -1.0, 1.0))


@dataclass
class _Chain:
    members: List[Fragment]
    proto: Optional[np.ndarray]

    @property
    def t_start(self) -> float:
        return self.members[0].t_start

    @property
    def t_end(self) -> float:
        return self.members[-1].t_end

    @property
    def first_camera(self) -> str:
        return self.members[0].camera

    @property
    def last_camera(self) -> str:
        return self.members[-1].camera

    def n_desc(self) -> int:
        return sum(len(m.descriptors) for m in self.members)


def _merge_proto(chains: Sequence[_Chain]) -> Optional[np.ndarray]:
    descs = [d for c in chains for m in c.members for d in m.descriptors]
    if not descs:
        return None
    m = np.mean(np.stack(descs), axis=0)
    n = float(np.linalg.norm(m))
    return m / n if n > 0 else None


def _calibrate(frs: Sequence[Fragment], cfg: LinkConfig) -> Dict[str, float]:
    """Per-camera and cross-camera distance limits (see LinkConfig.adaptive)."""
    limits = {"*": cfg.max_distance, "cross": cfg.cross_camera_max_distance}
    if not cfg.adaptive:
        return limits
    protos = [(f, f.prototype()) for f in frs]
    protos = [(f, p) for f, p in protos if p is not None]
    per_cam: Dict[str, List[float]] = {}
    every: List[float] = []
    for i, (a, pa) in enumerate(protos):
        for b, pb in protos[i + 1:]:
            if min(a.t_end, b.t_end) - max(a.t_start, b.t_start) < cfg.negative_min_overlap_s:
                continue
            d = cosine_distance(pa, pb)
            every.append(d)
            if a.camera == b.camera:
                per_cam.setdefault(a.camera, []).append(d)

    def cap(base: float, dists: List[float]) -> Optional[float]:
        if len(dists) < cfg.adaptive_min_pairs:
            return None
        return min(base, cfg.adaptive_factor * float(np.quantile(dists, 0.05)))

    overall = cap(cfg.max_distance, every)
    if overall is not None:
        limits["*"] = overall
    for cam, dists in per_cam.items():
        limits[cam] = cap(cfg.max_distance, dists) or limits["*"]
    cross = cap(cfg.cross_camera_max_distance, every)
    if cross is not None:
        limits["cross"] = cross
    return limits


def _link_pass(
    chains: List[_Chain],
    cfg: LinkConfig,
    cross: bool,
    transit: Dict[Tuple[str, str], Tuple[float, float]],
    limits: Dict[str, float],
) -> Tuple[List[_Chain], int, int]:
    """One greedy pass. ``cross`` False: same-camera pairs only."""
    cands: List[Tuple[float, int, int]] = []
    for i, a in enumerate(chains):
        if a.proto is None or a.n_desc() < cfg.min_descriptors:
            continue
        for j, b in enumerate(chains):
            if i == j or b.proto is None or b.n_desc() < cfg.min_descriptors:
                continue
            gap = b.t_start - a.t_end
            if gap < -cfg.overlap_tolerance_s:
                continue
            same = a.last_camera == b.first_camera
            if same == cross:
                continue
            if same:
                if gap > cfg.max_gap_s:
                    continue
                limit = limits.get(a.last_camera, limits["*"])
            else:
                lo, hi = transit.get((a.last_camera, b.first_camera),
                                     (cfg.cross_camera_min_gap_s, cfg.cross_camera_max_gap_s))
                if gap < lo - cfg.overlap_tolerance_s or gap > hi:
                    continue
                limit = limits["cross"]
            d = cosine_distance(a.proto, b.proto)
            if d > limit:
                continue
            cands.append((d + cfg.gap_penalty_per_s * max(0.0, gap), i, j))
    cands.sort()

    # Ambiguity: another candidate for the same end, nearly as cheap, that
    # cannot be the same person as this one (it overlaps it in time). Two
    # candidates one after the other are not rivals: both may be this
    # shopper, and the nearer one is joined first.
    outs: Dict[int, List[Tuple[float, int]]] = {}
    ins: Dict[int, List[Tuple[float, int]]] = {}
    for cost, i, j in cands:
        outs.setdefault(i, []).append((cost, j))
        ins.setdefault(j, []).append((cost, i))

    def _overlap(x: _Chain, y: _Chain) -> bool:
        return x.t_start < y.t_end - cfg.overlap_tolerance_s and y.t_start < x.t_end - cfg.overlap_tolerance_s

    def _rival(cost: float, mine: int, others: List[Tuple[float, int]]) -> bool:
        return any(
            o != mine and c - cost < cfg.ambiguity_margin and _overlap(chains[o], chains[mine])
            for c, o in others
        )

    succ: Dict[int, int] = {}
    pred: Dict[int, int] = {}
    skipped = 0
    links = 0
    for cost, i, j in cands:
        if i in succ or j in pred:
            continue
        if _rival(cost, j, outs[i]) or _rival(cost, i, ins[j]):
            skipped += 1
            continue
        # Never close a loop (j's chain already leads to i).
        k, loop = j, False
        while k in succ:
            k = succ[k]
            if k == i:
                loop = True
                break
        if loop:
            continue
        succ[i] = j
        pred[j] = i
        links += 1

    merged: List[_Chain] = []
    for i in range(len(chains)):
        if i in pred:
            continue
        path = [chains[i]]
        k = i
        while k in succ:
            k = succ[k]
            path.append(chains[k])
        members = [m for c in path for m in c.members]
        merged.append(_Chain(members, _merge_proto(path)))
    return merged, links, skipped


def link_fragments(
    fragments: Sequence[Fragment],
    config: Optional[LinkConfig] = None,
    transit: Optional[Dict[Tuple[str, str], Tuple[float, float]]] = None,
) -> LinkResult:
    cfg = config or LinkConfig()
    frs = sorted(fragments, key=lambda f: (f.t_start, str(f.camera), str(f.key)))
    chains = [_Chain([f], f.prototype()) for f in frs]
    same_links = cross_links = skipped = 0
    limits = _calibrate(frs, cfg)
    if cfg.enabled and len(chains) > 1:
        chains, same_links, s1 = _link_pass(chains, cfg, False, transit or {}, limits)
        skipped += s1
        if len({f.camera for f in frs}) > 1:
            chains, cross_links, s2 = _link_pass(chains, cfg, True, transit or {}, limits)
            skipped += s2
            # A shopper who went to another camera and came back is now one
            # chain per visit to this camera: join those as well.
            chains, more, s3 = _link_pass(chains, cfg, False, transit or {}, limits)
            same_links += more
            skipped += s3
    chains.sort(key=lambda c: (c.t_start, str(c.first_camera)))
    shopper_of: Dict[Hashable, int] = {}
    for n, c in enumerate(chains, 1):
        for m in c.members:
            shopper_of[m.key] = n
    return LinkResult(shopper_of, len(chains), same_links, cross_links, skipped,
                      {k: round(v, 3) for k, v in limits.items()})
