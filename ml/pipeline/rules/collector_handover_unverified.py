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
        reported: set[int] = set()
        for run in timeline.runs(lambda s: s.bags_on_desk > 0):
            onset = timeline.states[run[0]].t
            # the collector is often detected only for a frame or two at the door: look around the bag's appearance
            around = [s for s in timeline.states if abs(s.t - onset) <= cfg.collector_leave_sec]
            collectors = {p.track_id for s in around for p in s.visitors if p.entered}
            for track_id in collectors - reported:
                presence = [s.t for s in timeline.states if any(p.track_id == track_id for p in s.visitors)]
                first_seen, last_seen = min(presence), max(presence)
                if last_seen - first_seen + 1.0 > cfg.collector_leave_sec:
                    continue  # stayed for the document check / bag opening
                left_at = last_seen + 1.0
                checked = any(first_seen <= s.t <= left_at and (s.cash_on_desk or s.has_action(ACTION_MACHINE_COUNTING)) for s in timeline.states)
                if checked:
                    continue
                reported.add(track_id)
                break
            else:
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

