from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from app.settings import ROOT, ScreenConfig
from pipeline.clip_zero_shot import ClipZeroShot, crop
from pipeline.geometry import Box
from pipeline.observers.base import SCREEN_APPLICATION, SCREEN_DESKTOP, SCREEN_LOCK, SCREEN_OFF, SCREEN_UNKNOWN

log = logging.getLogger(__name__)
KNOWN_STATES = (SCREEN_APPLICATION, SCREEN_DESKTOP, SCREEN_LOCK, SCREEN_OFF)


def panel_box(box: Box, fraction: float) -> Box:
    """Upper part of a laptop/monitor box: the display panel, without keyboard and desk that dominate CLIP otherwise."""
    x1, y1, x2, y2 = box
    return (x1, y1, x2, y1 + (y2 - y1) * fraction)


class Prototypes:
    def __init__(self, path: Path):
        data = np.load(path)
        self.embeddings = data["embeddings"].astype(np.float32)
        self.labels = data["labels"]
        log.info("screen prototypes: %d crops from %s (%s)", len(self.labels), path.name, dict(Counter(self.labels.tolist())))

    def vote(self, embedding: np.ndarray, k: int, min_similarity: float) -> str:
        sims = self.embeddings @ embedding
        top = np.argsort(-sims)[:k]
        if float(sims[top[0]]) < min_similarity:
            return SCREEN_UNKNOWN
        votes = Counter(self.labels[top].tolist())
        return max(votes, key=votes.get)


class ScreenClassifier:
    """Visible state of a monitor crop: off / lock_screen / desktop / application.

    Few-shot mode: k-NN over CLIP embeddings of labelled crops from the dataset (same camera, same wallpaper).
    Fallback: luminance gate for dark screens + CLIP zero-shot text prompts (lock screen vs application).
    """

    def __init__(self, cfg: ScreenConfig, clip: ClipZeroShot):
        self.cfg = cfg
        self.clip = clip
        self.prototypes = _load_prototypes(cfg.prototypes)
        self.bank = None if self.prototypes else clip.prompt_bank(cfg.prompts)

    def classify(self, image: np.ndarray, box: Box) -> str:
        region = crop(image, panel_box(box, self.cfg.panel_fraction))
        if region is None:
            return SCREEN_UNKNOWN
        if self.prototypes is not None:
            label = self.prototypes.vote(self.clip.embed(region), self.cfg.knn_k, self.cfg.min_similarity)
            return label if label in KNOWN_STATES else SCREEN_UNKNOWN
        if float(cv2.cvtColor(region, cv2.COLOR_BGR2GRAY).mean()) < self.cfg.min_luminance:
            return SCREEN_OFF
        label = self.clip.classify(region, self.bank)
        return label if label in (SCREEN_LOCK, SCREEN_APPLICATION) else SCREEN_UNKNOWN


def _load_prototypes(path: Path | None) -> Prototypes | None:
    if path is None:
        return None
    resolved = path if path.is_absolute() else ROOT / path
    if not resolved.is_file():
        log.warning("screen prototypes %s not found, falling back to text prompts", resolved)
        return None
    return Prototypes(resolved)
