"""The generic learned baseline: Gaussian-kernel ridge regression."""

from __future__ import annotations

import pytest

np = pytest.importorskip("numpy")

from carbon import learned_baseline

BOUNDS = {"a": (0.0, 2.0), "b": (-5.0, 5.0)}


def _data(n, seed):
    rng = np.random.default_rng(seed)
    rows = [
        {"a": float(a), "b": float(b)}
        for a, b in zip(rng.uniform(0, 2, n), rng.uniform(-5, 5, n))
    ]
    x = learned_baseline.scale(rows, ("a", "b"), BOUNDS)
    y = np.stack([np.sin(x[:, 0]) + x[:, 1] ** 2, 100 + 3 * x[:, 0]], axis=1)
    return x, y


def test_inputs_are_scaled_to_their_box():
    x = learned_baseline.scale(
        [{"a": 0.0, "b": 5.0}, {"a": 1.0, "b": 0.0}], ("a", "b"), BOUNDS
    )
    assert x.tolist() == [[-1.0, 1.0], [0.0, 0.0]]


def test_a_smooth_function_is_learned_and_the_fit_is_deterministic():
    x, y = _data(300, 1)
    test_x, test_y = _data(50, 2)
    model = learned_baseline.KernelRidge(x, y, 1.0, 1e-8)
    error = np.abs(model.predict(test_x) - test_y).max(0)
    assert error[0] < 1e-2 and error[1] < 1e-3
    again = learned_baseline.KernelRidge(x, y, 1.0, 1e-8)
    assert np.array_equal(model.predict(test_x), again.predict(test_x))


def test_selection_keeps_the_best_eligible_hyperparameters():
    x, y = _data(100, 3)
    test_x, test_y = _data(30, 4)

    def score(model):
        if model.length == 0.25:
            return None  # ineligible, whatever its error
        return float(np.abs(model.predict(test_x) - test_y).mean())

    model, chosen = learned_baseline.select(x, y, score)
    eligible = [g for g in chosen["grid"] if g["score"] is not None]
    assert chosen["length"] != 0.25
    assert min(g["score"] for g in eligible) == score(model)
    with pytest.raises(ValueError, match="eligible"):
        learned_baseline.select(x, y, lambda model: None)
