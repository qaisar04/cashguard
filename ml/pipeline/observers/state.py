from __future__ import annotations

from typing import Sequence

import logging
from collections import Counter
from dataclasses import dataclass

from app.settings import StateConfig
from pipeline.anchor import locate_anchor
from pipeline.clip_zero_shot import ClipZeroShot, crop
from pipeline.crop_state import STATE_UNKNOWN, CropStateClassifier, load_prototypes
from pipeline.detectors.base import Detector
from pipeline.observers.base import STATE_ATTENDED, STATE_CLOSED, STATE_OPEN, Observation
from pipeline.video import Frame

log = logging.getLogger(__name__)
KNOWN_STATES = (STATE_OPEN, STATE_ATTENDED, STATE_CLOSED)


@dataclass(frozen=True)
class StateProbe:
    """One static object: where to crop it, how to classify the crop, which observation kind an open state becomes."""

    name: str
    kind: str
    cfg: StateConfig
    classifier: CropStateClassifier


class StateObserver:
    """Emits `safe_open` / `door_open` boxes on the frames where the few-shot crop classifier says the object is open
    and unattended (an open safe with a hand in it is `attended`: being used, not left open)."""

    name = "state"

    def __init__(self, anchor_detector: Detector | None, probes: list[StateProbe]):
        self.anchor_detector = anchor_detector
        self.probes = probes

    def observe(self, frames: list[Frame], prior: Sequence[Observation] = ()) -> list[Observation]:
        observations: list[Observation] = []
        for probe in self.probes:
            box = locate_anchor(self.anchor_detector, frames, probe.cfg.anchor, probe.name, probe.classifier.similarity)
            labels = [self._classify(probe, frame, box) for frame in frames]
            labels = smooth(labels, probe.cfg.smooth_frames)
            open_frames = [frame for frame, label in zip(frames, labels) if label == STATE_OPEN]
            observations.extend(Observation(ts=f.ts, kind=probe.kind, box=box, score=1.0) for f in open_frames)
            log.info("%s state: %s", probe.name, dict(Counter(labels)))
        return observations

    @staticmethod
    def _classify(probe: StateProbe, frame: Frame, box) -> str:
        region = crop(frame.image, box)
        return STATE_UNKNOWN if region is None else probe.classifier.classify(region)


def smooth(labels: list[str], window: int) -> list[str]:
    """Majority vote over a centred window; a lone misclassified frame must not split an open run."""
    if window <= 1:
        return labels
    half = window // 2
    out = []
    for i in range(len(labels)):
        votes = Counter(labels[max(0, i - half) : i + half + 1])
        out.append(max(votes, key=lambda label: (votes[label], label == labels[i])))
    return out


def build_probe(name: str, kind: str, cfg: StateConfig, clip: ClipZeroShot) -> StateProbe | None:
    prototypes = load_prototypes(cfg.prototypes, name, cfg.embedding)
    if prototypes is None:
        log.warning("%s state classifier disabled: no prototypes", name)
        return None
    classifier = CropStateClassifier(prototypes, clip, cfg.knn_k, cfg.min_similarity, KNOWN_STATES)
    return StateProbe(name=name, kind=kind, cfg=cfg, classifier=classifier)
