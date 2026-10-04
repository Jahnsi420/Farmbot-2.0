"""Geometry for troop deployment along the edge of the (diamond shaped) map."""

from __future__ import annotations

from dataclasses import dataclass

Point = tuple[float, float]

SIDES = ("top_left", "top_right", "bottom_right", "bottom_left")


@dataclass
class Diamond:
    """Corners of the playable area in relative screen coordinates."""

    top: Point
    right: Point
    bottom: Point
    left: Point

    @property
    def center(self) -> Point:
        xs = (self.top[0], self.right[0], self.bottom[0], self.left[0])
        ys = (self.top[1], self.right[1], self.bottom[1], self.left[1])
        return sum(xs) / 4, sum(ys) / 4

    def edge(self, side: str) -> tuple[Point, Point]:
        return {
            "top_left": (self.left, self.top),
            "top_right": (self.top, self.right),
            "bottom_right": (self.right, self.bottom),
            "bottom_left": (self.bottom, self.left),
        }[side]


def _lerp(a: Point, b: Point, t: float) -> Point:
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def edge_points(diamond: Diamond, side: str, n: int, outward: float = 0.0,
                margin: float = 0.1) -> list[Point]:
    """`n` evenly spaced points on one edge, pushed `outward` away from the center.

    `margin` keeps points away from the corners, which are often off-screen.
    """
    if n <= 0:
        return []
    a, b = diamond.edge(side)
    cx, cy = diamond.center
    points = []
    for i in range(n):
        t = margin + (1 - 2 * margin) * ((i + 0.5) / n)
        x, y = _lerp(a, b, t)
        points.append((x + (x - cx) * outward, y + (y - cy) * outward))
    return points


def spread(diamond: Diamond, sides: list[str], count: int, outward: float = 0.0) -> list[Point]:
    """Distribute `count` deployments as evenly as possible over the given sides."""
    if not sides or count <= 0:
        return []
    for side in sides:
        if side not in SIDES:
            raise ValueError(f"Unbekannte Seite '{side}', erlaubt: {', '.join(SIDES)}")
    base, extra = divmod(count, len(sides))
    points: list[Point] = []
    for i, side in enumerate(sides):
        points += edge_points(diamond, side, base + (1 if i < extra else 0), outward)
    return points
