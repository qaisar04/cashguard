from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Protocol, Sequence

import numpy as np

from app.settings import VlmConfig, ZonesConfig
from pipeline.geometry import Box, center, clip
from pipeline.observers.base import ATTR_ACTION, ATTR_WINDOW, FULL_FRAME_BOX, KIND_ACTION, KIND_PERSON, Observation
from pipeline.video import Frame
from pipeline.zones import Zones, build_zones

log = logging.getLogger(__name__)

ACTION_HAND_COUNTING = "hand_counting"
ACTION_MACHINE_COUNTING = "machine_counting"
ACTION_CLIENT_GIVES_CASH = "client_gives_cash"
ACTION_ID_DOCUMENT = "id_document"
ACTION_CASH_INTO_SAFE = "cash_into_safe"
ACTION_BAG_HANDOVER = "bag_handover"
ACTION_BAG_CHECKED = "bag_checked"

QUESTIONS: dict[str, str] = {
    ACTION_HAND_COUNTING: "the teller counts, sorts or flips through banknotes with her hands",
    ACTION_MACHINE_COUNTING: "the teller puts banknotes into the counting machine or takes them out of it",
    ACTION_CLIENT_GIVES_CASH: "a visitor hands cash to the teller or lays cash on the desk",
    ACTION_ID_DOCUMENT: "a visitor shows or hands over an ID card or passport, or the teller holds such a document",
    ACTION_CASH_INTO_SAFE: "the teller puts bundles of money or a money bag into a safe or cabinet",
    ACTION_BAG_HANDOVER: "a visitor puts a bag or pouch on the desk or hands it to the teller",
    ACTION_BAG_CHECKED: "the teller opens a bag, or checks or signs papers, while a visitor is still standing at the desk",
}
ANSWER_SCORES = {"yes": 0.9, "unsure": 0.5, "no": 0.0}
PROMPT_HEADER = (
    "These are {n} frames taken about {gap:.0f} seconds apart by a fixed camera above a bank teller's desk. "
    "The teller sits at the desk with a laptop and a grey banknote counting machine; a client or a cash collector "
    "may stand on the other side of the desk. Judge only what is visible in these frames.\n"
    "Answer with one JSON object whose keys are listed below and whose values are \"yes\", \"no\" or \"unsure\":\n"
)
PROMPT_FOOTER = "Reply with the JSON object only."
LIST_HEADER = (
    "Below is a list of statements with a key each. Reply with the keys of the statements that are true in these "
    "frames, separated by commas, or with the single word none. Do not explain.\n"
)
LIST_FOOTER = "Keys:"
LISTED_SCORE = 0.9
SCENE = (
    "These are {n} frames taken about {gap:.0f} seconds apart by a fixed camera above a bank teller's desk. "
    "The teller sits at the desk with a laptop and a grey banknote counting machine; a client or a cash collector "
    "may stand on the other side of the desk."
)
YES_NO_PROMPT = SCENE + " Looking only at these frames: is it true that {question}? Answer yes or no."
MODE_JSON = "json"
MODE_YES_NO = "yes_no"
MODE_LIST = "list"
JSON_OBJECT = re.compile(r"\{.*?\}", re.DOTALL)
MIN_WINDOW_FRAMES = 2
SINGLE_TILE_EDGE = 512
YES_WORDS = ("Yes", "yes", " Yes", " yes")
NO_WORDS = ("No", "no", " No", " no")
DESK_CROP_HEIGHT_FACTOR = 0.5  # the desk surface is flat: half the desk radius covers it vertically


def build_prompt(n_frames: int, gap_sec: float) -> str:
    lines = [f'- "{action}": {text}' for action, text in QUESTIONS.items()]
    return PROMPT_HEADER.format(n=n_frames, gap=gap_sec) + "\n".join(lines) + "\n" + PROMPT_FOOTER


def build_list_prompt(n_frames: int, gap_sec: float) -> str:
    lines = [f'- {action}: {text}' for action, text in QUESTIONS.items()]
    return SCENE.format(n=n_frames, gap=gap_sec) + "\n" + LIST_HEADER + "\n".join(lines) + "\n" + LIST_FOOTER


def parse_listed(text: str) -> dict[str, float]:
    """Keys the model listed as true; `none`, prose or garbage yields no event."""
    found = {key for key in QUESTIONS if re.search(rf"\b{re.escape(key)}\b", text or "")}
    return {key: LISTED_SCORE for key in found}


def build_yes_no_prompt(action: str, n_frames: int, gap_sec: float) -> str:
    return YES_NO_PROMPT.format(n=n_frames, gap=gap_sec, question=QUESTIONS[action])


