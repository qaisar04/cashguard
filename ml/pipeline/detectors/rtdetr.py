from __future__ import annotations

import logging

import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, RTDetrForObjectDetection

from pipeline.detectors.base import Detection, resolve_device
from pipeline.geometry import clip

log = logging.getLogger(__name__)


class RtDetrDetector:
    """Closed-set COCO detector (Apache-2.0): robust people/laptops/bags; `queries` map group -> COCO class names."""

    def __init__(self, model_name: str, device: str, score_threshold: float, batch_size: int):
        self.device = resolve_device(device)
        self.threshold = score_threshold
        self.batch_size = batch_size
        self.processor = AutoImageProcessor.from_pretrained(model_name)
        self.model = RTDetrForObjectDetection.from_pretrained(model_name).to(self.device).eval()
        self.id2label = {int(k): v for k, v in self.model.config.id2label.items()}
        log.info("RT-DETR %s loaded on %s", model_name, self.device)

    def detect(self, images: list[np.ndarray], queries: dict[str, list[str]]) -> list[list[Detection]]:
        class_to_group = {name: group for group, names in queries.items() for name in names}
        results: list[list[Detection]] = []
        for start in range(0, len(images), self.batch_size):
            results.extend(self._detect_batch(images[start : start + self.batch_size], class_to_group))
        return results

    @torch.inference_mode()
    def _detect_batch(self, images: list[np.ndarray], class_to_group: dict[str, str]) -> list[list[Detection]]:
        pil = [Image.fromarray(img[:, :, ::-1]) for img in images]
        inputs = self.processor(images=pil, return_tensors="pt").to(self.device)
        outputs = self.model(**inputs)
        target_sizes = torch.tensor([img.shape[:2] for img in images], device=self.device)
        processed = self.processor.post_process_object_detection(outputs, threshold=self.threshold, target_sizes=target_sizes)
        detections: list[list[Detection]] = []
        for img, result in zip(images, processed):
            h, w = img.shape[:2]
            per_image = []
            for box, score, label in zip(result["boxes"], result["scores"], result["labels"]):
                group = class_to_group.get(self.id2label[int(label)])
                if group is None:
                    continue
                x1, y1, x2, y2 = box.tolist()
                per_image.append(Detection(group=group, box=clip((x1 / w, y1 / h, x2 / w, y2 / h)), score=float(score)))
            detections.append(per_image)
        return detections
