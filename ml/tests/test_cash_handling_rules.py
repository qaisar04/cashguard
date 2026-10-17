from __future__ import annotations

from pipeline.observers.machine import ACTION_MACHINE_COUNTING
from pipeline.rules.cash_not_machine_verified import CashNotMachineVerifiedRule
from pipeline.rules.collector_handover_unverified import CollectorHandoverUnverifiedRule
from pipeline.rules.counting_not_in_client_presence import CountingNotInClientPresenceRule
from pipeline.rules.unrecounted_cash_to_safe import UnrecountedCashToSafeRule
from tests.helpers import COUNTER, SEAT, person, rules_cfg, state, timeline

CASHIER = person(1, SEAT)
CLIENT = person(2, COUNTER, first_seen=0.0)
MACHINE = (ACTION_MACHINE_COUNTING,)


def test_handover_without_machine_fires():
    states = [state(t, [CASHIER, CLIENT]) for t in range(0, 5)] + [state(t, [CASHIER, CLIENT], cash=1, cash_with_visitor=True) for t in range(5, 9)]
    found = CashNotMachineVerifiedRule().evaluate(timeline(states), rules_cfg())
    assert len(found) == 1 and found[0].onset == 5.0


def test_handover_after_machine_count_is_clean():
    states = [state(t, [CASHIER, CLIENT], actions=MACHINE) for t in range(0, 5)]
    states += [state(t, [CASHIER, CLIENT], cash=1, cash_with_visitor=True) for t in range(5, 9)]
    assert CashNotMachineVerifiedRule().evaluate(timeline(states), rules_cfg()) == []


def test_counting_after_client_left_fires():
    states = [state(t, [CASHIER, CLIENT]) for t in range(0, 10)] + [state(t, [CASHIER], actions=MACHINE) for t in range(10, 15)]
    found = CountingNotInClientPresenceRule().evaluate(timeline(states), rules_cfg())
    assert len(found) == 1 and found[0].onset == 10.0


def test_counting_with_client_present_is_clean():
    states = [state(t, [CASHIER, CLIENT], actions=MACHINE) for t in range(0, 10)]
    assert CountingNotInClientPresenceRule().evaluate(timeline(states), rules_cfg()) == []


def test_counting_long_after_client_left_is_not_this_type():
    states = [state(t, [CASHIER, CLIENT]) for t in range(0, 5)] + [state(t, [CASHIER]) for t in range(5, 30)]
    states += [state(t, [CASHIER], actions=MACHINE) for t in range(30, 35)]
    assert CountingNotInClientPresenceRule().evaluate(timeline(states), rules_cfg()) == []


def test_bag_cash_to_safe_without_count_fires():
    states = [state(t, [CASHIER], bags=1) for t in range(0, 10)] + [state(t, [CASHIER], safe_attended=True) for t in range(10, 14)]
    found = UnrecountedCashToSafeRule().evaluate(timeline(states), rules_cfg())
    assert len(found) == 1 and found[0].onset == 10.0


def test_cash_to_safe_after_count_is_clean():
    states = [state(t, [CASHIER], bags=1, actions=MACHINE) for t in range(0, 10)] + [state(t, [CASHIER], safe_attended=True) for t in range(10, 14)]
    assert UnrecountedCashToSafeRule().evaluate(timeline(states), rules_cfg()) == []


def test_collector_drops_bag_and_leaves_fires():
    collector = person(3, COUNTER, first_seen=2.0)
    states = [state(t, [CASHIER]) for t in range(0, 2)] + [state(t, [CASHIER, collector], bags=1) for t in range(2, 6)]
    states += [state(t, [CASHIER], bags=1) for t in range(6, 20)]
    found = CollectorHandoverUnverifiedRule().evaluate(timeline(states), rules_cfg())
    assert len(found) == 1 and found[0].onset == 2.0 and found[0].end == 6.0


def test_collector_waits_while_bag_is_opened_is_clean():
    collector = person(3, COUNTER, first_seen=2.0)
    states = [state(t, [CASHIER]) for t in range(0, 2)] + [state(t, [CASHIER, collector], bags=1) for t in range(2, 6)]
    states += [state(t, [CASHIER, collector], bags=1, cash=1) for t in range(6, 12)] + [state(t, [CASHIER], bags=1) for t in range(12, 20)]
    assert CollectorHandoverUnverifiedRule().evaluate(timeline(states), rules_cfg()) == []
