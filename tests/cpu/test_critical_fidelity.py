"""D = min(V, C) for the sealed graders (owner decision
OWNER-EVALUATION-FOCUS-AND-DATA-CYCLE-01 section 1): a correct action alone
cannot earn full Design. The shared module on a synthetic two-limit batch."""

from __future__ import annotations

import copy

import pytest

from carbon.scoring import critical_fidelity as cf

BLOCK = cf.block(
    [
        ("torque", "margin", "torque_margin", "N.m", 0.1),
        ("ripple", "margin", "ripple_margin", "1", 0.01),
    ],
    ("1", "MINIMIZE", 0.01),
)
CASES = ["a0", "a1", "b0", "b1"]
ACTIONS = ["a", "b"]


def _reference():
    return {
        "cases": {
            "a0": {"torque_margin": 0.5, "ripple_margin": 0.05},
            "a1": {"torque_margin": -0.2, "ripple_margin": 0.02},
            "b0": {"torque_margin": 0.3, "ripple_margin": -0.04},
            "b1": {"torque_margin": 0.1, "ripple_margin": 0.01},
        },
        "actions": {
            "a": {"feasible": False, "objective": 0.12},
            "b": {"feasible": False, "objective": 0.2},
        },
    }


def _model(reference, shift=None):
    cases = {cid: dict(row) for cid, row in reference["cases"].items()}
    for (cid, quantity), delta in (shift or {}).items():
        cases[cid][quantity] += delta
    return {"cases": cases, "selected": "a"}


def _reduce(model, reference=None):
    reference = reference or _reference()
    return cf.reduce(
        BLOCK,
        case_ids=CASES,
        action_ids=ACTIONS,
        reference=reference,
        prediction=model,
    )


def test_exact_margins_earn_full_critical_credit():
    reference = _reference()
    result = _reduce(_model(reference))
    assert result["C"] == 1.0
    d, record = cf.design(1.0, result)
    assert d == 1.0 and record["rule"] == "D=min(V,C)"
    assert record["reference_kind"] == "POINT_ESTIMATE_DIAGNOSTIC"


def test_the_right_pick_with_wrong_margins_scores_d_below_one():
    reference = _reference()
    model = _model(reference, {("a1", "torque_margin"): 0.1})
    d, record = cf.design(1.0, _reduce(model))
    assert d == pytest.approx(0.5) and d < 1.0
    assert record["components"]["torque"]["worst_effective_error"] == pytest.approx(0.1)


def test_an_unselected_candidates_error_caps_d():
    reference = _reference()
    # Action "a" is the selection; the error is on a "b" cell only.
    model = _model(reference, {("b0", "ripple_margin"): 0.02})
    d, _ = cf.design(1.0, _reduce(model))
    assert d == pytest.approx(1 / 3)


def test_d_is_the_lesser_of_value_and_critical_credit():
    reference = _reference()
    model = _model(reference, {("a0", "torque_margin"): 0.1})
    assert cf.design(0.25, _reduce(model))[0] == 0.25
    assert cf.design(0.9, _reduce(model))[0] == pytest.approx(0.5)


def test_a_zero_value_stays_zero_and_none_stays_none():
    result = _reduce(_model(_reference()))
    assert cf.design(0.0, result)[0] == 0.0
    assert cf.design(None, result)[0] is None


def test_a_missing_critical_prediction_has_no_d_not_a_smaller_error():
    reference = _reference()
    model = _model(reference)
    model["cases"]["b1"] = {}
    d, record = cf.design(1.0, _reduce(model))
    assert d is None
    assert record["candidate_issues"]


def test_a_nonfinite_prediction_has_no_d():
    reference = _reference()
    model = _model(reference)
    model["cases"]["a0"]["torque_margin"] = float("nan")
    assert cf.design(1.0, _reduce(model))[0] is None


def test_a_reference_side_missing_is_reported_not_charged():
    reference = _reference()
    for row in reference["cases"].values():
        row["torque_margin"] = abs(row["torque_margin"])
    result = _reduce(_model(reference), reference)
    assert result["C"] == 1.0
    assert result["reference_limitations"]
    assert cf.design(1.0, result)[0] == 1.0


def test_the_block_is_validated():
    cf.validate_block(BLOCK)
    for mutate in (
        lambda b: b.update(rule="D=V"),
        lambda b: b["components"][0].update(scale=0),
        lambda b: b["components"][0].update(kind="gap"),
        lambda b: b["components"].append(dict(b["components"][0])),
        lambda b: b["objective"].update(direction="UP"),
        lambda b: b.update(components_not_applied=[]),
    ):
        bad = copy.deepcopy(BLOCK)
        mutate(bad)
        with pytest.raises(cf.CriticalFidelityRefused):
            cf.validate_block(bad)
