"""The common sealed-exam module (Validator contract
VALIDATOR_EXAM_ARCHITECTURE_COMMON_20261022 §1, C2/C3/C5/C6; owner rule: one
exam architecture for all five Challenges).

Each test states a rule once and shows the five Challenges' thin wrappers
(Motor, Cooling, Battery, F08, F02) reduce to it: they supply only limits and
quantities. The wrappers here mirror the per-Challenge checks that
`dc/motor-grid`, `dc/cooling-heated-faces` and `dc/battery-sealed` carry today.
Synthetic values; no real exam."""

from __future__ import annotations

import pytest

from carbon.challenge_validator import sealed_exam_common as common
from carbon.challenge_validator.sealed_exam_common import (
    FEASIBLE,
    INFEASIBLE,
    PER_CONDITION,
    ROBUST,
    UNRESOLVED,
)


def _grid(designs, conditions):
    return [
        {"design_id": f"design-{d}", "condition_id": f"condition-{c}"}
        for d in range(designs)
        for c in range(conditions)
    ]


# --- labels ---------------------------------------------------------------------


def test_a_label_needs_every_limit_beyond_u_to_be_feasible():
    assert common.label([(0.5, 0.1), (0.3, 0.1)]) == FEASIBLE
    assert common.label([(0.5, 0.1), (-0.2, 0.1)]) == INFEASIBLE
    # Inside U on either limit, and not violated beyond U: neither side.
    assert common.label([(0.5, 0.1), (0.05, 0.1)]) == UNRESOLVED
    assert common.label([(-0.05, 0.1)]) == UNRESOLVED
    # A violation beyond U wins over a limit that is only within U.
    assert common.label([(-0.5, 0.1), (0.05, 0.1)]) == INFEASIBLE
    # The boundary is strict on both sides.
    assert common.label([(0.1, 0.1)]) == UNRESOLVED
    assert common.label([(-0.1, 0.1)]) == UNRESOLVED
    for bad in ([], [(float("nan"), 0.1)], [(0.1, float("inf"))], [(0.1, -1.0)]):
        with pytest.raises(ValueError):
            common.label(bad)


def test_motor_labels_through_the_common_label():
    """Motor: mean torque >= 4.0 N.m, ripple fraction <= 0.30, each with its U."""
    u_torque, u_ripple = 0.0052, 0.026

    def motor(torque, ripple):
        return common.label_value(
            [(torque, 4.0, ">=", u_torque), (ripple, 0.30, "<=", u_ripple)]
        )

    assert motor(5.0, 0.10) == FEASIBLE
    assert motor(3.0, 0.10) == INFEASIBLE
    assert motor(5.0, 0.40) == INFEASIBLE
    assert motor(4.001, 0.10) == UNRESOLVED
    assert motor(5.0, 0.31) == UNRESOLVED


def test_cooling_labels_with_a_relative_u_supplied_by_the_wrapper():
    u_die, u_rel = 0.037, 0.03

    def cooling(die, hydraulic):
        return common.label_value(
            [(die, 100.0, "<=", u_die), (hydraulic, 0.25, "<=", u_rel * abs(hydraulic))]
        )

    assert cooling(90.0, 0.10) == FEASIBLE
    assert cooling(101.0, 0.10) == INFEASIBLE
    assert cooling(90.0, 0.30) == INFEASIBLE
    assert cooling(99.99, 0.10) == UNRESOLVED


# --- straddle (C6) ----------------------------------------------------------------


def test_a_straddle_needs_a_third_of_all_cells_on_each_side_per_limit():
    third = [FEASIBLE] * 10 + [INFEASIBLE] * 10 + [UNRESOLVED] * 10
    assert common.straddle({"q": third}) is None
    short = [FEASIBLE] * 10 + [INFEASIBLE] * 9 + [UNRESOLVED] * 11
    assert common.straddle({"q": short}) == "straddle_short:q"
    # Cells within U or unresolved count on neither side.
    assert common.straddle({"q": [FEASIBLE, INFEASIBLE, None, None, None, None]}) == (
        "straddle_short:q"
    )
    # Every limit is checked and the failure names it.
    assert (
        common.straddle({"torque": third, "ripple": [FEASIBLE] * 30})
        == "straddle_short:ripple"
    )
    # The unresolved fraction cap (Motor's U decision) is its own failure.
    assert (
        common.straddle(
            {"q": third}, unresolved_max_fraction=0.25
        )
        == "unresolved_over_fraction:q"
    )
    assert common.straddle({"q": third}, unresolved_max_fraction=1 / 3) is None
    for bad in ({}, {"q": []}):
        with pytest.raises(ValueError):
            common.straddle(bad)


def test_battery_straddle_over_140_cells_is_one_limit():
    sides = [FEASIBLE if k % 2 else INFEASIBLE for k in range(140)]
    assert common.straddle({"plating_margin_m160_v": sides}) is None
    assert (
        common.straddle({"plating_margin_m160_v": [FEASIBLE] * 140})
        == "straddle_short:plating_margin_m160_v"
    )


# --- grid and pack fields (C2, C3) ---------------------------------------------------


