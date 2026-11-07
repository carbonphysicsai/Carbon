"""The de_polish_v1 grading optimizer (`pool_model_search.model_search_de`) and crown_d's optimizer dispatch.

Golden vector: design-optimum's reference `de_polish_search.py` (sha 39c05c53) on the pure-Python golden model below at
budget 3000, seed 0 gives sha256 abf6a9bf... over every call's (design, status); bit-exact or it is not this optimizer
(spec GRADING_OPTIMIZER_SPEC_DE_POLISH.md, owner decision 7 Nov 13:15Z). All fixtures are SYNTHETIC.
"""

import dataclasses
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_crown_d import (
    HOST,
    _evaluator,
    _problem,
    _rule,
    _sha,
    _zero_doc,
)

from carbon.scoring import crown_d as cd
from carbon.scoring import pool_model_search as pms
from carbon.scoring import pool_solver_reference as psr
from carbon.scoring.pool_grader import Limit

GOLDEN_SHA256 = "abf6a9bf98107a1697efccc5e32a68b6fd4f165dcf330f8c5c076129f1678d37"
GOLDEN_CALLS = 2701
GOLDEN_PICK = [1.0, 0.403766119113, 1.0, 0.224160837459, 0.0, 0.349916666023]
NAMES = [f"x{i}" for i in range(6)]


def golden_model(rows):
    """Pure Python (the reference selftest's model, verbatim): a torque-like objective with a saturation knee, a ragged
    ripple limit, a volume limit; an invalid-prediction corner."""
    out = []
    for x in rows:
        a, b, c, d, e, f = x
        if a < 0.05 and b < 0.05:
            out.append(None)
            continue
        knee = (0.4 + 0.9 * a) * (0.6 + 0.8 * b) / (1.25 - b)
        sat = 1.0 / (1.0 + 2.5 * max(0.0, knee - 1.3) ** 2)
        torque = (
            3.0 * (0.3 + a) * (0.2 + b) * sat * (1.0 - 0.5 * e)
            + 0.4 * c
            - 0.3 * (f - 0.6) ** 2
        )
        tri = abs(((5.0 * c + 2.0 * d) % 2.0) - 1.0)
        ripple = 0.04 + 0.10 * (c - 0.75) ** 2 + 0.05 * b + 0.03 * e + 0.05 * tri
        out.append({"torque": torque, "ripple": ripple, "volume": a * (0.4 + f)})
    return out


def golden_problem(seed=0):
    return psr.Problem(
        target_id="golden",
        fixed={},
        outputs=("torque", "ripple", "volume"),
        objective="torque",
        sense="max",
        limits=(Limit("ripple", "<=", 0.10), Limit("volume", "<=", 0.75)),
        u={"torque": 0.001, "ripple": 0.001, "volume": 0.0005},
        box=((0.0, 1.0),) * 6,
        start=(0.5,) * 6,
        seed=seed,
    )


def _golden_ev(model=golden_model):
    return pms.model_evaluator(model, input_names=NAMES, design_names=NAMES)


def _digest(result):
    body = json.dumps(
        [[list(p.design), p.status] for p in result.points], separators=(",", ":")
    )
    return hashlib.sha256(body.encode()).hexdigest()


@pytest.fixture(scope="module")
def golden():
    return pms.model_search_de(
        golden_problem(), _golden_ev(), host_class=HOST, budget=3000
    )


# --- the optimizer ---


def test_golden_vector_is_bit_exact(golden):
    assert _digest(golden) == GOLDEN_SHA256
    assert golden.counts["model_calls"] == GOLDEN_CALLS
    assert [round(v, 12) for v in golden.pick.design] == GOLDEN_PICK
    assert golden.pick.model_feasible
    assert golden.settings["optimizer"] == "de_polish_v1"


def test_two_runs_are_identical(golden):
    again = pms.model_search_de(
        golden_problem(), _golden_ev(), host_class=HOST, budget=3000
    )
    assert _digest(again) == _digest(golden) and again.pick == golden.pick


@pytest.mark.parametrize("budget", [96, 500, 1234])
def test_the_budget_is_never_exceeded(budget):
    res = pms.model_search_de(
        golden_problem(), _golden_ev(), host_class=HOST, budget=budget
    )
    assert res.counts["model_calls"] <= budget == res.settings["budget"]
    assert [c.generation for c in res.checkpoints] == [
        max(1, min(res.counts["model_calls"], int(f * budget)))
        for f in pms.DE_CHECKPOINTS
    ]


def test_invalid_predictions_are_typed_and_never_picked(golden):
    refused = golden.counts["by_status"].get(psr.DERIVE_REFUSED, 0)
    assert refused > 0  # the golden model's invalid corner is visited
    assert golden.pick.predicted is not None


def test_refusals_before_any_model_call():
    calls = []

    def model(rows):
        calls.append(len(rows))
        return golden_model(rows)

    with pytest.raises(psr.SolverReferenceRefused, match="host_not_custody"):
        pms.model_search_de(
            golden_problem(), _golden_ev(model), host_class="lium", budget=3000
        )
    with pytest.raises(
        psr.SolverReferenceRefused, match="budget_too_small_for_one_de_generation"
    ):
        pms.model_search_de(
            golden_problem(), _golden_ev(model), host_class=HOST, budget=95
        )
    with pytest.raises(psr.SolverReferenceRefused, match="budget_too_small"):
        pms.model_search_de(
            golden_problem(), _golden_ev(model), host_class=HOST, budget=3000.0
        )
    assert calls == []


