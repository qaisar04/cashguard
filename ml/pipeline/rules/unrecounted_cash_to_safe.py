from __future__ import annotations

from app.settings import RulesConfig
from pipeline.observers.vlm import ACTION_CASH_INTO_SAFE, ACTION_HAND_COUNTING, ACTION_MACHINE_COUNTING
from pipeline.rules.base import Candidate, evidence_points, fmt
from pipeline.timeline import SecondState, Timeline

TYPE_ID = "unrecounted_cash_to_safe"


class UnrecountedCashToSafeRule:
    """Cash goes into the safe and nothing was counted (by hand or machine) in the preceding minutes."""

    type_id = TYPE_ID

    def evaluate(self, timeline: Timeline, cfg: RulesConfig) -> list[Candidate]:
        out: list[Candidate] = []
        for run in timeline.runs(lambda s: s.has_action(ACTION_CASH_INTO_SAFE)):
            onset, end = timeline.states[run[0]].t, timeline.states[run[1] - 1].t
            if _counted_before(timeline.states, onset, cfg.recount_lookback_sec):
                continue
            out.append(
                Candidate(
                    type_id=TYPE_ID,
                    onset=onset,
                    end=end,
                    description=(
                        f"На {fmt(onset)} кассир убирает пачки наличных в сейф; пересчёт перед этим "
                        "не производился."
                    ),
                    evidence_ts=evidence_points(onset, end),
                )
            )
        return out


def _counted_before(states: list[SecondState], onset: float, lookback_sec: float) -> bool:
    return any(
        onset - lookback_sec <= s.t < onset and s.has_action(ACTION_HAND_COUNTING, ACTION_MACHINE_COUNTING) for s in states
    )
