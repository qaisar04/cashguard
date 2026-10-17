from __future__ import annotations

from app.settings import RulesConfig
from pipeline.observers.machine import ACTION_MACHINE_COUNTING
from pipeline.rules.base import Candidate, evidence_points, fmt
from pipeline.timeline import SecondState, Timeline

TYPE_ID = "cash_not_machine_verified"


class CashNotMachineVerifiedRule:
    """Cash changes hands with a visitor without the counting machine having run around that moment."""

    type_id = TYPE_ID

    def evaluate(self, timeline: Timeline, cfg: RulesConfig) -> list[Candidate]:
        out: list[Candidate] = []
        for run in timeline.runs(lambda s: s.cash_with_visitor and s.cashier_present):
            states = timeline.states[run[0] : run[1]]
            onset, end = states[0].t, states[-1].t
            if end - onset < cfg.handover_min_sec:
                continue
            if machine_used_around(timeline.states, onset, end, cfg.machine_lookaround_sec):
                continue
            out.append(
                Candidate(
                    type_id=TYPE_ID,
                    onset=onset,
                    end=end,
                    description=(
                        f"С {fmt(onset)} по {fmt(end)} наличные передаются между кассиром и посетителем; "
                        f"счётно-сортировальная машина за {cfg.machine_lookaround_sec:.0f} с до и после этого не работала."
                    ),
                    evidence_ts=evidence_points(onset, end),
                )
            )
        return out


def machine_used_around(states: list[SecondState], onset: float, end: float, lookaround_sec: float) -> bool:
    return any(onset - lookaround_sec <= s.t <= end + lookaround_sec and s.has_action(ACTION_MACHINE_COUNTING) for s in states)
