from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.jobs import JobStore
from app.schemas import Event, EvidenceFrame, RuleReference
from app.settings import OBSERVER_DETECTOR, OBSERVER_STUB, PipelineConfig, Settings, load_pipeline_config
from pipeline.analyzer import AnalysisEvent, Analyzer
from pipeline.observers.base import KIND_DOOR_OPEN, KIND_SAFE_OPEN, Observer
from rules.catalog import RuleCatalog

log = logging.getLogger(__name__)
SAFE = "safe"
DOOR = "door"


class UnknownObserver(ValueError):
    pass


@dataclass
class AppState:
    settings: Settings
    analyzer: Analyzer
    jobs: JobStore


class _Holder:
    settings: Settings
    analyzer: Analyzer
    jobs: JobStore
    initialized: bool = False

    def init(self, settings: Settings) -> None:
        self.initialized = True
        cfg = load_pipeline_config(settings.config_path)
        self.settings = settings
        self.analyzer = Analyzer(cfg, build_observers(settings, cfg), RuleCatalog.load())
        self.jobs = JobStore(self.run_events, settings.workers, settings.job_ttl_sec)
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        log.info("ML service ready: observer=%s, data_dir=%s", settings.observer, settings.data_dir)

    def run_events(self, video_path: Path) -> list[Event]:
        events, _ = self.analyzer.analyze(video_path)
        return [to_schema(e) for e in events]


def build_observers(settings: Settings, cfg: PipelineConfig) -> list[Observer]:
    if settings.observer == OBSERVER_STUB:
        from pipeline.observers.stub import StubObserver

        return [StubObserver(settings.stub_fixture)]
    if settings.observer == OBSERVER_DETECTOR:
        return _build_detector_observers(cfg)
    raise UnknownObserver(f"Unknown observer: {settings.observer}")


def _build_detector_observers(cfg: PipelineConfig) -> list[Observer]:
    from pipeline.clip_zero_shot import ClipZeroShot
    from pipeline.detectors.factory import BACKEND_OWLV2, build_detector
    from pipeline.observers.detector import DetectorObserver
    from pipeline.observers.state import StateObserver, build_probe
    from pipeline.person_verifier import PersonVerifier
    from pipeline.screen import ScreenClassifier

    needs_clip = cfg.screen.enabled or cfg.person_verifier.enabled or cfg.safe.enabled or cfg.door.enabled
    clip = ClipZeroShot(cfg.screen.clip_model, cfg.detectors[0].device) if needs_clip else None
    screen = ScreenClassifier(cfg.screen, clip) if cfg.screen.enabled else None
    verifier = PersonVerifier(cfg.person_verifier, clip) if cfg.person_verifier.enabled else None
    detectors = [(build_detector(d), d) for d in cfg.detectors]
    observers: list[Observer] = [DetectorObserver(detectors, screen, verifier)]
    wanted = [(name, kind, state) for name, kind, state in ((SAFE, KIND_SAFE_OPEN, cfg.safe), (DOOR, KIND_DOOR_OPEN, cfg.door)) if state.enabled]
    probes = [p for p in (build_probe(name, kind, state, clip) for name, kind, state in wanted) if p is not None]
    if probes:
        owl = next((d for d, c in detectors if c.backend == BACKEND_OWLV2), None)
        anchor = owl.with_threshold(min(p.cfg.anchor.score_threshold for p in probes)) if owl is not None else None
        observers.append(StateObserver(anchor, probes))
    return observers


def to_schema(e: AnalysisEvent) -> Event:
    return Event(
        type_id=e.type_id,
        type=e.type_name,
        timecode_sec=e.timecode_sec,
        description=e.description,
        evidence_frames=[EvidenceFrame(timestamp_sec=ts, image_base64=img) for ts, img in e.evidence],
        rule=RuleReference(document=e.document, clause=e.clause, url=e.url),
    )


state = _Holder()
