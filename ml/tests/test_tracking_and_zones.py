from __future__ import annotations

from pipeline.observers.base import KIND_PERSON, Observation
from pipeline.tracking import Track, track
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


def _workplace_timeline(items, extra=()):
    from pipeline.observers.base import KIND_BAG, KIND_DRINK, KIND_PERSONAL_ITEM
    from pipeline.timeline import build_timeline
    from tests.helpers import SEAT

    kinds = {"item": KIND_PERSONAL_ITEM, "drink": KIND_DRINK, "bag": KIND_BAG}
    cashier = Track(1, [(float(t), box_at(SEAT)) for t in range(4)])
    obs = [Observation(ts=float(t), kind=kinds[kind], box=box_at(where, 0.03), score=0.5) for t, kind, where in items]
    return build_timeline([0.0, 1.0, 2.0, 3.0], obs + list(extra), [cashier], zones())


def test_timeline_counts_resting_personal_item_and_drink_near_seated_cashier():
    near = (0.55, 0.55)
    tl = _workplace_timeline([(t, "item", near) for t in range(4)] + [(t, "drink", near) for t in range(4)])
    assert [s.personal_items_on_desk for s in tl.states] == [1, 1, 1, 1]
    assert [s.drinks_on_desk for s in tl.states] == [1, 1, 1, 1]


def test_timeline_ignores_personal_item_carried_past_the_desk():
    moving = [(0, "item", (0.45, 0.45)), (1, "item", (0.55, 0.45)), (2, "item", (0.45, 0.55)), (3, "item", (0.55, 0.55))]
    tl = _workplace_timeline(moving)
    assert [s.personal_items_on_desk for s in tl.states] == [0, 0, 0, 0]


def test_timeline_treats_personal_item_overlapping_cash_bag_as_valuables():
    from pipeline.observers.base import KIND_BAG

    near = (0.55, 0.55)
    bag = [Observation(ts=float(t), kind=KIND_BAG, box=box_at(near, 0.03), score=0.5) for t in range(4)]
    tl = _workplace_timeline([(t, "item", near) for t in range(4)], extra=bag)
    assert [s.personal_items_on_desk for s in tl.states] == [0, 0, 0, 0]
    assert [s.bags_on_desk for s in tl.states] == [1, 1, 1, 1]


def test_timeline_ignores_items_on_desk_but_away_from_cashier():
    from tests.helpers import COUNTER

    tl = _workplace_timeline([(t, "item", COUNTER) for t in range(4)] + [(t, "drink", COUNTER) for t in range(4)])
    assert zones().on_desk(COUNTER)
    assert [s.personal_items_on_desk for s in tl.states] == [0, 0, 0, 0]
    assert [s.drinks_on_desk for s in tl.states] == [0, 0, 0, 0]
