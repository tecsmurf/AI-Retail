"""Shopper linking: join fragments of one person, never two people."""

from __future__ import annotations

import numpy as np

from app.cv.linker import Fragment, LinkConfig, link_fragments
from app.cv.reid import ColourEncoder

RNG = np.random.default_rng(7)
DIM = 64


def person() -> np.ndarray:
    v = RNG.normal(size=DIM)
    return v / np.linalg.norm(v)


def looks(p: np.ndarray, noise: float = 0.15, n: int = 3):
    out = []
    for _ in range(n):
        v = p + RNG.normal(scale=noise / np.sqrt(DIM), size=DIM)
        out.append(v / np.linalg.norm(v))
    return out


def frag(key, t0, t1, p, camera="A", **kw):
    return Fragment(key=key, camera=camera, t_start=t0, t_end=t1, descriptors=looks(p, **kw))


def groups(result):
    out = {}
    for k, s in result.shopper_of.items():
        out.setdefault(s, set()).add(k)
    return sorted(sorted(g) for g in out.values())


def test_hidden_shopper_is_one_person():
    a, b = person(), person()
    r = link_fragments([frag(1, 0, 10, a), frag(2, 0, 30, b), frag(3, 14, 30, a)])
    assert groups(r) == [[1, 3], [2]]
    assert r.shoppers == 2 and r.same_camera_links == 1


def test_fragments_at_the_same_time_are_never_joined():
    a = person()
    # Same look, overlapping in time: two people dressed alike.
    r = link_fragments([frag(1, 0, 10, a), frag(2, 5, 20, a)])
    assert r.shoppers == 2


def test_different_people_are_not_joined():
    r = link_fragments([frag(1, 0, 10, person()), frag(2, 12, 20, person())])
    assert r.shoppers == 2


def test_gap_limit_and_reentry():
    a = person()
    # A long gap is a re-entry, not an occlusion: never joined by default.
    assert link_fragments([frag(1, 0, 10, a), frag(2, 45, 50, a)]).shoppers == 2
    loose = dict(reentry_factor=1.0)
    assert link_fragments([frag(1, 0, 10, a), frag(2, 45, 50, a)], LinkConfig(max_gap_s=30, **loose)).shoppers == 2
    assert link_fragments([frag(1, 0, 10, a), frag(2, 45, 50, a)], LinkConfig(max_gap_s=60, **loose)).shoppers == 1


def test_occlusion_needs_reappearing_close_by():
    a = person()
    box = (0.40, 0.50, 0.44, 0.70)
    near = (0.42, 0.51, 0.46, 0.71)
    far = (0.85, 0.50, 0.89, 0.70)  # 2.25 box heights away after 2 s
    edge = (0.00, 0.50, 0.04, 0.70)

    def pair(last, first):
        f1, f2 = frag(1, 0, 10, a), frag(2, 12, 20, a)
        f1.last_box, f2.first_box = last, first
        return link_fragments([f1, f2]).shoppers

    assert pair(box, near) == 1
    assert pair(box, far) == 2   # reappeared elsewhere: someone else may have walked in
    assert pair(edge, near) == 2  # walked out of the picture


def test_ambiguous_successor_is_left_alone():
    a = person()
    # Two later fragments, at the same time as each other, both look exactly
    # like fragment 1: either could be that shopper, so neither is joined.
    f1 = Fragment(1, "A", 0, 10, [a])
    f2 = Fragment(2, "A", 12, 20, [a])
    f3 = Fragment(3, "A", 12.5, 21, [a])
    r = link_fragments([f1, f2, f3], LinkConfig(gap_penalty_per_s=0.0))
    assert r.shoppers == 3 and r.skipped_ambiguous >= 1


def test_chain_of_three_and_no_descriptors():
    a = person()
    r = link_fragments([frag(1, 0, 5, a), frag(2, 8, 12, a), frag(3, 20, 30, a), Fragment(4, "A", 40, 45, [])])
    assert groups(r) == [[1, 2, 3], [4]]


def test_cross_camera_transit_window():
    a, b = person(), person()
    frs = [frag(1, 0, 20, a, camera="door"), frag(2, 0, 25, b, camera="door"),
           frag(3, 30, 60, a, camera="aisle"), frag(4, 40, 70, b, camera="aisle")]
    r = link_fragments(frs)
    assert groups(r) == [[1, 3], [2, 4]]
    assert r.cross_camera_links == 2
    # Too slow for the configured transit time between these cameras.
    r = link_fragments(frs, transit={("door", "aisle"): (0, 5)})
    assert r.shoppers == 4


def test_cross_camera_needs_no_time_overlap():
    a = person()
    r = link_fragments([frag(1, 0, 20, a, camera="A"), frag(2, 10, 30, a, camera="B")])
    assert r.shoppers == 2


def test_disabled():
    a = person()
    r = link_fragments([frag(1, 0, 5, a), frag(2, 8, 12, a)], LinkConfig(enabled=False))
    assert r.shoppers == 2


def test_colour_encoder_tells_clothes_apart():
    frame = np.zeros((200, 200, 3), np.uint8)
    frame[:, :100] = (40, 40, 200)   # red clothes (BGR)
    frame[:, 100:] = (200, 120, 40)  # blue clothes
    enc = ColourEncoder()
    v = enc.embed(frame, [(10, 10, 90, 190), (15, 20, 85, 180), (110, 10, 190, 190), (0, 0, 2, 2)])
    assert v.shape == (4, enc.dim)
    assert float(v[0] @ v[1]) > 0.95
    assert float(v[0] @ v[2]) < 0.5
    assert not v[3].any()  # too small to describe
