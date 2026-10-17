from __future__ import annotations

import logging
from statistics import median
from typing import Sequence

import cv2
import numpy as np

from app.settings import MachineConfig
from pipeline.geometry import Box
from pipeline.observers.base import ATTR_ACTION, ATTR_WINDOW, FULL_FRAME_BOX, KIND_ACTION, KIND_MACHINE, Observation
from pipeline.video import Frame

log = logging.getLogger(__name__)

ACTION_MACHINE_COUNTING = "machine_counting"
BLUR_KERNEL = (5, 5)


class MachineObserver:
    """Banknote-counting-machine activity from frame differencing inside the detected machine box.

    Notes moving through the counter (or hands loading it) produce a mean absolute difference of 7-33 between
    consecutive sampled frames versus 1-2 at rest, independent of the camera angle. Emits `machine_counting` actions.
    """

    name = "machine"

    def __init__(self, cfg: MachineConfig):
        self.cfg = cfg

    def observe(self, frames: list[Frame], prior: Sequence[Observation] = ()) -> list[Observation]:
        box = _machine_box(prior)
        if box is None or not frames:
            log.info("machine: no machine detected, no activity observations")
            return []
        h, w = frames[0].image.shape[:2]
        x1, y1, x2, y2 = int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)
        if x2 - x1 < 2 or y2 - y1 < 2:
            return []
        previous = None
        active: list[Observation] = []
        for frame in frames:
            gray = cv2.GaussianBlur(cv2.cvtColor(frame.image[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY), BLUR_KERNEL, 0)
            if previous is not None and previous.shape == gray.shape:
                diff = float(np.mean(cv2.absdiff(gray, previous)))
                if diff >= self.cfg.activity_threshold:
                    active.append(
                        Observation(
                            ts=frame.ts,
                            kind=KIND_ACTION,
                            box=box,
                            score=min(1.0, diff / self.cfg.activity_threshold / 2),
                            attrs={ATTR_ACTION: ACTION_MACHINE_COUNTING, ATTR_WINDOW: [frame.ts, frame.ts]},
                        )
                    )
            previous = gray
        log.info("machine: box %s, active in %d/%d frames", [round(v, 2) for v in box], len(active), len(frames))
        return active


def _machine_box(prior: Sequence[Observation]) -> Box | None:
    boxes = [o.box for o in prior if o.kind == KIND_MACHINE]
    if not boxes:
        return None
    return tuple(median(b[i] for b in boxes) for i in range(4))
