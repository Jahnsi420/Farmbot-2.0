"""Where to deploy troops: evenly spaced points along configured lines."""

from __future__ import annotations

import math

Point = tuple[float, float]
Line = tuple[Point, Point]


def line_points(line: Line, n: int) -> list[Point]:
    """`n` evenly spaced points on a line, keeping half a step away from both ends."""
    (x1, y1), (x2, y2) = line
    return [
        (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t)
        for t in ((i + 0.5) / n for i in range(max(n, 0)))
    ]


def spread(lines: dict[str, Line], names: list[str], count: int) -> list[Point]:
    """Distribute `count` deployments as evenly as possible over the named lines."""
    if not names or count <= 0:
        return []
    for name in names:
        if name not in lines:
            raise ValueError(f"Unbekannte Absetzlinie '{name}', vorhanden: {', '.join(lines)}")
    base, extra = divmod(count, len(names))
    points: list[Point] = []
    for i, name in enumerate(names):
        points += line_points(lines[name], base + (1 if i < extra else 0))
    return points


def to_pixels(lines: dict[str, Line], width: int, height: int, shift: float = 0) -> dict[str, Line]:
    """Lines in screen pixels, each moved `shift` pixels outwards (away from the screen center)."""
    out = {}
    for name, ((x1, y1), (x2, y2)) in lines.items():
        a, b = (x1 * width, y1 * height), (x2 * width, y2 * height)
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy) or 1
        nx, ny = -dy / length, dx / length
        mid = ((a[0] + b[0]) / 2 - width / 2, (a[1] + b[1]) / 2 - height / 2)
        if nx * mid[0] + ny * mid[1] < 0:  # point the normal away from the center
            nx, ny = -nx, -ny
        out[name] = ((a[0] + nx * shift, a[1] + ny * shift), (b[0] + nx * shift, b[1] + ny * shift))
    return out