def parse_answer(text: str) -> dict[str, float]:
    """Maps the model's JSON answer to {action: confidence}; anything unparsable or unknown means 'no event'."""
    match = JSON_OBJECT.search(text or "")
    if match is None:
        return {}
    try:
        raw = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    result: dict[str, float] = {}
    for key, value in raw.items():
        if key not in QUESTIONS:
            continue
        score = _score(value)
        if score > 0:
            result[key] = score
    return result


def _score(value) -> float:
    if isinstance(value, bool):
        return ANSWER_SCORES["yes"] if value else 0.0
    if isinstance(value, (int, float)):
        return min(max(float(value), 0.0), 1.0)
    if isinstance(value, str):
        return ANSWER_SCORES.get(value.strip().lower(), 0.0)
    return 0.0


class VlmBackend(Protocol):
    def ask(self, images: list[np.ndarray], prompt: str) -> str: ...

    def yes_probability(self, images: list[np.ndarray], prompt: str) -> float: ...


@dataclass(frozen=True)
class Window:
    frames: list[Frame]

    @property
    def start(self) -> float:
        return self.frames[0].ts

    @property
    def end(self) -> float:
        return self.frames[-1].ts

    @property
    def gap_sec(self) -> float:
        return (self.end - self.start) / max(len(self.frames) - 1, 1)


class VlmObserver:
    """Asks a small VLM yes/no questions about short frame windows and emits `action` observations."""

    name = "vlm"

    def __init__(self, cfg: VlmConfig, zones_cfg: ZonesConfig, backend: VlmBackend):
        self.cfg = cfg
        self.zones_cfg = zones_cfg
        self.backend = backend

    def observe(self, frames: list[Frame], prior: Sequence[Observation] = ()) -> list[Observation]:
        if not frames:
            return []
        aspect = frames[0].width / frames[0].height
        zones = build_zones(self.zones_cfg, list(prior), aspect)
        windows = select_windows(frames, prior, zones, self.cfg)
        observations: list[Observation] = []
        started = time.monotonic()
        for window in windows:
            observations.extend(self._observe_window(window, prior, zones))
        elapsed = time.monotonic() - started
        log.info("vlm: %d windows in %.1f s (%.2f s/window) -> %d actions", len(windows), elapsed, elapsed / max(len(windows), 1), len(observations))
        return observations

    def _observe_window(self, window: Window, prior: Sequence[Observation], zones: Zones) -> list[Observation]:
        crop = crop_box(window, prior, zones, self.cfg)
        images = [_crop_resize(f.image, crop, self.cfg.max_side) for f in window.frames]
        scores = self._scores(images, window)
        log.debug("vlm window %.0f-%.0f: %s", window.start, window.end, scores)
        return [
            Observation(
                ts=window.start,
                kind=KIND_ACTION,
                box=FULL_FRAME_BOX,
                score=score,
                attrs={ATTR_ACTION: action, ATTR_WINDOW: [window.start, window.end]},
            )
            for action, score in scores.items()
            if score >= self.cfg.min_confidence
        ]

    def _scores(self, images: list[np.ndarray], window: Window) -> dict[str, float]:
        if self.cfg.mode == MODE_JSON:
            return parse_answer(self.backend.ask(images, build_prompt(len(images), window.gap_sec)))
        if self.cfg.mode == MODE_LIST:
            return parse_listed(self.backend.ask(images, build_list_prompt(len(images), window.gap_sec)))
        return {
            action: self.backend.yes_probability(images, build_yes_no_prompt(action, len(images), window.gap_sec))
            for action in QUESTIONS
        }


def select_windows(frames: list[Frame], prior: Sequence[Observation], zones: Zones, cfg: VlmConfig) -> list[Window]:
    persons_at = _person_timestamps_near_desk(prior, zones) if cfg.require_person_near_desk else None
    windows: list[Window] = []
    t0 = frames[0].ts
    last = frames[-1].ts
    min_frames = min(cfg.frames_per_window, MIN_WINDOW_FRAMES)
    while t0 <= last:
        picked = _pick_frames(frames, t0, min(t0 + cfg.window_sec, last), cfg.frames_per_window)
        if len(picked) >= min_frames and (persons_at is None or any(f.ts in persons_at for f in picked)):
            windows.append(Window(frames=picked))
        t0 += cfg.stride_sec
    return windows


def _person_timestamps_near_desk(prior: Sequence[Observation], zones: Zones) -> set[float] | None:
    persons = [o for o in prior if o.kind == KIND_PERSON]
    if not persons:
        return None
    return {o.ts for o in persons if zones.on_desk(center(o.box))}


def _pick_frames(frames: list[Frame], start: float, end: float, count: int) -> list[Frame]:
    targets = [start + (end - start) * i / max(count - 1, 1) for i in range(count)]
    picked: list[Frame] = []
    for target in targets:
        frame = min(frames, key=lambda f: abs(f.ts - target))
        if not picked or frame.ts > picked[-1].ts:
            picked.append(frame)
    return picked