def test_a_grid_is_a_complete_cross_of_the_registered_shape():
    assert common.validate_grid(_grid(5, 6), shape=(5, 6)) is None
    assert common.validate_grid(_grid(4, 4), shape=(4, 4)) is None
    assert common.validate_grid(_grid(35, 4), shape=(35, 4)) is None
    # A single-condition Challenge (F02, F08): the cases are the designs.
    assert common.validate_grid(_grid(8, 1), shape=(8, 1)) is None
    wrong = _grid(5, 6)
    for broken, shape in (
        (wrong[:-1], (5, 6)),
        (wrong + [wrong[0]], (5, 6)),
        (wrong, (6, 5)),
        ([{**wrong[0], "condition_id": ""}] + wrong[1:], (5, 6)),
        ([{"design_id": "design-0"}] + wrong[1:], (5, 6)),
        ([], (5, 6)),
    ):
        assert common.validate_grid(broken, shape=shape) == common.GRID_INCOMPLETE


def test_pack_fields_are_one_cohort_with_design_and_condition_ids():
    records = _grid(5, 6)
    cohorts = (common.GRID_COHORT,) * 30
    assert common.validate_pack_fields(cohorts, records, shape=(5, 6)) is None
    assert common.validate_pack_fields(cohorts[:-1] + ("screening",), records) == (
        common.PACK_COHORT
    )
    # Six per-condition cohorts are not the registered layout.
    per_condition = tuple(f"decision_condition_{c}" for _ in range(5) for c in range(6))
    assert common.validate_pack_fields(per_condition, records) == common.PACK_COHORT
    missing = [{"design_id": "design-0"}] + records[1:]
    assert common.validate_pack_fields(cohorts, missing) == common.PACK_FIELDS
    assert common.validate_pack_fields(cohorts[:29], records) == common.PACK_FIELDS
    assert common.validate_pack_fields(cohorts, records, shape=(6, 5)) == (
        common.GRID_INCOMPLETE
    )


def test_evaluation_versions_follow_the_common_name():
    for name in (
        "battery-dual-sealed-grid-4x35-v1",
        "motor-dual-sealed-batch-30-v1",
        "f02-dual-sealed-batch-8-v1",
        "cooling-dual-sealed-grid-4x4-v1",
    ):
        assert common.evaluation_version_ok(name), name
    for name in ("battery-dual-development-bank-v2", "motor-sealed-v1", "", None):
        assert not common.evaluation_version_ok(name), name


# --- the decision check (C5) -----------------------------------------------------------


def _labels(grid, table):
    return lambda cell: table[(cell["design_id"], cell["condition_id"])]


def _table(designs, conditions, feasible):
    return {
        (f"design-{d}", f"condition-{c}"): (FEASIBLE if feasible(d, c) else INFEASIBLE)
        for d in range(designs)
        for c in range(conditions)
    }


def test_robust_choice_needs_a_design_feasible_everywhere_and_a_nontrivial_condition():
    """Motor's rule (5 x 6), the same for Cooling (4 x 4), F08 and F02."""
    grid = _grid(5, 6)

    def check(feasible, shape=(5, 6)):
        return common.decision_check(
            grid,
            _labels(grid, _table(5, 6, feasible)),
            choice=ROBUST,
            shape=shape,
        )

    # Design 0 holds everywhere; the others fail at condition 0: a real choice.
    assert check(lambda d, c: d == 0 or c > 0) is None
    # Everything feasible everywhere: no non-trivial condition.
    assert check(lambda d, c: True) == common.NO_NONTRIVIAL_CONDITION
    # No design feasible at every condition (each design fails one condition).
    assert check(lambda d, c: c != d) == common.NO_DESIGN_FEASIBLE_EVERYWHERE
    # Nothing feasible at all: the non-trivial clause is reported first.
    assert check(lambda d, c: False) == common.NO_NONTRIVIAL_CONDITION
    # An incomplete grid is its own failure.
    assert (
        common.decision_check(
            grid[:-1],
            _labels(grid, _table(5, 6, lambda d, c: True)),
            choice=ROBUST,
            shape=(5, 6),
        )
        == common.GRID_INCOMPLETE
    )
    assert check(lambda d, c: True, shape=(6, 5)) == common.GRID_INCOMPLETE


def test_unresolved_cells_are_neither_feasible_nor_infeasible():
    grid = _grid(2, 2)
    labels = {
        ("design-0", "condition-0"): FEASIBLE,
        ("design-0", "condition-1"): FEASIBLE,
        ("design-1", "condition-0"): UNRESOLVED,
        ("design-1", "condition-1"): INFEASIBLE,
    }
    assert common.decision_check(grid, _labels(grid, labels), choice=ROBUST) is None
    labels[("design-1", "condition-1")] = UNRESOLVED
    assert (
        common.decision_check(grid, _labels(grid, labels), choice=ROBUST)
        == common.NO_NONTRIVIAL_CONDITION
    )


def test_per_condition_choice_is_batterys_every_scenario_decides_for_itself():
    """Battery: 35 candidates (designs) x 4 scenarios (conditions)."""
    grid = _grid(35, 4)

    def check(feasible):
        return common.decision_check(
            grid,
            _labels(grid, _table(35, 4, feasible)),
            choice=PER_CONDITION,
            shape=(35, 4),
        )

    assert check(lambda d, c: d % 2 == 0) is None
    assert check(lambda d, c: d % 2 == 0 and c != 2) == common.CONDITION_NO_FEASIBLE
    assert check(lambda d, c: True) == common.CONDITION_NO_INFEASIBLE
    with pytest.raises(ValueError):
        common.decision_check(grid, lambda cell: FEASIBLE, choice="other")
