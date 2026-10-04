"""Where to deploy troops: evenly spaced points along configured lines."""

from __future__ import annotations

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
