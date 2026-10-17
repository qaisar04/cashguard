from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from pipeline.observers.base import Observation
from pipeline.video import Frame


class StubObserver:
    """Replays observations from a JSON fixture: [{"ts", "kind", "box", "score", "attrs"}].

    Used for tests and for running the full API without model weights.
    """

    name = "stub"

    def __init__(self, fixture: Path | None):
        self._observations = _load(fixture) if fixture else []

    def observe(self, frames: list[Frame], prior: Sequence[Observation] = ()) -> list[Observation]:
        if not frames:
            return []
        last_ts = frames[-1].ts
        return [o for o in self._observations if o.ts <= last_ts + 1.0]


def _load(fixture: Path) -> list[Observation]:
    raw = json.loads(fixture.read_text(encoding="utf-8"))
    return [
        Observation(
            ts=float(item["ts"]),
            kind=item["kind"],
            box=tuple(float(v) for v in item["box"]),
            score=float(item.get("score", 1.0)),
            attrs=dict(item.get("attrs", {})),
        )
        for item in raw
    ]
