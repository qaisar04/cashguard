from __future__ import annotations

import logging

import cv2
import numpy as np

from app.settings import ScreenConfig
from pipeline.clip_zero_shot import ClipZeroShot, crop
from pipeline.crop_state import CropStateClassifier, load_prototypes
from pipeline.geometry import Box
from pipeline.observers.base import SCREEN_APPLICATION, SCREEN_DESKTOP, SCREEN_LOCK, SCREEN_OFF, SCREEN_UNKNOWN

log = logging.getLogger(__name__)
KNOWN_STATES = (SCREEN_APPLICATION, SCREEN_DESKTOP, SCREEN_LOCK, SCREEN_OFF)
PROTOTYPES_NAME = "screen"


def panel_box(box: Box, fraction: float) -> Box:
    """Upper part of a laptop/monitor box: the display panel, without keyboard and desk that dominate CLIP otherwise."""
    x1, y1, x2, y2 = box
    return (x1, y1, x2, y1 + (y2 - y1) * fraction)


class ScreenClassifier:
    """Visible state of a monitor crop: off / lock_screen / desktop / application.

    Few-shot mode: k-NN over CLIP embeddings of labelled crops from the dataset (same camera, same wallpaper).
    Fallback: luminance gate for dark screens + CLIP zero-shot text prompts (lock screen vs application).
    """

    def __init__(self, cfg: ScreenConfig, clip: ClipZeroShot):
        self.cfg = cfg
        self.clip = clip
        prototypes = load_prototypes(cfg.prototypes, PROTOTYPES_NAME, cfg.embedding)
        self.few_shot = (
            CropStateClassifier(prototypes, clip, cfg.knn_k, cfg.min_similarity, KNOWN_STATES) if prototypes else None
        )
        if self.few_shot is None:
            log.warning("screen classifier falls back to text prompts")
        self.bank = None if self.few_shot else clip.prompt_bank(cfg.prompts)

    def classify(self, image: np.ndarray, box: Box) -> str:
        region = crop(image, panel_box(box, self.cfg.panel_fraction))
        if region is None:
            return SCREEN_UNKNOWN
        if self.few_shot is not None:
            return self.few_shot.classify(region)
        if float(cv2.cvtColor(region, cv2.COLOR_BGR2GRAY).mean()) < self.cfg.min_luminance:
            return SCREEN_OFF
        label = self.clip.classify(region, self.bank)
        return label if label in (SCREEN_LOCK, SCREEN_APPLICATION) else SCREEN_UNKNOWN
