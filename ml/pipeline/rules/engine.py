from __future__ import annotations

import logging

from app.settings import RulesConfig
from pipeline.rules.base import Candidate, Rule
from pipeline.rules.cash_exposed_to_visitor import CashExposedToVisitorRule
from pipeline.rules.cash_not_machine_verified import CashNotMachineVerifiedRule
from pipeline.rules.cash_room_door_open import CashRoomDoorOpenRule
from pipeline.rules.collector_handover_unverified import CollectorHandoverUnverifiedRule
from pipeline.rules.counting_not_in_client_presence import CountingNotInClientPresenceRule
from pipeline.rules.no_client_identification import NoClientIdentificationRule
from pipeline.rules.safe_left_open import SafeLeftOpenRule
from pipeline.rules.unauthorized_entry import UnauthorizedEntryRule
from pipeline.rules.unrecounted_cash_to_safe import UnrecountedCashToSafeRule
from pipeline.rules.valuables_left_unattended import ValuablesLeftUnattendedRule
from pipeline.rules.workstation_unlocked import WorkstationUnlockedRule
from pipeline.timeline import Timeline

log = logging.getLogger(__name__)


ALL_RULES: list[Rule] = [
    WorkstationUnlockedRule(),
    ValuablesLeftUnattendedRule(),
    SafeLeftOpenRule(),
    CashRoomDoorOpenRule(),
    UnauthorizedEntryRule(),
    CashExposedToVisitorRule(),
    CashNotMachineVerifiedRule(),
    NoClientIdentificationRule(),
    UnrecountedCashToSafeRule(),
    CollectorHandoverUnverifiedRule(),
    CountingNotInClientPresenceRule(),
]


class UnknownRule(ValueError):
    pass


def default_rules(enabled: list[str] | None = None) -> list[Rule]:
    if enabled is None:
        return list(ALL_RULES)
    known = {rule.type_id: rule for rule in ALL_RULES}
    unknown = [type_id for type_id in enabled if type_id not in known]
    if unknown:
        raise UnknownRule(f"rules.enabled contains unknown rule(s): {unknown}")
    return [known[type_id] for type_id in enabled]


class RuleEngine:
    def __init__(self, rules: list[Rule], cfg: RulesConfig):
        self.rules = rules
        self.cfg = cfg

    def run(self, timeline: Timeline) -> list[Candidate]:
        candidates: list[Candidate] = []
        for rule in self.rules:
            found = rule.evaluate(timeline, self.cfg)
            log.info("rule %s: %d candidate(s)", rule.type_id, len(found))
            candidates.extend(found)
        candidates = _suppress(candidates)
        candidates = _merge_same_type(candidates, self.cfg.merge_gap_sec)
        candidates.sort(key=lambda c: c.onset)
        return candidates[: self.cfg.max_events]


def _suppress(candidates: list[Candidate]) -> list[Candidate]:
    kept: list[Candidate] = []
    for c in candidates:
        overlapped = any(
            c.type_id in other.suppresses and _overlaps(c, other, slack=1.0) for other in candidates if other is not c
        )
        if not overlapped:
            kept.append(c)
    return kept


def _overlaps(a: Candidate, b: Candidate, slack: float) -> bool:
    return a.onset <= b.end + slack and b.onset <= a.end + slack


def _merge_same_type(candidates: list[Candidate], gap_sec: float) -> list[Candidate]:
    merged: list[Candidate] = []
    for c in sorted(candidates, key=lambda c: (c.type_id, c.onset)):
        last = merged[-1] if merged else None
        if last is not None and last.type_id == c.type_id and c.onset - last.end <= gap_sec:
            last.end = max(last.end, c.end)
            continue
        merged.append(c)
    return merged
