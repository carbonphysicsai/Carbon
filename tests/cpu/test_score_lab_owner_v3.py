"""Synthetic two-action banks only; no battery measurements or model fitting."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from carbon.design_search import indexed, tasks
from scripts.dev.score_lab import owner_v3 as owner


def fixture(*, weights=None, deltas=(0.6, 0.4, 0.4, 0.4, 0.4), bad=None):
    indices, refs, intervals = [], [], []
    for band, weight, delta in zip(owner.BANDS, weights or [0.2] * 5, deltas):
        task = tasks.task(
            f"toy-{band}",
            identity={
                "challenge": "toy-only",
                "contract_version": owner.JOB,
                "action_grammar": {
                    "schema": tasks.GRAMMAR_SCHEMA,
                    "version": "toy-not-battery",
                    "variables": [
                        {"name": "choice", "type": "enum", "values": ["a", "b"]}
                    ],
                    "rules": [],
                },
                "optimizer": {"class": "exhaustive", "version": "v1"},
                "query_budget": 2,
                "seed": 0,
                "observer_version": "toy-observer",
                "reference_bank": "toy-only",
            },
            conditions=[{"id": "toy", "stratum": "toy"}],
            strata={"toy": {"p": 1, "q": 1, "w": 1}},
            candidates=["a", "b"],
            actions={"a": {"choice": "a"}, "b": {"choice": "b"}},
            objective={
                "quantity": "minutes",
                "unit": "min",
                "sense": "min",
                "aggregate": "worst",
            },
            limits=[{"quantity": "toy-margin", "unit": "toy", "op": ">=", "value": 0}],
        )
        indices.append({"index_value": band, "buyer_weight": weight, "task": task})
        values = {
            ("a", "toy"): {
                "minutes": 10 + delta,
                "toy-margin": -1 if band == bad else 1,
            },
            ("b", "toy"): {"minutes": 10, "toy-margin": 1},
        }
        refs.append({"index_value": band, "values": values})
        intervals.append(
            {
                "index_value": band,
                "candidates": {
                    c: [v["minutes"], v["minutes"]] for (c, _), v in values.items()
                },
            }
        )
    registered = indexed.indexed_task(
        "toy-map",
        index_axis="ambient_c",
        indices=indices,
        query_budget=10,
        value_equivalence={
            "quantity": "minutes",
            "unit": "min",
            "tolerance": 0.5,
            "rule": indexed.EQUIVALENCE_RULE,
        },
    )
    commitment = tasks.run_indexed_optimizer(
        registered,
        lambda _index, action, _cond: {
            "minutes": 1 if action["choice"] == "a" else 2,
            "toy-margin": 1,
        },
        model_id="toy-model",
    )["commitment"]
    return registered, commitment, refs, intervals


def judge(data):
    return owner.judge(*data, scope="SYNTHETIC_FIXTURE")


def test_deadzone_before_weighting_preserves_old_result_and_authentic_band_terms():
    data = fixture()
    original = tasks.judge_indexed(*data[:3])
    before = copy.deepcopy(original)
    result = judge(data)
    assert original["regret"] == 0
    assert result["regret_min"] == pytest.approx(0.12)
    assert result["per_index"][0]["weighted_regret_min"] == pytest.approx(0.12)
    assert [r["weighted_regret_min"] for r in result["per_index"]][1:] == [0] * 4
    assert result["historical_aggregate_regret_unchanged"] == 0
    assert tasks.judge_indexed(*data[:3]) == before
    assert judge(data) == result


def test_equivalence_is_full_delta_not_delta_minus_tolerance():
    result = judge(fixture(deltas=(0.5, 0.6, 0, 0.5, 0.6)))
    assert result["regret_min"] == pytest.approx(0.24)


def test_zero_weight_band_is_mandatory_and_unsafe_loss_never_zero():
    result = judge(fixture(weights=[0.25, 0.25, 0.25, 0.25, 0], bad=40))
    assert result["reference_mask"]["included"]
    assert result["kind"] == "SELECTED_INFEASIBLE"
    assert result["regret_min"] is None
    assert result["regret_ranking_eligible"] is False


def test_missing_unused_reference_excludes_question_independent_of_predictions():
    task, commitment, refs, intervals = fixture()
    del refs[4]["values"][("b", "toy")]
    expected = owner.reference_mask(task, refs, intervals)
    assert expected["included"] is False
    assert [40, "b", "UNRESOLVED_REFERENCE"] in expected["reasons"]
    outcome = judge((task, commitment, refs, intervals))
    assert outcome["reference_mask"] == expected
    assert outcome["kind"] == "REFERENCE_UNRESOLVED"
    assert outcome["regret_min"] is None


def test_deadzone_interval_discontinuity_not_small_objective_error():
    task, commitment, refs, intervals = fixture(deltas=(0.5,) * 5)
    intervals[0]["candidates"]["a"] = [10.49, 10.51]
    result = judge((task, commitment, refs, intervals))
    assert [5, "a", "DEADZONE_INTERVAL_AMBIGUOUS"] in result["reference_mask"][
        "reasons"
    ]
    assert result["regret_min"] is None


def test_possible_winner_change_is_reference_only_exclusion():
    task, commitment, refs, intervals = fixture(deltas=(0.4,) * 5)
    intervals[0]["candidates"]["b"] = [9.5, 10.5]
    mask = owner.reference_mask(task, refs, intervals)
    assert [5, "a", "WINNER_INTERVAL_AMBIGUOUS"] in mask["reasons"]
    assert not mask["included"]


def test_bad_enclosure_cannot_certify_point_or_extra_candidate():
    task, _, refs, intervals = fixture()
    intervals[0]["candidates"]["a"] = [11, 12]
    with pytest.raises(tasks.TaskError, match="outside"):
        owner.reference_mask(task, refs, intervals)
    intervals[0]["candidates"]["a"] = [10, float("nan")]
    with pytest.raises(tasks.TaskError, match="finite"):
        owner.reference_mask(task, refs, intervals)


def test_absent_enclosure_is_unresolved_not_point_truth():
    task, _, refs, intervals = fixture()
    del intervals[0]["candidates"]["a"]
    assert not owner.reference_mask(task, refs, intervals)["included"]


def test_missing_band_order_or_foreign_commitment_refused():
    task, commitment, refs, intervals = fixture()
    with pytest.raises(tasks.TaskError, match="band order"):
        owner.reference_mask(task, refs[::-1], intervals)
    commitment["model_id"] = "altered"
    with pytest.raises(tasks.TaskError, match="commitment"):
        judge((task, commitment, refs, intervals))


def test_unsafe_and_missed_questions_cannot_disappear_from_regret_mean():
    safe = judge(fixture())
    unsafe = judge(fixture(bad=40))
    # Real offered questions have distinct task identities.
    unsafe["task_digest"] = "toy-second-question"
    result = owner.model_summary([safe, unsafe])
    assert result["offered_questions"] == 2
    assert result["infeasible_pick_count"] == 1
    assert result["mean_regret_min"] is None
    assert not result["regret_ranking_eligible"]
    assert owner.model_summary([])["mean_regret_min"] is None
    with pytest.raises(tasks.TaskError, match="duplicate"):
        owner.model_summary([safe, safe])


def test_scope_cannot_be_live():
    with pytest.raises(tasks.TaskError, match="development"):
        owner.judge(*fixture(), scope="LIVE")


def test_bad_reference_quantity_is_typed_reference_failure_not_candidate_loss():
    task, commitment, refs, intervals = fixture()
    refs[0]["values"][("b", "toy")]["minutes"] = None
    result = judge((task, commitment, refs, intervals))
    assert result["kind"] == "REFERENCE_UNRESOLVED"
    assert result["regret_min"] is None
    assert [5, "b", "MISSING_OR_INVALID_REFERENCE_ROW"] in result["reference_mask"][
        "reasons"
    ]


def test_none_mass_retained_without_poisoning_fixed_feasible_stratum_mean():
    safe = judge(fixture())
    task, _, refs, intervals = fixture()
    for panel in refs:
        for values in panel["values"].values():
            values["toy-margin"] = -1
    declined = tasks.run_indexed_optimizer(
        task, lambda *_args: {"minutes": 1, "toy-margin": -1}, model_id="toy-decline"
    )["commitment"]
    none = judge((task, declined, refs, intervals))
    assert none["kind"] == "CORRECT_ABSTENTION"
    none["task_digest"] = "toy-none-question"
    result = owner.model_summary([safe, none])
    assert result["offered_questions"] == 2
    assert result["reference_FEASIBLE_EXISTS_questions"] == 1
    assert result["correct_abstention_count"] == 1
    assert result["mean_regret_min"] == pytest.approx(0.12)
    assert owner.model_summary([none])["mean_regret_min"] is None
    assert result["full_population_scalar_available"] is False


def test_model_errors_never_earn_correct_none_abstention():
    task, _, refs, intervals = fixture()
    for panel in refs:
        for values in panel["values"].values():
            values["toy-margin"] = -1
    failed = tasks.run_indexed_optimizer(
        task, lambda *_args: None, model_id="toy-failed"
    )["commitment"]
    assert failed["execution"]["model_failures"] > 0
    result = judge((task, failed, refs, intervals))
    assert result["kind"] == "CANDIDATE_UNAVAILABLE"
    assert owner.model_summary([result])["correct_abstention_count"] == 0


def test_registered_cohort_uses_existing_kit_with_distinct_recipe_seed_identities():
    root = Path(__file__).resolve().parents[2]
    directory = root / "Business/research/score-lab-campaign-01/acquisition-v1"
    cohort = json.loads((directory / "cohort.json").read_text(encoding="utf-8"))
    plan = json.loads((directory / "acquisition.json").read_text(encoding="utf-8"))
    models = [
        owner.cohort_member(
            cohort, expected_digest=plan["cohort_digest"], recipe_id=r["id"], seed=s
        )
        for r in cohort["recipes"]
        for s in cohort["seeds"]
    ]
    assert len({m["kit"].model_id for m in models}) == 18
    assert len({m["code"]["recipe_settings_digest"] for m in models}) == 6
    assert all(m["kit"].family == "battery-v3" for m in models)
    assert all(
        m["kit"].names == ("c1", "c2", "switch_v", "cooling", "ambient_c", "soc0")
        for m in models
    )
    with pytest.raises(tasks.TaskError, match="seed"):
        owner.cohort_member(
            cohort, expected_digest=plan["cohort_digest"], recipe_id="default", seed=999
        )
    cohort["recipes"][0]["overrides"]["width"] = 7
    with pytest.raises(tasks.TaskError, match="registered cohort"):
        owner.cohort_member(
            cohort, expected_digest=plan["cohort_digest"], recipe_id="default", seed=11
        )


def test_registered_worker_inputs_are_finite_disjoint_and_have_authentic_rungs():
    root = Path(__file__).resolve().parents[2]
    plan = json.loads(
        (
            root
            / "Business/research/score-lab-campaign-01/acquisition-v1/acquisition.json"
        ).read_text(encoding="utf-8")
    )
    digest = tasks.digest(plan)
    stages = [
        owner.acquisition_inputs(plan, expected_digest=digest, stage=s)
        for s in ("calibration-pilot", "calibration-rest", "evaluation", "refinement")
    ]
    assert [len(s["jobs"]) for s in stages] == [18, 27, 120, 60]
    ids = [j["case_id"] for s in stages for j in s["jobs"]]
    assert len(ids) == len(set(ids)) == 225
    assert {j["switch_voltage_v"] for j in stages[2]["jobs"]} == {4, 4.05, 4.1, 4.15}
    assert all(
        j["soc0"] == 0.1 and j["c2"] <= j["c1"] for s in stages for j in s["jobs"]
    )
    assert all(j["refined"] is (j["rung"] != 1) for s in stages for j in s["jobs"])
    with pytest.raises(tasks.TaskError, match="registered acquisition"):
        owner.acquisition_inputs(
            plan, expected_digest="sha256:wrong", stage="evaluation"
        )
