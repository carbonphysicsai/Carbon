"""Graph route v2 wiring of the self-trust trainer and state (SELF_TRUST H3d-2c-1): the v4 trainer is pinned and named only by a trust
version's adapter block; a trust candidate's fit runs the two-phase trainer around the version's own pinned trainer, its state is the
trust state and its prediction is the physics columns; every other candidate is exactly what it was.
"""

from __future__ import annotations

import dataclasses
import hashlib
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from carbon.development_session import (
    physical_graph_adapter_v2 as v2,
)
from carbon.development_session import (
    physical_graph_state_v2,
    physical_graph_state_v3,
    physical_graph_trainer_v2,
)
from carbon.development_session import (
    physical_graph_trainer_v4 as v4,
)
from carbon.development_session import (
    physical_graph_trust_registry as registry,
)
from carbon.development_session.construction_recipe import RecipeRefused

KEY = next(iter(v2.SPECS))
BASE = v2.SPECS[KEY]
K = 2


def trust_spec_row():
    return dataclasses.replace(BASE, trust_outputs=K)


def model(trust, *, spec=None):
    spec = spec or trust_spec_row()
    members = None
    return v2.EnsembleGraphModel(
        recipe=SimpleNamespace(digest="sha256:" + "a" * 64),
        spec=spec,
        forward={"doc": True},
        prepared=SimpleNamespace(parameters=(object(),), loss=None),
        allowlist=object(),
        settings={"ensemble": [{"training": {"steps": 3}}], "train_fraction": 0.5},
        members=members,
        trust_parameters=(0,) if trust else None,
    )


def fitted(trust_block=None):
    out = {
        "members": [[np.ones(2, dtype=np.float32)]],
        "combine": np.ones((1, BASE.outputs), dtype=np.float32),
        "mu": np.zeros(BASE.outputs, dtype=np.float32),
        "sd": np.ones(BASE.outputs, dtype=np.float32),
        "selected_rows": 5,
        "train_loss": 0.5,
        "member_losses": [0.25],
    }
    if trust_block is not None:
        out["trust"] = trust_block
    return out


def data(spec):
    dtype = np.dtype(spec.dtype)
    return (
        np.zeros((spec.rows, spec.inputs), dtype=dtype),
        np.zeros((spec.rows, spec.outputs), dtype=dtype),
    )


# -- the pin ------------------------------------------------------------------------------------------------------------------------


def test_the_trust_trainer_is_pinned_by_its_bytes():
    path = Path(v2.__file__).resolve().parents[2] / v2.TRAINER_V4_PATH
    assert hashlib.sha256(path.read_bytes()).hexdigest() == v2.TRAINER_V4_SHA256
    assert v2.trust_trainer_source() == path.read_bytes()
    assert v2.TRAINER_V4_PIN == (v2.TRAINER_V4_PATH, v2.TRAINER_V4_SHA256)


def test_no_served_version_names_the_trust_trainer_or_state():
    for key in v2.SPECS:
        block = v2.adapter_block(*key)
        assert "trust" not in block
        assert v2.TRAINER_V4_SHA256 not in repr(block)
        assert block["trainer"]["module"] != v2.TRAINER_V4_MODULE


# -- the registration ---------------------------------------------------------------------------------------------------------------


def test_only_registered_versions_are_in_the_registry_and_an_unregistered_version_refuses_typed():
    # Motor 1.9 is the one registered version (owner MOTOR19-TRUST-REGISTRATION + MOTOR19-TRUST-FLOOR-0)
    assert set(registry.REGISTRATIONS) == {("electric-motor-magnetics", "1.9")}
    with pytest.raises(v4.TrustRefused) as refused:
        registry.trust_spec("x", "1", width=3, outputs=1, trust_parameters=(0,))
    assert refused.value.code == "trust_version_not_registered"


def test_a_registered_versions_values_flow_into_the_spec_and_a_missing_one_stays_none(
    monkeypatch,
):
    def derive(native, inputs):
        return native[:, :1]

    monkeypatch.setitem(
        registry.REGISTRATIONS, ("x", "1"), {"derive": derive, "epochs": 4}
    )
    spec = registry.trust_spec("x", "1", width=3, outputs=1, trust_parameters=[2, 5])
    assert spec.derive is derive and spec.trust_parameters == (2, 5)
    assert spec.epochs == 4 and spec.sigma_floor is None and spec.learning_rate is None
    with pytest.raises(v4.TrustRefused) as refused:
        v4.check(spec)  # the owner's values are never invented
    assert refused.value.code == "trust_value_is_human_input"


# -- the fit -------------------------------------------------------------------------------------------------------------------------


