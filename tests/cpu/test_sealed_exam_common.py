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
        common.straddle({"q": third}, unresolved_max_fraction=0.25)
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


# --- the pack set and the version aggregate (OWNER-FULL-EXAM-BANK-01) --------------------


def _digest(c):
    return "sha256:" + c * 64


def _content(case_bank, reference_rows):
    return {"case_bank": _digest(case_bank), "reference_rows": _digest(reference_rows)}


def test_a_pack_set_has_one_body_and_its_digest_is_the_evaluation_key():
    one = common.pack_set_document(
        "motor", "1.0", [_content("b", "2"), _content("a", "1")]
    )
    two = common.pack_set_document(
        "motor", "1.0", [_content("a", "1"), _content("b", "2")]
    )
    assert one == two and one["batches"] == [_content("a", "1"), _content("b", "2")]
    key = common.pack_set_key(one)
    assert key.startswith("sha256:") and len(key) == 71
    # A rotation is a new set and so a new key.
    rotated = common.pack_set_document(
        "motor", "1.0", [_content("a", "1"), _content("c", "3")]
    )
    assert common.pack_set_key(rotated) != key
    # A version with no registered sealed exam keys by its construction version.
    other = common.pack_set_document(
        "motor", "1.1", [_content("a", "1"), _content("b", "2")]
    )
    assert common.pack_set_key(other) != key


def test_the_set_key_is_the_exam_content_without_any_version():
    """The Validator's content-key ruling: {challenge, evaluation version, per
    batch {case_bank, reference_rows}}; no construction or pack version."""
    contents = [_content("b", "2"), _content("a", "1")]
    f14 = common.pack_set_document("f08-ribbed-bracket", "1.4", contents)
    f15 = common.pack_set_document("f08-ribbed-bracket", "1.5", contents)
    assert (
        f14
        == f15
        == {
            "schema": common.PACK_SET_SCHEMA,
            "challenge_id": "f08-ribbed-bracket",
            "evaluation_version": "f08-dual-sealed-grid-8x1-v2",
            "batches": [_content("a", "1"), _content("b", "2")],
        }
    )
    key = common.pack_set_key(f14)
    assert common.pack_set_key(f15) == key
    # One batch's reference rows changed, or separately its case bank: a new exam.
    for changed in (_content("a", "9"), _content("9", "1")):
        moved = common.pack_set_document(
            "f08-ribbed-bracket", "1.5", [changed, _content("b", "2")]
        )
        assert common.pack_set_key(moved) != key
    # Another Challenge on the same content is another set.
    f02 = common.pack_set_document("f02", "2.4", contents)
    assert common.pack_set_key(f02) != key


def test_a_stored_set_keeps_its_key_and_meaning():
    batches = [_digest("a"), _digest("b")]
    contents = [_content("a", "1"), _content("b", "2")]
    v1 = common.pack_set_document_v1("f08-ribbed-bracket", "1.4", batches)
    v2 = common.pack_set_document_v2("f08-ribbed-bracket", "1.4", batches)
    assert v1["challenge"] == {"id": "f08-ribbed-bracket", "version": "1.4"}
    v3 = common.pack_set_document("f08-ribbed-bracket", "1.4", contents)
    keys = [common.pack_set_key(d) for d in (v1, v2, v3)]
    assert len(set(keys)) == 3
    for key, document in zip(keys, (v1, v2, v3), strict=True):
        found = common.verified_pack_set(
            "f08-ribbed-bracket", "1.4", batches, key, contents
        )
        assert found == document
    assert common.stored_set_key("f08-ribbed-bracket", "1.4", batches, keys[2]) is None
    # A v1 key named its version: it never verifies for 1.5; a v2 key does.
    with pytest.raises(common.PackSetRefused, match="pack_set_key_mismatch"):
        common.verified_pack_set(
            "f08-ribbed-bracket", "1.5", batches, keys[0], contents
        )
    assert common.stored_set_key("f08-ribbed-bracket", "1.5", batches, keys[1]) == v2
    # A content key over other content, or the wrong number of batches, refuses.
    for wrong in ([_content("a", "1"), _content("b", "9")], contents[:1]):
        with pytest.raises(common.PackSetRefused, match="pack_set_key_mismatch"):
            common.verified_pack_set(
                "f08-ribbed-bracket", "1.4", batches, keys[2], wrong
            )


@pytest.mark.parametrize(
    "challenge,version,contents",
    [
        ("motor", "1.0", []),
        ("motor", "1.0", [_content("a", "1"), _content("a", "1")]),
        (
            "motor",
            "1.0",
            [{"case_bank": "sha256:short", "reference_rows": _digest("1")}],
        ),
        ("motor", "1.0", [{"case_bank": _digest("a")}]),
        ("motor", "1.0", [_digest("a")]),
        ("", "1.0", [_content("a", "1")]),
        ("motor", "", [_content("a", "1")]),
    ],
)
def test_a_malformed_pack_set_is_refused(challenge, version, contents):
    with pytest.raises(common.PackSetRefused):
        common.pack_set_document(challenge, version, contents)


def test_a_body_not_built_by_the_builder_has_no_key():
    body = common.pack_set_document(
        "motor", "1.0", [_content("a", "1"), _content("b", "2")]
    )
    for broken in (
        {**body, "batches": list(reversed(body["batches"]))},
        {**body, "extra": 1},
        {**body, "schema": "other"},
        {k: v for k, v in body.items() if k != "challenge_id"},
        {**body, "evaluation_version": ""},
        {**common.pack_set_document_v2("motor", "1.0", [_digest("a")]), "extra": 1},
        {**common.pack_set_document_v1("motor", "1.0", [_digest("a")]), "extra": 1},
    ):
        with pytest.raises(common.PackSetRefused):
            common.pack_set_key(broken)


def _batch(a, d, ok=True, extra=None):
    gates = {"native": ok, "coverage": True}
    gates.update(extra or {})
    return {"gates": gates, "A": a, "D": d}


def test_the_version_grade_is_the_equal_weight_mean_over_its_batches():
    graded = common.aggregate([_batch(0.8, 0.4), _batch(0.6, 0.2)])
    assert graded["eligible"] is True and graded["batches"] == 2
    assert graded["A"] == pytest.approx(0.7) and graded["D"] == pytest.approx(0.3)
    assert graded["total"] == pytest.approx(0.5)
    # One batch is the version of a single-batch launch set.
    single = common.aggregate([_batch(0.8, 0.4)])
    assert single["total"] == pytest.approx(0.6)


def test_a_gate_must_pass_on_every_batch_and_a_failure_shows_no_number():
    graded = common.aggregate([_batch(0.8, 0.4), _batch(0.9, 0.9, ok=False)])
    assert graded["gates"] == {"coverage": True, "native": False}
    assert graded["eligible"] is False
    assert graded["A"] is graded["D"] is graded["total"] is None


def test_an_aggregate_refuses_what_cannot_be_averaged():
    for bad in (
        [],
        [_batch(0.8, 0.4), _batch(0.6, 0.2, extra={"more": True})],
        [_batch(float("nan"), 0.4)],
        [_batch(0.8, None)],
        [_batch(1.2, 0.4)],
        [{"A": 0.5, "D": 0.5}],
    ):
        with pytest.raises(common.PackSetRefused):
            common.aggregate(bad)
    with pytest.raises(common.PackSetRefused):
        common.aggregate([_batch(0.5, 0.5)], value_weight=1.0)
