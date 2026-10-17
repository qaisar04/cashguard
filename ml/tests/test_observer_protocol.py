from __future__ import annotations

import inspect

from pipeline.observers.detector import DetectorObserver
from pipeline.observers.state import StateObserver
from pipeline.observers.stub import StubObserver
from pipeline.observers.vlm import VlmObserver


def test_every_observer_accepts_prior_observations():
    # analyzer calls observer.observe(frames, prior=...) for every observer in the chain
    for cls in (DetectorObserver, StateObserver, StubObserver, VlmObserver):
        params = inspect.signature(cls.observe).parameters
        assert "prior" in params, cls.__name__
