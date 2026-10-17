"""Writes a short synthetic .mov (moving rectangle) for smoke tests without the dataset."""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

WIDTH, HEIGHT, FPS = 464, 848, 30
BACKGROUND = (60, 60, 60)
PERSON_COLOR = (200, 170, 140)


def write(path: Path, seconds: int) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))
    if not writer.isOpened():
        raise RuntimeError("cannot open VideoWriter")
    for i in range(seconds * FPS):
        frame = np.full((HEIGHT, WIDTH, 3), BACKGROUND, dtype=np.uint8)
        cv2.rectangle(frame, (150, 380), (330, 470), (120, 100, 80), -1)  # desk
        cv2.rectangle(frame, (250, 330), (300, 380), (230, 230, 230), -1)  # laptop
        x = 230 if i < seconds * FPS // 2 else 40
        cv2.rectangle(frame, (x, 300), (x + 50, 420), PERSON_COLOR, -1)  # "person" leaves the seat halfway
        cv2.putText(frame, f"t={i / FPS:.1f}s", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        writer.write(frame)
    writer.release()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--seconds", type=int, default=12)
    args = parser.parse_args()
    write(args.output, args.seconds)
    print(f"wrote {args.output}")
