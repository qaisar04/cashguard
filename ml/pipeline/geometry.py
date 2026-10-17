from __future__ import annotations

from dataclasses import dataclass
from math import hypot

Box = tuple[float, float, float, float]  # normalized x1, y1, x2, y2
Point = tuple[float, float]


@dataclass(frozen=True)
class Polygon:
    points: tuple[Point, ...]

    def contains(self, p: Point) -> bool:
        x, y = p
        inside = False
        n = len(self.points)
        for i in range(n):
            x1, y1 = self.points[i]
            x2, y2 = self.points[(i + 1) % n]
            if (y1 > y) != (y2 > y):
                x_cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                if x < x_cross:
                    inside = not inside
        return inside


def center(box: Box) -> Point:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def iou(a: Box, b: Box) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


def distance(a: Point, b: Point, aspect: float) -> float:
    """Distance in units of frame height; aspect = width / height."""
    return hypot((a[0] - b[0]) * aspect, a[1] - b[1])


def clip(box: Box) -> Box:
    return (
        min(max(box[0], 0.0), 1.0),
        min(max(box[1], 0.0), 1.0),
        min(max(box[2], 0.0), 1.0),
        min(max(box[3], 0.0), 1.0),
    )
