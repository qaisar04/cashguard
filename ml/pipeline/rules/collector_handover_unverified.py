from __future__ import annotations

from app.settings import RulesConfig
from pipeline.observers.machine import ACTION_MACHINE_COUNTING
from pipeline.rules.base import Candidate, evidence_points, fmt
from pipeline.timeline import Timeline

TYPE_ID = "collector_handover_unverified"


class CollectorHandoverUnverifiedRule:
    """A bag appears on the desk while a visitor is present, the visitor is gone within a few seconds, and the bag
    was neither opened (no cash appears) nor its content counted in his presence."""

    type_id = TYPE_ID

    def evaluate(self, timeline: Timeline, cfg: RulesConfig) -> list[Candidate]:
        out: list[Candidate] = []
        for run in timeline.runs(lambda s: s.bags_on_desk > 0):
            onset = timeline.states[run[0]].t
            with_visitor = [s for s in timeline.states[run[0] : run[1]] if s.visitors]
            if not with_visitor or with_visitor[0].t - onset > 1.0:
                continue
            left_at = _visitors_gone_at(timeline, run[0], cfg.client_gone_sec)
            if left_at is None or left_at - onset > cfg.collector_leave_sec:
                continue
            checked = any(onset <= s.t <= left_at and (s.cash_on_desk or s.has_action(ACTION_MACHINE_COUNTING)) for s in timeline.states)
            if checked:
                continue
            out.append(
                Candidate(
                    type_id=TYPE_ID,
                    onset=onset,
                    end=left_at,
                    description=(
                        f"На {fmt(onset)} инкассатор оставляет сумку на столе и на {fmt(left_at)} уходит; "
                        "сумка в его присутствии не вскрыта и её содержимое не пересчитано."
                    ),
                    evidence_ts=evidence_points(onset, left_at),
                )
            )
        return out


def _visitors_gone_at(timeline: Timeline, index: int, gone_sec: float) -> float | None:
    states = timeline.states
    for i in range(index, len(states)):
        if states[i].visitors:
            continue
        stretch = [s for s in states[i:] if s.t - states[i].t <= gone_sec]
        if all(not s.visitors for s in stretch) and (states[-1].t - states[i].t >= gone_sec or stretch[-1] is states[-1]):
            return states[i].t
    return None
