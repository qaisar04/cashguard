from __future__ import annotations

import logging

import numpy as np

from pipeline.detectors.base import resolve_device
from pipeline.geometry import Box

log = logging.getLogger(__name__)

MIN_CROP_SIDE_PX = 12


class ClipZeroShot:
    """One CLIP model shared by every crop classifier; each classifier registers its own prompt groups."""

    def __init__(self, model_name: str, device: str):
        import torch
        from transformers import CLIPModel, CLIPProcessor

        self.device = resolve_device(device)
        self.processor = CLIPProcessor.from_pretrained(model_name)
        self.model = CLIPModel.from_pretrained(model_name).to(self.device).eval()
        self._torch = torch
        log.info("CLIP %s loaded on %s", model_name, self.device)

    def prompt_bank(self, prompts: dict[str, list[str]]) -> "PromptBank":
        labels = list(prompts.keys())
        texts = [p for label in labels for p in prompts[label]]
        owners = [label for label in labels for _ in prompts[label]]
        with self._torch.inference_mode():
            tokens = self.processor(text=texts, return_tensors="pt", padding=True).to(self.device)
            feats = _embedding(self.model.get_text_features(**tokens))
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return PromptBank(feats, owners)

    def embed(self, crop: np.ndarray) -> np.ndarray:
        from PIL import Image

        with self._torch.inference_mode():
            inputs = self.processor(images=Image.fromarray(crop[:, :, ::-1]), return_tensors="pt").to(self.device)
            feats = _embedding(self.model.get_image_features(**inputs))
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats[0].float().cpu().numpy()

    def classify(self, crop: np.ndarray, bank: "PromptBank") -> str:
        feats = self._torch.from_numpy(self.embed(crop)).to(self.device)
        with self._torch.inference_mode():
            sims = (feats @ bank.features.T).tolist()
        best: dict[str, float] = {}
        for owner, sim in zip(bank.owners, sims):
            best[owner] = max(best.get(owner, -1.0), sim)
        return max(best, key=best.get)


class PromptBank:
    def __init__(self, features, owners: list[str]):
        self.features = features
        self.owners = owners


def crop(image: np.ndarray, box: Box) -> np.ndarray | None:
    h, w = image.shape[:2]
    x1, y1 = int(box[0] * w), int(box[1] * h)
    x2, y2 = int(box[2] * w), int(box[3] * h)
    if x2 - x1 < MIN_CROP_SIDE_PX or y2 - y1 < MIN_CROP_SIDE_PX:
        return None
    return image[y1:y2, x1:x2]


def _embedding(output):
    # transformers >= 5 returns a model output whose pooler_output holds the projected embedding; older versions return the tensor
    return getattr(output, "pooler_output", output)
