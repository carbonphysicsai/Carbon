"""Shared fixture-only toy semantics for B-07C, B-07F, and B-E4.

The values in this module are deterministic engineering fixtures.  They are
not a physical population, an official reference, or qualification evidence.
"""

from __future__ import annotations

import hashlib
import json
import math

FIXTURE_TRAINING_OBSERVATIONS = ((1, 1), (2, 4))
FIXTURE_HELDOUT_OBSERVATIONS = ((3, 9), (4, 16))


def _digest(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def construct_fixture_model(
    observations: tuple[tuple[int, int], ...], level: int, seed: bytes
) -> tuple[float, str]:
    """Fit the registered toy coefficient using exactly ``level`` observations."""

    if (
        type(observations) is not tuple
        or type(level) is not int
        or type(seed) is not bytes
    ):
        raise ArithmeticError
    ordered = observations if seed[0] % 2 == 0 else tuple(reversed(observations))
    selected = ordered[:level]
    denominator = sum(x * x for x, _ in selected)
    if len(selected) != level or denominator <= 0:
        raise ArithmeticError
    coefficient = float(sum(x * y for x, y in selected) / denominator)
    if not math.isfinite(coefficient):
        raise ArithmeticError
    return coefficient, _digest({"coefficient": coefficient.hex(), "level": level})


def evaluate_fixture_reference(
    coefficient: float, observations: tuple[tuple[int, int], ...]
) -> float:
    """Return deterministic held-out mean squared error for the toy fixture."""

    if (
        type(coefficient) is not float
        or type(observations) is not tuple
        or not observations
    ):
        raise ArithmeticError
    value = float(
        sum((coefficient * x - y) ** 2 for x, y in observations) / len(observations)
    )
    if not math.isfinite(value) or value < 0.0:
        raise ArithmeticError
    return value
