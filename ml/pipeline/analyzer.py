from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from app.settings import PipelineConfig, VideoConfig
from pipeline.evidence import EvidenceBuilder, PersonMarks, person_marks
from pipeline.observers.base import KIND_PERSON, Observation, Observer
from pipeline.rules.base import Candidate
from pipeline.rules.engine import RuleEngine, default_rules
from pipeline.timeline import build_timeline
from pipeline.tracking import Track, annotate_tracks, track
from pipeline.video import Frame, probe, sample_frames
from pipeline.zones import Zones, build_zones
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
class TrackDiagnostics:
    id: int
    first_ts: float
    last_ts: float
    mean_score: float
    mean_center: tuple[float, float]
    reflection: bool
    behind_glass: bool
    entered: bool
    inside: bool | None
    counted: bool


@dataclass(frozen=True)
class AnalysisMeta:
    frames: int
    sampled_fps: float
    duration_sec: float
    observations: int
    observers: list[str]
    elapsed_ms: int
    tracks: list[TrackDiagnostics]


DIAGNOSTICS_DIR = "diagnostics"


@dataclass(frozen=True)
class Analysis:
    events: list[AnalysisEvent]
    persons: PersonMarks
    zones: Zones
    tracks: list[Track]


class Analyzer:
    def __init__(self, cfg: PipelineConfig, observers: list[Observer], catalog: RuleCatalog, diagnostics_dir: Path | None = None):
        self.cfg = cfg
        self.observers = observers
        self.catalog = catalog
        self.diagnostics_dir = diagnostics_dir
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
            analysis = self.analyze_observations(frames, observations, aspect)
        meta = AnalysisMeta(
            frames=len(frames),
            sampled_fps=fps,
            duration_sec=round(info.duration_sec, 2),
            observations=len(observations),
            observers=[o.name for o in self.observers],
            elapsed_ms=int((time.monotonic() - started) * 1000),
            tracks=[_track_diagnostics(t) for t in analysis.tracks],
        )
        log.info("analyzed %s: %d event(s) in %d ms", video_path.name, len(analysis.events), meta.elapsed_ms)
        self._write_diagnostics(video_path, analysis.events, meta)
        return analysis.events, meta

    def _write_diagnostics(self, video_path: Path, events: list["AnalysisEvent"], meta: AnalysisMeta) -> None:
        """Keyed by the file's sha256 so an evaluator can find the record for an uploaded copy of a known video."""
        if self.diagnostics_dir is None:
            return
        self.diagnostics_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "video": video_path.name,
            "events": [{"type_id": e.type_id, "timecode_sec": e.timecode_sec} for e in events],
            "meta": asdict(meta),
        }
        (self.diagnostics_dir / f"{_sha256(video_path)}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    def analyze_observations(self, frames: list[Frame], observations: list[Observation], aspect: float) -> Analysis:
        """Everything after detection: tracking, zones, rules and evidence rendering for already observed frames."""
        zones = build_zones(self.cfg.zones, observations, aspect)
        persons = [o for o in observations if o.kind == KIND_PERSON]
        tracks = track(persons, self.cfg.tracking.iou_threshold, self.cfg.tracking.max_missing_sec)
        annotate_tracks(tracks, zones, self.cfg.tracking)
        marks = person_marks(tracks, zones)
        timeline = build_timeline([f.ts for f in frames], observations, tracks, zones)
        candidates = self.engine.run(timeline)
        events = [self._to_event(c, frames, observations, marks) for c in candidates]
        return Analysis(events=events, persons=marks, zones=zones, tracks=tracks)

    def _to_event(self, c: Candidate, frames: list[Frame], observations: list[Observation], marks: PersonMarks) -> AnalysisEvent:
        rule = self.catalog.get(c.type_id)
        return AnalysisEvent(
            type_id=c.type_id,
            type_name=rule.name_ru,
            timecode_sec=round(c.onset, 2),
            description=f"{c.description} {rule.reference.citation}",
            evidence=self.evidence.build(frames, observations, c.evidence_ts, marks),
            document=rule.reference.document,
            clause=rule.reference.clause,
            url=rule.reference.url,
        )


def _effective_fps(video_path: Path, cfg: VideoConfig) -> float:
    duration = probe(video_path).duration_sec
    if duration <= 0 or duration * cfg.fps <= cfg.max_frames:
        return cfg.fps
    return cfg.max_frames / duration


def _track_diagnostics(t) -> TrackDiagnostics:
    centers = [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for _, b in t.points]
    return TrackDiagnostics(
        id=t.id,
        first_ts=round(t.first_ts, 2),
        last_ts=round(t.last_ts, 2),
        mean_score=round(t.mean_score, 3),
        mean_center=(round(sum(c[0] for c in centers) / len(centers), 3), round(sum(c[1] for c in centers) / len(centers), 3)),
        reflection=t.reflection,
        behind_glass=t.behind_glass,
        entered=t.entered,
        inside=t.inside,
        counted=t.counted(),
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
