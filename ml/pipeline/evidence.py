from __future__ import annotations

import base64

import cv2
import numpy as np

from app.settings import EvidenceConfig
from pipeline.observers.base import KIND_BAG, KIND_CASH, KIND_DOOR_OPEN, KIND_MONITOR, KIND_PERSON, KIND_SAFE_OPEN, Observation
from pipeline.video import Frame

# OpenCV's Hershey fonts have no Cyrillic glyphs, so on-frame labels are English.
LABELS = {
    KIND_PERSON: "person",
    KIND_MONITOR: "screen",
    KIND_CASH: "cash",
    KIND_BAG: "bag/folder",
    KIND_SAFE_OPEN: "open safe",
    KIND_DOOR_OPEN: "open door",
}
COLORS_BGR = {
    KIND_PERSON: (255, 160, 0),
    KIND_MONITOR: (0, 200, 255),
    KIND_CASH: (0, 200, 0),
    KIND_BAG: (200, 0, 200),
    KIND_SAFE_OPEN: (0, 0, 255),
    KIND_DOOR_OPEN: (0, 120, 255),
}
BOX_THICKNESS = 2
FONT = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE = 0.5
TIMESTAMP_MARGIN = 10


class EvidenceBuilder:
    def __init__(self, cfg: EvidenceConfig):
        self.cfg = cfg

    def build(self, frames: list[Frame], observations: list[Observation], timestamps: list[float]) -> list[tuple[float, str]]:
        by_ts: dict[float, list[Observation]] = {}
        for o in observations:
            by_ts.setdefault(o.ts, []).append(o)
        result: list[tuple[float, str]] = []
        seen: set[float] = set()
        for ts in timestamps[: self.cfg.frames]:
            frame = min(frames, key=lambda f: abs(f.ts - ts))
            if frame.ts in seen:
                continue
            seen.add(frame.ts)
            image = frame.image.copy()
            if self.cfg.draw_boxes:
                _draw(image, by_ts.get(frame.ts, []))
            result.append((round(frame.ts, 2), _encode(image, self.cfg)))
        return result


def _draw(image: np.ndarray, observations: list[Observation]) -> None:
    h, w = image.shape[:2]
    for o in observations:
        color = COLORS_BGR.get(o.kind)
        if color is None:
            continue
        x1, y1, x2, y2 = int(o.box[0] * w), int(o.box[1] * h), int(o.box[2] * w), int(o.box[3] * h)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, BOX_THICKNESS)
        label = LABELS.get(o.kind, o.kind)
        state = o.attrs.get("screen_state")
        if state:
            label = f"{label}: {state}"
        cv2.putText(image, label, (x1, max(y1 - 4, 12)), FONT, FONT_SCALE, color, 1, cv2.LINE_AA)


def _encode(image: np.ndarray, cfg: EvidenceConfig) -> str:
    h, w = image.shape[:2]
    scale = cfg.max_side / max(h, w)
    if scale < 1:
        image = cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, cfg.jpeg_quality])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return base64.b64encode(buf.tobytes()).decode("ascii")
