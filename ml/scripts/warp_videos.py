"""Writes perspective-warped copies of videos (±15° rotation + skew) for the robustness check.

  python scripts/warp_videos.py --videos-dir ~/Downloads/open/videos --out eval/warped --ids X-4 X-11 ...
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from scripts.evaluate import find_video

ROTATION_DEG = 15.0
SKEW = 0.08           # fraction of width/height moved at the corners
FOURCC = "mp4v"


def warp_matrix(w: int, h: int, sign: int) -> np.ndarray:
    rotation = cv2.getRotationMatrix2D((w / 2, h / 2), sign * ROTATION_DEG, 1.0)
    rotation = np.vstack([rotation, [0, 0, 1]])
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dx, dy = SKEW * w, SKEW * h
    dst = np.float32([[dx * (sign > 0), dy], [w - dx * (sign < 0), 0], [w, h - dy], [dx, h]])
    skew = cv2.getPerspectiveTransform(src, dst)
    return skew @ rotation


def warp_video(src: Path, dst: Path, sign: int) -> None:
    cap = cv2.VideoCapture(str(src))
    fps = cap.get(cv2.CAP_PROP_FPS)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    matrix = warp_matrix(w, h, sign)
    writer = cv2.VideoWriter(str(dst), cv2.VideoWriter_fourcc(*FOURCC), fps, (w, h))
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        writer.write(cv2.warpPerspective(frame, matrix, (w, h), borderMode=cv2.BORDER_REPLICATE))
    cap.release()
    writer.release()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--videos-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ids", nargs="+", required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for i, video_id in enumerate(args.ids):
        src = find_video(args.videos_dir, video_id)
        if src is None:
            print(f"{video_id}: not found")
            continue
        sign = 1 if i % 2 == 0 else -1
        dst = args.out / f"{video_id.upper().replace('Х', 'X')}.mov"
        warp_video(src, dst, sign)
        print(f"{video_id}: rotation {sign * ROTATION_DEG:+.0f}°, skew {SKEW} -> {dst}")


if __name__ == "__main__":
    main()
