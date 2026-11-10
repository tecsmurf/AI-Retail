"""Track stitching: joining tracker fragments of one person, never two people."""

from __future__ import annotations

import pytest

from app.cv.event_engine import EntryLine, EventEngine
from app.cv.stitcher import StitchConfig, TrackStitcher


def box_at(x: float, y: float, w: float = 0.08, h: float = 0.25):
    return (x - w / 2, y - h, x + w / 2, y)


def run(stitcher, frames):
    """frames: list of (t, [(raw_id, (x, y))]) -> list of visitor-id sets."""
    out = []
    for t, obs in frames:
        mapped = stitcher.update(t, [(rid, box_at(x, y), 0.9) for rid, (x, y) in obs])
        out.append({vid for vid, _, _ in mapped})
    return out


def walker(raw_before, raw_after, gap=(2.0, 2.6), speed=0.15, fps=5, end=5.0, y=0.7):
    """One person walking right at `speed` frame-widths/s; tracker loses them
    during `gap` and gives a new id afterwards."""
    frames = []
    for i in range(int(end * fps)):
        t = i / fps
        x = 0.2 + speed * t
        if gap[0] <= t < gap[1]:
            frames.append((t, []))
        else:
            frames.append((t, [(raw_before if t < gap[0] else raw_after, (x, y))]))
    return frames


def test_fragment_after_short_loss_is_joined():
    s = TrackStitcher()
    ids = set().union(*run(s, walker(1, 2)))
    assert ids == {1}
    assert s.stitches == 1
    assert s.visitor_count == 1


def test_disabled_stitcher_passes_ids_through():
    s = TrackStitcher(StitchConfig(enabled=False))
    ids = set().union(*run(s, walker(1, 2)))
    assert ids == {1, 2}


def test_gap_longer_than_limit_is_a_new_visitor():
    s = TrackStitcher(StitchConfig(max_gap_s=1.0))
    ids = set().union(*run(s, walker(1, 2, gap=(1.0, 3.0))))
    assert len(ids) == 2


def test_far_away_new_track_is_a_different_person():
    s = TrackStitcher()
    frames = [(i / 5, [(1, (0.3, 0.7))]) for i in range(10)]
    # Person 1 vanishes mid-frame; someone appears on the other side.
    frames += [(2.0 + i / 5, [(2, (0.8, 0.7))]) for i in range(10)]
    ids = set().union(*run(s, frames))
    assert len(ids) == 2
    assert s.stitches == 0


def test_track_lost_at_frame_edge_is_not_joined():
    # Person 1 walks out at the right edge; person 2 walks in at the same spot.
    s = TrackStitcher()
    frames = [(i / 5, [(1, (0.80 + 0.03 * i, 0.7))]) for i in range(6)]  # ends at x=0.95 (box at edge)
    frames += [(1.4 + i / 5, [(2, (0.95 - 0.03 * i, 0.7))]) for i in range(6)]
    ids = set().union(*run(s, frames))
    assert len(ids) == 2


def test_very_different_box_size_is_not_joined():
    s = TrackStitcher()
    run(s, [(i / 5, [(1, (0.5, 0.7))]) for i in range(5)])
    vids = {vid for vid, _, _ in s.update(1.4, [(2, box_at(0.5, 0.7, h=0.6), 0.9)])}
    assert vids == {2}


def test_ambiguous_candidates_are_not_joined():
    s = TrackStitcher()
    # Two people standing close together both get lost; one new id appears
    # exactly between them.
    frames = [(i / 5, [(1, (0.45, 0.7)), (2, (0.55, 0.7))]) for i in range(5)]
    run(s, frames)
    vids = {vid for vid, _, _ in s.update(1.4, [(3, box_at(0.5, 0.7), 0.9)])}
    assert vids == {3}


def test_returning_original_id_while_fragment_alive_gets_own_visitor():
    s = TrackStitcher()
    run(s, [(i / 5, [(1, (0.5, 0.7))]) for i in range(5)])
    # Raw 2 appears where 1 was: stitched to visitor 1.
    assert {v for v, _, _ in s.update(1.2, [(2, box_at(0.5, 0.7), 0.9)])} == {1}
    # Raw 1 comes back next to raw 2: they are two people.
    vids = [v for v, _, _ in s.update(1.4, [(1, box_at(0.52, 0.7), 0.9), (2, box_at(0.5, 0.7), 0.9)])]
    assert len(set(vids)) == 2


def test_stitched_track_crosses_line_once():
    """A walker split in two right before the entry line is one ENTRY, not a
    lost track plus a new one."""
    s = TrackStitcher()
    engine = EventEngine([], EntryLine((0.5, 0.0), (0.5, 1.0), "left"))
    for t, obs in walker(1, 2, gap=(1.6, 2.0), speed=0.15, end=4.0):
        mapped = s.update(t, [(rid, box_at(x, y), 0.9) for rid, (x, y) in obs])
        engine.update(t, mapped)
    events = engine.finish()
    assert [e.event_type for e in events] == ["ENTRY"]
    assert {e.track_id for e in events} == {1}


def test_bytetrack_split_by_fast_motion_is_rejoined():
    """Reproduces the documented ByteTrack weakness: at 5 fps a box moving
    ~0.6 box widths per frame breaks IoU matching. The stitcher rejoins it."""
    pytest.importorskip("supervision")
    from app.cv.detector import Detection
    from app.cv.tracker import PersonTracker

    tracker = PersonTracker(frame_rate=5)
    s = TrackStitcher()
    raw, visitors = set(), set()
    W, H = 1280.0, 720.0
    for i in range(30):
        t = i / 5
        # Walks slowly, then a fast stretch (e.g. hidden behind a shopper and
        # re-detected further on), then slowly again.
        x = 100 + i * 8 if i < 12 else 100 + 12 * 8 + (i - 12) * 26 if i < 15 else 100 + 12 * 8 + 3 * 26 + (i - 15) * 8
        dets = [] if 12 <= i < 14 else [Detection((x, 300, x + 40, 400), 0.85)]
        tracked = tracker.update(dets)
        obs = [(tb.track_id, (tb.bbox[0] / W, tb.bbox[1] / H, tb.bbox[2] / W, tb.bbox[3] / H), tb.confidence)
               for tb in tracked]
        raw |= {o[0] for o in obs}
        visitors |= {v for v, _, _ in s.update(t, obs)}
    assert len(visitors) == 1
    assert len(raw) == 2  # ByteTrack alone counts two people
