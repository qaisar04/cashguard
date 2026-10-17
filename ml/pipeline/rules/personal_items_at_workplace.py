from __future__ import annotations

from app.settings import RulesConfig
from pipeline.rules.base import Candidate, evidence_points, fmt
from pipeline.timeline import SecondState, Timeline

TYPE_ID = "personal_items_at_workplace"


class PersonalItemsAtWorkplaceRule:
    type_id = TYPE_ID

    def evaluate(self, timeline: Timeline, cfg: RulesConfig) -> list[Candidate]:
        def personal_items_with_cashier(s: SecondState) -> bool:
            return s.personal_items_on_desk > 0 and s.cashier_present

        out: list[Candidate] = []
        for run in timeline.runs(personal_items_with_cashier):
            if timeline.span_sec(run) < cfg.personal_items_sec:
                continue
            onset, end = timeline.states[run[0]].t, timeline.states[run[1] - 1].t
            out.append(
                Candidate(
                    type_id=TYPE_ID,
                    onset=onset,
                    end=end,
                    description=(
                        f"С {fmt(onset)} по {fmt(end)} на кассовом столе рядом с кассиром лежат личные вещи "
                        "(сумка или верхняя одежда), кассир находится на рабочем месте."
                    ),
                    evidence_ts=evidence_points(onset, end),
                )
            )
        return out
