from __future__ import annotations

import base64
from dataclasses import dataclass

import cv2
import numpy as np

from app.settings import EvidenceConfig
from pipeline.geometry import Box, center
from pipeline.observers.base import (
    KIND_BAG,
    KIND_CASH,
    KIND_DOOR_OPEN,
    KIND_DRINK,
    KIND_MONITOR,
    KIND_PERSON,
    KIND_PERSONAL_ITEM,
    KIND_SAFE_OPEN,
    Observation,
)
from pipeline.timeline import ROLE_CASHIER, ROLE_VISITOR
from pipeline.tracking import Track
from pipeline.video import Frame
from pipeline.zones import Zones

# OpenCV's Hershey fonts have no Cyrillic glyphs, so on-frame labels are English.
LABELS = {
    KIND_MONITOR: "screen",
    KIND_CASH: "cash",
    KIND_BAG: "bag/folder",
    KIND_SAFE_OPEN: "open safe",
    KIND_DOOR_OPEN: "open door",
    KIND_PERSONAL_ITEM: "personal item",
    KIND_DRINK: "drink",
}
COLORS_BGR = {
    KIND_MONITOR: (0, 200, 255),
    KIND_CASH: (0, 200, 0),
    KIND_BAG: (200, 0, 200),
    KIND_SAFE_OPEN: (0, 0, 255),
    KIND_DOOR_OPEN: (0, 120, 255),
    KIND_PERSONAL_ITEM: (255, 0, 120),
    KIND_DRINK: (120, 200, 60),
}
IGNORED_REFLECTION = "reflection"
IGNORED_OUTSIDE = "outside"
ROLE_COLORS_BGR = {
    ROLE_CASHIER: (255, 160, 0),
    ROLE_VISITOR: (0, 80, 255),
}
IGNORED_COLOR_BGR = (150, 150, 150)
ZONE_DOOR = "door"
ZONE_GLASS = "glass"
ZONE_COLORS_BGR = {ZONE_DOOR: (0, 255, 255), ZONE_GLASS: (255, 0, 255)}
ZONE_THICKNESS = 1
IGNORED_LABEL_PREFIX = "ignored: "
BOX_THICKNESS = 2
IGNORED_BOX_THICKNESS = 1
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.5
IGNORED_FONT_SCALE = 0.4


@dataclass(frozen=True)
class PersonMark:
    """One person box on an evidence frame: the role the rules took it for, or the reason they ignored it."""

    track_id: int
    box: Box
    label: str
    counted: bool


PersonMarks = dict[float, list[PersonMark]]


def person_marks(tracks: list[Track], zones: Zones) -> PersonMarks:
    """Per timestamp, the person boxes the rules reasoned about (by role) and the ones they discarded (by reason).

    Raw person detections are never drawn: a reviewer must see the same people the rules saw.
    """
    marks: PersonMarks = {}
    for t in tracks:
        counted = t.counted()
        for ts, box in t.points:
            label = _role(box, zones) if counted else _ignored_reason(t)
            marks.setdefault(ts, []).append(PersonMark(track_id=t.id, box=box, label=label, counted=counted))
    return marks


def _role(box: Box, zones: Zones) -> str:
    return ROLE_CASHIER if zones.at_cashier_seat(center(box)) else ROLE_VISITOR


def _ignored_reason(t: Track) -> str:
    return IGNORED_REFLECTION if t.reflection else IGNORED_OUTSIDE


class EvidenceBuilder:
    def __init__(self, cfg: EvidenceConfig):
        self.cfg = cfg

    def build(
        self,
        frames: list[Frame],
        observations: list[Observation],
        timestamps: list[float],
        persons: PersonMarks | None = None,
    ) -> list[tuple[float, str]]:
        by_ts: dict[float, list[Observation]] = {}
        for o in observations:
            if o.kind != KIND_PERSON:
                by_ts.setdefault(o.ts, []).append(o)
        persons = persons or {}
        result: list[tuple[float, str]] = []
        seen: set[float] = set()
        for ts in timestamps[: self.cfg.frames]:
            frame = min(frames, key=lambda f: abs(f.ts - ts))
            if frame.ts in seen:
                continue
            seen.add(frame.ts)
            image = frame.image.copy()
            if self.cfg.draw_boxes:
                _draw_persons(image, persons.get(frame.ts, []))
                _draw(image, by_ts.get(frame.ts, []))
            result.append((round(frame.ts, 2), _encode(image, self.cfg)))
        return result


def _draw(image: np.ndarray, observations: list[Observation]) -> None:
    for o in observations:
        color = COLORS_BGR.get(o.kind)
        if color is None:
            continue
        label = LABELS.get(o.kind, o.kind)
        state = o.attrs.get("screen_state")
        if state:
            label = f"{label}: {state}"
        _draw_box(image, o.box, label, color, BOX_THICKNESS, FONT_SCALE)


def _draw_persons(image: np.ndarray, marks: list[PersonMark]) -> None:
    # ignored boxes first, so a counted person drawn over the same spot stays legible
    for m in sorted(marks, key=lambda m: m.counted):
        if m.counted:
            _draw_box(image, m.box, m.label, ROLE_COLORS_BGR[m.label], BOX_THICKNESS, FONT_SCALE)
        else:
            _draw_box(image, m.box, IGNORED_LABEL_PREFIX + m.label, IGNORED_COLOR_BGR, IGNORED_BOX_THICKNESS, IGNORED_FONT_SCALE)


def draw_zones(image: np.ndarray, zones: Zones) -> None:
    """Debug overlay: the entrance band and the reflection strip the tracker reasoned with (not for reviewer evidence)."""
    h, w = image.shape[:2]
    for name, polygon in ((ZONE_DOOR, zones.door), (ZONE_GLASS, zones.glass)):
        pts = np.array([[int(x * w), int(y * h)] for x, y in polygon.points], dtype=np.int32)
        cv2.polylines(image, [pts], True, ZONE_COLORS_BGR[name], ZONE_THICKNESS)
        cv2.putText(image, f"{name} ({zones.source})", (pts[-1][0] + 4, pts[-1][1] - 4), FONT, IGNORED_FONT_SCALE, ZONE_COLORS_BGR[name], 1, cv2.LINE_AA)


def _draw_box(image: np.ndarray, box: Box, label: str, color: tuple[int, int, int], thickness: int, font_scale: float) -> None:
    h, w = image.shape[:2]
    x1, y1, x2, y2 = int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)
    cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)
    cv2.putText(image, label, (x1, max(y1 - 4, 12)), FONT, font_scale, color, 1, cv2.LINE_AA)


def _encode(image: np.ndarray, cfg: EvidenceConfig) -> str:
    h, w = image.shape[:2]
    scale = cfg.max_side / max(h, w)
    if scale < 1:
        image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, cfg.jpeg_quality])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return base64.b64encode(buf.tobytes()).decode("ascii")
