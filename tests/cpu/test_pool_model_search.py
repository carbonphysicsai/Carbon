"""The model-driven search for the fixed-optimizer design-value proof (analytic stand-in models only)."""

import math

import pytest

from carbon.scoring import pool_model_search as pms
from carbon.scoring import pool_solver_reference as psr
from carbon.scoring.pool_grader import Limit

HOST = "custody2"
INPUTS = (
    "load",
    "x0",
    "x1",
)  # model input order: one fixed condition, two design variables
DESIGN = ("x0", "x1")


def _problem(bound=0.5, **kw):
    args = {
        "target_id": "t1",
        "fixed": {"load": 1.0},
        "outputs": ("f", "g"),
        "objective": "f",
        "sense": "max",
        "limits": (Limit("g", "<=", bound),),
        "u": {"f": 0.01, "g": 0.01},
        "box": ((0.0, 1.0), (0.0, 1.0)),
    }
    args.update(kw)
    return pms.proof_problem(**args)


def _derived(rows):
    # f = load * (x0 + x1), g = x0^2 + x1^2: optimum on the circle at x0 = x1 = 0.5, f = 1
    return [{"f": r[0] * (r[1] + r[2]), "g": r[1] ** 2 + r[2] ** 2} for r in rows]


def _evaluator(predict=_derived, derive=None):
    return pms.model_evaluator(
        predict, input_names=INPUTS, design_names=DESIGN, derive=derive
    )


def test_a_host_off_the_custody_list_refuses_before_any_model_call():
    calls = []

    def predict(rows):
        calls.append(rows)
        return _derived(rows)

    with pytest.raises(psr.SolverReferenceRefused, match="host_not_custody"):
        pms.model_search(_problem(), _evaluator(predict), host_class="lium")
    assert calls == []


def test_the_proof_setting_runs_200_model_calls_and_finds_the_model_optimum():
    result = pms.model_search(_problem(), _evaluator(), host_class=HOST)
    assert result.counts["model_calls"] == 200 and len(result.points) == 200
    assert result.settings == {
        "population": 10,
        "generations": 20,
        "sigma0": 0.3,
        "seed": 0,
        "start": (0.5, 0.5),
        "host_class": HOST,
    }
    assert result.pick.model_feasible
    assert result.pick.predicted["g"] <= 0.5
    assert result.pick.predicted["f"] > 1.0 - 0.02


def test_checkpoints_are_generations_5_10_20_and_never_get_worse():
    result = pms.model_search(_problem(), _evaluator(), host_class=HOST)
    gens = [c.generation for c in result.checkpoints]
    assert gens == [5, 10, 20]
    values = [c.predicted["f"] for c in result.checkpoints if c.model_feasible]
    assert values == sorted(values)
    assert result.checkpoints[-1] == result.pick
    for c in result.checkpoints:
        assert c.index < c.generation * 10  # chosen only from the calls made by then


def test_the_optimizer_is_fixed_so_only_the_model_changes_the_pick():
    a = pms.model_search(_problem(), _evaluator(), host_class=HOST)
    b = pms.model_search(_problem(), _evaluator(), host_class=HOST)
    assert [p.design for p in a.points] == [p.design for p in b.points]

    def shifted(rows):  # a different model: its optimum moves
        return [{"f": r[1] + 2 * r[2], "g": r[1] ** 2 + r[2] ** 2} for r in rows]

    c = pms.model_search(_problem(), _evaluator(shifted), host_class=HOST)
    # same seed, same start: the first generation's designs are the same for any model
    assert [p.design for p in a.points[:10]] == [p.design for p in c.points[:10]]
    assert c.pick.design != a.pick.design
    assert c.pick.design[1] > c.pick.design[0]


def test_the_model_sees_the_full_input_row_in_model_order():
    seen = []

    def predict(rows):
        seen.extend(rows)
        return _derived(rows)

    pms.model_search(
        _problem(fixed={"load": 2.0}), _evaluator(predict), host_class=HOST
    )
    assert all(len(r) == 3 and r[0] == 2.0 for r in seen)
    assert all(0.0 <= r[1] <= 1.0 and 0.0 <= r[2] <= 1.0 for r in seen)


