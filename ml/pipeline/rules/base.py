from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.settings import RulesConfig
from pipeline.timeline import Timeline


@dataclass
class Candidate:
    type_id: str
    onset: float
    end: float
    description: str
    evidence_ts: list[float] = field(default_factory=list)
    suppresses: set[str] = field(default_factory=set)


class Rule(Protocol):
    type_id: str

    def evaluate(self, timeline: Timeline, cfg: RulesConfig) -> list[Candidate]: ...


def evidence_points(onset: float, end: float) -> list[float]:
    if end - onset < 1.0:
        return [onset]
    return [onset, (onset + end) / 2, end]


def fmt(ts: float) -> str:
    return f"{ts:.0f} с"
