"""Temporal event engine: tracks + zones -> business events.

The engine is pure Python and deterministic: it receives one observation set
per analysed frame (time in seconds from the start of the video, track ids and
normalized boxes) and emits events. It never looks at pixels, so it is fully
unit-testable with synthetic tracks.

Definitions (see docs/CV_VALIDATION.md and docs/METRICS.md):

* Reference point: bottom-centre of the person box (ground-contact estimate).
* ZONE_ENTER: the reference point stays in a zone for ``zone_enter_min_s``;
  the event is time-stamped at the first sample inside. ZONE_EXIT: the point
  stays outside for ``zone_exit_grace_s``; time-stamped at the first sample
  outside. Short flickers across a boundary therefore produce no events.
  ``dwell_seconds`` = exit time - enter time.
* QUEUE_ENTER/QUEUE_EXIT: the same for QUEUE zones, with ``queue_enter_min_s``
  so people walking through a queue region are not counted as waiting.
  QUEUE_EXIT carries ``queue_wait_seconds``.
* QUEUE_COMPLETED (observed): after leaving the queue the track reaches a
  BILLING (counter) zone within ``queue_service_link_s``.
  QUEUE_ABANDONED (inferred): a counter zone exists on this camera, the track
  stayed visible, and it did not reach the counter within the link window.
  If the track is lost, the outcome is unknown and no outcome event is emitted.
* ENTRY/EXIT: the reference point crosses the camera's virtual entry line
  segment and stays on the new side for ``line_confirm_samples`` samples.
  Without an entry line, no ENTRY/EXIT is produced.
* Tracks with fewer than ``min_track_samples`` observations emit nothing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from app.cv.geometry import segments_intersect, side_of_line
from app.cv.zone_mapper import ZoneMapper, ZonePolygon

Box = Tuple[float, float, float, float]  # normalized x1, y1, x2, y2


@dataclass
class EngineConfig:
    zone_enter_min_s: float = 1.0
    zone_exit_grace_s: float = 1.0
    queue_enter_min_s: float = 3.0
    queue_service_link_s: float = 10.0
    line_confirm_samples: int = 2
    line_deadband: float = 0.005
    min_crossing_interval_s: float = 1.0
    min_track_samples: int = 3
    # A track not observed for this long is finalized (should be >= the
    # tracker's lost-track buffer so re-acquired tracks keep their state).
    track_end_grace_s: float = 3.0
    occupancy_interval_s: float = 5.0

    def as_dict(self) -> dict:
        return dict(self.__dict__)


@dataclass
class EntryLine:
    p1: Tuple[float, float]
    p2: Tuple[float, float]
    inside: str  # "left" | "right" of p1->p2 as seen on screen

    @property
    def inside_sign(self) -> int:
        return 1 if self.inside == "right" else -1

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional[EntryLine]:
        if not data:
            return None
        return cls(tuple(data["p1"]), tuple(data["p2"]), data["inside"])


@dataclass
class EngineEvent:
    event_type: str
    track_id: int
    t: float  # seconds from video start
    zone_name: Optional[str] = None
    zone_type: Optional[str] = None
    zone_id: Optional[str] = None
    dwell_seconds: Optional[float] = None
    queue_wait_seconds: Optional[float] = None
    queue_abandoned: Optional[bool] = None
    confidence: Optional[float] = None
    box: Optional[Box] = None
    meta: dict = field(default_factory=dict)
    seq: int = 0  # per-track sequence number (deterministic ids)

    def key(self, namespace: str) -> str:
        raw = f"{namespace}:{self.track_id}:{self.seq}:{self.event_type}"
        return hashlib.sha256(raw.encode()).hexdigest()[:40]


def reference_point(box: Box) -> Tuple[float, float]:
    x1, _, x2, y2 = box
    return ((x1 + x2) / 2.0, y2)


@dataclass
class _TrackState:
    track_id: int
    first_t: float
    last_t: float
    samples: int = 0
    last_box: Optional[Box] = None
    last_conf: float = 0.0
    # zone state machine
    zone: Optional[ZonePolygon] = None
    zone_enter_t: float = 0.0
    candidate: Optional[ZonePolygon] = None
    candidate_known: bool = False
    candidate_since: float = 0.0
    # queue outcome
    pending_queue_exit_t: Optional[float] = None
    pending_queue_wait: Optional[float] = None
    pending_queue_zone: Optional[ZonePolygon] = None
    # line crossing
    side: int = 0  # committed side (+1/-1), 0 unknown
    last_point_committed: Optional[Tuple[float, float]] = None
    new_side: int = 0
    new_side_count: int = 0
    new_side_first_t: float = 0.0
    new_side_first_point: Optional[Tuple[float, float]] = None
    last_crossing_t: float = -1e9
    # output
    seq: int = 0
    held: List[EngineEvent] = field(default_factory=list)
    confirmed: bool = False
    entered: bool = False
    exited: bool = False


class EventEngine:
    def __init__(
        self,
        zones: Sequence[ZonePolygon] = (),
        entry_line: Optional[EntryLine] = None,
        config: Optional[EngineConfig] = None,
    ) -> None:
        self.cfg = config or EngineConfig()
        self.mapper = zones if isinstance(zones, ZoneMapper) else ZoneMapper(list(zones))
        self.entry_line = entry_line
        self.has_counter = self.mapper.has_type("BILLING")
        self.tracks: Dict[int, _TrackState] = {}
        self.events: List[EngineEvent] = []
        self.occupancy: List[Tuple[float, str, str, int]] = []  # (t, zone, type, count)
        self._next_occupancy_t = 0.0
        self.finished_tracks = 0
        self.discarded_short_tracks = 0

    # ── Public API ───────────────────────────────────────────────

    def update(self, t: float, observations: Sequence[Tuple[int, Box, float]]) -> None:
        seen = set()
        zone_counts: Dict[str, int] = {z.name: 0 for z in self.mapper.zones}
        for track_id, box, conf in observations:
            seen.add(track_id)
            st = self.tracks.get(track_id)
            if st is None:
                st = _TrackState(track_id=track_id, first_t=t, last_t=t)
                self.tracks[track_id] = st
            st.samples += 1
            st.last_t = t
            st.last_box = box
            st.last_conf = conf
            point = reference_point(box)
            zone = self.mapper.get_zone(*point)
            if zone is not None:
                zone_counts[zone.name] += 1
            self._update_zone(st, t, zone)
            if self.entry_line is not None:
                self._update_line(st, t, point)
            self._update_queue_outcome(st, t)
            if not st.confirmed and st.samples >= self.cfg.min_track_samples:
                st.confirmed = True
                self.events.extend(st.held)
                st.held = []

        # Finalize tracks that have been absent for longer than the grace time.
        for track_id in [tid for tid, s in self.tracks.items() if tid not in seen]:
            st = self.tracks[track_id]
            if t - st.last_t >= self.cfg.track_end_grace_s:
                self._finish_track(st, reason="track_lost")

        if self.mapper.zones and t >= self._next_occupancy_t:
            for z in self.mapper.zones:
                self.occupancy.append((t, z.name, z.zone_type, zone_counts[z.name]))
            self._next_occupancy_t = t + self.cfg.occupancy_interval_s

    def finish(self, reason: str = "video_end") -> List[EngineEvent]:
        for st in list(self.tracks.values()):
            self._finish_track(st, reason=reason)
        self.events.sort(key=lambda e: (e.t, e.track_id, e.seq))
        return self.events

    @property
    def active_track_count(self) -> int:
        return len(self.tracks)

    # ── Internals ────────────────────────────────────────────────

    def _emit(self, st: _TrackState, event: EngineEvent) -> None:
        st.seq += 1
        event.seq = st.seq
        event.track_id = st.track_id
        if event.confidence is None:
            event.confidence = round(st.last_conf, 3)
        if event.box is None:
            event.box = st.last_box
        if st.confirmed:
            self.events.append(event)
        else:
            st.held.append(event)

    def _enter_threshold(self, zone: Optional[ZonePolygon]) -> float:
        if zone is None:
            return self.cfg.zone_exit_grace_s
        if zone.zone_type == "QUEUE":
            return self.cfg.queue_enter_min_s
        return self.cfg.zone_enter_min_s

    def _update_zone(self, st: _TrackState, t: float, zone: Optional[ZonePolygon]) -> None:
        if _same(zone, st.zone):
            st.candidate_known = False
            return
        if not st.candidate_known or not _same(zone, st.candidate):
            st.candidate = zone
            st.candidate_known = True
            st.candidate_since = t
        # A zone change needs the new state to persist. Leaving to "no zone"
        # uses the exit grace; entering a zone uses that zone's enter minimum.
        if t - st.candidate_since + 1e-9 >= self._enter_threshold(st.candidate):
            self._commit_zone(st, st.candidate, st.candidate_since)
            st.candidate_known = False

    def _commit_zone(self, st: _TrackState, new_zone: Optional[ZonePolygon], at: float) -> None:
        old = st.zone
        if old is not None:
            self._close_zone(st, old, at, reason="moved")
        st.zone = new_zone
        st.zone_enter_t = at
        if new_zone is not None:
            if new_zone.zone_type == "QUEUE":
                self._emit(st, EngineEvent("QUEUE_ENTER", st.track_id, at, new_zone.name, "QUEUE", new_zone.zone_id))
            else:
                self._emit(
                    st,
                    EngineEvent("ZONE_ENTER", st.track_id, at, new_zone.name, new_zone.zone_type, new_zone.zone_id),
                )
            if new_zone.zone_type == "BILLING" and st.pending_queue_exit_t is not None:
                if at - st.pending_queue_exit_t <= self.cfg.queue_service_link_s:
                    self._emit(
                        st,
                        EngineEvent(
                            "QUEUE_COMPLETED",
                            st.track_id,
                            at,
                            st.pending_queue_zone.name if st.pending_queue_zone else None,
                            "QUEUE",
                            queue_wait_seconds=round(st.pending_queue_wait or 0.0, 2),
                            queue_abandoned=False,
                            meta={"basis": "observed", "counter_zone": new_zone.name},
                        ),
                    )
                st.pending_queue_exit_t = None

    def _close_zone(self, st: _TrackState, zone: ZonePolygon, at: float, reason: str) -> None:
        dwell = max(0.0, at - st.zone_enter_t)
        if zone.zone_type == "QUEUE":
            self._emit(
                st,
                EngineEvent(
                    "QUEUE_EXIT",
                    st.track_id,
                    at,
                    zone.name,
                    "QUEUE",
                    zone.zone_id,
                    queue_wait_seconds=round(dwell, 2),
                    meta={"exit_reason": reason},
                ),
            )
            if reason == "moved":
                st.pending_queue_exit_t = at
                st.pending_queue_wait = dwell
                st.pending_queue_zone = zone
        else:
            self._emit(
                st,
                EngineEvent(
                    "ZONE_EXIT",
                    st.track_id,
                    at,
                    zone.name,
                    zone.zone_type,
                    zone.zone_id,
                    dwell_seconds=round(dwell, 2),
                    meta={"exit_reason": reason},
                ),
            )

    def _update_queue_outcome(self, st: _TrackState, t: float) -> None:
        if st.pending_queue_exit_t is None:
            return
        if t - st.pending_queue_exit_t > self.cfg.queue_service_link_s:
            if self.has_counter:
                self._emit_abandon(st, st.pending_queue_exit_t + self.cfg.queue_service_link_s)
            st.pending_queue_exit_t = None

    def _emit_abandon(self, st: _TrackState, at: float) -> None:
        self._emit(
            st,
            EngineEvent(
                "QUEUE_ABANDONED",
                st.track_id,
                at,
                st.pending_queue_zone.name if st.pending_queue_zone else None,
                "QUEUE",
                queue_wait_seconds=round(st.pending_queue_wait or 0.0, 2),
                queue_abandoned=True,
                meta={"basis": "inferred", "rule": "left queue and did not reach counter"},
            ),
        )

    def _update_line(self, st: _TrackState, t: float, point: Tuple[float, float]) -> None:
        line = self.entry_line
        side = side_of_line(line.p1, line.p2, point, self.cfg.line_deadband)
        if side == 0:
            return
        if st.side == 0:
            st.side = side
            st.last_point_committed = point
            return
        if side == st.side:
            st.last_point_committed = point
            st.new_side = 0
            st.new_side_count = 0
            return
        if st.new_side != side:
            st.new_side = side
            st.new_side_count = 0
            st.new_side_first_t = t
            st.new_side_first_point = point
        st.new_side_count += 1
        if st.new_side_count < self.cfg.line_confirm_samples:
            return
        crossed = segments_intersect(st.last_point_committed, st.new_side_first_point, line.p1, line.p2)
        if crossed and st.new_side_first_t - st.last_crossing_t >= self.cfg.min_crossing_interval_s:
            event_type = "ENTRY" if side == line.inside_sign else "EXIT"
            self._emit(st, EngineEvent(event_type, st.track_id, st.new_side_first_t, meta={"basis": "line_crossing"}))
            st.last_crossing_t = st.new_side_first_t
            if event_type == "ENTRY":
                st.entered = True
            else:
                st.exited = True
        # Either way the track now lives on the new side (a jump around the
        # end of the line segment is not a crossing).
        st.side = side
        st.last_point_committed = point
        st.new_side = 0
        st.new_side_count = 0

    def _finish_track(self, st: _TrackState, reason: str) -> None:
        if st.zone is not None:
            self._close_zone(st, st.zone, st.last_t, reason=reason)
            st.zone = None
        if st.pending_queue_exit_t is not None:
            # Visible for the whole link window without reaching the counter.
            if self.has_counter and st.last_t - st.pending_queue_exit_t >= self.cfg.queue_service_link_s:
                self._emit_abandon(st, st.pending_queue_exit_t + self.cfg.queue_service_link_s)
            st.pending_queue_exit_t = None
        if not st.confirmed:
            self.discarded_short_tracks += 1
        self.finished_tracks += 1
        del self.tracks[st.track_id]


def _same(a: Optional[ZonePolygon], b: Optional[ZonePolygon]) -> bool:
    if a is None or b is None:
        return a is b
    return a.name == b.name
