from __future__ import annotations

from app.settings import RulesConfig
from pipeline.rules.base import Candidate, evidence_points, fmt
from pipeline.timeline import SecondState, Timeline

TYPE_ID = "safe_left_open"


class SafeLeftOpenRule:
    type_id = TYPE_ID

    def evaluate(self, timeline: Timeline, cfg: RulesConfig) -> list[Candidate]:
        def open_and_nobody_at_safe(s: SecondState) -> bool:
            return s.safe_open and not s.person_at_safe

        out: list[Candidate] = []
        for run in timeline.runs(open_and_nobody_at_safe):
            if timeline.span_sec(run) < cfg.safe_open_sec:
                continue
            onset, end = timeline.states[run[0]].t, timeline.states[run[1] - 1].t
            out.append(
                Candidate(
                    type_id=TYPE_ID,
                    onset=onset,
                    end=end,
                    description=(
                        f"С {fmt(onset)} по {fmt(end)} дверца сейфа открыта, "
                        "при этом рядом с сейфом никого нет — кассир отошёл, не закрыв сейф."
                    ),
                    evidence_ts=evidence_points(onset, end),
                )
            )
        return out
