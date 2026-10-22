"""Cooling's sealed-exam population: a 4 designs x 4 conditions grid
(owner-approved Cooling draw, relayed by the Validator 2026-10-20).

**Law.** Each batch is a full grid: 4 designs (channel width, fin width,
channel depth, flow per kW) crossed with 4 operating conditions (inlet, heat
load, hot-spot ratio, centre, width), all drawn fresh from the registered
input box (`carbon.cold_plate.domain.INPUT_BOUNDS`). Every one of the 16 cells
must pass the development population's screen (closed-form hottest wall at
most 95 C and laminar flow), so each reference stays inside the coolant model.

**Placement (closed-form, never a label).** 40 seeded candidate designs and
40 seeded candidate conditions are predicted by the closed-form model
(`carbon.cold_plate.analytic`); a seeded subset search then accepts the first
4 x 4 whose predictions put 7-9 of the 16 cells feasible on each limit (die
peak <= 100 C, hydraulic power <= 0.25 W), so that about a third lands on each
side of both. The exam QA floor is 6 each side; 7-9 leaves room for the
closed-form model's error (working decision, Data Collection, 2026-10-20).
The predictions are placement only and are never stored or used as a label.

**Disjointness.** No cell repeats a published Cooling case (the family's
overlap keys); the published set is validated before it is cached and fails
closed when missing or empty.

A DEVELOPMENT population; not qualified, and no LIVE or reward-bearing
evaluation may use it.
"""

from __future__ import annotations

from pathlib import Path

from carbon.cold_plate import analytic, population
from carbon.cold_plate.domain import INPUT_BOUNDS
from carbon.cold_plate.exam import feasibility

from .domain import (
    CONDITION_INPUTS,
    DESIGN_INPUTS,
    DIE_LIMIT_C,
    HYDRAULIC_LIMIT_W,
    INPUTS,
)

POPULATION_VERSION = "carbon.cold-plate.sealed-grid-4x4.v1"
REPOSITORY = Path(__file__).resolve().parents[2]
GRID = 4
CELLS = GRID * GRID
CANDIDATES = 40
WINDOW = (7, 9)  # predicted feasible cells of 16, per limit
SEARCH = 200_000


def admitted(case):
    """In the box and through the development screen (each cell's validity)."""
    if type(case) is not dict or set(case) != set(INPUTS):
        return False
    if not all(INPUT_BOUNDS[k][0] <= case[k] <= INPUT_BOUNDS[k][1] for k in INPUTS):
        return False
    return population.admitted(case)


def grid_of(cases):
    """The 4 x 4 grid a case list forms: (designs, conditions), each a sorted
    list of input tuples, or ValueError when the cases are not a full grid."""
    designs = sorted({tuple(c[k] for k in DESIGN_INPUTS) for c in cases})
    conditions = sorted({tuple(c[k] for k in CONDITION_INPUTS) for c in cases})
    cells = {
        (tuple(c[k] for k in DESIGN_INPUTS), tuple(c[k] for k in CONDITION_INPUTS))
        for c in cases
    }
    if (
        len(cases) != CELLS
        or len(designs) != GRID
        or len(conditions) != GRID
        or len(cells) != CELLS
    ):
        raise ValueError("not a full 4 x 4 design x condition grid")
    return designs, conditions


_PUBLISHED = {}


def _published():
    """Published Cooling overlap keys, validated before they are cached."""
    if "set" not in _PUBLISHED:
        from carbon.challenge_validator.confirmation_sources import PopulationSource

        if not (REPOSITORY / "docs" / "development" / "evidence").is_dir():
            raise RuntimeError("cooling_published_evidence_missing")
        source = PopulationSource(
            "chip-cold-plate", "cold_plate_exam", ("cold-plate-*", "cooling-*")
        )
        published = source.published(REPOSITORY)
        if not published:
            raise RuntimeError("cooling_published_set_empty")
        _PUBLISHED["set"] = (frozenset(published), source.key)
    return _PUBLISHED["set"]


def _side_counts(predicted):
    die = sum(p["die_peak_c"] <= DIE_LIMIT_C for p in predicted)
    hydraulic = sum(p["hydraulic_w"] <= HYDRAULIC_LIMIT_W for p in predicted)
    return die, hydraulic


def draw(rng, count, *, max_attempts=None):
    """One placed 4 x 4 grid (16 cases, design-major) and the subset tries it
    took. `count` must be 16: the batch is the grid."""
    if count != CELLS:
        raise ValueError(f"a Cooling sealed batch is one {GRID} x {GRID} grid")
    published, key = _published()
    designs = [
        {k: rng.uniform(*INPUT_BOUNDS[k]) for k in DESIGN_INPUTS}
        for _ in range(CANDIDATES)
    ]
    conditions = [
        {k: rng.uniform(*INPUT_BOUNDS[k]) for k in CONDITION_INPUTS}
        for _ in range(CANDIDATES)
    ]
    table = {}
    for i, d in enumerate(designs):
        for j, c in enumerate(conditions):
            case = {**d, **c}
            if admitted(case) and key(case) not in published:
                prediction = feasibility(
                    case,
                    analytic.predict(case),
                    die_limit_c=DIE_LIMIT_C,
                    hydraulic_limit_w=HYDRAULIC_LIMIT_W,
                )
                table[i, j] = prediction
    tries = 0
    for tries in range(1, (max_attempts or SEARCH) + 1):
        di = rng.sample(range(CANDIDATES), GRID)
        cj = rng.sample(range(CANDIDATES), GRID)
        cells = [(i, j) for i in di for j in cj]
        if any(cell not in table for cell in cells):
            continue
        die, hydraulic = _side_counts([table[cell] for cell in cells])
        if WINDOW[0] <= die <= WINDOW[1] and WINDOW[0] <= hydraulic <= WINDOW[1]:
            cases = [
                {**designs[i], **conditions[j]} for i in sorted(di) for j in sorted(cj)
            ]
            return cases, tries
    raise RuntimeError(f"{tries} subset tries placed no grid in the window")


__all__ = ["POPULATION_VERSION", "admitted", "draw", "grid_of"]
