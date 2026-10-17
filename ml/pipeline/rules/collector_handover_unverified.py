from __future__ import annotations

from app.settings import RulesConfig
from pipeline.observers.vlm import ACTION_BAG_CHECKED, ACTION_BAG_HANDOVER
from pipeline.rules.base import Candidate, evidence_points, fmt
from pipeline.timeline import Timeline, person_left_at

TYPE_ID = "collector_handover_unverified"


class CollectorHandoverUnverifiedRule:
    """A visitor drops a bag and is gone shortly after, with no bag opening or document check in between."""

    type_id = TYPE_ID

    def evaluate(self, timeline: Timeline, cfg: RulesConfig) -> list[Candidate]:
        out: list[Candidate] = []
        for run in timeline.runs(lambda s: s.has_action(ACTION_BAG_HANDOVER)):
            onset = timeline.states[run[0]].t
            left_at = person_left_at(timeline.states[run[0] :], cfg.client_gone_sec, open_ended=True)
            if left_at is None or left_at - onset > cfg.collector_leave_sec:
                continue
            if any(onset <= s.t <= left_at and s.has_action(ACTION_BAG_CHECKED) for s in timeline.states):
                continue
            out.append(
                Candidate(
                    type_id=TYPE_ID,
                    onset=onset,
                    end=left_at,
                    description=(
                        f"На {fmt(onset)} инкассатор оставляет сумку на столе и на {fmt(left_at)} уходит; "
                        "сопроводительные документы не проверены, сумка в его присутствии не вскрыта."
                    ),
                    evidence_ts=evidence_points(onset, left_at),
                )
            )
        return out
