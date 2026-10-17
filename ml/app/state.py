from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from app.jobs import JobStore
from app.schemas import Event, EvidenceFrame, RuleReference
from app.settings import OBSERVER_DETECTOR, OBSERVER_STUB, Settings, load_pipeline_config
from pipeline.analyzer import DIAGNOSTICS_DIR, AnalysisEvent, Analyzer
from pipeline.observers.base import Observer
from rules.catalog import RuleCatalog

log = logging.getLogger(__name__)


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
        self.analyzer = Analyzer(cfg, [_build_observer(settings, cfg)], RuleCatalog.load(), settings.data_dir / DIAGNOSTICS_DIR)
        self.jobs = JobStore(self.run_events, settings.workers, settings.job_ttl_sec)
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        log.info("ML service ready: observer=%s, data_dir=%s", settings.observer, settings.data_dir)

    def run_events(self, video_path: Path) -> list[Event]:
        events, _ = self.analyzer.analyze(video_path)
        return [to_schema(e) for e in events]


def _build_observer(settings: Settings, cfg) -> Observer:
    if settings.observer == OBSERVER_STUB:
        from pipeline.observers.stub import StubObserver

        return StubObserver(settings.stub_fixture)
    if settings.observer == OBSERVER_DETECTOR:
        from pipeline.clip_zero_shot import ClipZeroShot
        from pipeline.detectors.factory import build_detector
        from pipeline.observers.detector import DetectorObserver
        from pipeline.person_verifier import PersonVerifier
        from pipeline.screen import ScreenClassifier

        clip = ClipZeroShot(cfg.screen.clip_model, cfg.detectors[0].device) if cfg.screen.enabled or cfg.person_verifier.enabled else None
        screen = ScreenClassifier(cfg.screen, clip) if cfg.screen.enabled else None
        verifier = PersonVerifier(cfg.person_verifier, clip) if cfg.person_verifier.enabled else None
        return DetectorObserver([(build_detector(d), d) for d in cfg.detectors], screen, verifier)
    raise UnknownObserver(f"Unknown observer: {settings.observer}")


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
