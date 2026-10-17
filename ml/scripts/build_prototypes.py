"""Builds CLIP prototype embeddings for a crop-state classifier (screen, safe, door) from labelled video spans.

  python scripts/build_prototypes.py --target screen --spec prototypes/screen_spans.yml --out prototypes/screen.npz
  python scripts/build_prototypes.py --target safe --spec prototypes/safe_spans.yml --out prototypes/safe.npz --lovo
  python scripts/build_prototypes.py --target door --sheet debug/sheets --videos X-30,X-31   # crops per second, to pick spans
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
import yaml

from app.settings import PipelineConfig, load_pipeline_config
from pipeline.anchor import locate_anchor
from pipeline.clip_zero_shot import ClipZeroShot, crop
from pipeline.crop_state import Embedder, Prototypes, embedder
from pipeline.detectors.factory import BACKEND_OWLV2, build_detector
from pipeline.geometry import Box
from pipeline.observers.base import KIND_MONITOR
from pipeline.observers.state import build_probe
from pipeline.screen import panel_box
from pipeline.video import Frame, sample_frames

CYRILLIC_KHA = "Х"
LATIN_X = "X"
SAMPLE_FPS = 1.0
DETECT_THRESHOLD = 0.5  # looser than the runtime threshold: more crops, the span label is trusted anyway
TARGET_SCREEN = "screen"
TARGET_SAFE = "safe"
TARGET_DOOR = "door"
TARGETS = (TARGET_SCREEN, TARGET_SAFE, TARGET_DOOR)
SHEET_TILE_W = 160
SHEET_COLS = 10
SHEET_LABEL_COLOR = (0, 0, 255)

CropFn = Callable[[list[Frame]], list[Box | None]]
DEFAULT_STEP = 1  # every n-th second of a span; long static spans need no more than one crop every few seconds


def find_video(videos_dir: Path, video_id: str) -> Path:
    wanted = video_id.upper().replace(CYRILLIC_KHA, LATIN_X)
    for path in videos_dir.iterdir():
        if path.suffix.lower() == ".mov" and path.stem.upper().replace(CYRILLIC_KHA, LATIN_X) == wanted:
            return path
    raise FileNotFoundError(video_id)


def build_crop_fn(target: str, cfg: PipelineConfig, clip: ClipZeroShot) -> CropFn:
    if target == TARGET_SCREEN:
        monitor_cfg = next(d for d in cfg.detectors if KIND_MONITOR in d.queries)
        detector = build_detector(monitor_cfg.model_copy(update={"score_threshold": DETECT_THRESHOLD}))

        def monitor_boxes(frames: list[Frame]) -> list[Box | None]:
            dets = detector.detect([f.image for f in frames], {KIND_MONITOR: monitor_cfg.queries[KIND_MONITOR]})
            return [panel_box(max(d, key=lambda x: x.score).box, cfg.screen.panel_fraction) if d else None for d in dets]

        return monitor_boxes
    state_cfg = cfg.safe if target == TARGET_SAFE else cfg.door
    owl_cfg = next((d for d in cfg.detectors if d.backend == BACKEND_OWLV2), None)
    owl = build_detector(owl_cfg.model_copy(update={"score_threshold": state_cfg.anchor.score_threshold})) if owl_cfg else None
    probe = build_probe(target, target, state_cfg, clip)
    if probe is None:
        print(f"{target}: no prototypes yet, anchor candidates are not verified (first build)")

    def anchor_boxes(frames: list[Frame]) -> list[Box | None]:
        box = locate_anchor(owl, frames, state_cfg.anchor, target, probe.classifier.similarity if probe else None)
        return [box] * len(frames)

    return anchor_boxes


class CropCache:
    def __init__(self, videos_dir: Path, crop_fn: CropFn, max_side: int):
        self.videos_dir = videos_dir
        self.crop_fn = crop_fn
        self.max_side = max_side
        self._cache: dict[str, list[tuple[Frame, np.ndarray | None]]] = {}

    def crops(self, video_id: str) -> list[tuple[Frame, np.ndarray | None]]:
        key = video_id.upper().replace(CYRILLIC_KHA, LATIN_X)
        if key not in self._cache:
            _, frames = sample_frames(find_video(self.videos_dir, video_id), SAMPLE_FPS, self.max_side)
            boxes = self.crop_fn(frames)
            self._cache[key] = [(f, crop(f.image, b) if b is not None else None) for f, b in zip(frames, boxes)]
        return self._cache[key]


def write_sheet(video_id: str, crops: list[tuple[Frame, np.ndarray | None]], out_dir: Path) -> None:
    tiles = []
    for frame, region in crops:
        if region is None:
            continue
        tile = cv2.resize(region, (SHEET_TILE_W, int(SHEET_TILE_W * region.shape[0] / region.shape[1])))
        cv2.putText(tile, f"{frame.ts:.0f}", (3, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, SHEET_LABEL_COLOR, 1)
        tiles.append(tile)
    if not tiles:
        print(f"{video_id}: no crops")
        return
    height = max(t.shape[0] for t in tiles)
    tiles = [cv2.copyMakeBorder(t, 0, height - t.shape[0], 0, 2, cv2.BORDER_CONSTANT) for t in tiles]
    blank = np.zeros_like(tiles[0])
    tiles += [blank] * (-len(tiles) % SHEET_COLS)
    rows = [np.hstack(tiles[i : i + SHEET_COLS]) for i in range(0, len(tiles), SHEET_COLS)]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{video_id}.jpg"
    cv2.imwrite(str(path), np.vstack(rows))
    print(f"{video_id}: {len(crops)} crops -> {path}")


def embed_spans(spec: dict, cache: CropCache, embed: Embedder) -> tuple[list[np.ndarray], list[str], list[str]]:
    embeddings: list[np.ndarray] = []
    labels: list[str] = []
    videos: list[str] = []
    for span in spec["spans"]:
        count = 0
        step = int(span.get("step", DEFAULT_STEP))
        for frame, region in cache.crops(span["video"]):
            if region is None or not (span["start"] <= frame.ts <= span["end"]) or round(frame.ts - span["start"]) % step:
                continue
            embeddings.append(embed(region))
            labels.append(str(span["label"]))
            videos.append(span["video"])
            count += 1
        print(f"{span['video']} {span['start']}-{span['end']} {span['label']}: {count} crops")
    return embeddings, labels, videos


def leave_one_video_out(embeddings: np.ndarray, labels: np.ndarray, videos: np.ndarray, k: int) -> None:
    """k-NN accuracy per label when the crop's own video is excluded from the prototypes."""
    correct: Counter = Counter()
    total: Counter = Counter()
    confusion: dict[str, Counter] = defaultdict(Counter)
    nearest: list[float] = []
    for i in range(len(labels)):
        mask = videos != videos[i]
        if not mask.any():
            continue
        sims = embeddings[mask] @ embeddings[i]
        top = np.argsort(-sims)[:k]
        nearest.append(float(sims[top[0]]))
        votes = Counter(labels[mask][top].tolist())
        predicted = max(votes, key=votes.get)
        total[labels[i]] += 1
        correct[labels[i]] += predicted == labels[i]
        confusion[labels[i]][predicted] += 1
    for label in sorted(total):
        print(f"LOVO {label}: {correct[label]}/{total[label]} = {correct[label] / total[label]:.2f}  predicted as {dict(confusion[label])}")
    print(f"LOVO overall: {sum(correct.values())}/{sum(total.values())} = {sum(correct.values()) / max(1, sum(total.values())):.2f}")
    print(f"LOVO nearest-neighbour similarity: min {min(nearest):.3f}, p5 {np.percentile(nearest, 5):.3f}, median {np.median(nearest):.3f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=TARGETS, required=True)
    parser.add_argument("--spec", type=Path, help="labelled spans (videos_dir, spans: video/start/end/label)")
    parser.add_argument("--out", type=Path, help="prototype .npz to write")
    parser.add_argument("--lovo", action="store_true", help="report leave-one-video-out k-NN accuracy per label")
    parser.add_argument("--sheet", type=Path, help="write one contact sheet of crops per video (every sampled second)")
    parser.add_argument("--videos", default="", help="comma-separated video ids for --sheet (default: videos of the spec)")
    parser.add_argument("--videos-dir", type=Path, default=None)
    args = parser.parse_args()
    spec = yaml.safe_load(args.spec.read_text(encoding="utf-8")) if args.spec else {"spans": []}
    videos_dir = (args.videos_dir or Path(spec["videos_dir"])).expanduser()
    cfg = load_pipeline_config()
    clip = ClipZeroShot(cfg.screen.clip_model, cfg.detectors[0].device)
    cache = CropCache(videos_dir, build_crop_fn(args.target, cfg, clip), cfg.video.max_side)

    if args.sheet:
        ids = [v for v in args.videos.split(",") if v] or sorted({s["video"] for s in spec["spans"]})
        for video_id in ids:
            write_sheet(video_id, cache.crops(video_id), args.sheet)
    if not args.spec:
        return
    target_cfg = {TARGET_SCREEN: cfg.screen, TARGET_SAFE: cfg.safe, TARGET_DOOR: cfg.door}[args.target]
    embeddings, labels, videos = embed_spans(spec, cache, embedder(clip, target_cfg.embedding))
    prototypes = Prototypes(np.stack(embeddings).astype(np.float16), np.array(labels), target_cfg.embedding)
    if args.lovo:
        leave_one_video_out(prototypes.embeddings, prototypes.labels, np.array(videos), target_cfg.knn_k)
    if args.out:
        prototypes.save(args.out, np.array(videos))
        print(f"{len(labels)} {target_cfg.embedding} prototypes -> {args.out}")


if __name__ == "__main__":
    main()
