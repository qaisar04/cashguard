from __future__ import annotations

from app.settings import RulesConfig
from pipeline.rules.base import Candidate, departure_ts, evidence_points, fmt
from pipeline.rules.workstation_unlocked import TYPE_ID as WORKSTATION_TYPE
from pipeline.timeline import SecondState, Timeline

TYPE_ID = "valuables_left_unattended"


class ValuablesLeftUnattendedRule:
    type_id = TYPE_ID

    def evaluate(self, timeline: Timeline, cfg: RulesConfig) -> list[Candidate]:
        def valuables_and_alone(s: SecondState) -> bool:
            return (s.cash_on_desk + s.bags_on_desk) > 0 and not s.cashier_present

        out: list[Candidate] = []
        for run in timeline.runs(valuables_and_alone):
            if timeline.span_sec(run) < cfg.unattended_sec:
                continue
            states = timeline.states[run[0] : run[1]]
            onset, end = departure_ts(timeline, run[0], cfg), states[-1].t
            out.append(
                Candidate(
                    type_id=TYPE_ID,
                    onset=onset,
                    end=end,
                    description=(
                        f"С {fmt(onset)} по {fmt(end)} кассир отсутствует на рабочем месте, "
                        f"на столе остаются {_what(states)} без присмотра."
                    ),
                    evidence_ts=evidence_points(onset, end),
                    suppresses={WORKSTATION_TYPE},
                )
            )
        return out


def _what(states: list[SecondState]) -> str:
    cash = any(s.cash_on_desk for s in states)
    bags = any(s.bags_on_desk for s in states)
    if cash and bags:
        return "наличные деньги и сумка (папка с документами)"
    if cash:
        return "наличные деньги"
    return "сумка или папка с документами"
