from __future__ import annotations

from app.settings import GlassDetectionConfig, ZonesConfig
from pipeline.observers.base import KIND_GLASS, KIND_PERSON, Observation
from pipeline.tracking import annotate_tracks, track
from pipeline.zones import ZONE_SOURCE_CONFIG, ZONE_SOURCE_DETECTED, build_zones, detect_glazing
from tests.helpers import DOOR_POLY, GLASS_POLY, box_at, tracking_cfg

ASPECT = 0.55
WHOLE = (0.0, 0.03, 0.47, 0.52)        # the glazing as OWLv2 sees it on Х-4
EDGE_PANE = (0.0, 0.04, 0.24, 0.52)    # the pane touching the left frame edge (door + fixed pane)
FAR_PANE = (0.20, 0.05, 0.47, 0.47)


def _cfg(**glass) -> ZonesConfig:
    return ZonesConfig(cashier_radius=0.16, desk_radius=0.3, safe_radius=0.18, door=DOOR_POLY, glass=GLASS_POLY,
                       glass_detection=GlassDetectionConfig(pad=0.0, **glass))


def _glass(ts: float, *boxes) -> list[Observation]:
    return [Observation(ts=ts, kind=KIND_GLASS, box=b, score=0.4) for b in boxes]


def _frames(n: int, *boxes) -> list[Observation]:
    return [o for t in range(n) for o in _glass(float(t), *boxes)]


def test_glazing_is_the_median_of_whole_and_edge_pane():
    obs = _frames(3, WHOLE, EDGE_PANE, FAR_PANE) + _glass(3.0, (0.0, 0.03, 0.60, 0.55), (0.0, 0.03, 0.35, 0.55), FAR_PANE)
    glazing = detect_glazing(obs, GlassDetectionConfig())
    assert glazing is not None
    assert glazing.whole == WHOLE and glazing.edge_pane == EDGE_PANE


def test_frames_without_a_sub_pane_do_not_count():
    only_whole = _frames(5, WHOLE)
    assert detect_glazing(only_whole, GlassDetectionConfig(min_frames=3)) is None
    assert detect_glazing(_frames(2, WHOLE, EDGE_PANE), GlassDetectionConfig(min_frames=3)) is None


def test_glazing_away_from_the_frame_edge_is_ignored():
    centred = _frames(5, (0.3, 0.0, 0.8, 0.5), (0.3, 0.0, 0.5, 0.5))
    assert detect_glazing(centred, GlassDetectionConfig()) is None


def test_right_edge_glazing_picks_the_right_pane():
    mirrored = _frames(3, (0.53, 0.03, 1.0, 0.52), (0.76, 0.04, 1.0, 0.52), (0.53, 0.05, 0.80, 0.47))
    glazing = detect_glazing(mirrored, GlassDetectionConfig())
    assert glazing is not None and glazing.edge_pane == (0.76, 0.04, 1.0, 0.52)


def test_detected_glazing_replaces_config_polygons():
    z = build_zones(_cfg(), _frames(3, WHOLE, EDGE_PANE, FAR_PANE), ASPECT)
    assert z.source == ZONE_SOURCE_DETECTED
    assert z.in_glass((0.20, 0.36)) and not z.in_glass((0.30, 0.36))      # client reflection at x=0.20 is inside the strip
    assert z.in_door((0.40, 0.30)) and not z.in_door((0.40, 0.60))


def test_config_polygons_are_the_fallback():
    z = build_zones(_cfg(), _frames(2, WHOLE, EDGE_PANE), ASPECT)
    assert z.source == ZONE_SOURCE_CONFIG
    assert z.in_glass((0.10, 0.30)) and not z.in_glass((0.20, 0.36))
    disabled = build_zones(_cfg(enabled=False), _frames(5, WHOLE, EDGE_PANE, FAR_PANE), ASPECT)
    assert disabled.source == ZONE_SOURCE_CONFIG


def test_client_reflection_beyond_fixed_strip_is_excluded_with_detected_pane():
    # Х-4 at 20 s: the client's mirror image sits at (0.16, 0.36), outside the fixed x<0.15 strip, inside the detected pane
    mirror = [Observation(ts=float(t), kind=KIND_PERSON, box=box_at((0.16, 0.36), 0.06), score=0.75) for t in range(10, 14)]
    z = build_zones(_cfg(), _frames(3, WHOLE, EDGE_PANE, FAR_PANE), ASPECT)
    tracks = track(mirror, 0.2, 2.0)
    annotate_tracks(tracks, z, tracking_cfg())
    assert tracks[0].behind_glass is True and tracks[0].counted() is False


def test_visitor_walking_from_the_door_to_the_desk_still_counts():
    walk = [(0.16, 0.36), (0.22, 0.38), (0.29, 0.42), (0.36, 0.42), (0.36, 0.42)]
    obs = [Observation(ts=float(10 + i), kind=KIND_PERSON, box=box_at(p, 0.1), score=0.9) for i, p in enumerate(walk)]
    z = build_zones(_cfg(), _frames(3, WHOLE, EDGE_PANE, FAR_PANE), ASPECT)
    tracks = track(obs, 0.2, 2.0)
    annotate_tracks(tracks, z, tracking_cfg())
    assert tracks[0].counted() is True and tracks[0].entered is True
