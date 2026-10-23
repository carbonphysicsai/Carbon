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
    [("torque", -1)],
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


# --- V = mean(V_pair, V_feas, V_var) (OWNER-DESIGN-DECISION-FIDELITY-01) -------

CELLS_OF = {"a": ["a0", "a1"], "b": ["b0", "b1"], "c": ["c0", "c1"]}


def _value_inputs():
    reference = {
        "cases": {
            "a0": {"torque_margin": 0.5, "ripple_margin": 0.05},
            "a1": {"torque_margin": 0.4, "ripple_margin": 0.04},
            "b0": {"torque_margin": 0.3, "ripple_margin": 0.03},
            "b1": {"torque_margin": 0.2, "ripple_margin": 0.02},
            "c0": {"torque_margin": -0.2, "ripple_margin": 0.05},
            "c1": {"torque_margin": 0.3, "ripple_margin": 0.05},
        },
        "actions": {
            "a": {"feasible": True, "objective": 0.10},
            "b": {"feasible": True, "objective": 0.20},
            "c": {"feasible": False, "objective": 0.05},
        },
    }
    prediction = {
        "cases": {cid: dict(row) for cid, row in reference["cases"].items()},
        "selected": "a",
        "objective": {a: row["objective"] for a, row in reference["actions"].items()},
    }
    return reference, prediction


def _value(reference, prediction, base_v=1.0):
    return cf.value(
        BLOCK3,
        cells_of=CELLS_OF,
        reference=reference,
        prediction=prediction,
        base_v=base_v,
        limits={"torque": 4.0},
    )


BLOCK3 = cf.block(
    [
        ("torque", "margin", "torque_margin", "N.m", 0.1),
        ("ripple", "margin", "ripple_margin", "1", 0.01),
    ],
    ("1", "MINIMIZE", 0.05),
    [("torque", -1)],
)


def test_a_model_equal_to_the_references_earns_full_v():
    reference, prediction = _value_inputs()
    v, record = _value(reference, prediction)
    assert v == 1.0
    assert (record["V_pair"], record["V_feas"], record["V_var"]) == (1.0, 1.0, 1.0)


def test_a_model_that_picks_right_but_orders_the_pairs_badly_gets_v_below_one():
    reference, prediction = _value_inputs()
    # The pick (a, lowest feasible objective) is unchanged; b and c are swapped
    # relative to a in the predicted objective, so pairs are misordered.
    prediction["objective"] = {"a": 0.10, "b": 0.04, "c": 0.30}
    v, record = _value(reference, prediction)
    assert record["V_pair"] < 1.0 and v < 1.0
    # The unselected pairs alone moved V_pair: the base question is still right.
    assert prediction["selected"] == "a"


def test_pair_cost_is_the_true_gap_of_the_misordered_pairs():
    reference, prediction = _value_inputs()
    prediction["objective"] = {"a": 0.10, "b": 0.04, "c": 0.30}
    _, record = _value(reference, prediction)
    # gaps: ab 0.10, ac 0.05, bc 0.15 (sum 0.30). a<b,b<c wrongly: ab misordered
    # (predicted b<a), bc misordered (predicted c>b)? bc: true c<b, pred b<c ->
    # misordered; ac: true c<a, pred a<c -> misordered. All three.
    assert record["V_pair"] == pytest.approx(0.0)


def test_a_wrong_accept_costs_the_true_violation_in_scale_units():
    reference, prediction = _value_inputs()
    prediction["cases"]["c0"]["torque_margin"] = 0.2  # accepts c, truth -0.2
    _, record = _value(reference, prediction)
    # cost = 0.2 / 0.1 = 2 on one of three actions -> mean 2/3 -> 1/(1+2/3).
    assert record["V_feas"] == pytest.approx(1 / (1 + 2 / 3))


def test_a_wrong_reject_costs_the_margin_given_up():
    reference, prediction = _value_inputs()
    prediction["cases"]["b1"]["torque_margin"] = -0.1  # rejects b, truth +0.2
    _, record = _value(reference, prediction)
    assert record["V_feas"] == pytest.approx(1 / (1 + (0.2 / 0.1) / 3))


def test_the_nearby_variants_ask_the_pick_again_under_the_shifted_limit():
    reference, prediction = _value_inputs()
    # 5% of the 4 N.m limit is 0.2: at -5% (margin + 0.2... sigma -1 lowers the
    # margin when the limit rises). Raising the limit by 0.2 removes b (0.2 -> 0)
    # only if margin < 0.2; b1 margin 0.2 stays feasible, so make b1 0.15 in the
    # reference and have the model not see it.
    reference["cases"]["b1"]["torque_margin"] = 0.15
    prediction["cases"]["b1"]["torque_margin"] = 0.25
    prediction["objective"] = {"a": 0.30, "b": 0.20, "c": 0.05}
    _, record = _value(reference, prediction, base_v=1.0)
    # The model prefers b; b is truly infeasible once the limit rises by 5%
    # (0.15 - 0.2 < 0) but the model still accepts it, so that variant is 0.
    assert record["V_var"] < 1.0
    assert record["variant_questions"] == 2


def test_a_missing_prediction_leaves_v_undefined():
    reference, prediction = _value_inputs()
    del prediction["objective"]["b"]
    assert _value(reference, prediction)[0] is None
    reference, prediction = _value_inputs()
    prediction["cases"]["a1"]["torque_margin"] = float("nan")
    assert _value(reference, prediction)[0] is None
    reference, prediction = _value_inputs()
    assert _value(reference, prediction, base_v=None)[0] is None


def test_an_action_ruled_out_exactly_costs_no_accept_error():
    reference, prediction = _value_inputs()
    v, record = cf.value(
        BLOCK3,
        cells_of=CELLS_OF,
        reference=reference,
        prediction=prediction,
        base_v=1.0,
        limits={"torque": 4.0},
        exact_ok={"a": False},
    )
    assert record["V_feas"] == 1.0


def test_a_straddle_far_from_the_limit_is_covered_not_out_of_proximity():
    """A sealed batch registers a straddle (one case on each side), not a distance
    bound: margins many scales from zero are covered, never charged."""
    reference = {
        "cases": {
            "a0": {"torque_margin": 5.0, "ripple_margin": 0.5},
            "a1": {"torque_margin": -4.0, "ripple_margin": -0.5},
            "b0": {"torque_margin": 6.0, "ripple_margin": 0.4},
            "b1": {"torque_margin": -3.0, "ripple_margin": -0.4},
        },
        "actions": {
            "a": {"feasible": False, "objective": 0.1},
            "b": {"feasible": False, "objective": 0.2},
        },
    }
    result = _reduce(_model(reference), reference)
    assert not any(
        "OUTSIDE_DECLARED_PROXIMITY" in x for x in result["reference_limitations"]
    )
    assert result["C"] == 1.0
