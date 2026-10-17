from __future__ import annotations

import numpy as np

from app.settings import PersonVerifierConfig
from pipeline.clip_zero_shot import ClipZeroShot, crop
from pipeline.geometry import Box


class PersonVerifier:
    """CLIP vote per person crop: inside the room vs. reflection / behind the glass wall."""

    def __init__(self, cfg: PersonVerifierConfig, clip: ClipZeroShot):
        self.clip = clip
        self.bank = clip.prompt_bank(cfg.prompts)

    def classify(self, image: np.ndarray, box: Box) -> str | None:
        region = crop(image, box)
        if region is None:
            return None
        return self.clip.classify(region, self.bank)
