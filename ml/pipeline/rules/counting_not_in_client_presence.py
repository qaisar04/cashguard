from __future__ import annotations

from app.settings import RulesConfig
from pipeline.observers.machine import ACTION_MACHINE_COUNTING
from pipeline.rules.base import Candidate, evidence_points, fmt
from pipeline.timeline import Timeline

TYPE_ID = "counting_not_in_client_presence"


class CountingNotInClientPresenceRule:
    """The counting machine runs while no visitor is at the desk, shortly after a visitor was there."""

    type_id = TYPE_ID

    def evaluate(self, timeline: Timeline, cfg: RulesConfig) -> list[Candidate]:
        out: list[Candidate] = []
        for run in timeline.runs(lambda s: s.has_action(ACTION_MACHINE_COUNTING) and not s.visitors_at_counter and s.cashier_present):
            states = timeline.states[run[0] : run[1]]
            onset, end = states[0].t, states[-1].t
            if end - onset + 1 < cfg.counting_alone_min_sec:
                continue
            if not _client_was_served(timeline, run[0], cfg):
                continue
            out.append(
                Candidate(
                    type_id=TYPE_ID,
                    onset=onset,
                    end=end,
                    description=(
                        f"С {fmt(onset)} по {fmt(end)} кассир пересчитывает наличные на машине, "
                        "а клиент, передавший их, уже покинул кассу."
                    ),
                    evidence_ts=evidence_points(onset, end),
                )
            )
        return out


def _client_was_served(timeline: Timeline, index: int, cfg: RulesConfig) -> bool:
    """A client stood at the counter long enough to be served (a one-frame figure in the corridor does not count)."""
    onset = timeline.states[index].t
    recent = [s for s in timeline.states[:index] if onset - cfg.client_gone_sec <= s.t < onset]
    at_counter = [s.t for s in recent if s.visitors_at_counter]
    return len(at_counter) >= cfg.client_served_min_sec and max(at_counter, default=-1.0) >= onset - cfg.client_gone_sec
