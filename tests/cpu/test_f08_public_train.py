"""The partial f08 DEVELOPMENT TRAIN is pinned and keeps provenance explicit."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest

from carbon.challenge_kit import f08_train


def test_f08_public_train_is_partial_pinned_and_immutable():
    material = f08_train.load_public_train()
    assert hashlib.sha256(material["train"]).hexdigest() == f08_train.TRAIN_SHA256
    assert material["inputs"].shape == (255, 6)
    assert material["targets"].shape == (255, 7)
    assert material["inputs"].dtype == material["targets"].dtype == np.float32
    assert not material["inputs"].flags.writeable
    assert not material["targets"].flags.writeable
    assert len(material["case_ids"]) == 255
    assert "train-0016" not in material["case_ids"]
    provenance = material["provenance"]
    assert provenance["original_256_complete"] is False
    assert provenance["failed_case"] == {
        "id": "train-0016",
        "status": "OBSERVER_FAILED",
    }
    assert provenance["original_action_evaluation_role"] == "EXCLUDED_ALL_256"
    assert len(provenance["original_action_sha256"]) == 256
    assert "mass_kg" not in provenance["learned_targets"]
    assert "cad_mass_kg" not in provenance["learned_targets"]


def test_f08_public_train_refuses_changed_bytes(tmp_path, monkeypatch):
    source = f08_train._DATA
    train = (source / f08_train._TRAIN).read_bytes()
    provenance = (source / f08_train._PROVENANCE).read_bytes()
    (tmp_path / f08_train._TRAIN).write_bytes(train[:-1] + bytes([train[-1] ^ 1]))
    (tmp_path / f08_train._PROVENANCE).write_bytes(provenance)
    monkeypatch.setattr(f08_train, "_DATA", tmp_path)
    with pytest.raises(ValueError, match="artifact identity differs"):
        f08_train.load_public_train()
