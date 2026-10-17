from __future__ import annotations

from app.settings import RulesConfig
from pipeline.rules.base import Candidate, evidence_points, fmt
from pipeline.rules.cash_room_door_open import TYPE_ID as DOOR_OPEN_TYPE
from pipeline.timeline import Timeline

TYPE_ID = "unauthorized_entry"


class UnauthorizedEntryRule:
    """A person enters while the cashier is already serving someone, or while the door has been standing open."""

    type_id = TYPE_ID

    def evaluate(self, timeline: Timeline, cfg: RulesConfig) -> list[Candidate]:
        out: list[Candidate] = []
        for track in timeline.tracks:
            if not track.entered or track.first_ts <= 0.0:
                continue
            idx = _index_at(timeline, track.first_ts)
            if idx is None:
                continue
            state = timeline.states[idx]
            if not state.cashier_present:
                continue
            others = [
                p for p in state.visitors
                if p.track_id != track.id and state.t - p.first_seen >= cfg.min_presence_sec and timeline.zones.on_desk(p.center)
            ]
            door_was_open = cfg.door_state_trusted and _door_open_before(timeline, idx, cfg.door_open_sec)
            if not others and not door_was_open:
                continue
            onset = state.t
            end = min(timeline.duration, onset + cfg.min_presence_sec)
            reason = (
                "в это время кассир обслуживает другого клиента"
                if others
                else "дверь кассы до этого оставалась открытой"
            )
            out.append(
                Candidate(
                    type_id=TYPE_ID,
                    onset=onset,
                    end=end,
                    description=f"На {fmt(onset)} в помещение кассы входит ещё один человек; {reason}.",
                    evidence_ts=evidence_points(onset, end),
                    suppresses={DOOR_OPEN_TYPE},
                )
            )
        return out


def _index_at(timeline: Timeline, ts: float) -> int | None:
    for i, s in enumerate(timeline.states):
        if abs(s.t - ts) < 1e-6:
            return i
    return None


def _door_open_before(timeline: Timeline, idx: int, min_sec: float) -> bool:
    count = 0
    for s in reversed(timeline.states[:idx]):
        if not s.door_open:
            break
        count += 1
    if count == 0:
        return False
    return timeline.states[idx - 1].t - timeline.states[idx - count].t >= min_sec - 1.0
