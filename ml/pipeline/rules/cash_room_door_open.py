from __future__ import annotations

from app.settings import RulesConfig
from pipeline.rules.base import Candidate, evidence_points, fmt
from pipeline.timeline import SecondState, Timeline

TYPE_ID = "cash_room_door_open"


class CashRoomDoorOpenRule:
    type_id = TYPE_ID

    def evaluate(self, timeline: Timeline, cfg: RulesConfig) -> list[Candidate]:
        def door_open(s: SecondState) -> bool:
            return s.door_open

        out: list[Candidate] = []
        for run in timeline.runs(door_open):
            if timeline.span_sec(run) < cfg.door_open_sec:
                continue
            onset, end = timeline.states[run[0]].t, timeline.states[run[1] - 1].t
            out.append(
                Candidate(
                    type_id=TYPE_ID,
                    onset=onset,
                    end=end,
                    description=(
                        f"С {fmt(onset)} по {fmt(end)} дверь кассового помещения остаётся открытой "
                        "во время работы кассира."
                    ),
                    evidence_ts=evidence_points(onset, end),
                )
            )
        return out
