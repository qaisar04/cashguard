from __future__ import annotations

import numpy as np
import pytest

from app.settings import EMBEDDING_GLOBAL, EMBEDDING_SPATIAL
from pipeline.crop_state import STATE_UNKNOWN, CropStateClassifier, Prototypes, PrototypesMismatch, load_prototypes
from pipeline.observers.state import smooth

OPEN = "open"
CLOSED = "closed"
AXES = {OPEN: np.array([1.0, 0.0, 0.0], dtype=np.float32), CLOSED: np.array([0.0, 1.0, 0.0], dtype=np.float32)}


class FakeClip:
    """Embeds a crop whose first pixel value selects a direction: 0 open axis, 1 closed axis, 2 far away, 3 in between."""

    def embed(self, crop: np.ndarray) -> np.ndarray:
        code = int(crop.flat[0])
        if code == 2:
            return np.array([0.0, 0.0, 1.0], dtype=np.float32)
        if code == 3:
            return np.array([0.6, 0.8, 0.0], dtype=np.float32)
        return AXES[OPEN] if code == 0 else AXES[CLOSED]

    def embed_spatial(self, crop: np.ndarray) -> np.ndarray:
        raise AssertionError("global prototypes must use the global embedding")


def region(code: int) -> np.ndarray:
    return np.full((4, 4, 3), code, dtype=np.uint8)


def prototypes() -> Prototypes:
    noisy_open = [np.array([0.95, 0.3, 0.0]), np.array([0.9, 0.4, 0.0])]
    embeddings = np.stack([AXES[OPEN], *noisy_open, AXES[CLOSED], np.array([0.3, 0.95, 0.0])]).astype(np.float32)
    labels = np.array([OPEN, OPEN, OPEN, CLOSED, CLOSED])
    return Prototypes(embeddings, labels, EMBEDDING_GLOBAL)


def classifier(knn_k: int = 1, min_similarity: float = 0.0) -> CropStateClassifier:
    return CropStateClassifier(prototypes(), FakeClip(), knn_k, min_similarity, (OPEN, CLOSED))


def test_nearest_prototype_label():
    assert classifier().classify(region(0)) == OPEN
    assert classifier().classify(region(1)) == CLOSED


def test_knn_majority_vote():
    assert classifier(knn_k=1).classify(region(3)) == CLOSED  # single nearest prototype is a closed one
    assert classifier(knn_k=3).classify(region(3)) == OPEN  # the two noisy open prototypes outvote it


def test_far_crop_is_unknown():
    assert classifier(min_similarity=0.5).classify(region(2)) == STATE_UNKNOWN
    assert classifier(min_similarity=0.0).classify(region(2)) != STATE_UNKNOWN


def test_similarity_is_best_match():
    assert classifier().similarity(region(0)) == pytest.approx(1.0)
    assert classifier().similarity(region(2)) == pytest.approx(0.0)


def test_label_outside_known_states_is_unknown():
    clf = CropStateClassifier(prototypes(), FakeClip(), 1, 0.0, (CLOSED,))
    assert clf.classify(region(0)) == STATE_UNKNOWN


def test_save_load_roundtrip_keeps_embedding_kind(tmp_path):
    path = tmp_path / "p.npz"
    proto = Prototypes(np.eye(2, dtype=np.float32), np.array([OPEN, CLOSED]), EMBEDDING_SPATIAL)
    proto.save(path, np.array(["X-1", "X-2"]))
    loaded = load_prototypes(path, "test", EMBEDDING_SPATIAL)
    assert loaded is not None and loaded.embedding == EMBEDDING_SPATIAL and loaded.labels.tolist() == [OPEN, CLOSED]
    with pytest.raises(PrototypesMismatch):
        load_prototypes(path, "test", EMBEDDING_GLOBAL)


def test_missing_prototypes_return_none(tmp_path):
    assert load_prototypes(tmp_path / "missing.npz", "test", EMBEDDING_GLOBAL) is None


def test_smooth_removes_lone_flips():
    assert smooth([OPEN, OPEN, CLOSED, OPEN, OPEN], 3) == [OPEN] * 5
    assert smooth([CLOSED, OPEN, OPEN, OPEN, CLOSED], 3) == [CLOSED, OPEN, OPEN, OPEN, CLOSED]
    assert smooth([OPEN, CLOSED], 1) == [OPEN, CLOSED]
