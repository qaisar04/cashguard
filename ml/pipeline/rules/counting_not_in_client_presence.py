from __future__ import annotations

from app.settings import RulesConfig
from pipeline.observers.vlm import ACTION_HAND_COUNTING, ACTION_MACHINE_COUNTING
from pipeline.rules.base import Candidate, evidence_points, fmt
from pipeline.timeline import Timeline, visitor_left_at

TYPE_ID = "counting_not_in_client_presence"


class CountingNotInClientPresenceRule:
    """The client walks away while the teller keeps counting the cash for a while longer."""

    type_id = TYPE_ID

    def evaluate(self, timeline: Timeline, cfg: RulesConfig) -> list[Candidate]:
        out: list[Candidate] = []
        for run in timeline.runs(lambda s: s.has_action(ACTION_HAND_COUNTING, ACTION_MACHINE_COUNTING)):
            states = timeline.states[run[0] : run[1]]
            left_at = visitor_left_at(states)
            end = states[-1].t
            if left_at is None or end - left_at < cfg.client_gone_sec:
                continue
            out.append(
                Candidate(
                    type_id=TYPE_ID,
                    onset=left_at,
                    end=end,
                    description=(
                        f"На {fmt(left_at)} клиент покидает кассу, а кассир продолжает пересчёт принятых "
                        f"от него наличных до {fmt(end)}."
                    ),
                    evidence_ts=evidence_points(left_at, end),
                )
            )
        return out
