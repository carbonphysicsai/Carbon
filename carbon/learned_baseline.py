"""A generic learned baseline: Gaussian-kernel ridge regression.

The readiness records' "one learned baseline" for Challenges with many
inputs (the cold plate's nine, the motor's eight). It knows each input's box
and nothing of the physics:
- inputs scaled to [-1, 1] by their declared bounds;
- each output column standardized on TRAIN;
- k(x, x') = exp(-|x - x'|^2 / (2 l^2)), coefficients (K + lambda I)^-1 Y.
Its two hyperparameters are chosen on PRACTICE from a declared grid by the
Challenge's own exam score (`select`); the private pool is touched once, to
score. Deterministic: a Cholesky solve, no random initialization.

numpy only (the `science-jax` group). A DEVELOPMENT baseline, not a
qualified model.
"""

from __future__ import annotations

import numpy as np

#: The declared grid. Length and ridge trade off along a valley, so the grid
#: spans both far enough that a Challenge's choice lands inside it; `select`
#: reports a choice on an edge, since the search there is truncated.
LENGTHS = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0)
RIDGES = (1e-8, 1e-6, 1e-4, 1e-2, 1e-1, 1.0)


def scale(rows, names, bounds):
    """Rows of input dicts as an array scaled to [-1, 1] by `bounds`."""
    low = np.array([bounds[n][0] for n in names], dtype=float)
    high = np.array([bounds[n][1] for n in names], dtype=float)
    x = np.array([[row[n] for n in names] for row in rows], dtype=float)
    return 2 * (x - low) / (high - low) - 1


def _kernel(a, b, length):
    squared = (a**2).sum(1)[:, None] + (b**2).sum(1)[None, :] - 2 * a @ b.T
    return np.exp(-np.maximum(squared, 0.0) / (2 * length**2))


class KernelRidge:
    def __init__(self, x, y, length, ridge):
        self.x, self.length = np.asarray(x, float), length
        y = np.asarray(y, float)
        self.mean, self.std = y.mean(0), y.std(0)
        self.std[self.std == 0] = 1.0
        k = _kernel(self.x, self.x, length) + ridge * np.eye(len(self.x))
        factor = np.linalg.cholesky(k)
        z = np.linalg.solve(factor, (y - self.mean) / self.std)
        self.alpha = np.linalg.solve(factor.T, z)

    def predict(self, x):
        k = _kernel(np.asarray(x, float), self.x, self.length)
        return k @ self.alpha * self.std + self.mean


def select(x, y, practice_score, lengths=LENGTHS, ridges=RIDGES):
    """Fit every (length, ridge) on TRAIN and keep the best by
    `practice_score(model)` (lower is better; None means ineligible).
    Returns the model, the whole grid's scores and `at_edge`: the
    hyperparameters whose chosen value is the grid's smallest or largest."""
    grid, best = [], None
    for length in lengths:
        for ridge in ridges:
            try:
                model = KernelRidge(x, y, length, ridge)
            except np.linalg.LinAlgError:
                grid.append({"length": length, "ridge": ridge, "score": None})
                continue
            score = practice_score(model)
            grid.append({"length": length, "ridge": ridge, "score": score})
            if score is not None and (best is None or score < best[0]):
                best = (score, model, length, ridge)
    if best is None:
        raise ValueError("no hyperparameter gave an eligible model")
    at_edge = [
        name
        for name, value, values in (
            ("length", best[2], lengths),
            ("ridge", best[3], ridges),
        )
        if len(values) > 1 and value in (min(values), max(values))
    ]
    return best[1], {
        "length": best[2],
        "ridge": best[3],
        "at_edge": at_edge,
        "grid": grid,
    }
