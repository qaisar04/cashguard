from __future__ import annotations

import numpy as np

from app.settings import VlmConfig, ZonesConfig
from pipeline.observers.base import ATTR_ACTION, ATTR_WINDOW, KIND_ACTION, KIND_MONITOR, KIND_PERSON, Observation
from pipeline.observers.vlm import (
    ACTION_CLIENT_GIVES_CASH,
    ACTION_HAND_COUNTING,
    ACTION_ID_DOCUMENT,
    MODE_JSON,
    MODE_YES_NO,
    QUESTIONS,
    VlmObserver,
    build_prompt,
    build_yes_no_prompt,
    parse_answer,
    select_windows,
)
from pipeline.timeline import build_timeline
from pipeline.video import Frame
from pipeline.zones import build_zones
from tests.helpers import DOOR_POLY, GLASS_POLY, SEAT, box_at

HEIGHT, WIDTH = 160, 90


def frames(seconds: int) -> list[Frame]:
    return [Frame(index=t * 30, ts=float(t), image=np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)) for t in range(seconds)]


def zones_cfg() -> ZonesConfig:
    return ZonesConfig(cashier_radius=0.16, desk_radius=0.3, safe_radius=0.18, door=DOOR_POLY, glass=GLASS_POLY)


def vlm_cfg(**overrides) -> VlmConfig:
    return VlmConfig(**{"enabled": True, "stride_sec": 5, "window_sec": 6, "frames_per_window": 3, "max_side": 64, **overrides})


def prior_with_person(seconds: list[float]) -> list[Observation]:
    monitor = [Observation(ts=0.0, kind=KIND_MONITOR, box=box_at(SEAT), score=0.9)]
    persons = [Observation(ts=t, kind=KIND_PERSON, box=box_at(SEAT, 0.1), score=0.9) for t in seconds]
    return monitor + persons


class FakeBackend:
    def __init__(self, answer: str = "{}", probabilities: dict[str, float] | None = None):
        self.answer = answer
        self.probabilities = probabilities or {}
        self.calls: list[tuple[int, str]] = []

    def ask(self, images, prompt):
        self.calls.append((len(images), prompt))
        return self.answer

    def yes_probability(self, images, prompt):
        self.calls.append((len(images), prompt))
        return next((p for action, p in self.probabilities.items() if QUESTIONS[action] in prompt), 0.0)


def test_parse_answer_maps_yes_unsure_no_and_ignores_noise():
    text = 'Sure, here it is: {"hand_counting": "yes", "machine_counting": "no", "id_document": "unsure", "weird": "yes"} thanks'
    assert parse_answer(text) == {ACTION_HAND_COUNTING: 0.9, ACTION_ID_DOCUMENT: 0.5}


def test_parse_answer_accepts_booleans_and_numbers():
    assert parse_answer('{"client_gives_cash": true, "hand_counting": 0.7, "id_document": false}') == {
        ACTION_CLIENT_GIVES_CASH: 0.9,
        ACTION_HAND_COUNTING: 0.7,
    }


def test_parse_answer_is_empty_on_garbage():
    assert parse_answer("I cannot tell.") == {}
    assert parse_answer('{"hand_counting": ') == {}
    assert parse_answer("[1, 2]") == {}
    assert parse_answer("") == {}


def test_prompt_lists_every_action_key():
    prompt = build_prompt(3, 3.0)
    for key in (ACTION_HAND_COUNTING, ACTION_CLIENT_GIVES_CASH, ACTION_ID_DOCUMENT):
        assert f'"{key}"' in prompt


def test_windows_follow_stride_and_skip_empty_room():
    all_frames = frames(21)
    prior = prior_with_person([0.0, 1.0, 2.0, 3.0, 15.0, 16.0, 17.0])
    zones = build_zones(zones_cfg(), prior, WIDTH / HEIGHT)
    windows = select_windows(all_frames, prior, zones, vlm_cfg())
    assert [(w.start, w.end) for w in windows] == [(0.0, 6.0), (10.0, 16.0), (15.0, 20.0)]
    assert [f.ts for f in windows[0].frames] == [0.0, 3.0, 6.0]


def test_windows_cover_everything_without_person_filter():
    all_frames = frames(11)
    zones = build_zones(zones_cfg(), [], WIDTH / HEIGHT)
    windows = select_windows(all_frames, [], zones, vlm_cfg(require_person_near_desk=False))
    assert [(w.start, w.end) for w in windows] == [(0.0, 6.0), (5.0, 10.0)]


def test_yes_no_prompt_names_the_question():
    assert QUESTIONS[ACTION_ID_DOCUMENT] in build_yes_no_prompt(ACTION_ID_DOCUMENT, 3, 3.0)


def test_observer_in_yes_no_mode_asks_every_question_and_keeps_confident_ones():
    backend = FakeBackend(probabilities={ACTION_HAND_COUNTING: 0.8, ACTION_ID_DOCUMENT: 0.3})
    observer = VlmObserver(vlm_cfg(mode=MODE_YES_NO, min_confidence=0.6), zones_cfg(), backend)
    found = observer.observe(frames(6), prior=prior_with_person([float(t) for t in range(6)]))
    assert [o.attrs[ATTR_ACTION] for o in found] == [ACTION_HAND_COUNTING]
    assert found[0].score == 0.8
    assert len(backend.calls) == len(QUESTIONS)


def test_observer_emits_actions_above_min_confidence_and_timeline_spreads_them():
    backend = FakeBackend('{"hand_counting": "yes", "id_document": "unsure", "machine_counting": "no"}')
    observer = VlmObserver(vlm_cfg(mode=MODE_JSON, min_confidence=0.6), zones_cfg(), backend)
    all_frames = frames(6)
    prior = prior_with_person([float(t) for t in range(6)])
    found = observer.observe(all_frames, prior=prior)
    assert len(found) == 1
    assert found[0].kind == KIND_ACTION and found[0].attrs[ATTR_ACTION] == ACTION_HAND_COUNTING
    assert found[0].attrs[ATTR_WINDOW] == [0.0, 5.0] and found[0].score == 0.9
    assert backend.calls[0][0] == 3
    zones = build_zones(zones_cfg(), prior, WIDTH / HEIGHT)
    timeline = build_timeline([f.ts for f in all_frames], prior + found, [], zones)
    assert all(s.actions == [ACTION_HAND_COUNTING] for s in timeline.states)


def test_observer_crops_to_desk_and_people():
    captured: list = []

    class Spy:
        def ask(self, images, prompt):
            captured.extend(images)
            return "{}"

        def yes_probability(self, images, prompt):
            return 0.0

    observer = VlmObserver(vlm_cfg(mode=MODE_JSON), zones_cfg(), Spy())
    assert observer.observe(frames(3), prior=prior_with_person([0.0, 1.0, 2.0])) == []
    assert captured and all(img.shape[0] <= 64 and img.shape[1] <= 64 for img in captured)
    assert captured[0].shape[0] < HEIGHT
