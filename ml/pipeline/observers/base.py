from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence

from pipeline.geometry import Box
from pipeline.video import Frame

KIND_PERSON = "person"
KIND_MONITOR = "monitor"
KIND_CASH = "cash"
KIND_BAG = "bag"
KIND_SAFE_OPEN = "safe_open"
KIND_DOOR_OPEN = "door_open"
KIND_PERSONAL_ITEM = "personal_item"
KIND_DRINK = "drink"
KIND_GLASS = "glass"
KIND_MACHINE = "machine"
KIND_SAFE_ATTENDED = "safe_attended"
KIND_ACTION = "action"

ATTR_SCREEN_STATE = "screen_state"
SCREEN_OFF = "off"
SCREEN_LOCK = "lock_screen"
SCREEN_APPLICATION = "application"
SCREEN_DESKTOP = "desktop"
SCREEN_UNLOCKED_STATES = (SCREEN_APPLICATION, SCREEN_DESKTOP)
SCREEN_UNKNOWN = "unknown"

STATE_OPEN = "open"
STATE_ATTENDED = "attended"  # open, with a person handling it: not "left open"
STATE_CLOSED = "closed"
ATTR_ACTION = "action"
ATTR_WINDOW = "window"
FULL_FRAME_BOX = (0.0, 0.0, 1.0, 1.0)


@dataclass(frozen=True)
class Observation:
    ts: float
    kind: str
    box: Box
    score: float
    attrs: dict = field(default_factory=dict)


class Observer(Protocol):
    name: str

    def observe(self, frames: list[Frame], prior: Sequence[Observation] = ()) -> list[Observation]:
        """`prior` holds the observations emitted by the observers that ran before this one."""
        ...
