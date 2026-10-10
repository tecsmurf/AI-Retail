"""Pure CV logic: geometry, zones, the event engine and tracker behaviour.
No model or video needed."""

from __future__ import annotations

import pytest

from app.cv.event_engine import EngineConfig, EntryLine, EventEngine
from app.cv.geometry import point_in_polygon, segments_intersect, side_of_line, validate_polygon
from app.cv.zone_mapper import InvalidZoneError, ZoneMapper, ZonePolygon

SQUARE = [(0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5)]


def box_at(x: float, y: float, w: float = 0.1, h: float = 0.2):
    """Normalized box whose bottom-centre (reference point) is (x, y)."""
    return (x - w / 2, y - h, x + w / 2, y)


def types(events):
    return [e.event_type for e in events]


# ── geometry ─────────────────────────────────────────────────────


def test_point_in_polygon_inside_outside_and_boundary():
    assert point_in_polygon(0.25, 0.25, SQUARE)
    assert not point_in_polygon(0.75, 0.25, SQUARE)
    assert point_in_polygon(0.5, 0.25, SQUARE)  # boundary counts as inside
    assert point_in_polygon(0.0, 0.0, SQUARE)


def test_validate_polygon_rejects_bad_shapes():
    assert validate_polygon(SQUARE) == []
    assert validate_polygon([(0, 0), (1, 1)])  # too few points
    assert validate_polygon([(0, 0), (1.2, 0), (1, 1)])  # outside [0,1]
    assert validate_polygon([(0, 0), (0.5, 0.5), (1, 1)])  # zero area
    assert validate_polygon([(0, 0), (1, 1), (1, 0), (0, 1)])  # bow-tie self-intersection


def test_segments_and_line_side():
    assert segments_intersect((0, 0), (1, 1), (0, 1), (1, 0))
    assert not segments_intersect((0, 0), (0.4, 0.4), (0.6, 0.6), (1, 0.6))
    # Horizontal line left->right: on screen (y down) a point below is on the right.
    assert side_of_line((0, 0.5), (1, 0.5), (0.5, 0.7)) == 1
    assert side_of_line((0, 0.5), (1, 0.5), (0.5, 0.3)) == -1


def test_zone_mapper_overlap_priority_then_smallest():
    big = ZonePolygon("Aisle", "SHELF", [(0, 0), (1, 0), (1, 1), (0, 1)])
    small = ZonePolygon("Endcap", "DISPLAY", [(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)])
    m = ZoneMapper([big, small])
    assert m.get_zone(0.5, 0.5).name == "Endcap"  # same priority: smallest wins
    m2 = ZoneMapper([ZonePolygon("Aisle", "SHELF", big.polygon, priority=5), small])
    assert m2.get_zone(0.5, 0.5).name == "Aisle"
    assert m.get_zone(1.5, 0.5) is None


def test_zone_mapper_rejects_invalid_zone():
    with pytest.raises(InvalidZoneError):
        ZoneMapper([ZonePolygon("Bad", "SHELF", [(0, 0), (1, 1), (1, 0), (0, 1)])])


# ── event engine: zones ──────────────────────────────────────────

SHELF = ZonePolygon("Shelf", "SHELF", SQUARE)


def run(engine, track_points, dt=0.2):
    """track_points: list of per-frame dicts {track_id: (x, y)}; None = absent."""
    t = 0.0
    for frame in track_points:
        engine.update(t, [(tid, box_at(*p), 0.9) for tid, p in frame.items()])
        t += dt
    return engine.finish()


def test_zone_dwell_with_debounce():
    # 2 s inside, then 3 s outside.
    frames = [{1: (0.25, 0.25)}] * 10 + [{1: (0.8, 0.8)}] * 15
    ev = run(EventEngine([SHELF]), frames)
    assert types(ev) == ["ZONE_ENTER", "ZONE_EXIT"]
    assert ev[0].t == pytest.approx(0.0)
    assert ev[1].dwell_seconds == pytest.approx(2.0, abs=0.01)


def test_brief_flicker_does_not_create_visits():
    # Inside for 0.4 s only (below zone_enter_min_s=1.0).
    frames = [{1: (0.8, 0.8)}] * 5 + [{1: (0.25, 0.25)}] * 2 + [{1: (0.8, 0.8)}] * 10
    assert types(run(EventEngine([SHELF]), frames)) == []


def test_short_boundary_excursion_keeps_one_visit():
    frames = [{1: (0.25, 0.25)}] * 10 + [{1: (0.55, 0.25)}] * 2 + [{1: (0.25, 0.25)}] * 10
    ev = run(EventEngine([SHELF]), frames)
    assert types(ev) == ["ZONE_ENTER", "ZONE_EXIT"]
    assert ev[1].meta["exit_reason"] == "video_end"


def test_short_tracks_are_discarded():
    engine = EventEngine([SHELF], config=EngineConfig(min_track_samples=3, zone_enter_min_s=0.0))
    ev = run(engine, [{1: (0.25, 0.25)}] * 2)
    assert ev == []
    assert engine.discarded_short_tracks == 1


def test_track_loss_closes_zone_with_last_seen_time():
    frames = [{1: (0.25, 0.25)}] * 10 + [{}] * 20
    ev = run(EventEngine([SHELF]), frames)
    assert types(ev) == ["ZONE_ENTER", "ZONE_EXIT"]
    assert ev[1].meta["exit_reason"] == "track_lost"
    assert ev[1].t == pytest.approx(1.8)


