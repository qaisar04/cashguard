from __future__ import annotations

import logging

import numpy as np
import torch
from PIL import Image
from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor

from pipeline.detectors.base import Detection, resolve_device
from pipeline.geometry import clip

log = logging.getLogger(__name__)

PHRASE_SEPARATOR = ". "


class GroundingDinoDetector:
    """Alternative open-vocabulary detector (Apache-2.0), slower but often more precise than OWLv2."""

    def __init__(self, model_name: str, device: str, score_threshold: float, batch_size: int):
        self.device = resolve_device(device)
        self.threshold = score_threshold
        self.batch_size = batch_size
        self.processor = AutoProcessor.from_pretrained(model_name)
        self.model = AutoModelForZeroShotObjectDetection.from_pretrained(model_name).to(self.device).eval()
        log.info("GroundingDINO %s loaded on %s", model_name, self.device)

    def detect(self, images: list[np.ndarray], queries: dict[str, list[str]]) -> list[list[Detection]]:
        phrase_to_group = {text.lower().strip("."): group for group, texts in queries.items() for text in texts}
        text = PHRASE_SEPARATOR.join(phrase_to_group.keys()) + "."
        results: list[list[Detection]] = []
        for start in range(0, len(images), self.batch_size):
            batch = images[start : start + self.batch_size]
            results.extend(self._detect_batch(batch, text, phrase_to_group))
        return results

    @torch.inference_mode()
    def _detect_batch(self, images: list[np.ndarray], text: str, phrase_to_group: dict[str, str]) -> list[list[Detection]]:
        pil = [Image.fromarray(img[:, :, ::-1]) for img in images]
        inputs = self.processor(images=pil, text=[text] * len(pil), return_tensors="pt").to(self.device)
        outputs = self.model(**inputs)
        target_sizes = [img.shape[:2] for img in images]
        processed = self.processor.post_process_grounded_object_detection(
            outputs, inputs.input_ids, threshold=self.threshold, text_threshold=self.threshold, target_sizes=target_sizes
        )
        detections: list[list[Detection]] = []
        for img, result in zip(images, processed):
            h, w = img.shape[:2]
            per_image = []
            labels = result.get("text_labels") or result.get("labels")
            for box, score, label in zip(result["boxes"], result["scores"], labels):
                group = _match_group(str(label), phrase_to_group)
                if group is None:
                    continue
                x1, y1, x2, y2 = box.tolist()
                per_image.append(Detection(group=group, box=clip((x1 / w, y1 / h, x2 / w, y2 / h)), score=float(score)))
            detections.append(per_image)
        return detections


def _match_group(label: str, phrase_to_group: dict[str, str]) -> str | None:
    label = label.lower()
    for phrase, group in phrase_to_group.items():
        if phrase in label or label in phrase:
            return group
    return None
