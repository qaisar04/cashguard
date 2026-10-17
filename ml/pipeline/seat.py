from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import median

from pipeline.geometry import Point, center, distance
from pipeline.tracking import Track
from pipeline.zones import Zones

log = logging.getLogger(__name__)

# A re-identified person shows up as a new track born on the frame where the old one dies (duplicate box):
# one shared timestamp is a hand-off, two or more are two people present together.
MAX_HANDOFF_OVERLAP = 1
# Standing boxes are 1.5-1.7x taller than seated ones on the dataset (0.21-0.26 vs 0.13-0.16 of frame height).
SEATED_HEIGHT_TOLERANCE = 1.25


@dataclass(frozen=True)
class Seat:
    """Where the cashier sits and which person tracks are the cashier.

    The laptop is on the desk between the cashier and the client, so distance to it cannot tell the two apart.
    The cashier is the person who dwells at the desk longest over the whole video; the seat is where that track
    sits. Other tracks are the cashier only when they never coexist with a cashier track (a re-track after a
    gap or a tracker hand-off) and settle at the seat itself for a while: a client stands across the desk from it,
    and the cashier walking out past her own standing spot (Х-15) does not settle.
    """

    anchor: Point
    cashier_ids: frozenset[int]


def locate_seat(tracks: list[Track], zones: Zones) -> Seat | None:
    candidates = [t for t in tracks if t.counted()]
    if zones.monitor is None or not candidates:
        return None
    dwell = {t.id: _desk_dwell(t, zones) for t in candidates}
    primary = max(candidates, key=lambda t: (dwell[t.id], -t.first_ts))
    if dwell[primary.id] <= 0:
        return None
    anchor = _workplace(primary, zones)
    cashiers = [primary]
    for t in sorted(candidates, key=lambda t: -dwell[t.id]):
        if t is primary or any(_overlap(t, c) > MAX_HANDOFF_OVERLAP for c in cashiers):
            continue
        if _settles_at(t, anchor, zones):
            cashiers.append(t)
    seat = Seat(anchor=anchor, cashier_ids=frozenset(t.id for t in cashiers))
    log.info("seat: anchor=(%.2f,%.2f) cashier tracks=%s", anchor[0], anchor[1], sorted(seat.cashier_ids))
    return seat


def _workplace(t: Track, zones: Zones) -> Point:
    """Where the cashier sits at the laptop.

    The whole-track median drifts to wherever she stood longest (Х-22: by the door, after 8 s at the laptop and
    12 s standing / walking out), and a standing person's box is ~1.5x taller with its centre higher in the frame
    (Х-24), so only the frames at the laptop with a seated-size box define the seat.
    """
    boxes = [b for _, b in t.points if distance(center(b), zones.monitor, zones.aspect) <= zones.cashier_radius]
    if not boxes:
        return _median_center([c for c in _centers(t) if zones.on_desk(c)])
    seated_height = min(b[3] - b[1] for b in boxes) * SEATED_HEIGHT_TOLERANCE
    return _median_center([center(b) for b in boxes if b[3] - b[1] <= seated_height])


def _settles_at(t: Track, anchor: Point, zones: Zones) -> bool:
    if distance(_median_center(_centers(t)), anchor, zones.aspect) > zones.seat_radius:
        return False
    settled = [ts for ts, box in t.points if distance(center(box), anchor, zones.aspect) <= zones.seat_radius]
    return bool(settled) and settled[-1] - settled[0] >= zones.seat_settle_sec


def _desk_dwell(t: Track, zones: Zones) -> float:
    """Seconds spent at the desk, each weighted by closeness to the laptop (1 at the laptop, 0 at desk_radius)."""
    return sum(max(0.0, 1.0 - distance(c, zones.monitor, zones.aspect) / zones.desk_radius) for c in _centers(t))


def _overlap(a: Track, b: Track) -> int:
    return len({ts for ts, _ in a.points} & {ts for ts, _ in b.points})


def _centers(t: Track) -> list[Point]:
    return [center(b) for _, b in t.points]


def _median_center(points: list[Point]) -> Point:
    return (median(p[0] for p in points), median(p[1] for p in points))
