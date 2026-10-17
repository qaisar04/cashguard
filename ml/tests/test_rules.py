from __future__ import annotations

from pipeline.observers.base import SCREEN_APPLICATION, SCREEN_LOCK
from pipeline.rules.cash_exposed_to_visitor import CashExposedToVisitorRule
from pipeline.rules.cash_room_door_open import CashRoomDoorOpenRule
from pipeline.rules.engine import RuleEngine, default_rules
from pipeline.rules.food_drink_at_workplace import FoodDrinkAtWorkplaceRule
from pipeline.rules.personal_items_at_workplace import PersonalItemsAtWorkplaceRule
from pipeline.rules.safe_left_open import SafeLeftOpenRule
from pipeline.rules.unauthorized_entry import UnauthorizedEntryRule
from pipeline.rules.valuables_left_unattended import ValuablesLeftUnattendedRule
from pipeline.rules.workstation_unlocked import WorkstationUnlockedRule
from pipeline.tracking import Track
from tests.helpers import AWAY, COUNTER, SEAT, box_at, person, rules_cfg, state, timeline

CASHIER = person(1, SEAT)


def test_workstation_unlocked_fires_when_cashier_leaves_with_application_open():
    states = [state(t, [CASHIER], screen=SCREEN_APPLICATION) for t in range(0, 5)]
    states += [state(t, [], screen=SCREEN_APPLICATION) for t in range(5, 12)]
    found = WorkstationUnlockedRule().evaluate(timeline(states), rules_cfg())
    assert len(found) == 1
    assert found[0].onset == 4.0  # departure: last second at the seat core; absence itself starts at 5
    assert found[0].evidence_ts[0] == 4.0


def test_workstation_unlocked_ignores_lock_screen():
    states = [state(t, [], screen=SCREEN_LOCK) for t in range(0, 12)]
    assert WorkstationUnlockedRule().evaluate(timeline(states), rules_cfg()) == []


def test_workstation_unlocked_ignores_short_absence():
    states = [state(t, [CASHIER], screen=SCREEN_APPLICATION) for t in range(0, 5)]
    states += [state(t, [], screen=SCREEN_APPLICATION) for t in range(5, 7)]
    states += [state(t, [CASHIER], screen=SCREEN_APPLICATION) for t in range(7, 12)]
    assert WorkstationUnlockedRule().evaluate(timeline(states), rules_cfg()) == []


def test_valuables_left_unattended_mentions_cash():
    states = [state(t, [CASHIER], cash=1) for t in range(0, 3)] + [state(t, [], cash=1) for t in range(3, 10)]
    found = ValuablesLeftUnattendedRule().evaluate(timeline(states), rules_cfg())
    assert len(found) == 1 and found[0].onset == 2.0  # departure second, absence starts at 3
    assert "наличные" in found[0].description


def test_valuables_not_fired_while_cashier_present():
    states = [state(t, [CASHIER], cash=1, bags=1) for t in range(0, 10)]
    assert ValuablesLeftUnattendedRule().evaluate(timeline(states), rules_cfg()) == []


def test_safe_left_open_requires_nobody_at_safe():
    states = [state(t, [CASHIER], safe_open=True, person_at_safe=True) for t in range(0, 3)]
    states += [state(t, [CASHIER], safe_open=True, person_at_safe=False) for t in range(3, 12)]
    found = SafeLeftOpenRule().evaluate(timeline(states), rules_cfg())
    assert len(found) == 1 and found[0].onset == 3.0


def test_door_open_needs_min_duration():
    short = [state(t, [CASHIER], door_open=True) for t in range(0, 3)] + [state(t, [CASHIER]) for t in range(3, 10)]
    assert CashRoomDoorOpenRule().evaluate(timeline(short), rules_cfg()) == []
    long = [state(t, [CASHIER], door_open=True) for t in range(0, 8)]
    assert len(CashRoomDoorOpenRule().evaluate(timeline(long), rules_cfg())) == 1


def test_unauthorized_entry_when_second_visitor_enters_during_service():
    client = person(2, COUNTER, first_seen=0.0)
    intruder = person(3, (0.2, 0.3), first_seen=6.0)
    states = [state(t, [CASHIER, client]) for t in range(0, 6)] + [state(t, [CASHIER, client, intruder]) for t in range(6, 12)]
    tracks = [Track(1, [(float(t), box_at(SEAT)) for t in range(12)]),
              Track(2, [(float(t), box_at(COUNTER)) for t in range(12)]),
              Track(3, [(float(t), box_at((0.2, 0.3))) for t in range(6, 12)], entered=True)]
    found = UnauthorizedEntryRule().evaluate(timeline(states, tracks), rules_cfg())
    assert len(found) == 1 and found[0].onset == 6.0
    assert "cash_room_door_open" in found[0].suppresses


