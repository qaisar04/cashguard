from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


class VideoReadError(RuntimeError):
    pass


@dataclass(frozen=True)
class Frame:
    index: int
    ts: float
    image: np.ndarray  # BGR, already downscaled

    @property
    def height(self) -> int:
        return self.image.shape[0]

    @property
    def width(self) -> int:
        return self.image.shape[1]


@dataclass(frozen=True)
class VideoInfo:
    native_fps: float
    frame_count: int
    width: int
    height: int

    @property
    def duration_sec(self) -> float:
        return self.frame_count / self.native_fps if self.native_fps else 0.0


def probe(path: Path) -> VideoInfo:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise VideoReadError(f"Cannot open video: {path}")
    try:
        return VideoInfo(
            native_fps=cap.get(cv2.CAP_PROP_FPS) or 0.0,
            frame_count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
    finally:
        cap.release()


def sample_frames(path: Path, target_fps: float, max_side: int) -> tuple[VideoInfo, list[Frame]]:
    info = probe(path)
    if info.native_fps <= 0:
        raise VideoReadError(f"Video reports no frame rate: {path}")
    step = max(1, round(info.native_fps / target_fps))
    cap = cv2.VideoCapture(str(path))
    frames: list[Frame] = []
    try:
        index = 0
        while True:
            ok, image = cap.read()
            if not ok:
                break
            if index % step == 0:
                frames.append(Frame(index=index, ts=index / info.native_fps, image=_downscale(image, max_side)))
            index += 1
    finally:
        cap.release()
    if not frames:
        raise VideoReadError(f"Video contains no decodable frames: {path}")
    return info, frames


def _downscale(image: np.ndarray, max_side: int) -> np.ndarray:
    h, w = image.shape[:2]
    scale = max_side / max(h, w)
    if scale >= 1:
        return image
    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
