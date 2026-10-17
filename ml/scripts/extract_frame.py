"""Dumps a frame at a timestamp with a normalized grid, to pick zone coordinates for config.yml."""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2

GRID_STEPS = 10
GRID_COLOR = (0, 255, 255)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--ts", type=float, default=0.0)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    cap = cv2.VideoCapture(str(args.video))
    cap.set(cv2.CAP_PROP_POS_MSEC, args.ts * 1000)
    ok, img = cap.read()
    cap.release()
    if not ok:
        raise SystemExit(f"cannot read frame at {args.ts}s")
    h, w = img.shape[:2]
    for i in range(1, GRID_STEPS):
        x, y = int(w * i / GRID_STEPS), int(h * i / GRID_STEPS)
        cv2.line(img, (x, 0), (x, h), GRID_COLOR, 1)
        cv2.line(img, (0, y), (w, y), GRID_COLOR, 1)
        cv2.putText(img, f"{i / GRID_STEPS:.1f}", (x + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, GRID_COLOR, 1)
        cv2.putText(img, f"{i / GRID_STEPS:.1f}", (2, y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, GRID_COLOR, 1)
    cv2.imwrite(str(args.out), img)
    print(f"wrote {args.out} ({w}x{h})")


if __name__ == "__main__":
    main()
