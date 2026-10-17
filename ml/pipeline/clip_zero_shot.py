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
        """Global image embedding: what the crop shows, regardless of where."""
        with self._torch.inference_mode():
            feats = _embedding(self.model.get_image_features(pixel_values=self._pixels(crop)))
            feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats[0].float().cpu().numpy()

    def embed_spatial(self, crop: np.ndarray) -> np.ndarray:
        """Grid of per-patch embeddings (unit vectors, flattened, unit norm): the dot product of two descriptors is the
        mean patch-wise cosine similarity, so a part of the crop that changes (a swung door) is not averaged away as it
        is in the global embedding."""
        with self._torch.inference_mode():
            vision = self.model.vision_model
            hidden = vision(pixel_values=self._pixels(crop)).last_hidden_state[0, 1:, :]
            tokens = self.model.visual_projection(vision.post_layernorm(hidden))
            tokens = tokens / tokens.norm(dim=-1, keepdim=True)
            flat = tokens.reshape(-1)
            flat = flat / flat.norm()
        return flat.float().cpu().numpy()

    def _pixels(self, crop: np.ndarray):
        from PIL import Image

        return self.processor(images=Image.fromarray(crop[:, :, ::-1]), return_tensors="pt").to(self.device)["pixel_values"]

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
