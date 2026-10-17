from __future__ import annotations

from pipeline.observers.base import KIND_PERSON, Observation
from pipeline.tracking import track
from tests.helpers import box_at, zones


def test_tracker_keeps_identity_and_starts_new_track_after_gap():
    obs = [Observation(ts=float(t), kind=KIND_PERSON, box=box_at((0.5 + t * 0.005, 0.5)), score=1.0) for t in range(5)]
    obs += [Observation(ts=float(t), kind=KIND_PERSON, box=box_at((0.1, 0.1)), score=1.0) for t in range(9, 12)]
    tracks = track(obs, iou_threshold=0.2, max_missing_sec=2.0)
    assert [t.id for t in tracks] == [1, 2]
    assert tracks[0].first_ts == 0.0 and tracks[0].last_ts == 4.0
    assert tracks[1].first_ts == 9.0


def test_zones_distances_use_frame_height_units():
    z = zones()
    assert z.at_cashier_seat((0.5, 0.6))
    assert not z.at_cashier_seat((0.5, 0.8))
    assert z.on_desk((0.5, 0.78))
    assert z.in_door((0.1, 0.1)) and not z.in_door((0.9, 0.9))


def test_zones_fall_back_to_dwell_peak_without_monitor():
    from app.settings import ZonesConfig
    from pipeline.zones import build_zones
    from tests.helpers import DOOR_POLY, GLASS_POLY

    cfg = ZonesConfig(cashier_radius=0.16, desk_radius=0.3, safe_radius=0.18, door=DOOR_POLY, glass=GLASS_POLY)
    persons = [Observation(ts=float(t), kind=KIND_PERSON, box=box_at((0.45, 0.35)), score=0.9) for t in range(10)]
    persons += [Observation(ts=float(t), kind=KIND_PERSON, box=box_at((0.15, 0.34)), score=0.9) for t in range(5, 8)]
    z = build_zones(cfg, persons, aspect=0.55)
    assert z.monitor is not None and z.at_cashier_seat((0.45, 0.35)) and not z.at_cashier_seat((0.15, 0.34))
