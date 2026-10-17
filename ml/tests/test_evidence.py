from __future__ import annotations

import base64

import numpy as np

from app.settings import EvidenceConfig
from pipeline.evidence import IGNORED_OUTSIDE, IGNORED_REFLECTION, ROLE_CASHIER, ROLE_VISITOR, EvidenceBuilder, person_marks
from pipeline.observers.base import KIND_CASH, KIND_PERSON, Observation
from pipeline.tracking import annotate_tracks, track
from pipeline.video import Frame
from tests.helpers import COUNTER, SEAT, box_at, tracking_cfg, zones

MIRROR = (0.07, 0.42)


def _obs(path, start=0, score=0.9):
    return [Observation(ts=float(start + i), kind=KIND_PERSON, box=box_at(p, 0.1), score=score) for i, p in enumerate(path)]


def _marks(observations):
    z = zones()
    tracks = track(observations, 0.2, 2.0)
    annotate_tracks(tracks, z, tracking_cfg())
    return person_marks(tracks, z), tracks


def test_counted_tracks_are_labelled_by_role():
    marks, _ = _marks(_obs([SEAT] * 4) + _obs([COUNTER] * 4, start=2))
    assert [m.label for m in marks[0.0]] == [ROLE_CASHIER]
    assert sorted(m.label for m in marks[3.0]) == [ROLE_CASHIER, ROLE_VISITOR]
    assert all(m.counted for ts in marks for m in marks[ts])


def test_track_in_glass_strip_is_marked_outside():
    marks, tracks = _marks(_obs([MIRROR] * 5))
    assert tracks[0].behind_glass
    assert [(m.label, m.counted) for m in marks[2.0]] == [(IGNORED_OUTSIDE, False)]


def test_mirrored_track_is_marked_reflection():
    seat_path = [(0.50 + 0.03 * i, 0.50 + 0.01 * i) for i in range(6)]
    mirror_path = [(0.20 - 0.03 * i, 0.20 + 0.01 * i) for i in range(6)]
    marks, tracks = _marks(_obs(seat_path) + _obs(mirror_path, start=1, score=0.6))
    assert tracks[1].reflection
    by_track = {m.track_id: m for m in marks[3.0]}
    assert by_track[2].label == IGNORED_REFLECTION and by_track[2].counted is False
    assert by_track[1].counted is True


def test_builder_draws_only_marked_persons_and_other_kinds():
    cfg = EvidenceConfig(frames=3, max_side=200, jpeg_quality=80, draw_boxes=True)
    frame = Frame(index=0, ts=1.0, image=np.zeros((100, 60, 3), dtype=np.uint8))
    persons = _obs([SEAT] * 2) + _obs([MIRROR] * 2)
    cash = [Observation(ts=1.0, kind=KIND_CASH, box=box_at((0.5, 0.55), 0.02), score=0.5)]
    marks, _ = _marks(persons)
    plain = EvidenceBuilder(cfg).build([frame], persons + cash, [1.0])
    with_marks = EvidenceBuilder(cfg).build([frame], persons + cash, [1.0], marks)
    assert len(plain) == len(with_marks) == 1 and with_marks[0][0] == 1.0
    # raw person boxes never reach the frame; marks do
    assert plain[0][1] != with_marks[0][1]
    base64.b64decode(with_marks[0][1])
