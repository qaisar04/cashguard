from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from app.settings import PipelineConfig, VideoConfig
from pipeline.evidence import EvidenceBuilder
from pipeline.observers.base import KIND_PERSON, Observation, Observer
from pipeline.rules.base import Candidate
from pipeline.rules.engine import RuleEngine, default_rules
from pipeline.timeline import build_timeline
from pipeline.tracking import annotate_tracks, track
from pipeline.video import probe, sample_frames
from pipeline.zones import build_zones
from rules.catalog import RuleCatalog

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalysisEvent:
    type_id: str
    type_name: str
    timecode_sec: float
    description: str
    evidence: list[tuple[float, str]]
    document: str
    clause: str
    url: str


@dataclass(frozen=True)
class AnalysisMeta:
    frames: int
    sampled_fps: float
    duration_sec: float
    observations: int
    observers: list[str]
    elapsed_ms: int


class Analyzer:
    def __init__(self, cfg: PipelineConfig, observers: list[Observer], catalog: RuleCatalog):
        self.cfg = cfg
        self.observers = observers
        self.catalog = catalog
        self.engine = RuleEngine(default_rules(cfg.rules.enabled), cfg.rules)
        self.evidence = EvidenceBuilder(cfg.evidence)
        self._lock = threading.Lock()

    def analyze(self, video_path: Path) -> tuple[list[AnalysisEvent], AnalysisMeta]:
        started = time.monotonic()
        with self._lock:
            fps = _effective_fps(video_path, self.cfg.video)
            info, frames = sample_frames(video_path, fps, self.cfg.video.max_side)
            observations: list[Observation] = []
            for observer in self.observers:
                observations.extend(observer.observe(frames, prior=tuple(observations)))
            aspect = info.width / info.height if info.height else 1.0
            zones = build_zones(self.cfg.zones, observations, aspect)
            persons = [o for o in observations if o.kind == KIND_PERSON]
            tracks = track(persons, self.cfg.tracking.iou_threshold, self.cfg.tracking.max_missing_sec)
            annotate_tracks(tracks, zones, self.cfg.tracking)
            timeline = build_timeline([f.ts for f in frames], observations, tracks, zones)
            candidates = self.engine.run(timeline)
            events = [self._to_event(c, frames, observations) for c in candidates]
        meta = AnalysisMeta(
            frames=len(frames),
            sampled_fps=fps,
            duration_sec=round(info.duration_sec, 2),
            observations=len(observations),
            observers=[o.name for o in self.observers],
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )
        log.info("analyzed %s: %d event(s) in %d ms", video_path.name, len(events), meta.elapsed_ms)
        return events, meta

    def _to_event(self, c: Candidate, frames, observations) -> AnalysisEvent:
        rule = self.catalog.get(c.type_id)
        return AnalysisEvent(
            type_id=c.type_id,
            type_name=rule.name_ru,
            timecode_sec=round(c.onset, 2),
            description=c.description,
            evidence=self.evidence.build(frames, observations, c.evidence_ts),
            document=rule.reference.document,
            clause=rule.reference.clause,
            url=rule.reference.url,
        )


def _effective_fps(video_path: Path, cfg: VideoConfig) -> float:
    duration = probe(video_path).duration_sec
    if duration <= 0 or duration * cfg.fps <= cfg.max_frames:
        return cfg.fps
    return cfg.max_frames / duration
