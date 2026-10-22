"""Motor's sealed-grid population: placed 5 designs x 6 conditions batches
(OWNER-MOTOR-EXAM-GRID-01; Validator ruling VALIDATOR_RULING_MOTOR_GRID_SPLIT_20261022).

**Law.** Each batch is a full grid: 5 designs (the six geometry inputs) crossed
with 6 operating conditions (current density, current angle), drawn fresh from
the registered input box (`carbon.motor.domain.INPUT_BOUNDS`), 30 cells in
design-major order. The placement reads `carbon.motor_exam.population`'s
TRAIN-fitted predictor, unchanged.

**Placement (fitted, never a label).** From 40 seeded candidate designs and 40
seeded candidate conditions a seeded subset search accepts the first 5 x 6 with:
1. every cell buildable (the development screen, `carbon.motor.population.admitted`);
2. 16-19 of 30 cells predicted feasible on each limit (mean torque >= 4.0 N.m,
   ripple fraction <= 0.30), so the exam QA's floor of 10 a side holds;
3. the decision contract's needs: 1 to 3 designs predicted feasible at all 6
   conditions, every condition with at least one predicted-feasible design, and
   no condition where all 5 designs are predicted feasible.
The predictions place cells only: they are never stored, scored or used as a
label. A seed whose subset search finds no grid raises; the producer's operator
moves to the next role (placement precedes every solve, so that is not a
redraw) and records the roles tried.

**Disjointness.** No cell repeats a published Motor case (the family's overlap
keys); the published set is validated before it is cached and fails closed when
missing or empty.

A DEVELOPMENT population; not qualified, and no LIVE or reward-bearing
evaluation may use it.
"""

from __future__ import annotations

import numpy as np

from carbon.motor import population as development
from carbon.motor_exam import population as placed

from .domain import (
    CONDITION_INPUTS,
    DESIGN_INPUTS,
    INPUT_BOUNDS,
    INPUTS,
    MAX_RIPPLE_FRACTION,
    MIN_TORQUE_NM,
)

POPULATION_VERSION = "carbon.motor.sealed-grid-5x6.v1"
DESIGNS = 5
CONDITIONS = 6
CELLS = DESIGNS * CONDITIONS
CANDIDATES = 40
WINDOW = placed.WINDOW  # predicted feasible cells of 30, per limit
SEARCH = 200_000

admitted = development.admitted


def grid_of(cases):
    """The 5 x 6 grid a case list forms: (designs, conditions), each a sorted
    list of input tuples, or ValueError when the cases are not a full grid."""
    designs = sorted({tuple(c[k] for k in DESIGN_INPUTS) for c in cases})
    conditions = sorted({tuple(c[k] for k in CONDITION_INPUTS) for c in cases})
    cells = {
        (tuple(c[k] for k in DESIGN_INPUTS), tuple(c[k] for k in CONDITION_INPUTS))
        for c in cases
    }
    if (
        len(cases) != CELLS
        or len(designs) != DESIGNS
        or len(conditions) != CONDITIONS
        or len(cells) != CELLS
    ):
        raise ValueError("not a full 5 x 6 design x condition grid")
    return designs, conditions


def predict(cases):
    """Placement predictions: (mean torque, ripple fraction) per case."""
    return placed.predict(cases)


def draw(rng, count, *, max_attempts=None):
    """One placed 5 x 6 grid (30 cases, design-major) and the subset tries it
    took. `count` must be 30: the batch is the grid."""
    if count != CELLS:
        raise ValueError(f"a Motor sealed batch is one {DESIGNS} x {CONDITIONS} grid")
    published, key = placed._published()
    designs = [
        {k: rng.uniform(*INPUT_BOUNDS[k]) for k in DESIGN_INPUTS}
        for _ in range(CANDIDATES)
    ]
    conditions = [
        {k: rng.uniform(*INPUT_BOUNDS[k]) for k in CONDITION_INPUTS}
        for _ in range(CANDIDATES)
    ]
    cells = [{**d, **c} for d in designs for c in conditions]
    buildable = np.array(
        [development.admitted(x) and key(x) not in published for x in cells]
    ).reshape(CANDIDATES, CANDIDATES)
    torque, ripple = predict(cells)
    torque_ok = (torque >= MIN_TORQUE_NM).reshape(CANDIDATES, CANDIDATES)
    ripple_ok = (ripple <= MAX_RIPPLE_FRACTION).reshape(CANDIDATES, CANDIDATES)
    tries = 0
    for tries in range(1, (max_attempts or SEARCH) + 1):
        di = rng.sample(range(CANDIDATES), DESIGNS)
        cj = rng.sample(range(CANDIDATES), CONDITIONS)
        sub = np.ix_(di, cj)
        if not buildable[sub].all():
            continue
        a, b = int(torque_ok[sub].sum()), int(ripple_ok[sub].sum())
        if not (WINDOW[0] <= a <= WINDOW[1] and WINDOW[0] <= b <= WINDOW[1]):
            continue
        feasible = torque_ok[sub] & ripple_ok[sub]  # design x condition
        everywhere = feasible.all(axis=1)
        if (
            1 <= int(everywhere.sum()) <= 3
            and feasible.any(axis=0).all()
            and not feasible.all(axis=0).any()
        ):
            return [{**designs[i], **conditions[j]} for i in sorted(di) for j in sorted(cj)], tries
    raise RuntimeError(f"{tries} subset tries placed no grid in the window")


__all__ = ["POPULATION_VERSION", "admitted", "draw", "grid_of", "predict"]
