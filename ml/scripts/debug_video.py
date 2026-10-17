"""Runs the configured observer on one video and writes annotated frames + a JSON dump, for threshold/zone tuning.

Example: python scripts/debug_video.py ~/Downloads/open/videos/Х-22.mov --out debug/X-22 --max-frames 30
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from app.settings import load_pipeline_config
from app.state import _build_observers
from app.settings import Settings
from pipeline.analyzer import Analyzer
from pipeline.evidence import EvidenceBuilder
from pipeline.video import sample_frames
from rules.catalog import RuleCatalog


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--observer", default=None, help="detector | stub (default: ML_OBSERVER env)")
    args = parser.parse_args()

    settings = Settings(**({"observer": args.observer} if args.observer else {}))
    cfg = load_pipeline_config(settings.config_path)
    observers = _build_observers(settings, cfg)
    info, frames = sample_frames(args.video, cfg.video.fps, cfg.video.max_side)
    if args.max_frames:
        frames = frames[: args.max_frames]
    observations = []
    for observer in observers:
        observations.extend(observer.observe(frames, prior=tuple(observations)))

    args.out.mkdir(parents=True, exist_ok=True)
    builder = EvidenceBuilder(cfg.evidence.model_copy(update={"frames": 1, "max_side": 960, "draw_boxes": True}))
    for frame in frames:
        _, jpeg = builder.build([frame], observations, [frame.ts])[0]
        (args.out / f"{frame.ts:06.1f}.jpg").write_bytes(base64.b64decode(jpeg))
    dump = [{"ts": o.ts, "kind": o.kind, "box": [round(v, 4) for v in o.box], "score": round(o.score, 3), "attrs": o.attrs} for o in observations]
    (args.out / "observations.json").write_text(json.dumps(dump, ensure_ascii=False, indent=1), encoding="utf-8")

    analyzer = Analyzer(cfg, observers, RuleCatalog.load())
    events, meta = analyzer.analyze(args.video)
    (args.out / "events.json").write_text(
        json.dumps([{"type_id": e.type_id, "timecode_sec": e.timecode_sec, "description": e.description} for e in events], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"{len(frames)} frames, {len(observations)} observations, {len(events)} event(s) in {meta.elapsed_ms} ms -> {args.out}")
    for e in events:
        print(f"  {e.type_id} @ {e.timecode_sec}s")


if __name__ == "__main__":
    main()
