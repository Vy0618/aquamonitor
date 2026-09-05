"""Stateless geometry utilities used by the line counter."""

from __future__ import annotations

from typing import TypeAlias

Point: TypeAlias = tuple[float, float]
Line: TypeAlias = tuple[Point, Point]


def centroid(xyxy: tuple[float, float, float, float]) -> Point:
    """Return the centre point of an ``(x1, y1, x2, y2)`` bounding box."""
    x1, y1, x2, y2 = xyxy
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def signed_distance(point: Point, line: Line) -> float:
    """Return the signed cross-product distance to an oriented line.

    A positive result is on the left side of a line from ``line[0]`` to
    ``line[1]``; a negative result is on its right side.
    """
    (x1, y1), (x2, y2) = line
    x, y = point
    return (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)


def side_of_line(point: Point, line: Line, *, epsilon: float = 1e-9) -> int:
    """Classify a point as -1, 0, or 1 relative to an oriented line."""
    distance = signed_distance(point, line)
    if distance > epsilon:
        return 1
    if distance < -epsilon:
        return -1
    return 0


def _orientation(a: Point, b: Point, c: Point) -> int:
    return side_of_line(c, (a, b))


def _on_segment(a: Point, point: Point, b: Point) -> bool:
    return (
        min(a[0], b[0]) <= point[0] <= max(a[0], b[0])
        and min(a[1], b[1]) <= point[1] <= max(a[1], b[1])
    )


def segments_intersect(first: Line, second: Line) -> bool:
    """Return whether two finite line segments intersect, including endpoints."""
    a, b = first
    c, d = second
    ab_c, ab_d = _orientation(a, b, c), _orientation(a, b, d)
    cd_a, cd_b = _orientation(c, d, a), _orientation(c, d, b)

    if ab_c != ab_d and cd_a != cd_b:
        return True
    return (
        (ab_c == 0 and _on_segment(a, c, b))
        or (ab_d == 0 and _on_segment(a, d, b))
        or (cd_a == 0 and _on_segment(c, a, d))
        or (cd_b == 0 and _on_segment(c, b, d))
    )


def crosses_line(previous: Point, current: Point, line: Line) -> bool:
    """Return true if motion crosses the finite line segment.

    Motion that begins or ends exactly on the line is not itself a crossing;
    the counter retains the previous non-zero side to handle that case.
    """
    previous_side = side_of_line(previous, line)
    current_side = side_of_line(current, line)
    return (
        previous_side != 0
        and current_side != 0
        and previous_side != current_side
        and segments_intersect((previous, current), line)
    )