def test_raw_predictions_go_through_derive_and_invalid_ones_are_never_picked():
    def raw(rows):
        return [[r[1], r[2]] for r in rows]

    def derive(inputs, row):
        x0, x1 = row
        if x0 > 0.6:  # the Challenge's validity gate refuses this prediction
            return None
        return {"f": inputs["load"] * (x0 + x1), "g": x0 * x0 + x1 * x1}

    result = pms.model_search(_problem(), _evaluator(raw, derive), host_class=HOST)
    refused = result.counts["by_status"].get(psr.DERIVE_REFUSED, 0)
    assert refused >= 1
    assert result.pick.model_feasible and result.pick.design[0] <= 0.6
    assert all(c.predicted is not None for c in result.checkpoints)


def test_non_finite_or_missing_predictions_are_typed_not_crashed():
    def bad(rows):
        out = _derived(rows)
        out[0] = {"f": math.nan, "g": 0.0}
        out[1] = None
        return out

    result = pms.model_search(_problem(), _evaluator(bad), host_class=HOST)
    assert result.counts["by_status"][psr.DERIVE_REFUSED] >= 2


def test_a_model_returning_the_wrong_count_refuses():
    with pytest.raises(psr.SolverReferenceRefused, match="model_returned_wrong_count"):
        pms.model_search(
            _problem(), _evaluator(lambda rows: _derived(rows)[:-1]), host_class=HOST
        )


def test_when_the_model_finds_nothing_feasible_the_pick_says_so():
    result = pms.model_search(_problem(bound=-1.0), _evaluator(), host_class=HOST)
    assert not result.pick.model_feasible
    assert not any(c.model_feasible for c in result.checkpoints)


@pytest.mark.parametrize(
    "kw, code",
    [
        ({"population": 1}, "population_and_generations_invalid"),
        ({"generations": 0}, "population_and_generations_invalid"),
        ({"sigma0": 0.0}, "sigma0_invalid"),
        ({"checkpoints": (5, 25)}, "checkpoints_must_be_generations_run"),
    ],
)
def test_settings_are_checked(kw, code):
    with pytest.raises(psr.SolverReferenceRefused, match=code):
        pms.model_search(_problem(), _evaluator(), host_class=HOST, **kw)


def test_smaller_settings_still_report_the_last_generation():
    result = pms.model_search(
        _problem(), _evaluator(), host_class=HOST, generations=4, checkpoints=(2,)
    )
    assert [c.generation for c in result.checkpoints] == [2]
    assert result.pick.generation == 4 and len(result.points) == 40


def test_the_pick_is_one_solve_job_with_the_full_row_by_name():
    problem = _problem()
    result = pms.model_search(problem, _evaluator(), host_class=HOST)
    job = pms.solve_job(
        result, problem, input_names=INPUTS, design_names=DESIGN, model_label="P"
    )
    assert job["schema"] == "carbon.model_search_pick.v1"
    assert list(job["inputs"]) == list(INPUTS)
    assert job["inputs"]["load"] == 1.0
    assert (job["inputs"]["x0"], job["inputs"]["x1"]) == result.pick.design
    assert job["model"] == "P" and job["target_id"] == "t1"
    assert job["model_feasible"] is True
    assert (
        "predicted" not in job
    )  # the solver host gets inputs, not the model's guesses
    shard = pms.solve_job(
        result,
        problem,
        input_names=INPUTS,
        design_names=DESIGN,
        model_label="F",
        job_writer=lambda rec: {"rows": [list(rec["inputs"].values())]},
    )
    assert shard == {"rows": [[1.0, *result.pick.design]]}


def test_a_job_refuses_a_row_it_cannot_complete():
    problem = _problem()
    result = pms.model_search(problem, _evaluator(), host_class=HOST)
    with pytest.raises(psr.SolverReferenceRefused, match="complete_the_row"):
        pms.solve_job(
            result,
            problem,
            input_names=(*INPUTS, "extra"),
            design_names=DESIGN,
            model_label="F",
        )
    with pytest.raises(psr.SolverReferenceRefused, match="model_label_required"):
        pms.solve_job(
            result, problem, input_names=INPUTS, design_names=DESIGN, model_label=""
        )


def test_design_names_must_be_model_inputs():
    with pytest.raises(psr.SolverReferenceRefused, match="design_names_must_be"):
        pms.model_evaluator(_derived, input_names=INPUTS, design_names=("x9",))
