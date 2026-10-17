from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from pipeline.geometry import Point, center
from pipeline.observers.base import (
    ATTR_SCREEN_STATE,
    KIND_BAG,
    KIND_CASH,
    KIND_DOOR_OPEN,
    KIND_MONITOR,
    KIND_PERSON,
    KIND_SAFE_OPEN,
    SCREEN_UNKNOWN,
    Observation,
)
from pipeline.tracking import Track
from pipeline.zones import Zones

ROLE_CASHIER = "cashier"
ROLE_VISITOR = "visitor"


@dataclass(frozen=True)
class Person:
    track_id: int
    center: Point
    at_seat: bool
    in_door: bool
    first_seen: float
    counted: bool = True
    entered: bool = False


@dataclass
class SecondState:
    t: float
    persons: list[Person] = field(default_factory=list)
    screen_state: str = SCREEN_UNKNOWN
    monitor_visible: bool = False
    cash_on_desk: int = 0
    bags_on_desk: int = 0
    safe_open: bool = False
    safe_center: Point | None = None
    person_at_safe: bool = False
    door_open: bool = False

    @property
    def cashier_present(self) -> bool:
        return any(p.at_seat for p in self.persons)

    @property
    def visitors(self) -> list[Person]:
        return [p for p in self.persons if not p.at_seat and p.counted]


@dataclass
class Timeline:
    states: list[SecondState]
    tracks: list[Track]
    zones: Zones

    @property
    def duration(self) -> float:
        return self.states[-1].t if self.states else 0.0

    def runs(self, predicate: Callable[[SecondState], bool]) -> list[tuple[int, int]]:
        """Index ranges [start, end) of consecutive states where predicate holds."""
        result: list[tuple[int, int]] = []
        start = None
        for i, s in enumerate(self.states):
            if predicate(s) and start is None:
                start = i
            elif not predicate(s) and start is not None:
                result.append((start, i))
                start = None
        if start is not None:
            result.append((start, len(self.states)))
        return result

    def span_sec(self, run: tuple[int, int]) -> float:
        start, end = run
        if end - start <= 1:
            return 0.0
        return self.states[end - 1].t - self.states[start].t


def build_timeline(frame_ts: list[float], observations: list[Observation], tracks: list[Track], zones: Zones) -> Timeline:
    by_ts: dict[float, list[Observation]] = {}
    for o in observations:
        by_ts.setdefault(o.ts, []).append(o)
    states = [_state_at(ts, by_ts.get(ts, []), tracks, zones) for ts in frame_ts]
    return Timeline(states=states, tracks=[t for t in tracks if t.counted()], zones=zones)


def _state_at(ts: float, obs: list[Observation], tracks: list[Track], zones: Zones) -> SecondState:
    state = SecondState(t=ts)
    for track in tracks:
        box = track.box_at(ts)
        if box is None or not track.counted():
            continue
        c = center(box)
        state.persons.append(
            Person(
                track_id=track.id,
                center=c,
                at_seat=zones.at_cashier_seat(c),
                in_door=zones.in_door(c),
                first_seen=track.first_ts,
                entered=track.entered,
            )
        )
    monitors = [o for o in obs if o.kind == KIND_MONITOR]
    if monitors:
        state.monitor_visible = True
        state.screen_state = max(monitors, key=lambda o: o.score).attrs.get(ATTR_SCREEN_STATE, SCREEN_UNKNOWN)
    state.cash_on_desk = sum(1 for o in obs if o.kind == KIND_CASH and zones.on_desk(center(o.box)))
    state.bags_on_desk = sum(1 for o in obs if o.kind == KIND_BAG and zones.on_desk(center(o.box)))
    safes = [o for o in obs if o.kind == KIND_SAFE_OPEN]
    if safes:
        state.safe_open = True
        state.safe_center = center(max(safes, key=lambda o: o.score).box)
        state.person_at_safe = any(zones.near(p.center, state.safe_center) for p in state.persons)
    state.door_open = any(o.kind == KIND_DOOR_OPEN and zones.in_door(center(o.box)) for o in obs)
    return state
