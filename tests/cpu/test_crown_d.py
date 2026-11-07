"""Crown-time D pure logic. All fixtures are SYNTHETIC (analytic stand-in model, made-up zero values)."""

import dataclasses
import hashlib
import json

import pytest

from carbon.scoring import crown_d as cd
from carbon.scoring import pool_model_search as pms
from carbon.scoring.pool_grader import Limit

HOST = "custody2"
INPUTS = ("load", "x0", "x1")
DESIGN = ("x0", "x1")


def _problem(**kw):
    args = {
        "target_id": "t1",
        "fixed": {"load": 1.0},
        "outputs": ("f", "g"),
        "objective": "f",
        "sense": "max",
        "limits": (Limit("g", "<=", 0.5),),
        "u": {"f": 0.01, "g": 0.01},
        "box": ((0.0, 1.0), (0.0, 1.0)),
    }
    args.update(kw)
    return pms.proof_problem(**args)


def _derived(rows):
    # f = load * (x0 + x1), g = x0^2 + x1^2: model optimum at x0 = x1 = 0.5, f = 1
    return [{"f": r[0] * (r[1] + r[2]), "g": r[1] ** 2 + r[2] ** 2} for r in rows]


def _evaluator(predict=_derived):
    return pms.model_evaluator(predict, input_names=INPUTS, design_names=DESIGN)


def _zero_doc(**rows):
    targets = rows or {"t1": {"s_zero": 0.6, "s_ref": 1.0, "source": "shortcut"}}
    return {"schema": cd.ZERO_SCHEMA_V1, "targets": targets}


