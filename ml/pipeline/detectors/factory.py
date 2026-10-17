from __future__ import annotations

from app.settings import DetectorConfig
from pipeline.detectors.base import Detector

BACKEND_OWLV2 = "owlv2"
BACKEND_GROUNDING_DINO = "grounding_dino"
BACKEND_RTDETR = "rtdetr"


class UnknownDetectorBackend(ValueError):
    pass


def build_detector(cfg: DetectorConfig) -> Detector:
    if cfg.backend == BACKEND_OWLV2:
        from pipeline.detectors.owlv2 import Owlv2Detector

        return Owlv2Detector(cfg.model, cfg.device, cfg.score_threshold, cfg.batch_size)
    if cfg.backend == BACKEND_GROUNDING_DINO:
        from pipeline.detectors.grounding_dino import GroundingDinoDetector

        return GroundingDinoDetector(cfg.model, cfg.device, cfg.score_threshold, cfg.batch_size)
    if cfg.backend == BACKEND_RTDETR:
        from pipeline.detectors.rtdetr import RtDetrDetector

        return RtDetrDetector(cfg.model, cfg.device, cfg.score_threshold, cfg.batch_size)
    raise UnknownDetectorBackend(f"Unknown detector backend: {cfg.backend}")
