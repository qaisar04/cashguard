from __future__ import annotations

from app.settings import RulesConfig
from pipeline.observers.vlm import ACTION_CLIENT_GIVES_CASH, ACTION_ID_DOCUMENT
from pipeline.rules.base import Candidate, evidence_points, fmt
from pipeline.timeline import Timeline

TYPE_ID = "no_client_identification"


class NoClientIdentificationRule:
    """A client hands over cash and no ID document has been shown at any point before that."""

    type_id = TYPE_ID

    def evaluate(self, timeline: Timeline, cfg: RulesConfig) -> list[Candidate]:
        out: list[Candidate] = []
        for run in timeline.runs(lambda s: s.has_action(ACTION_CLIENT_GIVES_CASH)):
            onset, end = timeline.states[run[0]].t, timeline.states[run[1] - 1].t
            if any(s.t <= end and s.has_action(ACTION_ID_DOCUMENT) for s in timeline.states):
                continue
            out.append(
                Candidate(
                    type_id=TYPE_ID,
                    onset=onset,
                    end=end,
                    description=(
                        f"На {fmt(onset)} клиент передаёт наличные кассиру; документ, удостоверяющий личность, "
                        "до этого не предъявлялся."
                    ),
                    evidence_ts=evidence_points(onset, end),
                )
            )
        return out
