"""Trainer v3 on a layout with SCALAR tail columns (Lead audit row 5: curve columns, then scalar columns).

The curve terms read the first slices x steps columns; `time_weighting` weights that block and leaves every tail column
at 1.0. Before this, a 241-column target with the 240-column Motor layout failed on a reshape / broadcast.
"""

from __future__ import annotations

import numpy as np
import pytest

from carbon.development_session import physical_graph_adapter_v2 as adapter

LAYOUT = adapter.MOTOR_18_LAYOUT
CURVE = LAYOUT["slices"] * LAYOUT["steps"]
SETTINGS = {
    "steps": 12,
    "batch_size": 16,
    "learning_rate": 1e-2,
    "warmup_steps": 0,
    "min_learning_rate_ratio": 0.1,
    "learning_rate_curve": "constant",
    "optimizer_family": "adam",
    "beta1": 0.9,
    "beta2": 0.999,
    "adam_epsilon": 1e-8,
    "weight_decay": 0.0,
    "clip_norm": 0.0,
    "loss": "mse",
    "huber_delta": 1.0,
}


class Linear:
    """A stand-in prepared graph: one dense layer, `inputs` -> `width`."""

    def __init__(self, inputs, width):
        self.inputs, self.width = inputs, width

    def init(self, key):
        import jax

        return [
            0.1 * jax.random.normal(key, (self.inputs, self.width)),
            np.zeros(self.width, dtype=np.float32),
        ]

    def apply(self, values, x):
        return [x @ values[0] + values[1]]

    predict = apply


def data(width, rows=32, inputs=8):
    rng = np.random.default_rng(0)
    x = rng.standard_normal((rows, inputs)).astype(np.float32)
    z = rng.standard_normal((rows, width)).astype(np.float32)
    return x, z


def member(width, weights, **knobs):
    pytest.importorskip("jax")
    pytest.importorskip("optax")
    from carbon.development_session.physical_graph_trainer_v3 import train_member

    x, z = data(width)
    return train_member(
        Linear(x.shape[1], width),
        x,
        z,
        {**SETTINGS, **knobs},
        weights,
        seed=0,
        member=0,
        layout=LAYOUT,
    )


def test_a_241_column_target_trains_with_every_curve_term_and_time_weighting():
    weights = np.full(CURVE + 1, 1.0 / (CURVE + 1))
    knobs = {
        "time_weighting": [1.0] * 30 + [3.0] * 30,
        "h1_weight": 0.5,
        "h2_weight": 0.5,
        "spectral_weight": 0.5,
    }
    first = member(CURVE + 1, weights, **knobs)
    repeat = member(CURVE + 1, weights, **knobs)
    assert all(np.isfinite(v).all() for v in first["params"])
    for a, b in zip(first["params"], repeat["params"], strict=True):
        assert np.array_equal(a, b)


def test_time_weighting_leaves_the_tail_column_at_weight_one():
    # Only the tail column carries loss weight, so the fit sees column 240 times ITS time weight. Any time weighting
    # then fits bit-for-bit what the all-ones weighting fits: the tail's weight is 1.0 whatever the curve block gets.
    weights = np.zeros(CURVE + 1)
    weights[CURVE] = 1.0
    flat = member(CURVE + 1, weights, time_weighting=[1.0] * 60)
    skewed = member(CURVE + 1, weights, time_weighting=[1.0] * 30 + [5.0] * 30)
    for a, b in zip(flat["params"], skewed["params"], strict=True):
        assert np.array_equal(a, b)


def test_a_target_narrower_than_the_curve_block_is_refused():
    weights = np.full(CURVE - 1, 1.0 / (CURVE - 1))
    with pytest.raises(ValueError, match="wider than the targets"):
        member(CURVE - 1, weights, time_weighting=[1.0] * 60)