def _sha(doc):
    return hashlib.sha256(
        json.dumps(doc, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _rule(**kw):
    args = {
        "zero_sha256": _sha(_zero_doc()),
        "weekly_solves": 10,
        "hold_seconds": 7200,
        "coarse_rung": "coarse",
        "fine_rung": "fine",
        "dedupe_grid": 0.01,
        "min_targets": 2,
        "optimizer": "cmaes_proof_v1",
    }
    args.update(kw)
    return cd.CrownDRule(**args)


ENTRY = cd.ZeroEntry(s_zero=0.6, s_ref=1.0, source="shortcut")


# --- rule ---


def test_a_complete_rule_passes():
    assert cd.check_rule(_rule()) == _rule()


@pytest.mark.parametrize(
    "name",
    # model_call_budget is per optimizer (None is required for cmaes_proof_v1): test_crown_d_de.py
    [
        f.name
        for f in dataclasses.fields(cd.CrownDRule)
        if f.name != "model_call_budget"
    ],
)
def test_each_none_field_is_human_input(name):
    with pytest.raises(cd.CrownDRefused) as err:
        cd.check_rule(_rule(**{name: None}))
    assert err.value.code == f"crown_d_{name}_is_human_input"


@pytest.mark.parametrize(
    "kw, code",
    [
        ({"zero_sha256": "ab" * 31}, "crown_d_zero_sha256_invalid"),
        ({"zero_sha256": "AB" * 32}, "crown_d_zero_sha256_invalid"),
        ({"weekly_solves": 0}, "crown_d_weekly_solves_invalid"),
        ({"weekly_solves": True}, "crown_d_weekly_solves_invalid"),
        ({"hold_seconds": 59}, "crown_d_hold_seconds_invalid"),
        ({"coarse_rung": ""}, "crown_d_rungs_must_be_distinct_names"),
        ({"fine_rung": "coarse"}, "crown_d_rungs_must_be_distinct_names"),
        ({"dedupe_grid": 0.0}, "crown_d_dedupe_grid_invalid"),
        ({"dedupe_grid": 0.2}, "crown_d_dedupe_grid_invalid"),
        ({"dedupe_grid": 1}, "crown_d_dedupe_grid_invalid"),
        ({"min_targets": 0}, "crown_d_min_targets_invalid"),
    ],
)
def test_bad_rule_values_refuse(kw, code):
    with pytest.raises(cd.CrownDRefused) as err:
        cd.check_rule(_rule(**kw))
    assert err.value.code == code


# --- zero record ---


def test_zero_record_parses_sorts_and_hashes_canonical_json():
    doc = _zero_doc(
        t2={"s_zero": -3.0, "s_ref": -1.0, "source": "train_best"},
        t1={"s_zero": 0.6, "s_ref": 1.0, "source": "fit_pick"},
    )
    record = cd.zero_record(doc)
    assert [tid for tid, _ in record.targets] == ["t1", "t2"]
    assert record.entry("t2") == cd.ZeroEntry(-3.0, -1.0, "train_best")
    assert record.sha256 == _sha(doc)
    with pytest.raises(cd.CrownDRefused, match="crown_d_zero_has_no_entry_for_target"):
        record.entry("t9")


@pytest.mark.parametrize(
    "doc, code",
    [
        ({"schema": cd.ZERO_SCHEMA_V1}, "crown_d_zero_malformed"),
        ({"schema": "other", "targets": {}}, "crown_d_zero_schema_unknown"),
        ({"schema": cd.ZERO_SCHEMA_V1, "targets": {}}, "crown_d_zero_has_no_targets"),
        (
            _zero_doc(t1={"s_zero": 1.0, "s_ref": 1.0, "source": "shortcut"}),
            "crown_d_zero_s_ref_not_above_s_zero",
        ),
        (
            _zero_doc(t1={"s_zero": 0.0, "s_ref": 1.0, "source": "oracle"}),
            "crown_d_zero_source_unknown",
        ),
        (
            _zero_doc(t1={"s_zero": float("nan"), "s_ref": 1.0, "source": "shortcut"}),
            "crown_d_zero_values_not_finite",
        ),
        (
            _zero_doc(t1={"s_zero": 0.0, "s_ref": float("inf"), "source": "shortcut"}),
            "crown_d_zero_values_not_finite",
        ),
        (_zero_doc(t1={"s_zero": 0.0, "s_ref": 1.0}), "crown_d_zero_malformed"),
    ],
)
def test_zero_record_refusals(doc, code):
    with pytest.raises(cd.CrownDRefused) as err:
        cd.zero_record(doc)
    assert err.value.code == code


def test_attach_zero_checks_sha_and_coverage():
    record = cd.attach_zero(_rule(), _zero_doc(), [_problem()])
    assert record.entry("t1") == ENTRY
    with pytest.raises(cd.CrownDRefused, match="crown_d_zero_sha256_mismatch"):
        cd.attach_zero(_rule(zero_sha256="0" * 64), _zero_doc(), [_problem()])
    with pytest.raises(cd.CrownDRefused, match="crown_d_zero_missing_a_target"):
        cd.attach_zero(_rule(), _zero_doc(), [_problem(), _problem(target_id="t2")])


# --- pick ---


def test_pick_returns_the_model_optimum():
    p = cd.pick(_problem(), _evaluator(), host_class=HOST, rule=_rule())
    assert p.target_id == "t1" and p.model_feasible and len(p.design) == 2
    x0, x1 = p.design
    assert x0**2 + x1**2 <= 0.5 and x0 + x1 > 1.0 - 0.02
    assert (
        cd.pick(_problem(), _evaluator(), host_class=HOST, rule=_rule()) == p
    )  # deterministic


def test_pick_refuses_off_custody_before_any_model_call():
    calls = []

    def predict(rows):
        calls.append(rows)
        return _derived(rows)

    with pytest.raises(ValueError, match="host_not_custody"):
        cd.pick(_problem(), _evaluator(predict), host_class="lium", rule=_rule())
    assert calls == []


# --- dedupe key ---


def _key(design, rung="coarse", target_id="t1"):
    return cd.dedupe_key("c1", 3, target_id, rung, _problem(), design, 0.01)


def test_dedupe_key_shares_within_half_a_cell_and_splits_across_cells():
    assert _key((0.500, 0.300)) == _key((0.504, 0.296))
    assert _key((0.50, 0.30)) != _key((0.51, 0.30))
    assert _key((0.50, 0.30)) != _key((0.50, 0.30), rung="fine")
    assert _key((0.50, 0.30)) != _key((0.50, 0.30), target_id="t2")
    assert len(_key((0.5, 0.3))) == 64


def test_dedupe_key_uses_the_unit_box():
    wide = _problem(box=((0.0, 10.0), (0.0, 1.0)))
    a = cd.dedupe_key("c1", 3, "t1", "coarse", wide, (5.00, 0.3), 0.01)
    b = cd.dedupe_key("c1", 3, "t1", "coarse", wide, (5.04, 0.3), 0.01)
    assert a == b


def test_dedupe_key_refuses_out_of_box_and_bad_input():
    with pytest.raises(cd.CrownDRefused, match="crown_d_design_outside_the_box"):
        _key((1.01, 0.5))
    with pytest.raises(cd.CrownDRefused, match="crown_d_design_invalid"):
        _key((0.5,))
    with pytest.raises(cd.CrownDRefused, match="crown_d_dedupe_grid_invalid"):
        cd.dedupe_key("c1", 3, "t1", "coarse", _problem(), (0.5, 0.5), 0.5)


# --- needs_fine ---


def test_needs_fine_near_a_limit():
    assert cd.needs_fine(_problem(), ENTRY, {"f": 0.9, "g": 0.495})
    assert cd.needs_fine(_problem(), ENTRY, {"f": 0.9, "g": 0.505})


def test_needs_fine_near_the_zero():
    assert cd.needs_fine(_problem(), ENTRY, {"f": 0.605, "g": 0.2})


def test_needs_fine_false_far_from_both():
    assert not cd.needs_fine(_problem(), ENTRY, {"f": 0.9, "g": 0.2})


def test_needs_fine_exact_u_never_within():
    exact = _problem(u={"f": 0.0, "g": 0.0})
    assert not cd.needs_fine(exact, ENTRY, {"f": 0.6, "g": 0.5})


def test_needs_fine_relative_u_and_min_sense():
    rel = _problem(u={"f": {"relative": 0.1}, "g": 0.01})
    assert cd.needs_fine(rel, ENTRY, {"f": 0.65, "g": 0.2})  # U(f) = 0.065
    mn = _problem(sense="min")
    assert cd.needs_fine(
        mn, cd.ZeroEntry(-0.6, -0.2, "shortcut"), {"f": 0.605, "g": 0.2}
    )


def test_needs_fine_refuses_missing_or_non_finite_outputs():
    with pytest.raises(cd.CrownDRefused, match="crown_d_outputs_missing_or_not_finite"):
        cd.needs_fine(_problem(), ENTRY, {"f": 0.9})
    with pytest.raises(cd.CrownDRefused, match="crown_d_outputs_missing_or_not_finite"):
        cd.needs_fine(_problem(), ENTRY, {"f": float("nan"), "g": 0.2})


# --- target_d ---


def test_target_d():
    p = _problem()
    assert cd.target_d(p, ENTRY, {"f": 0.95, "g": 0.51}) == 0.0  # truly infeasible
    assert cd.target_d(p, ENTRY, {"f": 0.5, "g": 0.2}) == 0.0  # below the zero
    assert cd.target_d(p, ENTRY, {"f": 0.6, "g": 0.2}) == 0.0  # at the zero
    assert cd.target_d(p, ENTRY, {"f": 0.8, "g": 0.2}) == pytest.approx(0.5)
    assert cd.target_d(p, ENTRY, {"f": 1.4, "g": 0.2}) == 1.0  # above the reference


# --- decide ---


def _solved(d):
    return {"state": "SOLVED", "outputs": {"f": 0.8, "g": 0.2}, "d": d}


def _decide(results, now=100.0, budget_deferred=False, expected=None, **rule):
    return cd.decide(
        _rule(**rule),
        results=results,
        expected_targets=sorted(results) if expected is None else expected,
        requested_at=0.0,
        now=now,
        budget_deferred=budget_deferred,
    )


REF_FAIL = {"state": "REFERENCE_FAILED", "code": "REFERENCE_NO_CONVERGENCE"}


def test_decide_all_solved():
    out = _decide({"t1": _solved(0.2), "t2": _solved(0.6)})
    assert out == {
        "state": "SOLVED",
        "d": pytest.approx(0.4),
        "targets": 2,
        "dropped": 0,
    }


def test_decide_reference_failure_dropped_above_min_targets():
    out = _decide({"t1": _solved(0.2), "t2": _solved(0.6), "t3": REF_FAIL})
    assert out["state"] == "SOLVED" and out["targets"] == 2 and out["dropped"] == 1
    assert out["d"] == pytest.approx(0.4)


def test_decide_reference_failure_below_min_targets():
    out = _decide({"t1": _solved(0.2), "t2": REF_FAIL})
    assert out == {
        "state": "FAILED_INFRA",
        "reason": "too_few_targets_after_reference_failures",
    }


def test_decide_holds_with_seconds_left():
    assert _decide({"t1": _solved(0.2), "t2": {"state": "PENDING"}}, now=100.5) == {
        "state": "HOLD",
        "seconds_left": 7100,
    }
    assert (
        _decide({"t1": _solved(0.2), "t2": {"state": "FAILED_INFRA"}})["state"]
        == "HOLD"
    )


def test_decide_hold_bound_reached():
    out = _decide({"t1": _solved(0.2), "t2": {"state": "FAILED_INFRA"}}, now=7200.0)
    assert out == {"state": "FAILED_INFRA", "reason": "hold_bound_reached"}


def test_decide_budget_deferred():
    out = _decide(
        {"t1": _solved(0.2), "t2": {"state": "PENDING"}},
        now=9999.0,
        budget_deferred=True,
    )
    assert out == {"state": "CROWN_DEFERRED_D_BUDGET"}


def test_decide_refuses_malformed_results():
    with pytest.raises(cd.CrownDRefused, match="crown_d_result_state_unknown"):
        _decide({"t1": {"state": "DONE"}})
    with pytest.raises(cd.CrownDRefused, match="crown_d_solved_result_invalid"):
        _decide({"t1": _solved(1.5)})
    with pytest.raises(cd.CrownDRefused, match="crown_d_reference_failed_needs_a_code"):
        _decide({"t1": {"state": "REFERENCE_FAILED"}})
    with pytest.raises(cd.CrownDRefused, match="crown_d_clock_invalid"):
        _decide({"t1": _solved(0.2)}, now=-1.0)


def test_pick_refuses_any_optimizer_but_the_fixed_one():
    from dataclasses import replace

    for change in ({"seed": 7}, {"start": (0.2, 0.5)}):
        with pytest.raises(cd.CrownDRefused, match="not_the_fixed_optimizer"):
            cd.pick(
                replace(_problem(), **change),
                _evaluator(),
                host_class=HOST,
                rule=_rule(),
            )


def test_decide_counts_a_target_with_no_result_as_pending_never_dropped():
    out = _decide({"t1": _solved(0.9)}, expected=["t1", "t2"], now=10.0)
    assert (
        out["state"] == "HOLD"
    )  # t2 has no result yet: D waits, it is not the mean of t1 alone
    with pytest.raises(cd.CrownDRefused, match="not_the_expected_targets"):
        _decide({"t1": _solved(0.9), "tx": _solved(0.1)}, expected=["t1"])
