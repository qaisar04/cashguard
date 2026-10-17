from __future__ import annotations

import logging
from statistics import median
from typing import Callable

import numpy as np

from app.settings import AnchorConfig
from pipeline.clip_zero_shot import crop
from pipeline.detectors.base import Detection, Detector
from pipeline.geometry import Box, clip
from pipeline.video import Frame

log = logging.getLogger(__name__)
ANCHOR_GROUP = "anchor"

Verifier = Callable[[np.ndarray], float]  # crop -> similarity to the object's prototypes


def locate_anchor(
    detector: Detector | None, frames: list[Frame], cfg: AnchorConfig, name: str, verify: Verifier | None = None
) -> Box:
    """Median box of a static object over the video, padded for the crop; the configured box when detection fails.

    Open-vocabulary prompts also fire on look-alikes (a white pedestal for "a gray metal cabinet"), so each candidate
    crop is verified against the object's own prototypes and the best-matching candidate per frame is kept. Without a
    verifier (the first prototype build) only the primary query is trusted and the top-scoring box wins.
    """
    queries = cfg.queries if verify is not None else cfg.queries[:1]
    hits = _detect_hits(detector, frames, cfg, queries, verify) if queries and detector is not None else []
    if len(hits) < cfg.min_hits:
        log.info("%s anchor: %d hit(s) < %d, using fallback box", name, len(hits), cfg.min_hits)
        return tuple(cfg.fallback_box)
    box = tuple(median(h.box[i] for h in hits) for i in range(4))
    score = median(h.score for h in hits)
    log.info("%s anchor: %d hit(s), median score %.2f, box %s", name, len(hits), score, [round(v, 3) for v in box])
    return pad_box(box, cfg.pad)


def pad_box(box: Box, pad: float) -> Box:
    x1, y1, x2, y2 = box
    dx, dy = (x2 - x1) * pad, (y2 - y1) * pad
    return clip((x1 - dx, y1 - dy, x2 + dx, y2 + dy))


def _detect_hits(
    detector: Detector, frames: list[Frame], cfg: AnchorConfig, queries: list[str], verify: Verifier | None
) -> list[Detection]:
    sampled = frames[:: cfg.stride]
    hits: list[Detection] = []
    for frame, per_frame in zip(sampled, detector.detect([f.image for f in sampled], {ANCHOR_GROUP: queries})):
        candidates = [d for d in per_frame if d.score >= cfg.score_threshold]
        best = _best_candidate(frame, candidates, cfg, verify)
        if best is not None:
            hits.append(best)
    return hits


def _best_candidate(frame: Frame, candidates: list[Detection], cfg: AnchorConfig, verify: Verifier | None) -> Detection | None:
    if not candidates:
        return None
    if verify is None:
        return max(candidates, key=lambda d: d.score)
    scored: list[Detection] = []
    for det in candidates:
        region = crop(frame.image, pad_box(det.box, cfg.pad))
        if region is None:
            continue
        similarity = verify(region)
        if similarity >= cfg.min_similarity:
            scored.append(Detection(group=det.group, box=det.box, score=similarity))
    return max(scored, key=lambda d: d.score) if scored else None
