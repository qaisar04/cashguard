from __future__ import annotations

import copy
import logging

import numpy as np
import torch
from PIL import Image
from transformers import Owlv2ForObjectDetection, Owlv2Processor

from pipeline.detectors.base import Detection, resolve_device
from pipeline.geometry import clip

log = logging.getLogger(__name__)


class Owlv2Detector:
    """Open-vocabulary detector (Apache-2.0). Boxes are returned normalized to the original image."""

    def __init__(self, model_name: str, device: str, score_threshold: float, batch_size: int):
        self.device = resolve_device(device)
        self.threshold = score_threshold
        self.batch_size = batch_size
        self.processor = Owlv2Processor.from_pretrained(model_name)
        self.model = Owlv2ForObjectDetection.from_pretrained(model_name).to(self.device).eval()
        log.info("OWLv2 %s loaded on %s", model_name, self.device)

    def with_threshold(self, score_threshold: float) -> "Owlv2Detector":
        """Same loaded model, different score cut-off (static-object anchors score lower than cash or bags)."""
        clone = copy.copy(self)
        clone.threshold = score_threshold
        return clone

    def detect(self, images: list[np.ndarray], queries: dict[str, list[str]]) -> list[list[Detection]]:
        prompts, groups = _flatten(queries)
        results: list[list[Detection]] = []
        for start in range(0, len(images), self.batch_size):
            batch = images[start : start + self.batch_size]
            results.extend(self._detect_batch(batch, prompts, groups))
        return results

    @torch.inference_mode()
    def _detect_batch(self, images: list[np.ndarray], prompts: list[str], groups: list[str]) -> list[list[Detection]]:
        pil = [Image.fromarray(img[:, :, ::-1]) for img in images]
        inputs = self.processor(text=[prompts] * len(pil), images=pil, return_tensors="pt").to(self.device)
        outputs = self.model(**inputs)
        # OWLv2 pads every image to a square of its longest side; boxes come back in that square's pixels.
        sides = [max(img.shape[:2]) for img in images]
        target_sizes = torch.tensor([[s, s] for s in sides], device=self.device)
        processed = self.processor.post_process_grounded_object_detection(
            outputs, threshold=self.threshold, target_sizes=target_sizes, text_labels=[prompts] * len(pil)
        )
        detections: list[list[Detection]] = []
        for img, result in zip(images, processed):
            h, w = img.shape[:2]
            per_image = []
            for box, score, label in zip(result["boxes"], result["scores"], result["labels"]):
                x1, y1, x2, y2 = box.tolist()
                per_image.append(
                    Detection(group=groups[int(label)], box=clip((x1 / w, y1 / h, x2 / w, y2 / h)), score=float(score))
                )
            detections.append(per_image)
        return detections


def _flatten(queries: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    prompts: list[str] = []
    groups: list[str] = []
    for group, texts in queries.items():
        for text in texts:
            prompts.append(text)
            groups.append(group)
    return prompts, groups
