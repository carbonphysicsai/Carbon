"""Bounded diagnostic comparison of native and frozen bundle predictions.

The trusted construction caller supplies the exact recipe, frozen-state and
public-probe identities after checking each worker artifact's custody. This
module reports observed differences; it defines no scientific tolerance or
qualification decision.
"""

from __future__ import annotations

import math
import re

import numpy as np

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_IDENTITY_FIELDS = frozenset({"recipe_digest", "state_digest", "probe_digest"})
_MAX_ELEMENTS = 1_000_000
_MAX_ARRAY_BYTES = 16 * 1024 * 1024


def compare_native_lowered_predictions(
    *,
    native: np.ndarray,
    lowered: np.ndarray,
    native_identity: dict[str, str],
    lowered_identity: dict[str, str],
) -> dict[str, object]:
    """Return raw deltas for one exact public probe, never a pass/fail verdict."""
    for identity in (native_identity, lowered_identity):
        if (
            type(identity) is not dict
            or set(identity) != _IDENTITY_FIELDS
            or any(
                type(value) is not str or _DIGEST.fullmatch(value) is None
                for value in identity.values()
            )
        ):
            raise ValueError("exact bundle comparison identity required")
    if native_identity != lowered_identity:
        raise ValueError("bundle comparison recipe, state or probe differs")
    for values in (native, lowered):
        if (
            type(values) is not np.ndarray
            or values.ndim < 1
            or not 0 < values.size <= _MAX_ELEMENTS
            or values.nbytes > _MAX_ARRAY_BYTES
            or values.dtype.kind not in "fiu"
            or values.dtype.itemsize > 8
            or not np.isfinite(values).all()
        ):
            raise ValueError("bounded finite numeric predictions required")
    if native.shape != lowered.shape:
        raise ValueError("bundle comparison output shapes differ")

    maximum = 0.0
    total = 0.0
    compensation = 0.0
    mismatch_count = 0
    for actual, frozen in zip(native.flat, lowered.flat, strict=True):
        actual_value, frozen_value = actual.item(), frozen.item()
        if actual_value != frozen_value:
            mismatch_count += 1
        delta = float(abs(actual_value - frozen_value))
        if not math.isfinite(delta):
            raise ValueError("bundle comparison delta is nonfinite")
        maximum = max(maximum, delta)
        adjusted = delta - compensation
        updated = total + adjusted
        compensation = (updated - total) - adjusted
        total = updated
    mean = total / native.size
    if not math.isfinite(mean):
        raise ValueError("bundle comparison mean is nonfinite")
    return {
        "schema": "carbon.development.bundle-prediction-comparison.v1",
        **native_identity,
        "shape": list(native.shape),
        "native_dtype": str(native.dtype),
        "lowered_dtype": str(lowered.dtype),
        "count": int(native.size),
        "exact_equal": mismatch_count == 0,
        "mismatch_count": mismatch_count,
        "max_abs_delta": maximum,
        "mean_abs_delta": mean,
    }
