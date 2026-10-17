from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import median

from app.settings import GlassDetectionConfig, ZonesConfig
from pipeline.geometry import Box, Point, Polygon, center, clip, distance
from pipeline.observers.base import KIND_GLASS, KIND_MONITOR, KIND_PERSON, Observation

log = logging.getLogger(__name__)

ANCHOR_CELL = 0.05
EDGE_TOLERANCE = 0.03
ZONE_SOURCE_CONFIG = "config"
ZONE_SOURCE_DETECTED = "detected"


@dataclass(frozen=True)
class Zones:
    monitor: Point | None
    cashier_radius: float
    desk_radius: float
    safe_radius: float
    door: Polygon
    glass: Polygon
    aspect: float
    source: str = ZONE_SOURCE_CONFIG

    def seat_distance(self, p: Point) -> float | None:
        return None if self.monitor is None else distance(p, self.monitor, self.aspect)

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


@dataclass(frozen=True)
class Glazing:
    """The glass front as detected: the whole glazing (door + panes) and the pane at the frame edge."""

    whole: Box
    edge_pane: Box


def build_zones(cfg: ZonesConfig, observations: list[Observation], aspect: float) -> Zones:
    monitors = [o for o in observations if o.kind == KIND_MONITOR]
    if monitors:
        monitor = _median_center([o.box for o in monitors])
    else:
        # No laptop in view (closed, or the cashier works at the counting machine): anchor the seat where people dwell most.
        persons = [o for o in observations if o.kind == KIND_PERSON]
        monitor = _dwell_peak([o.box for o in persons]) if persons else None
    door, glass, source = _polygon_from_config(cfg.door), _polygon_from_config(cfg.glass), ZONE_SOURCE_CONFIG
    glazing = detect_glazing([o for o in observations if o.kind == KIND_GLASS], cfg.glass_detection) if cfg.glass_detection.enabled else None
    if glazing is not None:
        door, glass, source = _rect(glazing.whole, cfg.glass_detection.pad), _rect(glazing.edge_pane, cfg.glass_detection.pad), ZONE_SOURCE_DETECTED
    log.info("zones: %s door=%s glass=%s", source, _fmt(door), _fmt(glass))
    return Zones(
        monitor=monitor,
        cashier_radius=cfg.cashier_radius,
        desk_radius=cfg.desk_radius,
        safe_radius=cfg.safe_radius,
        door=door,
        glass=glass,
        aspect=aspect,
        source=source,
    )


def detect_glazing(glass: list[Observation], cfg: GlassDetectionConfig) -> Glazing | None:
    """Median over frames of (whole glazing, edge pane); None when too few frames show a pane at the frame edge.

    OWLv2 returns the glazing as a whole plus its panes; the labels (wall / door) are unreliable, the geometry is not.
    The pane touching the frame edge is where the mirror images of the people in the room appear.
    """
    by_ts: dict[float, list[Box]] = {}
    for o in glass:
        by_ts.setdefault(o.ts, []).append(o.box)
    wholes: list[Box] = []
    panes: list[Box] = []
    for boxes in by_ts.values():
        whole = _union(boxes)
        pane = _edge_pane(boxes, whole, cfg.edge_pane_max_fraction)
        if pane is None:
            continue
        wholes.append(whole)
        panes.append(pane)
    if len(panes) < cfg.min_frames:
        return None
    return Glazing(whole=_median_box(wholes), edge_pane=_median_box(panes))


def _edge_pane(boxes: list[Box], whole: Box, max_fraction: float) -> Box | None:
    width = whole[2] - whole[0]
    if whole[0] <= EDGE_TOLERANCE:
        candidates = [b for b in boxes if b[0] <= EDGE_TOLERANCE and b[2] - b[0] <= max_fraction * width]
    elif whole[2] >= 1 - EDGE_TOLERANCE:
        candidates = [b for b in boxes if b[2] >= 1 - EDGE_TOLERANCE and b[2] - b[0] <= max_fraction * width]
    else:
        return None
    return max(candidates, key=lambda b: b[2] - b[0]) if candidates else None


def _union(boxes: list[Box]) -> Box:
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def _median_box(boxes: list[Box]) -> Box:
    return tuple(median(b[i] for b in boxes) for i in range(4))  # type: ignore[return-value]


def _rect(box: Box, pad: float) -> Polygon:
    x1, y1, x2, y2 = clip((box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad))
    return Polygon(((x1, y1), (x2, y1), (x2, y2), (x1, y2)))


def _polygon_from_config(points: list[list[float]]) -> Polygon:
    return Polygon(tuple((float(x), float(y)) for x, y in points))


def _fmt(polygon: Polygon) -> str:
    return "[" + ", ".join(f"({x:.2f},{y:.2f})" for x, y in polygon.points) + "]"


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
