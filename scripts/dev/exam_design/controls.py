"""Authored controls for the gate and comparison tests.

Everything here is a **synthetic control**, written by hand to exercise the exam.
None of it is a trained-model result, and the report labels it so.

Faulty outputs (each targets one gate; the expected gate is recorded so the
test can check the right gate fires, not merely that something failed):

    nan               schema_finite
    wrong_shape       schema_finite
    voltage_overshoot voltage_ceiling      (+20 mV on samples at the 4.2 V hold)
    v0_offset         initial_voltage      (+5 mV at t = 0)
    t0_offset         initial_temperature  (+0.5 C at t = 0)
    capacity_over     capacity_bound       (capacity above the parameter-set bound)
    nondeterministic  paired_repeat        (fresh noise on every call)
    time_shift        none - passes every gate, scores worse (a soft failure)

Negative controls (must pass every gate on every valid case):

    oracle            the reference itself, including cases that reach plating
                      conditions or dip below ambient temperature

Overfitting control:

    pool_leak         returns the *reference* for cases in an exposed set
                      (memorized screening cases) and a base model elsewhere
"""

from __future__ import annotations

import copy

import numpy as np

FAULTS = {
    "nan": "schema_finite",
    "wrong_shape": "schema_finite",
    "voltage_overshoot": "voltage_ceiling",
    "v0_offset": "initial_voltage",
    "t0_offset": "initial_temperature",
    "capacity_over": "capacity_bound",
    "nondeterministic": "paired_repeat",
    "time_shift": None,
}


def oracle(refs: dict[str, dict], case_ids) -> dict[str, dict]:
    return {c: copy.deepcopy(refs[c]["outputs"]) for c in case_ids if refs[c].get("status") == "OK"}


def fault(kind: str, base: dict[str, dict], q_bound: float, seed: int = 0) -> dict[str, dict]:
    rng = np.random.default_rng(seed)
    out = {}
    for cid, p in base.items():
        p = copy.deepcopy(p)
        v = np.asarray(p["voltage_v"], float)
        if kind == "nan":
            v[len(v) // 2] = np.nan
        elif kind == "wrong_shape":
            v = v[:-1]
        elif kind == "voltage_overshoot":
            hold = v >= 4.2 - 1e-3
            v[hold] += 0.02
            if not hold.any():
                v[np.argmax(v)] = 4.22
        elif kind == "v0_offset":
            v[0] += 0.005
        elif kind == "t0_offset":
            t = np.asarray(p["temperature_c"], float)
            t[0] += 0.5
            p["temperature_c"] = t.tolist()
        elif kind == "capacity_over":
            p["capacity_ah"] = [q_bound * 1.05 for _ in p["capacity_ah"]]
        elif kind == "nondeterministic":
            v = v + rng.normal(0, 1e-3, v.shape)
            v[0] = p["voltage_v"][0]
        elif kind == "time_shift":
            v = np.concatenate([v[:1], v[:1].repeat(2), v[1:-2]])
            t = np.asarray(p["temperature_c"], float)
            p["temperature_c"] = np.concatenate([t[:1], t[:1].repeat(2), t[1:-2]]).tolist()
        else:
            raise KeyError(kind)
        p["voltage_v"] = v.tolist()
        out[cid] = p
    return out


def pool_leak(base: dict[str, dict], refs: dict[str, dict], exposed: set[str]) -> dict[str, dict]:
    return {c: (copy.deepcopy(refs[c]["outputs"]) if c in exposed and refs[c].get("status") == "OK" else p)
            for c, p in base.items()}