def test_unauthorized_entry_ignores_previous_client_who_is_leaving():
    leaving = person(2, AWAY, first_seen=0.0)                   # away from the counter: walking out
    newcomer = person(3, (0.2, 0.3), first_seen=6.0)
    states = [state(t, [CASHIER, leaving]) for t in range(0, 6)] + [state(t, [CASHIER, leaving, newcomer]) for t in range(6, 12)]
    tracks = [Track(1, [(float(t), box_at(SEAT)) for t in range(12)]), Track(2, [(float(t), box_at(AWAY)) for t in range(12)]),
              Track(3, [(float(t), box_at((0.2, 0.3))) for t in range(6, 12)], entered=True)]
    assert UnauthorizedEntryRule().evaluate(timeline(states, tracks), rules_cfg()) == []


def test_valuables_takes_precedence_over_workstation_in_same_window():
    states = [state(t, [CASHIER], screen=SCREEN_APPLICATION, cash=1) for t in range(0, 3)]
    states += [state(t, [], screen=SCREEN_APPLICATION, cash=1) for t in range(3, 10)]
    events = RuleEngine(default_rules(), rules_cfg()).run(timeline(states))
    assert [e.type_id for e in events] == ["valuables_left_unattended"]


def test_unauthorized_entry_ignores_regular_client_arrival():
    client = person(2, COUNTER, first_seen=4.0)
    states = [state(t, [CASHIER]) for t in range(0, 4)] + [state(t, [CASHIER, client]) for t in range(4, 12)]
    tracks = [Track(1, [(float(t), box_at(SEAT)) for t in range(12)]), Track(2, [(float(t), box_at(COUNTER)) for t in range(4, 12)])]
    assert UnauthorizedEntryRule().evaluate(timeline(states, tracks), rules_cfg()) == []


def test_unauthorized_entry_after_door_left_open_suppresses_door_event():
    visitor = person(2, AWAY, first_seen=6.0)
    states = [state(t, [CASHIER], door_open=True) for t in range(0, 6)] + [state(t, [CASHIER, visitor], door_open=True) for t in range(6, 12)]
    tracks = [Track(1, [(float(t), box_at(SEAT)) for t in range(12)]), Track(2, [(float(t), box_at(AWAY)) for t in range(6, 12)], entered=True)]
    events = RuleEngine(default_rules(), rules_cfg()).run(timeline(states, tracks))
    assert [e.type_id for e in events] == ["unauthorized_entry"]


def test_unauthorized_entry_door_branch_ignores_a_track_that_vanishes_at_once():
    flicker = person(2, AWAY, first_seen=6.0)
    states = [state(t, [CASHIER], door_open=True) for t in range(0, 6)] + [state(t, [CASHIER, flicker], door_open=True) for t in range(6, 8)]
    states += [state(t, [CASHIER]) for t in range(8, 12)]
    tracks = [Track(1, [(float(t), box_at(SEAT)) for t in range(12)]), Track(2, [(float(t), box_at(AWAY)) for t in range(6, 8)], entered=True)]
    assert UnauthorizedEntryRule().evaluate(timeline(states, tracks), rules_cfg()) == []


def test_unauthorized_entry_ignores_door_state_when_not_trusted():
    visitor = person(2, AWAY, first_seen=6.0)
    states = [state(t, [CASHIER], door_open=True) for t in range(0, 6)] + [state(t, [CASHIER, visitor], door_open=True) for t in range(6, 12)]
    tracks = [Track(1, [(float(t), box_at(SEAT)) for t in range(12)]), Track(2, [(float(t), box_at(AWAY)) for t in range(6, 12)], entered=True)]
    assert UnauthorizedEntryRule().evaluate(timeline(states, tracks), rules_cfg(door_state_trusted=False)) == []


