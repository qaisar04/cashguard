"""Builds CLIP prototype embeddings for a crop-state classifier from labelled video spans.

  python scripts/build_prototypes.py --spec prototypes/screen_spans.yml --out prototypes/screen.npz
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import yaml

from app.settings import load_pipeline_config
from pipeline.clip_zero_shot import ClipZeroShot, crop
from pipeline.screen import panel_box
from pipeline.detectors.factory import build_detector
from pipeline.observers.base import KIND_MONITOR
from pipeline.video import sample_frames

CYRILLIC_KHA = "Х"
LATIN_X = "X"
SAMPLE_FPS = 1.0
DETECT_THRESHOLD = 0.5  # looser than the runtime threshold: more crops, the span label is trusted anyway


def find_video(videos_dir: Path, video_id: str) -> Path:
    wanted = video_id.upper().replace(CYRILLIC_KHA, LATIN_X)
    for path in videos_dir.iterdir():
        if path.suffix.lower() == ".mov" and path.stem.upper().replace(CYRILLIC_KHA, LATIN_X) == wanted:
            return path
    raise FileNotFoundError(video_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    spec = yaml.safe_load(args.spec.read_text(encoding="utf-8"))
    videos_dir = Path(spec["videos_dir"]).expanduser()
    cfg = load_pipeline_config()
    monitor_cfg = next(d for d in cfg.detectors if KIND_MONITOR in d.queries)
    detector = build_detector(monitor_cfg.model_copy(update={"score_threshold": DETECT_THRESHOLD}))
    clip = ClipZeroShot(cfg.screen.clip_model, monitor_cfg.device)

    embeddings: list[np.ndarray] = []
    labels: list[str] = []
    videos: list[str] = []
    cache: dict[str, tuple] = {}
    for span in spec["spans"]:
        video = find_video(videos_dir, span["video"])
        if video.name not in cache:
            _, frames = sample_frames(video, SAMPLE_FPS, cfg.video.max_side)
            dets = detector.detect([f.image for f in frames], {KIND_MONITOR: monitor_cfg.queries[KIND_MONITOR]})
            cache[video.name] = (frames, dets)
        frames, dets = cache[video.name]
        count = 0
        for frame, per_frame in zip(frames, dets):
            if not (span["start"] <= frame.ts <= span["end"]) or not per_frame:
                continue
            region = crop(frame.image, panel_box(max(per_frame, key=lambda d: d.score).box, cfg.screen.panel_fraction))
            if region is None:
                continue
            embeddings.append(clip.embed(region))
            labels.append(str(span["label"]))
            videos.append(span["video"])
            count += 1
        print(f"{span['video']} {span['start']}-{span['end']} {span['label']}: {count} crops")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.out, embeddings=np.stack(embeddings).astype(np.float16), labels=np.array(labels), videos=np.array(videos))
    print(f"{len(labels)} prototypes -> {args.out}")


if __name__ == "__main__":
    main()
