from __future__ import annotations

from app.settings import RulesConfig
from pipeline.observers.vlm import ACTION_HAND_COUNTING, ACTION_MACHINE_COUNTING
from pipeline.rules.base import Candidate, evidence_points, fmt
from pipeline.timeline import SecondState, Timeline

TYPE_ID = "cash_not_machine_verified"


class CashNotMachineVerifiedRule:
    """The teller counts banknotes by hand and the counting machine is not used anywhere near that time."""

    type_id = TYPE_ID

    def evaluate(self, timeline: Timeline, cfg: RulesConfig) -> list[Candidate]:
        out: list[Candidate] = []
        for run in timeline.runs(lambda s: s.has_action(ACTION_HAND_COUNTING)):
            onset, end = timeline.states[run[0]].t, timeline.states[run[1] - 1].t
            if _machine_used_around(timeline.states, onset, end, cfg.machine_lookaround_sec):
                continue
            out.append(
                Candidate(
                    type_id=TYPE_ID,
                    onset=onset,
                    end=end,
                    description=(
                        f"С {fmt(onset)} по {fmt(end)} кассир пересчитывает банкноты вручную; "
                        "счётно-сортировальная машина при этом не используется."
                    ),
                    evidence_ts=evidence_points(onset, end),
                )
            )
        return out


def _machine_used_around(states: list[SecondState], onset: float, end: float, slack_sec: float) -> bool:
    return any(onset - slack_sec <= s.t <= end + slack_sec and s.has_action(ACTION_MACHINE_COUNTING) for s in states)