def test_unauthorized_entry_ignores_retracked_person_born_mid_room():
    client = person(2, COUNTER, first_seen=0.0)
    retracked = person(3, (0.5, 0.8), first_seen=6.0, entered=False)
    states = [state(t, [CASHIER, client]) for t in range(0, 6)] + [state(t, [CASHIER, client, retracked]) for t in range(6, 12)]
    tracks = [Track(1, [(float(t), box_at(SEAT)) for t in range(12)]), Track(2, [(float(t), box_at(AWAY)) for t in range(12)]),
              Track(3, [(float(t), box_at((0.5, 0.8))) for t in range(6, 12)], entered=False)]
    assert UnauthorizedEntryRule().evaluate(timeline(states, tracks), rules_cfg()) == []


def test_cash_exposed_to_visitor_fires_on_new_visitor_only():
    first_client = person(2, AWAY, first_seen=0.0)
    next_client = person(3, (0.2, 0.3), first_seen=8.0)
    states = [state(t, [CASHIER, first_client], cash=1) for t in range(0, 8)] + [state(t, [CASHIER, next_client], cash=1) for t in range(8, 12)]
    found = CashExposedToVisitorRule().evaluate(timeline(states), rules_cfg())
    assert len(found) == 1 and found[0].onset == 8.0


def test_engine_merges_same_type_and_caps_events():
    states = [state(t, [], screen=SCREEN_APPLICATION) for t in range(0, 6)]
    states += [state(t, [CASHIER], screen=SCREEN_APPLICATION) for t in range(6, 8)]
    states += [state(t, [], screen=SCREEN_APPLICATION) for t in range(8, 14)]
    events = RuleEngine(default_rules(), rules_cfg(merge_gap_sec=5)).run(timeline(states))
    assert len(events) == 1 and events[0].onset == 0.0 and events[0].end == 13.0


def test_personal_items_fires_when_cashier_sits_with_bag_on_desk():
    states = [state(t, [CASHIER]) for t in range(0, 3)] + [state(t, [CASHIER], personal_items=1) for t in range(3, 10)]
    found = PersonalItemsAtWorkplaceRule().evaluate(timeline(states), rules_cfg())
    assert len(found) == 1 and found[0].onset == 3.0 and found[0].end == 9.0
    assert found[0].type_id == "personal_items_at_workplace"
    assert "личные вещи" in found[0].description and "3 с" in found[0].description


def test_personal_items_ignores_short_or_unattended_runs():
    short = [state(t, [CASHIER], personal_items=1) for t in range(0, 4)] + [state(t, [CASHIER]) for t in range(4, 10)]
    assert PersonalItemsAtWorkplaceRule().evaluate(timeline(short), rules_cfg()) == []
    alone = [state(t, [], personal_items=1) for t in range(0, 10)]
    assert PersonalItemsAtWorkplaceRule().evaluate(timeline(alone), rules_cfg()) == []


def test_personal_items_threshold_is_configurable():
    states = [state(t, [CASHIER], personal_items=1) for t in range(0, 4)]
    assert PersonalItemsAtWorkplaceRule().evaluate(timeline(states), rules_cfg(personal_items_sec=2)) != []
    assert PersonalItemsAtWorkplaceRule().evaluate(timeline(states), rules_cfg(personal_items_sec=5)) == []


def test_food_drink_fires_when_cashier_sits_with_cup_on_desk():
    states = [state(t, [CASHIER], drinks=1) for t in range(0, 6)] + [state(t, [CASHIER]) for t in range(6, 10)]
    found = FoodDrinkAtWorkplaceRule().evaluate(timeline(states), rules_cfg())
    assert len(found) == 1 and found[0].onset == 0.0 and found[0].end == 5.0
    assert found[0].type_id == "food_drink_at_workplace"
    assert "напиток" in found[0].description


def test_food_drink_ignores_short_or_unattended_runs():
    short = [state(t, [CASHIER], drinks=1) for t in range(0, 3)] + [state(t, [CASHIER]) for t in range(3, 10)]
    assert FoodDrinkAtWorkplaceRule().evaluate(timeline(short), rules_cfg()) == []
    alone = [state(t, [], drinks=1) for t in range(0, 10)]
    assert FoodDrinkAtWorkplaceRule().evaluate(timeline(alone), rules_cfg()) == []


def test_engine_reports_both_workplace_rules_together():
    states = [state(t, [CASHIER], personal_items=1, drinks=1) for t in range(0, 8)]
    events = RuleEngine(default_rules(), rules_cfg()).run(timeline(states))
    assert sorted(e.type_id for e in events) == ["food_drink_at_workplace", "personal_items_at_workplace"]
