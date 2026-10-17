from __future__ import annotations

from pipeline.observers.base import KIND_PERSON, Observation
from pipeline.rules.engine import RuleEngine, default_rules
from pipeline.timeline import build_timeline
from pipeline.tracking import ATTR_INSIDE, Track, annotate_tracks, track
from tests.helpers import box_at, rules_cfg, tracking_cfg, zones

SEAT_PATH = [(0.50 + 0.03 * i, 0.50 + 0.01 * i) for i in range(6)]          # cashier moving
MIRROR_PATH = [(0.20 - 0.03 * i, 0.20 + 0.01 * i) for i in range(6)]        # mirrored x, same y, inside the glass band


def _obs(path, start=0, kind=KIND_PERSON, score=0.9, attrs=None, size=0.12):
    return [Observation(ts=float(start + i), kind=kind, box=box_at(p, size), score=score, attrs=attrs or {}) for i, p in enumerate(path)]


def test_mirrored_track_is_flagged_as_reflection():
    tracks = track(_obs(SEAT_PATH) + _obs(MIRROR_PATH, start=1, score=0.6), 0.2, 2.0)
    annotate_tracks(tracks, zones(), tracking_cfg())
    assert [t.reflection for t in tracks] == [False, True]
    assert tracks[1].counted() is False


def test_static_pair_is_not_a_reflection():
    tracks = track(_obs([(0.5, 0.5)] * 6) + _obs([(0.2, 0.2)] * 6, score=0.6), 0.2, 2.0)
    annotate_tracks(tracks, zones(), tracking_cfg())
    assert not any(t.reflection for t in tracks)


def test_static_figure_in_glass_strip_is_not_counted():
    ghost = _obs([(0.06, 0.30)] * 6, start=4, attrs={ATTR_INSIDE: "inside"})   # CLIP wrongly says inside; geometry wins
    tracks = track(ghost, 0.2, 2.0)
    annotate_tracks(tracks, zones(), tracking_cfg())
    assert tracks[0].behind_glass is True and tracks[0].counted() is False


def test_track_passing_along_glass_never_counts():
    outside = [(0.05, 0.10 + 0.05 * i) for i in range(6)]      # slides along the glass strip, never leaves it
    tracks = track(_obs(outside, start=4), 0.2, 2.0)
    annotate_tracks(tracks, zones(), tracking_cfg())
    assert tracks[0].counted() is False


def test_track_entering_through_door_counts():
    walk_in = [(0.10, 0.30), (0.17, 0.36), (0.24, 0.42), (0.31, 0.48), (0.38, 0.54), (0.45, 0.60), (0.50, 0.65)]
    tracks = track(_obs(walk_in, start=4), 0.2, 2.0)
    annotate_tracks(tracks, zones(), tracking_cfg())
    assert tracks[0].behind_glass is False and tracks[0].counted() is True


def test_visitor_standing_by_the_door_inside_the_room_counts():
    by_door = _obs([(0.22, 0.36)] * 5, start=4)                # inside the door band but outside the glass strip
    tracks = track(by_door, 0.2, 2.0)
    annotate_tracks(tracks, zones(), tracking_cfg())
    assert tracks[0].counted() is True and tracks[0].entered is True


def test_reflection_present_from_first_frame_is_still_excluded():
    mirror = _obs([(0.07, 0.42)] * 8)                           # cashier's reflection in the glass strip from t=0
    tracks = track(mirror, 0.2, 2.0)
    annotate_tracks(tracks, zones(), tracking_cfg())
    assert tracks[0].counted() is False


def test_track_born_mid_room_is_present_but_not_an_entry():
    retracked = _obs([(0.5, 0.8)] * 5, start=4)
    tracks = track(retracked, 0.2, 2.0)
    annotate_tracks(tracks, zones(), tracking_cfg())
    assert tracks[0].counted() is True and tracks[0].entered is False


def test_clip_vote_can_veto_but_not_promote():
    vetoed = _obs([(0.22, 0.36)] * 5, start=4, attrs={ATTR_INSIDE: "reflection"})
    tracks = track(vetoed, 0.2, 2.0)
    annotate_tracks(tracks, zones(), tracking_cfg())
    assert tracks[0].inside is False and tracks[0].counted() is False


def test_reflection_does_not_trigger_visitor_rules():
    cashier = _obs(SEAT_PATH + [SEAT_PATH[-1]] * 6)
    mirror = _obs(MIRROR_PATH + [MIRROR_PATH[-1]] * 6, start=1, score=0.6)
    cash = [Observation(ts=float(t), kind="cash", box=box_at((0.45, 0.55), 0.02), score=0.5) for t in range(12)]
    frame_ts = [float(t) for t in range(12)]
    z = zones()
    tracks = track(cashier + mirror, 0.2, 2.0)
    annotate_tracks(tracks, z, tracking_cfg())
    timeline = build_timeline(frame_ts, cashier + mirror + cash, tracks, z)
    events = RuleEngine(default_rules(), rules_cfg()).run(timeline)
    assert [e.type_id for e in events if e.type_id in ("unauthorized_entry", "cash_exposed_to_visitor")] == []
