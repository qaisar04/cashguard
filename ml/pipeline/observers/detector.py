from __future__ import annotations

import logging
from typing import Sequence

from app.settings import DetectorConfig
from pipeline.detectors.base import Detector
from pipeline.observers.base import ATTR_SCREEN_STATE, KIND_MONITOR, KIND_PERSON, Observation
from pipeline.person_verifier import PersonVerifier
from pipeline.screen import ScreenClassifier
from pipeline.tracking import ATTR_INSIDE
from pipeline.video import Frame

log = logging.getLogger(__name__)


class DetectorObserver:
    """Emits per-frame boxes from one or more detectors (each with its own query groups); monitors carry a screen_state."""

    name = "detector"

    def __init__(
        self,
        detectors: list[tuple[Detector, DetectorConfig]],
        screen: ScreenClassifier | None,
        person_verifier: PersonVerifier | None = None,
    ):
        self.detectors = detectors
        self.screen = screen
        self.person_verifier = person_verifier

    def observe(self, frames: list[Frame], prior: Sequence[Observation] = ()) -> list[Observation]:
        images = [f.image for f in frames]
        per_frame: list[list] = [[] for _ in frames]
        for detector, cfg in self.detectors:
            sampled = list(range(0, len(frames), cfg.frame_stride))
            results = detector.detect([images[i] for i in sampled], cfg.queries)
            for i in range(len(frames)):
                # static things (cash, bags, glazing) do not move between adjacent seconds: reuse the nearest processed frame
                nearest = min(range(len(sampled)), key=lambda k: abs(sampled[k] - i))
                per_frame[i].extend(d for d in results[nearest] if cfg.passes(d.group, d.score))
        observations: list[Observation] = []
        for frame, detections in zip(frames, per_frame):
            for det in detections:
                attrs = {}
                if det.group == KIND_MONITOR and self.screen is not None:
                    attrs[ATTR_SCREEN_STATE] = self.screen.classify(frame.image, det.box)
                if det.group == KIND_PERSON and self.person_verifier is not None:
                    label = self.person_verifier.classify(frame.image, det.box)
                    if label is not None:
                        attrs[ATTR_INSIDE] = label
                observations.append(Observation(ts=frame.ts, kind=det.group, box=det.box, score=det.score, attrs=attrs))
        log.info("detector: %d frames -> %d observations", len(frames), len(observations))
        return observations
