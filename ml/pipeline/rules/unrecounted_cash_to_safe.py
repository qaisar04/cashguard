from __future__ import annotations

from app.settings import RulesConfig
from pipeline.observers.machine import ACTION_MACHINE_COUNTING
from pipeline.rules.base import Candidate, evidence_points, fmt
from pipeline.timeline import Timeline

TYPE_ID = "unrecounted_cash_to_safe"


class UnrecountedCashToSafeRule:
    """Cash / a collection bag was on the desk, then the safe is loaded, and the machine never ran in between."""

    type_id = TYPE_ID

    def evaluate(self, timeline: Timeline, cfg: RulesConfig) -> list[Candidate]:
        out: list[Candidate] = []
        for run in timeline.runs(lambda s: s.safe_attended):
            states = timeline.states[run[0] : run[1]]
            onset, end = states[0].t, states[-1].t
            earlier = [s for s in timeline.states if onset - cfg.recount_lookback_sec <= s.t < onset]
            later = [s for s in timeline.states if s.t > end]
            # the bundles must have been lying on the desk right before and be gone afterwards: that is what "put into
            # the safe" looks like. Taking a folder out of the safe (X-27) has no cash on the desk before it.
            if sum(1 for s in earlier if s.cash_on_desk) < cfg.cash_on_desk_min_sec:
                continue
            if later and any(s.cash_on_desk for s in later[: int(cfg.cash_on_desk_min_sec)]):
                continue
            if any(s.has_action(ACTION_MACHINE_COUNTING) for s in earlier):
                continue
            out.append(
                Candidate(
                    type_id=TYPE_ID,
                    onset=onset,
                    end=end,
                    description=(
                        f"На {fmt(onset)} кассир убирает наличные в сейф; за предыдущие {cfg.recount_lookback_sec:.0f} с "
                        "они лежали на столе, а счётно-сортировальная машина не использовалась."
                    ),
                    evidence_ts=evidence_points(onset, end),
                )
            )
        return out
