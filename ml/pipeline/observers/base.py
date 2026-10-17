from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from pipeline.geometry import Box
from pipeline.video import Frame

KIND_PERSON = "person"
KIND_MONITOR = "monitor"
KIND_CASH = "cash"
KIND_BAG = "bag"
KIND_SAFE_OPEN = "safe_open"
KIND_DOOR_OPEN = "door_open"
KIND_GLASS = "glass"

ATTR_SCREEN_STATE = "screen_state"
SCREEN_OFF = "off"
SCREEN_LOCK = "lock_screen"
SCREEN_APPLICATION = "application"
SCREEN_DESKTOP = "desktop"
SCREEN_UNLOCKED_STATES = (SCREEN_APPLICATION, SCREEN_DESKTOP)
SCREEN_UNKNOWN = "unknown"


@dataclass(frozen=True)
class Observation:
    ts: float
    kind: str
    box: Box
    score: float
    attrs: dict = field(default_factory=dict)


class Observer(Protocol):
    name: str

    def observe(self, frames: list[Frame]) -> list[Observation]: ...
