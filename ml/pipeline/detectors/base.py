from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from pipeline.geometry import Box


@dataclass(frozen=True)
class Detection:
    group: str
    box: Box
    score: float


class Detector(Protocol):
    def detect(self, images: list[np.ndarray], queries: dict[str, list[str]]) -> list[list[Detection]]: ...


def resolve_device(requested: str) -> str:
    import torch

    if requested != "auto":
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"
