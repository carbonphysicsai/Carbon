"""Motor's sealed-exam population: placed 30-case batches
(OWNER-MOTOR-EXAM-DRAW-01, owner-approved; relayed by the Validator 2026-10-21).

**Law.** Fresh seeded candidates from the registered DEVELOPMENT law
(`carbon.motor.population`: independent uniform over the input box, kept if
buildable), none repeating a published Motor case. A seeded subset search then
accepts the first 30 candidates whose predictions put 16-19 of 30 on the
feasible side of each limit (mean torque >= 4.0 N.m; peak-to-peak ripple
<= 0.30 of the mean), so about a third lands on each side of both after the
predictor's error. The exam QA's floor is 10 a side of 30.

**Placement (fitted, never a label).** Uniform batch 1 failed the straddle
check on ripple (about 39 % of the box is feasible on each limit), and the
closed-form model (`carbon.motor.analytic`) predicts no ripple. So placement
is fitted: two Gaussian kernel ridge models on the public TRAIN
(`motor-pools-v1/train.jsonl`, 150 L0 references, read by sha), on inputs
scaled to the box, one for mean torque and one for log ripple fraction.
Working values (Data Collection, 2026-10-21, from 10-fold cross-validation on
TRAIN): length scale 0.8, ridge 0.01 (torque) and 0.1 (log ripple); side
accuracy about 98 % (torque) and 78 % (ripple). Simulated on TRAIN with the
QA's within-U rule, the 16-19 window passes the straddle check about 96 % of
the time against about 57 % for uniform draws. The predictions place cases
only: they are never stored, scored or used as a label.

A DEVELOPMENT population; not qualified, and no LIVE or reward-bearing
evaluation may use it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from carbon.motor import population as development

from .domain import INPUT_BOUNDS, INPUTS, MAX_RIPPLE_FRACTION, MIN_TORQUE_NM

POPULATION_VERSION = "carbon.motor.sealed-placed-30.v1"
REPOSITORY = Path(__file__).resolve().parents[2]
CASES = 30
CANDIDATES = 300
WINDOW = (16, 19)  # predicted feasible cases of 30, per limit
SEARCH = 200_000
LENGTH_SCALE = 0.8
RIDGE = {"torque": 0.01, "log_ripple": 0.1}
TRAIN = (
    "docs/development/evidence/motor-pools-v1/train.jsonl",
    "d027f71133f2fdc0c74d2b62bdfc2fbeff445062f638dd2888f4f54c17389d4e",
)

admitted = development.admitted

_CACHE = {}


def _scaled(rows):
    low = np.array([INPUT_BOUNDS[k][0] for k in INPUTS])
    high = np.array([INPUT_BOUNDS[k][1] for k in INPUTS])
    return (np.asarray(rows, dtype=float) - low) / (high - low)


def _kernel(a, b):
    d = ((a[:, None, :] - b[None, :, :]) ** 2).sum(-1)
    return np.exp(-d / (2 * LENGTH_SCALE * LENGTH_SCALE))


def _model():
    """The placement fit on public TRAIN, validated before it is cached."""
    if "model" not in _CACHE:
        raw = (REPOSITORY / TRAIN[0]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != TRAIN[1]:
            raise RuntimeError("motor_placement_train_differs")
        rows = [json.loads(line) for line in raw.decode().splitlines() if line]
        x, torque, ripple = [], [], []
        for row in rows:
            curve = row["outputs"]["torque_nm"]
            mean = sum(curve) / len(curve)
            if row.get("status") != "OK" or not mean > 0:
                raise RuntimeError("motor_placement_train_invalid")
            x.append([row["inputs"][k] for k in INPUTS])
            torque.append(mean)
            ripple.append(np.log((max(curve) - min(curve)) / mean))
        z = _scaled(x)
        fits = {}
        for name, y in (("torque", torque), ("log_ripple", ripple)):
            y = np.asarray(y)
            k = _kernel(z, z) + RIDGE[name] * np.eye(len(z))
            fits[name] = (np.linalg.solve(k, y - y.mean()), y.mean())
        _CACHE["model"] = (z, fits)
    return _CACHE["model"]


def predict(cases):
    """Placement predictions: (mean torque, ripple fraction) per case."""
    z, fits = _model()
    k = _kernel(_scaled([[c[name] for name in INPUTS] for c in cases]), z)
    torque = k @ fits["torque"][0] + fits["torque"][1]
    ripple = np.exp(k @ fits["log_ripple"][0] + fits["log_ripple"][1])
    return torque, ripple


def _published():
    """Published Motor overlap keys, validated before they are cached."""
    if "published" not in _CACHE:
        from carbon.challenge_validator.confirmation_sources import PopulationSource

        if not (REPOSITORY / "docs" / "development" / "evidence").is_dir():
            raise RuntimeError("motor_published_evidence_missing")
        source = PopulationSource("electric-motor-magnetics", "motor", ("motor-*",))
        published = source.published(REPOSITORY)
        if not published:
            raise RuntimeError("motor_published_set_empty")
        _CACHE["published"] = (frozenset(published), source.key)
    return _CACHE["published"]


def draw(rng, count, *, max_attempts=None):
    """One placed batch (30 cases, in candidate order) and the subset tries
    it took. `count` must be 30."""
    if count != CASES:
        raise ValueError(f"a Motor sealed batch is {CASES} placed cases")
    published, key = _published()
    candidates, _ = development.draw(rng, CANDIDATES)
    candidates = [c for c in candidates if key(c) not in published]
    if len(candidates) < CASES:
        raise RuntimeError("motor_placement_candidates_short")
    torque, ripple = predict(candidates)
    torque_ok = torque >= MIN_TORQUE_NM
    ripple_ok = ripple <= MAX_RIPPLE_FRACTION
    tries = 0
    for tries in range(1, (max_attempts or SEARCH) + 1):
        chosen = sorted(rng.sample(range(len(candidates)), CASES))
        a, b = int(torque_ok[chosen].sum()), int(ripple_ok[chosen].sum())
        if WINDOW[0] <= a <= WINDOW[1] and WINDOW[0] <= b <= WINDOW[1]:
            return [candidates[i] for i in chosen], tries
    raise RuntimeError(f"{tries} subset tries placed no batch in the window")


__all__ = ["POPULATION_VERSION", "admitted", "draw", "predict"]
