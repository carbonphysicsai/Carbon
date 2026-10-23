"""Cooling's law-safe output encoding (Validator ruling
VALIDATOR_RULING_COOLING12_PEAK_GATE_20261022, finding G1).

A Cooling 1.2 backbone predicts `peak_c`, the 30 `profile_c` segment means and
`pressure_drop_pa` as 32 independent numbers, so wherever the true peak sits
near the hottest segment mean ordinary regression error breaks the mandatory
law `peak_c >= max(profile_c)` about half the time, and a small pressure drop
can come out non-positive. Neither gate changes.

Under this encoding (Cooling 1.3) the same 32 slots carry
- slot 0: `e`, a raw peak excess, with `peak_c = max(profile_c) + softplus(e)`;
- slots 1-30: `profile_c` as before;
- slot 31: `q`, a raw pressure, with `pressure_drop_pa = softplus(q)`;
so every decoded row satisfies both laws by construction. TRAIN targets are
encoded with the inverse (`encode_targets`); scoring decodes each predicted row
(`decode_row`) and scores the decoded outputs exactly as before.

Where a reference's peak equals its hottest segment mean (the law holds with
no margin), the inverse needs a positive excess: it uses the gate's own
tolerance unit (`exam._ulp`, 32 float32 ulp), the smallest excess the law
already treats as equal, never a new constant.
"""

from __future__ import annotations

import numpy as np

ENCODING = "carbon.cold-plate.law-safe-output-encoding.v1"
PEAK, PROFILE, PRESSURE = slice(0, 1), slice(1, 31), slice(31, 32)


def _softplus(x):
    x = np.asarray(x, dtype=np.float64)
    return np.log1p(np.exp(-np.abs(x))) + np.maximum(x, 0.0)


def _inverse_softplus(y):
    y = np.asarray(y, dtype=np.float64)
    if not np.all(y > 0):
        raise ValueError("softplus inverse needs positive values")
    # log(expm1(y)), stable for large y as y + log1p(-exp(-y)); each branch
    # sees only arguments it handles.
    small = y <= 20.0
    out = y + np.log1p(-np.exp(-np.maximum(y, 20.0)))
    out[small] = np.log(np.expm1(y[small]))
    return out


def _peak_floor(profile_max):
    from .exam import _ulp

    return np.asarray([_ulp(float(v)) for v in np.ravel(profile_max)]).reshape(
        np.shape(profile_max)
    )


def encode_targets(targets):
    """Native (n, 32) TRAIN targets as the encoded slots, float64."""
    y = np.asarray(targets, dtype=np.float64)
    if y.ndim != 2 or y.shape[1] != 32 or not np.all(np.isfinite(y)):
        raise ValueError("Cooling targets are finite (n, 32) rows")
    profile_max = y[:, PROFILE].max(axis=1)
    excess = y[:, 0] - profile_max
    floor = _peak_floor(profile_max)
    if np.any(excess < -floor):
        raise ValueError("a TRAIN reference breaks peak_bounds_profile")
    if np.any(y[:, 31] <= 0):
        raise ValueError("a TRAIN reference breaks pressure_drop_positive")
    out = y.copy()
    out[:, 0] = _inverse_softplus(np.maximum(excess, floor))
    out[:, 31] = _inverse_softplus(y[:, 31])
    return out


def decode_row(values):
    """One encoded predicted row (32 numbers) as the native named outputs."""
    row = np.asarray(values, dtype=np.float64).reshape(-1)
    if row.shape != (32,):
        raise ValueError("an encoded Cooling row holds 32 values")
    profile = row[PROFILE]
    return {
        "peak_c": float(profile.max() + _softplus(row[0])),
        "profile_c": profile.tolist(),
        "pressure_drop_pa": float(_softplus(row[31])),
    }


def decode_flat(values):
    """One encoded row as the native 32-value row (peak, 30 profile, pressure)."""
    native = decode_row(values)
    return [native["peak_c"], *native["profile_c"], native["pressure_drop_pa"]]
