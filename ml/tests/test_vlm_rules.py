from __future__ import annotations

from pipeline.observers.vlm import (
    ACTION_BAG_CHECKED,
    ACTION_BAG_HANDOVER,
    ACTION_CASH_INTO_SAFE,
    ACTION_CLIENT_GIVES_CASH,
    ACTION_HAND_COUNTING,
    ACTION_ID_DOCUMENT,
    ACTION_MACHINE_COUNTING,
)
from pipeline.rules.cash_not_machine_verified import CashNotMachineVerifiedRule
from pipeline.rules.collector_handover_unverified import CollectorHandoverUnverifiedRule
from pipeline.rules.counting_not_in_client_presence import CountingNotInClientPresenceRule
from pipeline.rules.engine import default_rules
from pipeline.rules.no_client_identification import NoClientIdentificationRule
from pipeline.rules.unrecounted_cash_to_safe import UnrecountedCashToSafeRule
from tests.helpers import COUNTER, ENABLED, SEAT, person, rules_cfg, state, timeline

CASHIER = person(1, SEAT)
CLIENT = person(2, COUNTER, first_seen=2.0)


def test_all_new_rules_are_registered():
    assert {r.type_id for r in default_rules(ENABLED)} >= {
        "cash_not_machine_verified", "no_client_identification", "unrecounted_cash_to_safe",
        "collector_handover_unverified", "counting_not_in_client_presence",
    }


def test_hand_counting_without_machine_fires():
    states = [state(t, [CASHIER, CLIENT]) for t in range(0, 20)]
    states += [state(t, [CASHIER, CLIENT], actions=[ACTION_HAND_COUNTING]) for t in range(20, 26)]
    found = CashNotMachineVerifiedRule().evaluate(timeline(states), rules_cfg())
    assert len(found) == 1 and found[0].onset == 20.0
    assert found[0].evidence_ts == [20.0, 22.5, 25.0]
    assert "вручную" in found[0].description


def test_hand_counting_next_to_machine_counting_is_a_precount():
    states = [state(t, [CASHIER, CLIENT], actions=[ACTION_HAND_COUNTING]) for t in range(10, 16)]
    states += [state(t, [CASHIER, CLIENT], actions=[ACTION_MACHINE_COUNTING]) for t in range(16, 22)]
    assert CashNotMachineVerifiedRule().evaluate(timeline(states), rules_cfg()) == []


def test_cash_without_id_document_fires():
    states = [state(t, [CASHIER, CLIENT]) for t in range(0, 10)]
    states += [state(t, [CASHIER, CLIENT], actions=[ACTION_CLIENT_GIVES_CASH]) for t in range(10, 16)]
    found = NoClientIdentificationRule().evaluate(timeline(states), rules_cfg())
    assert len(found) == 1 and found[0].onset == 10.0


def test_cash_after_id_document_is_clean():
    states = [state(t, [CASHIER, CLIENT], actions=[ACTION_ID_DOCUMENT]) for t in range(0, 6)]
    states += [state(t, [CASHIER, CLIENT], actions=[ACTION_CLIENT_GIVES_CASH]) for t in range(10, 16)]
    assert NoClientIdentificationRule().evaluate(timeline(states), rules_cfg()) == []


def test_cash_into_safe_without_recount_fires():
    states = [state(t, [CASHIER]) for t in range(0, 45)]
    states += [state(t, [CASHIER], actions=[ACTION_CASH_INTO_SAFE]) for t in range(45, 51)]
    found = UnrecountedCashToSafeRule().evaluate(timeline(states), rules_cfg())
    assert len(found) == 1 and found[0].onset == 45.0
    assert "сейф" in found[0].description


def test_cash_into_safe_after_counting_is_clean():
    states = [state(t, [CASHIER], actions=[ACTION_HAND_COUNTING]) for t in range(20, 40)]
    states += [state(t, [CASHIER]) for t in range(40, 45)]
    states += [state(t, [CASHIER], actions=[ACTION_CASH_INTO_SAFE]) for t in range(45, 51)]
    assert UnrecountedCashToSafeRule().evaluate(timeline(states), rules_cfg()) == []


def test_collector_leaving_right_after_handover_fires():
    states = [state(t, [CASHIER, CLIENT], actions=[ACTION_BAG_HANDOVER]) for t in range(5, 9)]
    states += [state(t, [CASHIER]) for t in range(9, 20)]
    found = CollectorHandoverUnverifiedRule().evaluate(timeline(states), rules_cfg())
    assert len(found) == 1 and found[0].onset == 5.0 and found[0].end == 9.0
    assert "инкассатор" in found[0].description


def test_collector_staying_for_the_check_is_clean():
    states = [state(t, [CASHIER, CLIENT], actions=[ACTION_BAG_HANDOVER]) for t in range(5, 9)]
    states += [state(t, [CASHIER, CLIENT], actions=[ACTION_BAG_CHECKED]) for t in range(9, 30)]
    states += [state(t, [CASHIER]) for t in range(30, 35)]
    assert CollectorHandoverUnverifiedRule().evaluate(timeline(states), rules_cfg()) == []


def test_collector_leaving_much_later_is_clean():
    states = [state(t, [CASHIER, CLIENT], actions=[ACTION_BAG_HANDOVER]) for t in range(5, 9)]
    states += [state(t, [CASHIER, CLIENT]) for t in range(9, 40)]
    states += [state(t, [CASHIER]) for t in range(40, 45)]
    assert CollectorHandoverUnverifiedRule().evaluate(timeline(states), rules_cfg()) == []


def test_client_leaving_during_counting_fires():
    states = [state(t, [CASHIER, CLIENT], actions=[ACTION_MACHINE_COUNTING]) for t in range(8, 13)]
    states += [state(t, [CASHIER], actions=[ACTION_MACHINE_COUNTING]) for t in range(13, 20)]
    found = CountingNotInClientPresenceRule().evaluate(timeline(states), rules_cfg())
    assert len(found) == 1 and found[0].onset == 13.0 and found[0].end == 19.0
    assert "клиент покидает" in found[0].description


def test_client_present_until_counting_ends_is_clean():
    states = [state(t, [CASHIER, CLIENT], actions=[ACTION_MACHINE_COUNTING]) for t in range(8, 20)]
    states += [state(t, [CASHIER]) for t in range(20, 25)]
    assert CountingNotInClientPresenceRule().evaluate(timeline(states), rules_cfg()) == []


def test_counting_that_ends_right_after_client_leaves_is_clean():
    states = [state(t, [CASHIER, CLIENT], actions=[ACTION_MACHINE_COUNTING]) for t in range(8, 13)]
    states += [state(t, [CASHIER], actions=[ACTION_MACHINE_COUNTING]) for t in range(13, 15)]
    assert CountingNotInClientPresenceRule().evaluate(timeline(states), rules_cfg()) == []