def test_a_perfect_model_lands_on_the_known_optimum():
    # max x0 + x1 s.t. x0^2 + x1^2 <= 0.5: optimum x0 = x1 = 0.5, f = 1 (regret vs the box median f = 1.0 at the
    # centre is 0 here, so measure the objective gap directly; the reference selftest's 7 problems: regret <= 0.003)
    res = pms.model_search_de(_problem(), _evaluator(), host_class=HOST, budget=3000)
    x0, x1 = res.pick.design
    assert res.pick.model_feasible and x0**2 + x1**2 <= 0.5
    assert 1.0 - (x0 + x1) <= 0.002


def test_model_search_cmaes_is_unchanged_by_the_new_optimizer():
    # the proof optimizer's pick on the same problem is what it was before de_polish_v1 landed
    res = pms.model_search(_problem(), _evaluator(), host_class=HOST)
    assert res.counts["model_calls"] == pms.PROOF_POPULATION * pms.PROOF_GENERATIONS
    assert "optimizer" not in res.settings


# --- crown_d dispatch ---


def _de_rule(**kw):
    return _rule(optimizer="de_polish_v1", model_call_budget=3000, **kw)


def test_pick_dispatches_on_the_registered_optimizer():
    cmaes = cd.pick(_problem(), _evaluator(), host_class=HOST, rule=_rule())
    direct = pms.model_search(_problem(), _evaluator(), host_class=HOST)
    assert cmaes.design == tuple(
        direct.pick.design
    )  # cmaes_proof_v1: the same call, bit for bit
    de = cd.pick(_problem(), _evaluator(), host_class=HOST, rule=_de_rule())
    direct = pms.model_search_de(_problem(), _evaluator(), host_class=HOST, budget=3000)
    assert de.design == tuple(direct.pick.design) and de.model_feasible


@pytest.mark.parametrize(
    "change, code",
    [
        ({"optimizer": None}, "crown_d_optimizer_is_human_input"),
        ({"optimizer": "nelder_mead"}, "crown_d_optimizer_unknown"),
        (
            {"optimizer": "de_polish_v1"},
            "crown_d_model_call_budget_is_human_input",
        ),
        (
            {"optimizer": "de_polish_v1", "model_call_budget": 3000.0},
            "crown_d_model_call_budget_invalid",
        ),
        (
            {"optimizer": "de_polish_v1", "model_call_budget": 0},
            "crown_d_model_call_budget_invalid",
        ),
        (
            {"model_call_budget": 3000},
            "crown_d_model_call_budget_not_used_by_cmaes_proof_v1",
        ),
    ],
)
def test_rule_refusals(change, code):
    with pytest.raises(cd.CrownDRefused) as err:
        cd.check_rule(dataclasses.replace(_rule(), **change))
    assert err.value.code == code


def test_de_pick_refuses_a_non_fixed_seed_or_a_budget_below_one_generation():
    with pytest.raises(cd.CrownDRefused, match="not_the_fixed_optimizer"):
        cd.pick(
            dataclasses.replace(_problem(), seed=3),
            _evaluator(),
            host_class=HOST,
            rule=_de_rule(),
        )
    with pytest.raises(
        cd.CrownDRefused, match="crown_d_model_call_budget_below_one_de_generation"
    ):
        cd.pick(
            _problem(),
            _evaluator(),
            host_class=HOST,
            rule=_rule(optimizer="de_polish_v1", model_call_budget=31),
        )


# --- the zero is built with the same optimizer ---


def _zero_v2(optimizer="de_polish_v1"):
    doc = _zero_doc()
    return {"schema": cd.ZERO_SCHEMA, "optimizer": optimizer, "targets": doc["targets"]}


def test_zero_v2_names_its_optimizer_and_v1_means_cmaes():
    assert cd.zero_record(_zero_v2()).optimizer == "de_polish_v1"
    assert cd.zero_record(_zero_doc()).optimizer == "cmaes_proof_v1"
    for bad, code in (
        (_zero_v2("nelder_mead"), "crown_d_zero_optimizer_unknown"),
        (
            {"schema": cd.ZERO_SCHEMA, "targets": _zero_doc()["targets"]},
            "crown_d_zero_malformed",
        ),
        ({**_zero_doc(), "optimizer": "de_polish_v1"}, "crown_d_zero_malformed"),
    ):
        with pytest.raises(cd.CrownDRefused) as err:
            cd.zero_record(bad)
        assert err.value.code == code


def test_attach_zero_refuses_a_zero_built_with_another_optimizer():
    doc = _zero_v2()
    record = cd.attach_zero(_de_rule(zero_sha256=_sha(doc)), doc, [_problem()])
    assert record.optimizer == "de_polish_v1"
    with pytest.raises(cd.CrownDRefused, match="zero_built_with_another_optimizer"):
        cd.attach_zero(
            _de_rule(zero_sha256=_sha(_zero_doc())), _zero_doc(), [_problem()]
        )
    with pytest.raises(cd.CrownDRefused, match="zero_built_with_another_optimizer"):
        cd.attach_zero(_rule(zero_sha256=_sha(doc)), doc, [_problem()])
