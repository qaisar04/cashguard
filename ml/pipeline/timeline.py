from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from pipeline.geometry import Box, Point, center, distance, iou
from pipeline.observers.base import (
    ATTR_ACTION,
    ATTR_SCREEN_STATE,
    ATTR_WINDOW,
    KIND_ACTION,
    KIND_BAG,
    KIND_CASH,
    KIND_DOOR_OPEN,
    KIND_DRINK,
    KIND_MONITOR,
    KIND_PERSON,
    KIND_PERSONAL_ITEM,
    KIND_SAFE_OPEN,
    SCREEN_UNKNOWN,
    Observation,
)
from pipeline.tracking import Track
from pipeline.zones import Zones

SAME_OBJECT_IOU = 0.3
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
    personal_items_on_desk: int = 0
    drinks_on_desk: int = 0
    safe_open: bool = False
    safe_center: Point | None = None
    person_at_safe: bool = False
    door_open: bool = False
    actions: list[str] = field(default_factory=list)

    def has_action(self, *actions: str) -> bool:
        return any(a in self.actions for a in actions)

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


def person_left_at(states: list[SecondState], gone_sec: float, open_ended: bool = False) -> float | None:
    """Start of a stretch where fewer people are in the room than during an earlier stretch with 2+ people.

    Both stretches must hold for `gone_sec` (shorter changes are track dropouts or reflections); with `open_ended`
    a drop that lasts until the final state counts even if it is shorter.
    """
    peak = 0
    for start, end, count in _count_runs(states):
        stable = end - start >= gone_sec or (open_ended and end == states[-1].t)
        if count >= peak:
            peak = count if end - start >= gone_sec else peak
        elif peak >= 2 and stable:
            return start
    return None


def _count_runs(states: list[SecondState]) -> list[tuple[float, float, int]]:
    runs: list[tuple[float, float, int]] = []
    for s in states:
        n = len(s.persons)
        if runs and runs[-1][2] == n:
            runs[-1] = (runs[-1][0], s.t, n)
        else:
            runs.append((s.t, s.t, n))
    return runs


def build_timeline(frame_ts: list[float], observations: list[Observation], tracks: list[Track], zones: Zones) -> Timeline:
    by_ts: dict[float, list[Observation]] = {}
    actions = [o for o in observations if o.kind == KIND_ACTION]
    for o in observations:
        if o.kind != KIND_ACTION:
            by_ts.setdefault(o.ts, []).append(o)
    states = []
    for i, ts in enumerate(frame_ts):
        neighbours = [o for j in (i - 1, i + 1) if 0 <= j < len(frame_ts) for o in by_ts.get(frame_ts[j], [])]
        states.append(_state_at(ts, by_ts.get(ts, []), neighbours, tracks, zones))
    for state in states:
        state.actions = _actions_at(state.t, actions)
    return Timeline(states=states, tracks=[t for t in tracks if t.counted()], zones=zones)


def _actions_at(ts: float, actions: list[Observation]) -> list[str]:
    """An action observation covers every second of its window [start, end]."""
    active: set[str] = set()
    for o in actions:
        start, end = o.attrs.get(ATTR_WINDOW, [o.ts, o.ts])
        if start <= ts <= end:
            active.add(o.attrs[ATTR_ACTION])
    return sorted(active)


def _state_at(ts: float, obs: list[Observation], neighbours: list[Observation], tracks: list[Track], zones: Zones) -> SecondState:
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
    state.personal_items_on_desk = sum(1 for o in _resting_personal_items(obs, neighbours) if _near_cashier(center(o.box), state, zones))
    state.drinks_on_desk = sum(1 for o in obs if o.kind == KIND_DRINK and _near_cashier(center(o.box), state, zones))
    safes = [o for o in obs if o.kind == KIND_SAFE_OPEN]
    if safes:
        state.safe_open = True
        state.safe_center = center(max(safes, key=lambda o: o.score).box)
        # the cashier seat is next to the safe: only someone standing at it (not seated at the desk) counts as "at the safe"
        state.person_at_safe = any(zones.near(p.center, state.safe_center) and not p.at_seat for p in state.persons)
    state.door_open = any(o.kind == KIND_DOOR_OPEN and zones.in_door(center(o.box)) for o in obs)
    return state


def _resting_personal_items(obs: list[Observation], neighbours: list[Observation]) -> list[Observation]:
    """A bag carried past the desk moves between frames; a cash bag is valuables, not a personal item."""
    valuables = [o.box for o in obs if o.kind == KIND_BAG]
    nearby = [o.box for o in neighbours if o.kind == KIND_PERSONAL_ITEM]
    return [
        o for o in obs if o.kind == KIND_PERSONAL_ITEM and not _same_object(o.box, valuables) and _same_object(o.box, nearby)
    ]


def _same_object(box: Box, others: list[Box]) -> bool:
    return any(iou(box, other) >= SAME_OBJECT_IOU for other in others)


def _near_cashier(p: Point, state: SecondState, zones: Zones) -> bool:
    """On the desk and within the seat radius of the person sitting at the cashier's seat."""
    if not zones.on_desk(p):
        return False
    return any(person.at_seat and distance(p, person.center, zones.aspect) <= zones.cashier_radius for person in state.persons)
