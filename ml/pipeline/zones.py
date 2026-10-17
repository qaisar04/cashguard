from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from app.settings import ZonesConfig
from pipeline.geometry import Box, Point, Polygon, center, distance
from pipeline.observers.base import KIND_MONITOR, KIND_PERSON, Observation

ANCHOR_CELL = 0.05


@dataclass(frozen=True)
class Zones:
    monitor: Point | None
    cashier_radius: float
    desk_radius: float
    safe_radius: float
    door: Polygon
    glass: Polygon
    aspect: float

    def at_cashier_seat(self, p: Point) -> bool:
        return self.monitor is not None and distance(p, self.monitor, self.aspect) <= self.cashier_radius

    def on_desk(self, p: Point) -> bool:
        return self.monitor is not None and distance(p, self.monitor, self.aspect) <= self.desk_radius

    def near(self, p: Point, anchor: Point) -> bool:
        return distance(p, anchor, self.aspect) <= self.safe_radius

    def in_door(self, p: Point) -> bool:
        return self.door.contains(p)

    def in_glass(self, p: Point) -> bool:
        return self.glass.contains(p)


def build_zones(cfg: ZonesConfig, observations: list[Observation], aspect: float) -> Zones:
    monitors = [o for o in observations if o.kind == KIND_MONITOR]
    if monitors:
        monitor = _median_center([o.box for o in monitors])
    else:
        # No laptop in view (closed, or the cashier works at the counting machine): anchor the seat where people dwell most.
        persons = [o for o in observations if o.kind == KIND_PERSON]
        monitor = _dwell_peak([o.box for o in persons]) if persons else None
    return Zones(
        monitor=monitor,
        cashier_radius=cfg.cashier_radius,
        desk_radius=cfg.desk_radius,
        safe_radius=cfg.safe_radius,
        door=Polygon(tuple((float(x), float(y)) for x, y in cfg.door)),
        glass=Polygon(tuple((float(x), float(y)) for x, y in cfg.glass)),
        aspect=aspect,
    )


def _median_center(boxes: list[Box]) -> Point:
    centers = [center(b) for b in boxes]
    return (median(c[0] for c in centers), median(c[1] for c in centers))


def _dwell_peak(boxes: list[Box]) -> Point:
    cells: dict[tuple[int, int], list[Point]] = {}
    for b in boxes:
        c = center(b)
        cells.setdefault((int(c[0] / ANCHOR_CELL), int(c[1] / ANCHOR_CELL)), []).append(c)
    densest = max(cells.values(), key=len)
    return (median(c[0] for c in densest), median(c[1] for c in densest))