def test_a_trust_candidates_fit_runs_the_two_phase_trainer_around_the_versions_own_trainer(
    monkeypatch,
):
    calls = {}

    def fake_train(prepared, inputs, targets, settings, *, seed, base_trainer, spec):
        calls.update(base=base_trainer, spec=spec, seed=seed)
        return fitted({"status": "trained", "held_out_rows": 3})

    def fail(
        *args, **kwargs
    ):  # the plain trainer must not be called directly for a trust candidate
        raise AssertionError("plain trainer called")

    monkeypatch.setattr(v4, "train", fake_train)
    monkeypatch.setattr(physical_graph_trainer_v2, "train", fail)
    monkeypatch.setitem(
        registry.REGISTRATIONS,
        (BASE.challenge_id, BASE.version),
        {
            "derive": lambda native, inputs: native,
            "sigma_floor": (0.1,) * K,
            "epochs": 2,
            "learning_rate": 0.01,
        },
    )
    candidate = model(trust=True)
    receipt = candidate.fit(*data(candidate.spec), seed=7)
    assert calls["base"] is physical_graph_trainer_v2 and calls["seed"] == 7
    assert calls["spec"].width == BASE.outputs and calls["spec"].outputs == K
    assert calls["spec"].trust_parameters == (0,)
    assert receipt["trust"] == {"status": "trained", "held_out_rows": 3}
    assert receipt["trust_trainer_sha256"] == "sha256:" + v2.TRAINER_V4_SHA256


def test_a_trust_fit_with_no_registration_refuses_typed_and_trains_nothing(monkeypatch):
    called = []
    monkeypatch.setattr(
        physical_graph_trainer_v2, "train", lambda *a, **k: called.append(1)
    )
    candidate = model(trust=True)
    with pytest.raises(RecipeRefused, match="graph_route_trust_version_not_registered"):
        candidate.fit(*data(candidate.spec), seed=0)
    assert called == []


def test_a_non_trust_candidates_fit_is_the_plain_trainer_with_no_trust_key(monkeypatch):
    seen = {}

    def plain(prepared, inputs, targets, settings, *, seed):
        seen["called"] = True
        return fitted()

    def fail(*args, **kwargs):
        raise AssertionError("trust trainer called")

    monkeypatch.setattr(physical_graph_trainer_v2, "train", plain)
    monkeypatch.setattr(v4, "train", fail)
    candidate = model(trust=False, spec=BASE)
    receipt = candidate.fit(*data(BASE), seed=0)
    assert (
        seen["called"]
        and "trust" not in receipt
        and "trust_trainer_sha256" not in receipt
    )


# -- the state and the prediction ----------------------------------------------------------------------------------------------------


def test_a_trust_models_frozen_state_is_the_trust_state_and_a_plain_ones_is_v2s(
    monkeypatch,
):
    captured = {}
    monkeypatch.setattr(
        physical_graph_state_v3,
        "freeze",
        lambda *args, **kwargs: captured.setdefault("v3", kwargs) or b"v3",
    )
    monkeypatch.setattr(
        physical_graph_state_v2, "freeze", lambda *args, **kwargs: b"v2"
    )
    trusted = model(trust=True)
    trusted.members, trusted.combine = [[np.ones(1)]], np.ones((1, BASE.outputs))
    trusted.mu, trusted.sd = np.zeros(BASE.outputs), np.ones(BASE.outputs)
    trusted.frozen_state()
    assert captured["v3"] == {"trust_width": K}
    plain = model(trust=False, spec=BASE)
    plain.members, plain.combine, plain.mu, plain.sd = (
        trusted.members,
        trusted.combine,
        trusted.mu,
        trusted.sd,
    )
    assert plain.frozen_state() == b"v2"


def test_a_trust_models_prediction_is_its_physics_columns_decoded():
    pytest.importorskip("jax")
    candidate = model(trust=True)
    width = BASE.outputs
    raw = np.arange(3 * (width + K), dtype=np.float64).reshape(3, width + K)
    candidate.prepared = SimpleNamespace(
        parameters=(object(),),
        loss=None,
        predict=lambda params, x, isolated=False: [raw],
    )
    candidate.members = [[np.ones(1)]]
    candidate.combine = np.full((1, width), 0.5)
    candidate.mu, candidate.sd = np.ones(width), np.full(width, 2.0)
    inputs = np.ones((3, BASE.inputs), dtype=np.dtype(BASE.dtype))
    result = candidate.predict(inputs)
    assert result.shape == (3, width)
    np.testing.assert_allclose(
        result, (raw[:, :width] * 0.5) * 2.0 + 1.0
    )  # the trust columns are not in the answer


def test_a_registration_without_a_derive_refuses_typed_not_with_a_key_error(
    monkeypatch,
):
    # door-code 11:41:07Z: entry.get('derive') lets the trainer's own check refuse it typed
    monkeypatch.setitem(
        registry.REGISTRATIONS,
        ("x", "1"),
        {"sigma_floor": (0.1,), "epochs": 1, "learning_rate": 0.01},
    )
    spec = registry.trust_spec("x", "1", width=3, outputs=1, trust_parameters=(0,))
    with pytest.raises(v4.TrustRefused) as refused:
        v4.check(spec)
    assert refused.value.code == "trust_spec_malformed"
