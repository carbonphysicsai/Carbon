"""Graph trainer v3 (Motor 1.8): the construction-only knobs, every default bit-identical to v2.

Lead call 16 Nov 2026 (CV-Motor L12281 (2)(a) and L12299 group (b)). Grading is unchanged; the
trainer and the version's limits block are the only moved material.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from test_graph_route_v2 import MOTOR, _fit, _refused, _x64

from carbon.development_session import physical_graph_adapter_v2 as adapter

KEY = (MOTOR, "1.8")
ROOT = Path(__file__).resolve().parents[2]


def fit(training, **extra):
    with _x64(KEY):
        return _fit(KEY, {"training": {"steps": 24, **training}, **extra})


def blob(model):
    return b"".join(
        np.ascontiguousarray(v).tobytes() for params in model.members for v in params
    )


def test_trainer_v3_pin_is_its_own_bytes_and_only_motor_18_uses_it():
    raw = (ROOT / adapter.TRAINER_V3_PATH).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == adapter.TRAINER_V3_SHA256
    assert adapter.trainer_source(adapter.SPECS[KEY]) == raw
    assert [k for k, s in adapter.SPECS.items() if s.trainer == "v3"] == [KEY]
    block = adapter.adapter_block(*KEY)["trainer"]
    assert block["sha256"] == "sha256:" + adapter.TRAINER_V3_SHA256
    other = adapter.adapter_block("f08-ribbed-bracket", "1.7")["trainer"]
    assert other["sha256"] == "sha256:" + adapter.TRAINER_SHA256


def test_the_layout_limits_are_the_public_important_limit_definition():
    path = (
        ROOT
        / "carbon/challenge_kit/data/motor-important-limit-definition-20261018.json"
    )
    constraints = json.loads(path.read_text())["constraints"]
    assert adapter.MOTOR_18_LAYOUT["limits"] == {
        "min_mean_torque_nm": constraints["min_mean_torque_nm"],
        "max_ripple_fraction": constraints["max_ripple_fraction"],
    }
    assert adapter.MOTOR_18_LAYOUT["slices"] * adapter.MOTOR_18_LAYOUT["steps"] == 240


def test_every_default_reproduces_the_v2_trainer_bit_for_bit():
    from carbon.development_session import physical_graph_trainer_v2 as v2
    from carbon.development_session import physical_graph_trainer_v3 as v3

    model, fitted, inputs = fit({})
    _raw, _inputs, targets = (
        None,
        inputs,
        __import__("test_graph_route_v2")._train(KEY)[2],
    )
    with _x64(KEY):
        settings = dict(model.settings)
        old = v2.train(model.prepared, inputs, targets, settings, seed=0)
        new = v3.train(model.prepared, inputs, targets, settings, seed=0)
    for a, b in zip(old["members"], new["members"], strict=True):
        for left, right in zip(a, b, strict=True):
            assert np.array_equal(left, right)
    assert old["train_loss"] == new["train_loss"]
    assert fitted["trainer_sha256"] == "sha256:" + adapter.TRAINER_V3_SHA256


KNOBS = {
    "microbatches": {"microbatches": 2, "batch_size": 4},
    "matrices": {"weight_decay_mask": "matrices"},
    "relative": {"relative_loss": True},
    "hard": {"hard_example_weight": 1.5, "batch_size": 4},
    "ema": {"inference_weights": "ema", "ema_decay": 0.9},
    "tail": {"tail_averaging": 0.5},
    "polish": {"steps": 40, "polish_steps": 8},
    "h1": {"h1_weight": 0.5},
    "h2": {"h2_weight": 0.5},
    "spectral": {"spectral_weight": 0.5},
    "time": {"time_weighting": [1.0] * 30 + [3.0] * 30},
    "important": {"important_region_weight": 2.0, "important_region_band": 0.5},
}


@pytest.fixture(scope="module")
def default():
    return blob(fit({})[0])


@pytest.mark.parametrize("name", sorted(KNOBS))
def test_each_knob_changes_the_build_and_repeats_bit_for_bit(name, default):
    first, repeat = fit(KNOBS[name])[0], fit(KNOBS[name])[0]
    assert blob(first) == blob(repeat)
    assert blob(first) != default
    assert all(np.isfinite(v).all() for params in first.members for v in params)


def test_the_row_differences_wrap_for_the_periodic_torque_and_not_for_the_linkages():
    jnp = pytest.importorskip("jax.numpy")
    from carbon.development_session.physical_graph_trainer_v3 import _differences

    x = jnp.arange(6.0) ** 2
    assert _differences(x, True, 1).shape == (6,)
    assert float(_differences(x, True, 1)[-1]) == float(x[0] - x[-1])
    assert _differences(x, False, 1).shape == (5,)
    assert _differences(x, False, 2).shape == (4,)
    assert np.allclose(_differences(x, False, 2), 2.0)


def test_the_important_region_mask_reads_the_public_limits():
    from carbon.development_session.physical_graph_trainer_v3 import important_mask

    steps = adapter.MOTOR_18_LAYOUT["steps"]
    rows = np.zeros((4, 240))
    rows[0, :steps] = 4.0  # mean exactly the floor, no ripple
    rows[1, :steps] = 40.0  # far above the floor, no ripple
    rows[2, :steps] = 10.0
    rows[2, 0] = 13.0  # ripple 3, mean ~10.05: fraction ~0.2985, at the cap
    rows[3, :steps] = -1.0  # negative mean: infinite ripple fraction
    mask = important_mask(rows, adapter.MOTOR_18_LAYOUT, 0.1)
    assert mask.tolist() == [1.0, 0.0, 1.0, 0.0]


@pytest.mark.parametrize(
    "training, code",
    [
        ({"ema_decay": 0.9}, "training_dependency_invalid"),
        (
            {"inference_weights": "ema", "tail_averaging": 0.5},
            "training_dependency_invalid",
        ),
        (
            {"inference_weights": "ema", "polish_steps": 8},
            "training_dependency_invalid",
        ),
        ({"polish_steps": 500}, "training_dependency_invalid"),
        (
            {"weight_decay": 0, "weight_decay_mask": "all"},
            "training_dependency_invalid",
        ),
        ({"important_region_band": 0.2}, "training_dependency_invalid"),
        ({"pde_weight": 1.0}, "surface_unserved"),
        ({"physics_warmup_steps": 5}, "surface_unserved"),
        ({"backend": "pytorch"}, "surface_unserved"),
        ({"time_weighting": [1.0] * 59}, "training_value_invalid"),
        ({"time_weighting": [0.0] * 60}, "training_value_invalid"),
        ({"tail_averaging": 0.95}, "training_value_invalid"),
        ({"microbatches": 9}, "training_value_invalid"),
        ({"relative_loss": 1}, "training_value_invalid"),
        ({"weight_decay_mask": "bias"}, "training_value_invalid"),
    ],
)
def test_v3_validation_refuses_by_name(training, code):
    assert code in _refused(KEY, {"training": training})


def test_a_version_on_v2_still_refuses_every_new_knob_as_unserved():
    f08 = ("f08-ribbed-bracket", "1.7")
    for name in ("ema_decay", "polish_steps", "weight_decay_mask", "microbatches"):
        assert "surface_unserved" in _refused(f08, {"training": {name: 1}})
