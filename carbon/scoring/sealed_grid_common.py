"""The sealed graders' shared grid grouping (Validator contract
VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022 §3: "one helper for the grid
grouping and the D call pattern").

Every Challenge's sealed grader (`motor_sealed_dual_pack`,
`battery_sealed_dual_pack`, and Cooling's, F02's and F08's to come) takes a bank
whose rows are the cells of one design x condition grid and needs the same
things before it can call its Challenge's decision measure: the grid's own
design and condition ids, the row index of every cell, and a refusal when the
rows are not a complete grid of the registered shape. That grouping lives here;
what a Challenge does with it (its quantities, its D) stays in its own module.

This file is part of each sealed grader's producer identity (it is listed in
their ``FILES``), so a change here re-versions every grader that uses it, once.
DEVELOPMENT only: no qualification, weight, reward or LIVE authority.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The one cohort a sealed grid's cells carry (the common exam architecture, C3).
GRID_COHORT = "decision_sealed_grid"


@dataclass(frozen=True)
class GridLayout:
    """A complete design x condition grid over some bank rows.

    ``designs`` and ``conditions`` are the grid's own ids in first-appearance
    order; ``cells`` maps ``(design, condition)`` to the row's index in the bank
    rows; ``indices`` lists the cells' row indices in row order."""

    designs: tuple
    conditions: tuple
    cells: dict
    indices: tuple

    def rows_of_design(self, design):
        return [self.cells[(design, c)] for c in self.conditions]

    def rows_of_condition(self, condition):
        return [self.cells[(d, condition)] for d in self.designs]


def grid_layout(rows, *, design_of, condition_of, shape, refuse, cohort=GRID_COHORT):
    """The grid ``rows`` form, or ``refuse(code)`` (which must raise).

    ``rows`` are the bank rows (dicts with a ``cohort``); the cells are the rows
    in ``cohort``. ``design_of(row)`` and ``condition_of(row)`` give a cell's
    ids (Motor reads ``design_id`` / ``condition_id``; Battery reads the
    candidate and scenario ids its records name). ``shape`` is the registered
    ``(designs, conditions)``. The refusal codes are ``grid_cohort`` (a
    row outside the grid's cohort that is not allowed), ``grid_shape`` (not the
    registered shape) and ``grid_incomplete`` (a repeated, missing or unnamed
    cell). A caller maps them to its own typed refusal."""
    cells, designs, conditions, indices = {}, [], [], []
    for index, row in enumerate(rows):
        if row.get("cohort") != cohort:
            continue
        design, condition = design_of(row), condition_of(row)
        if not (
            type(design) is str and design and type(condition) is str and condition
        ):
            refuse("grid_incomplete")
        if (design, condition) in cells:
            refuse("grid_incomplete")
        cells[(design, condition)] = index
        indices.append(index)
        if design not in designs:
            designs.append(design)
        if condition not in conditions:
            conditions.append(condition)
    if (len(designs), len(conditions)) != tuple(shape):
        refuse("grid_shape")
    if len(cells) != len(designs) * len(conditions):
        refuse("grid_incomplete")
    return GridLayout(tuple(designs), tuple(conditions), cells, tuple(indices))


class _NotAGrid(Exception):
    pass


def _not_a_grid(_code):
    raise _NotAGrid


def is_grid_bank(cohorts, records, *, shape, design_of, condition_of):
    """Whether a bank declares the sealed grid population: every cohort is
    `GRID_COHORT` and the records are a complete grid of ``shape`` (the
    graders' dispatch by the bank's declared population). ``design_of`` and
    ``condition_of`` read a record's cell ids."""
    if (
        type(cohorts) not in (tuple, list)
        or type(records) not in (tuple, list)
        or len(cohorts) != len(records)
        or not cohorts
        or any(c != GRID_COHORT for c in cohorts)
        or any(type(r) is not dict for r in records)
    ):
        return False
    rows = [{"cohort": GRID_COHORT, "record": r} for r in records]
    try:
        grid_layout(
            rows,
            design_of=lambda row: design_of(row["record"]),
            condition_of=lambda row: condition_of(row["record"]),
            shape=shape,
            refuse=_not_a_grid,
        )
    except _NotAGrid:
        return False
    return True


def decision_objective(layout, contract):
    """The objective document Motor's registered decision workflow reads
    (`motor_dual_measurement._decision`): the grid's own design and condition
    ids and the registered decision contract."""
    return {
        "design_ids": list(layout.designs),
        "condition_ids": list(layout.conditions),
        "decision_contract": contract,
    }


__all__ = [
    "GRID_COHORT",
    "GridLayout",
    "decision_objective",
    "grid_layout",
    "is_grid_bank",
]
