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


EVIDENCE_SPAN_SEC = 4.0  # every evidence frame must stay within ±5 s of the reported timecode (the onset)


def evidence_points(onset: float, end: float) -> list[float]:
    last = min(end, onset + EVIDENCE_SPAN_SEC)
    if last - onset < 1.0:
        return [onset]
    return [onset, (onset + last) / 2, last]


def fmt(ts: float) -> str:
    return f"{ts:.0f} с"


def departure_ts(timeline: Timeline, run_start: int, cfg: RulesConfig) -> float:
    """Timecode of an absence: the last second the cashier was still working at the seat core, not the first second
    the absence rule became true (walking out of the seat radius takes 2-4 s and the label marks the departure)."""
    onset = timeline.states[run_start].t
    for state in reversed(timeline.states[:run_start]):
        if onset - state.t > cfg.departure_lookback_sec:
            break
        distances = [timeline.zones.seat_distance(p.center) for p in state.persons if p.at_seat]
        if any(d is not None and d <= cfg.seat_core_radius for d in distances):
            return state.t
    return onset
