"""Pure geometry helpers for zone polygons and virtual lines.

All coordinates are *normalized* image coordinates: x and y in [0, 1], origin
at the top-left, y pointing down (the convention of every image library).
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

Point = Tuple[float, float]
EPS = 1e-9
# Points within this normalized distance of an edge count as on the boundary
# (~0.1 px on a 1080p frame).
BOUNDARY_TOLERANCE = 1e-4


def polygon_area(poly: Sequence[Point]) -> float:
    """Signed shoelace area (positive = counter-clockwise in math coords)."""
    area = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def _orient(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, p: Point, tol: float = BOUNDARY_TOLERANCE) -> bool:
    """True if p lies on segment ab (within tolerance)."""
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    seg_len2 = dx * dx + dy * dy
    if seg_len2 < EPS:
        return (px - ax) ** 2 + (py - ay) ** 2 <= tol * tol
    t = ((px - ax) * dx + (py - ay) * dy) / seg_len2
    if t < -EPS or t > 1 + EPS:
        return False
    cx, cy = ax + t * dx, ay + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2 <= tol * tol


def segments_intersect(p1: Point, p2: Point, q1: Point, q2: Point) -> bool:
    """Proper or touching intersection of segments p1p2 and q1q2."""
    d1 = _orient(q1, q2, p1)
    d2 = _orient(q1, q2, p2)
    d3 = _orient(p1, p2, q1)
    d4 = _orient(p1, p2, q2)
    if ((d1 > EPS and d2 < -EPS) or (d1 < -EPS and d2 > EPS)) and (
        (d3 > EPS and d4 < -EPS) or (d3 < -EPS and d4 > EPS)
    ):
        return True
    return (
        _on_segment(q1, q2, p1, EPS)
        or _on_segment(q1, q2, p2, EPS)
        or _on_segment(p1, p2, q1, EPS)
        or _on_segment(p1, p2, q2, EPS)
    )


def point_in_polygon(x: float, y: float, poly: Sequence[Point]) -> bool:
    """Ray casting with an explicit boundary rule: points on an edge or vertex
    are *inside*. This makes assignment deterministic for boundary points."""
    n = len(poly)
    if n < 3:
        return False
    p = (x, y)
    for i in range(n):
        if _on_segment(poly[i], poly[(i + 1) % n], p):
            return True
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def validate_polygon(points: Sequence[Sequence[float]]) -> List[str]:
    """Return a list of problems; empty means the polygon is usable."""
    problems: List[str] = []
    if not isinstance(points, (list, tuple)) or len(points) < 3:
        return ["polygon needs at least 3 points"]
    poly: List[Point] = []
    for idx, pt in enumerate(points):
        if not isinstance(pt, (list, tuple)) or len(pt) != 2:
            return [f"point {idx} must be [x, y]"]
        try:
            x, y = float(pt[0]), float(pt[1])
        except (TypeError, ValueError):
            return [f"point {idx} is not numeric"]
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            problems.append(f"point {idx} ({x}, {y}) is outside the normalized frame [0, 1]")
        poly.append((x, y))
    if problems:
        return problems
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 < EPS:
            problems.append(f"points {i} and {(i + 1) % n} are duplicates")
    if abs(polygon_area(poly)) < 1e-6:
        problems.append("polygon has (almost) zero area")
    # Non-adjacent edges must not intersect (simple polygon).
    for i in range(n):
        a1, a2 = poly[i], poly[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or (i + 1) % n == j:
                continue
            b1, b2 = poly[j], poly[(j + 1) % n]
            if segments_intersect(a1, a2, b1, b2):
                problems.append(f"edges {i} and {j} intersect (self-intersecting polygon)")
                return problems
    return problems


def side_of_line(p1: Point, p2: Point, pt: Point, deadband: float = 0.0) -> int:
    """+1 if pt is on the right of the directed line p1->p2 as seen on screen
    (y down), -1 if on the left, 0 if within ``deadband`` (normalized distance)."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = (dx * dx + dy * dy) ** 0.5
    if length < EPS:
        return 0
    cross = dx * (pt[1] - p1[1]) - dy * (pt[0] - p1[0])
    dist = cross / length
    if abs(dist) <= deadband:
        return 0
    return 1 if dist > 0 else -1


def validate_line(line: Optional[dict]) -> List[str]:
    if line is None:
        return []
    problems: List[str] = []
    try:
        p1 = tuple(float(v) for v in line["p1"])
        p2 = tuple(float(v) for v in line["p2"])
    except (KeyError, TypeError, ValueError):
        return ["entry line needs p1 and p2 as [x, y]"]
    if len(p1) != 2 or len(p2) != 2:
        return ["entry line points must be [x, y]"]
    for name, (x, y) in (("p1", p1), ("p2", p2)):
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            problems.append(f"{name} is outside the normalized frame [0, 1]")
    if (p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2 < 1e-6:
        problems.append("entry line is too short")
    if line.get("inside") not in ("left", "right"):
        problems.append("entry line 'inside' must be 'left' or 'right'")
    return problems