def test_event_keys_are_deterministic():
    frames = [{1: (0.25, 0.25)}] * 10 + [{1: (0.8, 0.8)}] * 10
    a = run(EventEngine([SHELF]), frames)
    b = run(EventEngine([SHELF]), frames)
    assert [e.key("job") for e in a] == [e.key("job") for e in b]
    assert len({e.key("job") for e in a}) == len(a)


# ── event engine: queue outcomes ─────────────────────────────────

QUEUE = ZonePolygon("Queue", "QUEUE", [(0.0, 0.5), (0.5, 0.5), (0.5, 1.0), (0.0, 1.0)])
COUNTER = ZonePolygon("Counter", "BILLING", [(0.5, 0.5), (1.0, 0.5), (1.0, 1.0), (0.5, 1.0)])
IN_Q, AT_COUNTER, AWAY = (0.25, 0.75), (0.75, 0.75), (0.25, 0.2)


def test_queue_completed_is_observed():
    frames = [{1: IN_Q}] * 25 + [{1: AT_COUNTER}] * 20
    ev = run(EventEngine([QUEUE, COUNTER]), frames)
    assert types(ev)[:3] == ["QUEUE_ENTER", "QUEUE_EXIT", "ZONE_ENTER"]
    assert "QUEUE_COMPLETED" in types(ev)
    done = next(e for e in ev if e.event_type == "QUEUE_COMPLETED")
    assert done.queue_wait_seconds == pytest.approx(5.0, abs=0.01)
    assert done.meta["basis"] == "observed"


def test_queue_abandoned_needs_visible_track_and_counter_zone():
    frames = [{1: IN_Q}] * 25 + [{1: AWAY}] * 70  # 14 s visible away from counter
    ev = run(EventEngine([QUEUE, COUNTER]), frames)
    assert "QUEUE_ABANDONED" in types(ev)
    assert next(e for e in ev if e.event_type == "QUEUE_ABANDONED").meta["basis"] == "inferred"


def test_queue_outcome_unknown_when_track_lost():
    frames = [{1: IN_Q}] * 25 + [{1: AWAY}] * 10 + [{}] * 30
    ev = run(EventEngine([QUEUE, COUNTER]), frames)
    assert "QUEUE_ABANDONED" not in types(ev) and "QUEUE_COMPLETED" not in types(ev)
    assert "QUEUE_EXIT" in types(ev)


def test_no_abandonment_without_counter_zone():
    frames = [{1: IN_Q}] * 25 + [{1: AWAY}] * 70
    assert "QUEUE_ABANDONED" not in types(run(EventEngine([QUEUE]), frames))


def test_walking_through_queue_is_not_queueing():
    frames = [{1: IN_Q}] * 10 + [{1: AWAY}] * 20  # 2 s < queue_enter_min_s (3 s)
    assert types(run(EventEngine([QUEUE, COUNTER]), frames)) == []


# ── event engine: entry line ─────────────────────────────────────

LINE = EntryLine((0.0, 0.5), (1.0, 0.5), "right")  # inside = below the line on screen


def test_entry_and_exit_by_line_crossing():
    frames = [{1: (0.5, 0.3)}] * 5 + [{1: (0.5, 0.7)}] * 10 + [{1: (0.5, 0.3)}] * 10
    ev = run(EventEngine([], LINE), frames)
    assert types(ev) == ["ENTRY", "EXIT"]


def test_jitter_on_the_line_is_not_counted():
    frames = []
    for i in range(30):
        frames.append({1: (0.5, 0.52 if i % 2 else 0.48)})  # alternates every sample
    assert types(run(EventEngine([], LINE), frames)) == []


def test_passing_beside_the_line_segment_is_not_a_crossing():
    short = EntryLine((0.4, 0.5), (0.6, 0.5), "right")
    frames = [{1: (0.9, 0.3)}] * 5 + [{1: (0.9, 0.7)}] * 10
    assert types(run(EventEngine([], short), frames)) == []


def test_new_track_is_not_an_entry_without_crossing():
    frames = [{1: (0.5, 0.8)}] * 20  # appears inside and never crosses
    assert types(run(EventEngine([], LINE), frames)) == []


# ── tracking: v1 tracker fragmentation regression ───────────────


def _walk(n=60, gap_every=7):
    """One person walking across the frame; the detector misses every 7th frame."""
    from app.cv.detector import Detection

    frames = []
    for i in range(n):
        if i % gap_every == gap_every - 1:
            frames.append([])
            continue
        x = 100 + i * 8
        frames.append([Detection((x, 200, x + 80, 400), 0.8)])
    return frames


def test_legacy_tracker_fragments_on_missed_detection():
    from app.cv.legacy_tracker import ByteTracker

    tracker = ByteTracker()
    ids = set()
    for dets in _walk():
        ids |= {t.track_id for t in tracker.update(dets)}
    assert len(ids) > 1  # documents the v1 bug: one person, several ids


def test_bytetrack_keeps_one_identity_across_misses():
    pytest.importorskip("supervision")
    from app.cv.tracker import PersonTracker

    tracker = PersonTracker(frame_rate=5)
    ids = set()
    for dets in _walk():
        ids |= {t.track_id for t in tracker.update(dets)}
    assert len(ids) == 1
