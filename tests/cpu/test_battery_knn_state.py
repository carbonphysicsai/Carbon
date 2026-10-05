"""KNN-STATE-DIGEST-01: battery KNN's versioned state digest.

`params_sha256` keeps its meaning (the stored TRAIN targets only, as the
exam-design campaign's research KNN reports it); `state_sha256`
(`carbon.battery.knn-state.v1`) also binds `k`, `train_fraction` and the unit
inputs. Engineering fixtures only: a 48-case TRAIN subset, seed 0.
"""

from __future__ import annotations

import hashlib

import pytest

from carbon.battery import knn_state


@pytest.fixture(scope="module")
def material():
    pytest.importorskip("jax")
    from carbon.battery import challenge as ch

    loaded = ch.PublicMaterial.load()
    return loaded, loaded.train.subset(48)


def _fit(material, **parameters):
    from carbon.battery.compile import compile_recipe, rebuild
    from carbon.reconstruction import capability_registry as r

    loaded, train = material
    strategy = {
        "schema_version": "1.0",
        "challenge_id": r.BATTERY_CHALLENGE,
        "backbone": "knn",
        "parameters": parameters,
    }
    _, recipe = compile_recipe(strategy)
    return rebuild(recipe, loaded, 0, train=train)


def test_params_sha256_keeps_its_meaning(material):
    model, stats = _fit(material)
    assert stats["params_sha256"] == hashlib.sha256(model.y.tobytes()).hexdigest()
    assert stats["state_schema"] == knn_state.SCHEMA == "carbon.battery.knn-state.v1"
    assert stats["state_sha256"] == knn_state.state_sha256(model)
    assert stats["state_sha256"] != stats["params_sha256"]


def test_state_digest_binds_neighbours_and_train_fraction(material):
    _, base = _fit(material, neighbours=3)
    _, other_k = _fit(material, neighbours=7)
    _, half = _fit(material, neighbours=3, train_fraction=0.5)
    assert base["params_sha256"] == other_k["params_sha256"]
    assert base["state_sha256"] != other_k["state_sha256"]
    assert half["state_sha256"] not in {base["state_sha256"], other_k["state_sha256"]}
    assert knn_state.trained_identity(base) != knn_state.trained_identity(other_k)


def test_state_digest_is_deterministic(material):
    _, first = _fit(material, neighbours=5)
    _, again = _fit(material, neighbours=5)
    assert first["state_sha256"] == again["state_sha256"]


def test_records_without_the_digest_keep_their_identity():
    old = {"seconds": 0.0, "params_sha256": "a" * 64}
    assert knn_state.trained_identity(old) == ("params_sha256", "a" * 64)
    new = {**old, "state_schema": knn_state.SCHEMA, "state_sha256": "b" * 64}
    assert knn_state.trained_identity(new) == (knn_state.SCHEMA, "b" * 64)
    with pytest.raises(ValueError):
        knn_state.trained_identity(
            {**new, "state_schema": "carbon.battery.knn-state.v9"}
        )
    with pytest.raises(ValueError):
        knn_state.trained_identity({**old, "state_sha256": "b" * 64})


def test_other_families_and_unfitted_knns():
    stats = {"params_sha256": "c" * 64}
    assert knn_state.with_state(object(), stats) is stats
    with pytest.raises(TypeError):
        knn_state.state_sha256(object())
    with pytest.raises(ValueError):
        knn_state.state_sha256(knn_state.KNN(3))


def test_digest_module_moves_no_level0_identity():
    """Outside the implementation digest and the practice worker's staged
    files, so Level-0 recipe, built-record and program digests stay put."""
    from carbon.battery import contracts, practice

    assert "knn_state.py" not in contracts.IMPLEMENTATION_MODULES
    assert "knn_state.py" not in set(practice.STAGED_MODULES.values())
