from __future__ import annotations

from app.settings import RulesConfig
from pipeline.rules.base import Candidate, evidence_points, fmt
from pipeline.timeline import SecondState, Timeline

TYPE_ID = "cash_exposed_to_visitor"


class CashExposedToVisitorRule:
    """Cash lies on the desk and a visitor who arrived after the cash appeared is present."""

    type_id = TYPE_ID

    def evaluate(self, timeline: Timeline, cfg: RulesConfig) -> list[Candidate]:
        out: list[Candidate] = []
        for run in timeline.runs(lambda s: s.cash_on_desk > 0):
            states = timeline.states[run[0] : run[1]]
            cash_since = states[0].t
            onset = _first_new_visitor(states, cash_since)
            if onset is None:
                continue
            end = min(states[-1].t, onset + cfg.min_presence_sec)
            out.append(
                Candidate(
                    type_id=TYPE_ID,
                    onset=onset,
                    end=end,
                    description=(
                        f"Наличные лежат открыто на столе с {fmt(cash_since)}; на {fmt(onset)} в кассу входит "
                        "посетитель, деньги остаются в открытом доступе."
                    ),
                    evidence_ts=evidence_points(onset, end),
                )
            )
        return out


def _first_new_visitor(states: list[SecondState], cash_since: float) -> float | None:
    for s in states:
        if not s.cashier_present:
            continue
        if any(p.entered and p.first_seen > cash_since for p in s.visitors):
            return s.t
    return None
