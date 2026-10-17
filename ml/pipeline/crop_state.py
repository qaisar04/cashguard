from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Callable

import numpy as np

from app.settings import EMBEDDING_GLOBAL, EMBEDDING_SPATIAL, ROOT
from pipeline.clip_zero_shot import ClipZeroShot

log = logging.getLogger(__name__)

STATE_UNKNOWN = "unknown"
KEY_EMBEDDINGS = "embeddings"
KEY_LABELS = "labels"
KEY_VIDEOS = "videos"
KEY_EMBEDDING = "embedding"

Embedder = Callable[[np.ndarray], np.ndarray]


class PrototypesMismatch(ValueError):
    pass


class Prototypes:
    """Labelled CLIP embeddings of crops from the dataset (scripts/build_prototypes.py)."""

    def __init__(self, embeddings: np.ndarray, labels: np.ndarray, embedding: str = EMBEDDING_GLOBAL):
        self.embeddings = embeddings.astype(np.float32)
        self.labels = labels
        self.embedding = embedding

    @classmethod
    def load(cls, path: Path, name: str) -> "Prototypes":
        data = np.load(path)
        embedding = str(data[KEY_EMBEDDING]) if KEY_EMBEDDING in data else EMBEDDING_GLOBAL
        proto = cls(data[KEY_EMBEDDINGS], data[KEY_LABELS], embedding)
        log.info("%s prototypes: %d %s crops from %s (%s)", name, len(proto.labels), embedding, path.name, dict(Counter(proto.labels.tolist())))
        return proto

    def save(self, path: Path, videos: np.ndarray) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            **{KEY_EMBEDDINGS: self.embeddings.astype(np.float16), KEY_LABELS: self.labels, KEY_VIDEOS: videos, KEY_EMBEDDING: self.embedding},
        )

    def best_similarity(self, embedding: np.ndarray) -> float:
        return float((self.embeddings @ embedding).max())

    def vote(self, embedding: np.ndarray, k: int, min_similarity: float) -> str:
        sims = self.embeddings @ embedding
        top = np.argsort(-sims)[:k]
        if float(sims[top[0]]) < min_similarity:
            return STATE_UNKNOWN
        votes = Counter(self.labels[top].tolist())
        return max(votes, key=votes.get)


class CropStateClassifier:
    """Few-shot state of a crop: k-NN over prototype embeddings; a nearest neighbour below min_similarity means unknown."""

    def __init__(self, prototypes: Prototypes, clip: ClipZeroShot, knn_k: int, min_similarity: float, known_states: tuple[str, ...]):
        self.prototypes = prototypes
        self.embed = embedder(clip, prototypes.embedding)
        self.knn_k = knn_k
        self.min_similarity = min_similarity
        self.known_states = known_states

    def classify(self, region: np.ndarray) -> str:
        label = self.prototypes.vote(self.embed(region), self.knn_k, self.min_similarity)
        return label if label in self.known_states else STATE_UNKNOWN

    def similarity(self, region: np.ndarray) -> float:
        """How much the crop looks like any prototype at all: used to tell the object from detector look-alikes."""
        return self.prototypes.best_similarity(self.embed(region))


def embedder(clip: ClipZeroShot, embedding: str) -> Embedder:
    return clip.embed_spatial if embedding == EMBEDDING_SPATIAL else clip.embed


def load_prototypes(path: Path | None, name: str, embedding: str) -> Prototypes | None:
    if path is None:
        return None
    resolved = path if path.is_absolute() else ROOT / path
    if not resolved.is_file():
        log.warning("%s prototypes %s not found", name, resolved)
        return None
    prototypes = Prototypes.load(resolved, name)
    if prototypes.embedding != embedding:
        raise PrototypesMismatch(f"{name} prototypes hold {prototypes.embedding} embeddings, config asks for {embedding}: rebuild them")
    return prototypes