def crop_box(window: Window, prior: Sequence[Observation], zones: Zones, cfg: VlmConfig) -> Box:
    """Desk area plus every person seen in the window, so hands and the counting machine stay large in the crop."""
    boxes: list[Box] = []
    if zones.monitor is not None:
        mx, my = zones.monitor
        dx, dy = zones.desk_radius / zones.aspect, zones.desk_radius * DESK_CROP_HEIGHT_FACTOR
        boxes.append((mx - dx, my - dy, mx + dx, my + dy))
    timestamps = {f.ts for f in window.frames}
    boxes.extend(o.box for o in prior if o.kind == KIND_PERSON and o.ts in timestamps and zones.on_desk(center(o.box)))
    if not boxes:
        return FULL_FRAME_BOX
    x1 = min(b[0] for b in boxes) - cfg.crop_margin
    y1 = min(b[1] for b in boxes) - cfg.crop_margin
    x2 = max(b[2] for b in boxes) + cfg.crop_margin
    y2 = max(b[3] for b in boxes) + cfg.crop_margin
    return clip(_ensure_min_height((x1, y1, x2, y2), cfg.min_crop_height))


def _ensure_min_height(box: Box, min_height: float) -> Box:
    x1, y1, x2, y2 = box
    missing = min_height - (y2 - y1)
    if missing > 0:
        y1 -= missing / 2
        y2 += missing / 2
    return (x1, y1, x2, y2)


def _crop_resize(image: np.ndarray, box: Box, max_side: int) -> np.ndarray:
    import cv2

    h, w = image.shape[:2]
    x1, y1, x2, y2 = int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)
    crop = image[y1:max(y2, y1 + 1), x1:max(x2, x1 + 1)]
    ch, cw = crop.shape[:2]
    scale = max_side / max(ch, cw)
    if scale < 1:
        crop = cv2.resize(crop, (int(cw * scale), int(ch * scale)), interpolation=cv2.INTER_AREA)
    return crop


class HfVlmBackend:
    """Any `image-text-to-text` checkpoint with a multi-image chat template (Qwen3-VL, SmolVLM2, ...)."""

    def __init__(self, model_name: str, device: str, max_new_tokens: int):
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        from pipeline.detectors.base import resolve_device

        self.device = resolve_device(device)
        dtype = torch.float16 if self.device != "cpu" else torch.float32
        self.processor = AutoProcessor.from_pretrained(model_name)
        _disable_tiling(self.processor.image_processor)
        self.model = AutoModelForImageTextToText.from_pretrained(model_name, dtype=dtype).to(self.device).eval()
        self.max_new_tokens = max_new_tokens
        self._yes_ids = self._answer_token_ids(YES_WORDS)
        self._no_ids = self._answer_token_ids(NO_WORDS)
        log.info("vlm backend: %s on %s (%s)", model_name, self.device, dtype)

    def ask(self, images: list[np.ndarray], prompt: str) -> str:
        import torch

        inputs = self._encode(images, prompt)
        with torch.inference_mode():
            generated = self.model.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False)
        new_tokens = generated[:, inputs["input_ids"].shape[1]:]
        return self.processor.batch_decode(new_tokens, skip_special_tokens=True)[0]

    def yes_probability(self, images: list[np.ndarray], prompt: str) -> float:
        """P(yes) / (P(yes) + P(no)) over the first answer token: one forward pass, no sampling."""
        import torch

        inputs = self._encode(images, prompt)
        with torch.inference_mode():
            logits = self.model(**inputs).logits[0, -1].float()
        probs = torch.softmax(logits, dim=-1)
        yes = float(probs[self._yes_ids].sum())
        no = float(probs[self._no_ids].sum())
        return yes / (yes + no) if yes + no > 0 else 0.0

    def _encode(self, images: list[np.ndarray], prompt: str) -> dict:
        from PIL import Image

        pil_images = [Image.fromarray(img[:, :, ::-1]) for img in images]
        content = [{"type": "image", "image": im} for im in pil_images] + [{"type": "text", "text": prompt}]
        messages = [{"role": "user", "content": content}]
        inputs = self.processor.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors="pt"
        )
        return {k: (v.to(self.model.dtype) if v.is_floating_point() else v).to(self.device) for k, v in inputs.items()}

    def _answer_token_ids(self, words: tuple[str, ...]) -> list[int]:
        ids = {self.processor.tokenizer.encode(w, add_special_tokens=False)[0] for w in words}
        return sorted(ids)


def _disable_tiling(image_processor) -> None:
    """SmolVLM/Idefics3 upscale to 2048 px and cut 4x4 tiles (17x64 tokens per image); one tile per image is enough here."""
    if getattr(image_processor, "do_image_splitting", None):
        image_processor.do_image_splitting = False
        image_processor.size = {"longest_edge": SINGLE_TILE_EDGE}
