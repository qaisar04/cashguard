from __future__ import annotations

from app.settings import RulesConfig, TrackingConfig, ZonesConfig
from pipeline.geometry import Polygon
from pipeline.observers.base import SCREEN_UNKNOWN
from pipeline.timeline import Person, SecondState, Timeline
from pipeline.tracking import Track
from pipeline.zones import Zones

ENABLED = ["workstation_unlocked", "valuables_left_unattended", "safe_left_open", "cash_room_door_open", "unauthorized_entry", "cash_exposed_to_visitor",
           "personal_items_at_workplace", "food_drink_at_workplace"]
SEAT = (0.5, 0.5)
AWAY = (0.1, 0.1)
COUNTER = (0.25, 0.40)   # far side of the desk: within desk_radius of the seat, outside cashier_radius
DOOR_POLY = [[0.0, 0.0], [0.50, 0.0], [0.50, 0.45], [0.0, 0.55]]
GLASS_POLY = [[0.0, 0.0], [0.15, 0.0], [0.15, 0.60], [0.0, 0.60]]


def rules_cfg(**overrides) -> RulesConfig:
    base = dict(enabled=ENABLED, door_state_trusted=True, unattended_sec=3, safe_open_sec=4, door_open_sec=4, personal_items_sec=4, food_drink_sec=4, min_presence_sec=3, merge_gap_sec=10, max_events=5)
    base.update(overrides)
    return RulesConfig(**base)


def zones() -> Zones:
    cfg = ZonesConfig(cashier_radius=0.16, desk_radius=0.3, safe_radius=0.18, door=DOOR_POLY, glass=GLASS_POLY)
    return Zones(monitor=SEAT, cashier_radius=cfg.cashier_radius, desk_radius=cfg.desk_radius, safe_radius=cfg.safe_radius,
                 door=Polygon(tuple(tuple(p) for p in DOOR_POLY)), glass=Polygon(tuple(tuple(p) for p in GLASS_POLY)), aspect=0.55)


def person(track_id: int, where, first_seen: float = 0.0, entered: bool | None = None) -> Person:
    z = zones()
    return Person(track_id=track_id, center=where, at_seat=z.at_cashier_seat(where), in_door=z.in_door(where),
                  first_seen=first_seen, entered=(first_seen > 0) if entered is None else entered)


def state(t: float, persons=(), screen=SCREEN_UNKNOWN, cash=0, bags=0, safe_open=False, person_at_safe=False, door_open=False,
          personal_items=0, drinks=0) -> SecondState:
    return SecondState(t=float(t), persons=list(persons), screen_state=screen, monitor_visible=True, cash_on_desk=cash,
                       bags_on_desk=bags, personal_items_on_desk=personal_items, drinks_on_desk=drinks, safe_open=safe_open, safe_center=(0.8, 0.5) if safe_open else None,
                       person_at_safe=person_at_safe, door_open=door_open)


def timeline(states: list[SecondState], tracks: list[Track] | None = None) -> Timeline:
    return Timeline(states=states, tracks=tracks or [], zones=zones())


def box_at(p, size=0.05):
    return (p[0] - size, p[1] - size, p[0] + size, p[1] + size)


def tracking_cfg() -> TrackingConfig:
    return TrackingConfig(iou_threshold=0.2, max_missing_sec=2.0, reflection_corr=0.8, reflection_min_steps=3,
                          reflection_min_motion=0.05, edge_margin=0.06, inside_vote_ratio=0.5)
