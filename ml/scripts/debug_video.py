"""Runs the configured observer on one video and writes annotated frames + a JSON dump, for threshold/zone tuning.

Example: python scripts/debug_video.py ~/Downloads/open/videos/Х-22.mov --out debug/X-22 --max-frames 30

Person boxes are drawn the way the rules saw them: `cashier` / `visitor` for counted tracks, muted
`ignored: reflection` / `ignored: outside` for tracks the rules discarded. `--observer stub --fixture
<dir>/observations.json` replays an earlier dump without running the detectors.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

import cv2
import numpy as np

from app.settings import Settings, load_pipeline_config
from app.state import _build_observer
from pipeline.analyzer import Analyzer
from pipeline.evidence import EvidenceBuilder, draw_zones
from pipeline.video import sample_frames
from rules.catalog import RuleCatalog

DEBUG_MAX_SIDE = 960


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--observer", default=None, help="detector | stub (default: ML_OBSERVER env)")
    parser.add_argument("--fixture", type=Path, default=None, help="observations.json for --observer stub (default: ML_STUB_FIXTURE env)")
    args = parser.parse_args()

    overrides = {k: v for k, v in (("observer", args.observer), ("stub_fixture", args.fixture)) if v}
    settings = Settings(**overrides)
    cfg = load_pipeline_config(settings.config_path)
    observer = _build_observer(settings, cfg)
    info, frames = sample_frames(args.video, cfg.video.fps, cfg.video.max_side)
    if args.max_frames:
        frames = frames[: args.max_frames]
    observations = observer.observe(frames)
    aspect = info.width / info.height if info.height else 1.0
    analysis = Analyzer(cfg, [observer], RuleCatalog.load()).analyze_observations(frames, observations, aspect)

    args.out.mkdir(parents=True, exist_ok=True)
    builder = EvidenceBuilder(cfg.evidence.model_copy(update={"frames": 1, "max_side": DEBUG_MAX_SIDE, "draw_boxes": True}))
    for frame in frames:
        _, jpeg = builder.build([frame], observations, [frame.ts], analysis.persons)[0]
        image = cv2.imdecode(np.frombuffer(base64.b64decode(jpeg), np.uint8), cv2.IMREAD_COLOR)
        draw_zones(image, analysis.zones)
        cv2.imwrite(str(args.out / f"{frame.ts:06.1f}.jpg"), image)
    dump = [{"ts": o.ts, "kind": o.kind, "box": [round(v, 4) for v in o.box], "score": round(o.score, 3), "attrs": o.attrs} for o in observations]
    (args.out / "observations.json").write_text(json.dumps(dump, ensure_ascii=False, indent=1), encoding="utf-8")
    events = analysis.events
    (args.out / "events.json").write_text(
        json.dumps([{"type_id": e.type_id, "timecode_sec": e.timecode_sec, "description": e.description} for e in events], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    for i, e in enumerate(events):
        for ts, jpeg in e.evidence:
            (args.out / f"evidence_{i}_{e.type_id}_{ts:06.1f}.jpg").write_bytes(base64.b64decode(jpeg))
    zones = analysis.zones
    print(f"zones ({zones.source}): door={[tuple(round(v, 2) for v in p) for p in zones.door.points]} glass={[tuple(round(v, 2) for v in p) for p in zones.glass.points]}")
    print(f"{len(frames)} frames, {len(observations)} observations, {len(events)} event(s) -> {args.out}")
    for e in events:
        print(f"  {e.type_id} @ {e.timecode_sec}s")


if __name__ == "__main__":
    main()
