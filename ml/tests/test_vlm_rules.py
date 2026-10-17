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


def test_cash_without_id_document_fires():
    states = [state(t, [CASHIER, CLIENT]) for t in range(0, 10)]
    states += [state(t, [CASHIER, CLIENT], actions=[ACTION_CLIENT_GIVES_CASH]) for t in range(10, 16)]
    found = NoClientIdentificationRule().evaluate(timeline(states), rules_cfg())
    assert len(found) == 1 and found[0].onset == 10.0


def test_collector_bag_is_not_a_client_payment():
    states = [state(t, [CASHIER, CLIENT], actions=[ACTION_CLIENT_GIVES_CASH, ACTION_BAG_HANDOVER]) for t in range(5, 11)]
    assert NoClientIdentificationRule().evaluate(timeline(states), rules_cfg()) == []


def test_cash_after_id_document_is_clean():
    states = [state(t, [CASHIER, CLIENT], actions=[ACTION_ID_DOCUMENT]) for t in range(0, 6)]
    states += [state(t, [CASHIER, CLIENT], actions=[ACTION_CLIENT_GIVES_CASH]) for t in range(10, 16)]
    assert NoClientIdentificationRule().evaluate(timeline(states), rules_cfg()) == []


