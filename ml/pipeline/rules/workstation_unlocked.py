from __future__ import annotations

from app.settings import RulesConfig
from pipeline.observers.base import SCREEN_UNLOCKED_STATES
from pipeline.rules.base import Candidate, evidence_points, fmt
from pipeline.timeline import SecondState, Timeline

TYPE_ID = "workstation_unlocked"


class WorkstationUnlockedRule:
    type_id = TYPE_ID

    def evaluate(self, timeline: Timeline, cfg: RulesConfig) -> list[Candidate]:
        def unlocked_and_alone(s: SecondState) -> bool:
            return s.screen_state in SCREEN_UNLOCKED_STATES and not s.cashier_present

        out: list[Candidate] = []
        for run in timeline.runs(unlocked_and_alone):
            if timeline.span_sec(run) < cfg.unattended_sec:
                continue
            onset, end = timeline.states[run[0]].t, timeline.states[run[1] - 1].t
            out.append(
                Candidate(
                    type_id=TYPE_ID,
                    onset=onset,
                    end=end,
                    description=(
                        f"С {fmt(onset)} по {fmt(end)} кассир отсутствует на рабочем месте, "
                        f"при этом {_screen_text(timeline.states[run[0]].screen_state)} "
                        "(экран не заблокирован и не погашен)."
                    ),
                    evidence_ts=evidence_points(onset, end),
                )
            )
        return out


def _screen_text(state: str) -> str:
    if state == "desktop":
        return "компьютер остаётся разблокированным (виден рабочий стол)"
    return "на экране компьютера остаётся открытое рабочее приложение"
