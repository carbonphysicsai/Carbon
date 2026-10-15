"""Synthetic construction/measurement receipts only; never train or solve."""

import copy
import json

import pytest

from carbon.development_comparison import l5_candidate_arms as arms


@pytest.fixture
def inputs():
    return arms.standin()


def reseal(value, field="receipt_digest"):
    value.pop(field, None)
    value.update(arms.seal(value, field))


def run(inputs):
    plan, receipts = inputs
    return arms.compare(arms.PairPlan.from_document(plan), receipts)


def test_actual_standin_is_paired_null_on_target_and_all_four_neighbours(inputs):
    report = run(inputs)
    assert report["status"] == "SYNTHETIC_FIXTURE_RESULT"
    assert len(report["budget_records"]) == 10
    assert set(report["effects"]) == {
        "target:target",
        *[
            f"near_variant:{x}"
            for x in ("objective", "constraint", "operating", "boundary")
        ],
    }
    for metrics in report["effects"].values():
        effect = metrics["decision_loss"]
        assert effect["result"] == "NO_OBSERVED_DIFFERENCE"
        assert effect["interval"] == [0, 0]
        assert effect["measured_pairs"] == effect["expected_pairs"] == 30
        assert effect["equivalence"] is None
    assert report["accepted_improvement"] is None
    assert report["adoption"] == report["thresholds"] == "HUMAN_INPUT"
    assert not any(report["eligibility"].values())
    assert "partly-broken hunt" in report["hunt_recovery_caveat"]


def test_raw_plan_cannot_enter_comparison_and_encoded_plan_cannot_be_mutated(inputs):
    plan, receipts = inputs
    with pytest.raises(arms.ComparisonRefused, match="validated PairPlan"):
        arms.compare(plan, receipts)
    validated = arms.PairPlan.from_document(plan)
    plan["common"]["steps"] = 100
    assert validated.document()["common"]["steps"] == 4
    assert arms.compare(validated, receipts)["status"] == "SYNTHETIC_FIXTURE_RESULT"


@pytest.mark.parametrize(
    "key,value",
    [
        ("width", 99),
        ("depth", 2),
        ("steps", 5),
        ("data_digest", "sha256:" + "f" * 64),
        ("seeds", [12]),
        ("route", "another-host"),
    ],
)
def test_unequal_construction_refuses_after_digest_rebound(inputs, key, value):
    plan, _ = inputs
    plan["arms"]["candidate"]["configuration"] = copy.deepcopy(plan["common"])
    plan["arms"]["candidate"]["configuration"][key] = value
    reseal(plan, "plan_digest")
    with pytest.raises(arms.ComparisonRefused, match="unequal"):
        arms.PairPlan.from_document(plan)


@pytest.mark.parametrize(
    "counter",
    [
        "updates",
        "objective_evaluations",
        "gradient_evaluations",
        "tokens",
        "wall_s",
        "core_s",
    ],
)
def test_extra_actual_cost_is_not_hidden_by_equal_declared_limits(inputs, counter):
    plan, receipts = inputs
    record = receipts[-1]
    record["events"][0][counter] = plan["common"]["budget"][counter] + 1
    record["totals"][counter] = record["events"][0][counter]
    reseal(record)
    with pytest.raises(arms.ComparisonRefused, match="budget exceeded"):
        run(inputs)


def test_omitted_counter_and_false_total_refuse(inputs):
    record = inputs[1][-1]
    record["events"][0].pop("gradient_evaluations")
    reseal(record)
    with pytest.raises(arms.ComparisonRefused, match="closed schema"):
        run(inputs)


def test_reported_total_cannot_hide_line_search_work(inputs):
    record = inputs[1][-1]
    extra = {
        **record["events"][0],
        "id": "line-1",
        "phase": "line_search",
        "updates": 0,
        "objective_evaluations": 2,
        "gradient_evaluations": 2,
        "line_search_trials": 2,
    }
    record["events"].append(extra)
    reseal(record)
    with pytest.raises(arms.ComparisonRefused, match="do not reconcile"):
        run(inputs)
    record["totals"]["objective_evaluations"] += 2
    record["totals"]["gradient_evaluations"] += 2
    reseal(record)
    report = run(inputs)
    assert (
        report["budget_records"]["candidate:4"]["actual"]["gradient_evaluations"] == 6
    )


def test_quasi_newton_requires_both_arms_actual_line_search(inputs):
    plan, receipts = inputs
    plan["candidate_id"] = "QUASI_NEWTON"
    descriptor = plan["arms"]["candidate"]
    descriptor["construction"]["feature"]["candidate_id"] = "QUASI_NEWTON"
    descriptor["construction_digest"] = arms.digest(
        {
            "implementation_ref": descriptor["implementation_ref"],
            "construction": descriptor["construction"],
        }
    )
    reseal(plan, "plan_digest")
    for record in receipts:
        record["plan_digest"] = plan["plan_digest"]
        record["construction_digest"] = plan["arms"][record["arm"]][
            "construction_digest"
        ]
        reseal(record)
    with pytest.raises(arms.ComparisonRefused, match="line-search metering"):
        run(inputs)
    for record in receipts:
        record["events"].append(
            {
                **record["events"][0],
                "id": "line-1",
                "phase": "line_search",
                "updates": 0,
                "objective_evaluations": 2,
                "gradient_evaluations": 2,
                "line_search_trials": 2,
            }
        )
        record["totals"]["objective_evaluations"] += 2
        record["totals"]["gradient_evaluations"] += 2
        reseal(record)
    assert run(inputs)["candidate_id"] == "QUASI_NEWTON"
    record = receipts[-1]
    record["events"][-1]["gradient_evaluations"] = 1
    record["totals"]["gradient_evaluations"] -= 1
    reseal(record)
    with pytest.raises(arms.ComparisonRefused, match="objective AND gradient"):
        run(inputs)


@pytest.mark.parametrize(
    "change", ["missing", "duplicate", "reference", "construction", "digest"]
)
def test_pair_and_source_identity_controls(inputs, change):
    plan, receipts = inputs
    if change == "missing":
        receipts.pop()
    elif change == "duplicate":
        receipts.append(copy.deepcopy(receipts[-1]))
    elif change == "reference":
        next(iter(receipts[-1]["measurements"].values()))["reference_digest"] = (
            "sha256:" + "e" * 64
        )
        reseal(receipts[-1])
    elif change == "construction":
        receipts[-1]["construction_digest"] = plan["arms"]["baseline"][
            "construction_digest"
        ]
        reseal(receipts[-1])
    else:
        receipts[-1]["events"][0]["updates"] = 3
    with pytest.raises(arms.ComparisonRefused):
        run(inputs)


def test_missing_reference_never_becomes_a_conditional_positive(inputs):
    plan, receipts = inputs
    record = receipts[-1]
    target = next(q for q, s in plan["scenarios"].items() if s["kind"] == "target")
    record["measurements"][target]["status"] = "UNRESOLVED"
    record["measurements"][target]["values"]["decision_loss"] = None
    reseal(record)
    effect = run(inputs)["effects"]["target:target"]["decision_loss"]
    assert effect["result"] == "UNRESOLVED_INCOMPLETE_PAIRS"
    assert effect["measured_pairs"] == effect["expected_pairs"] - 1
    assert effect["point_improvement"] is effect["interval"] is None


def test_infrastructure_failure_preserves_nulls(inputs):
    record = inputs[1][-1]
    record["completion"] = "FAILED_INFRA"
    for item in record["measurements"].values():
        item["status"] = "FAILED_INFRA"
        item["values"]["decision_loss"] = None
    reseal(record)
    report = run(inputs)
    assert all(
        x["decision_loss"]["result"] == "UNRESOLVED_INCOMPLETE_PAIRS"
        for x in report["effects"].values()
    )


def test_infra_before_model_creation_keeps_null_identity_without_fabrication(inputs):
    record = inputs[1][-1]
    record["completion"] = "FAILED_INFRA"
    record["model_digest"] = None
    record["events"] = [
        {
            "id": "setup-failed",
            "phase": "setup",
            "updates": 0,
            "objective_evaluations": 0,
            "gradient_evaluations": 0,
            "line_search_trials": 0,
            "tokens": 0,
            "wall_s": 0.02,
            "core_s": 0.01,
        }
    ]
    record["totals"] = {
        key: record["events"][0][key] for key in (*arms.COUNTERS, "wall_s", "core_s")
    }
    for item in record["measurements"].values():
        item["status"] = "FAILED_INFRA"
        item["values"]["decision_loss"] = None
    reseal(record)
    report = run(inputs)
    assert report["model_artifacts"]["candidate:4"] is None
    assert report["budget_records"]["candidate:4"]["actual"]["updates"] == 0
    assert all(
        metrics["decision_loss"]["point_improvement"] is None
        for metrics in report["effects"].values()
    )
    record["model_digest"] = "invalid-existing-digest"
    reseal(record)
    with pytest.raises(arms.ComparisonRefused, match="model artifact"):
        run(inputs)


def test_target_gain_cannot_erase_neighbour_harm_or_adopt(inputs):
    plan, receipts = inputs
    for record in receipts:
        if record["arm"] == "candidate":
            for qid, item in record["measurements"].items():
                item["values"]["decision_loss"] += (
                    -1 if plan["scenarios"][qid]["kind"] == "target" else 1
                )
            reseal(record)
    report = run(inputs)
    assert (
        report["effects"]["target:target"]["decision_loss"]["result"]
        == "POSITIVE_DIRECTION"
    )
    assert all(
        metrics["decision_loss"]["result"] == "NEGATIVE_DIRECTION"
        for key, metrics in report["effects"].items()
        if key.startswith("near_variant:")
    )
    assert report["target_only_is_a_win"] is False
    assert report["accepted_improvement"] is None


def test_mixed_deltas_with_zero_mean_are_unresolved_not_equivalence(inputs):
    plan, receipts = inputs
    target = [q for q, s in plan["scenarios"].items() if s["kind"] == "target"]
    for record in receipts:
        if record["arm"] == "candidate":
            for i, qid in enumerate(target):
                record["measurements"][qid]["values"]["decision_loss"] += (
                    1 if i % 2 else -1
                )
            reseal(record)
    effect = run(inputs)["effects"]["target:target"]["decision_loss"]
    assert effect["point_improvement"] == pytest.approx(0)
    assert effect["interval"][0] < 0 < effect["interval"][1]
    assert effect["result"] == "UNRESOLVED"


def test_zero_fixture_cannot_be_relabelled_public_measured_execution(inputs):
    plan, receipts = inputs
    plan["evidence_basis"] = "PUBLIC_DEVELOPMENT"
    reseal(plan, "plan_digest")
    for record in receipts:
        record["evidence_basis"] = "PUBLIC_DEVELOPMENT"
        record["plan_digest"] = plan["plan_digest"]
        reseal(record)
    with pytest.raises(arms.ComparisonRefused, match="zero-cost fixture"):
        run(inputs)


def test_fixture_has_no_measured_cpu_charge_and_public_costs_are_retained(inputs):
    report = run(inputs)
    for budget in report["budget_records"].values():
        assert budget["core_cost"]["status"] == "SYNTHETIC_ASSUMPTION"
        assert budget["core_cost_ledger"] == []
    plan, receipts = inputs
    plan["evidence_basis"] = "PUBLIC_DEVELOPMENT"
    reseal(plan, "plan_digest")
    for record in receipts:
        record["evidence_basis"] = "PUBLIC_DEVELOPMENT"
        record["plan_digest"] = plan["plan_digest"]
        for event in record["events"]:
            event["wall_s"] = event["core_s"] = 0.1
        record["totals"]["wall_s"] = record["totals"]["core_s"] = sum(
            event["core_s"] for event in record["events"]
        )
        reseal(record)
    budget = run(inputs)["budget_records"]["candidate:4"]
    assert budget["metering_authority"] == "HOST_DECLARED_NOT_AUTHENTICATED"
    assert budget["core_cost"]["value"] == pytest.approx(0.3)
    assert {row["category"] for row in budget["core_cost_ledger"]} == {
        "fitting",
        "inference",
        "verification",
    }
    assert (
        next(
            row
            for row in budget["core_cost_ledger"]
            if row["category"] == "verification"
        )["arm"]
        == "VERIFICATION"
    )


def test_finite_values_cannot_overflow_into_positive_effect(inputs):
    _, receipts = inputs
    for record in receipts:
        for item in record["measurements"].values():
            item["values"]["decision_loss"] = (
                1e308 if record["arm"] == "baseline" else -1e308
            )
        reseal(record)
    with pytest.raises(arms.ComparisonRefused, match="overflow"):
        run(inputs)


def test_update_count_cannot_be_disguised_as_prediction_and_tiny_bootstrap_refuses(
    inputs,
):
    plan, receipts = inputs
    record = receipts[-1]
    record["events"][1]["updates"] = 4
    record["events"][0]["updates"] = 0
    reseal(record)
    with pytest.raises(arms.ComparisonRefused, match="construction phase"):
        run(inputs)
    plan["bootstrap"]["replicates"] = 1
    reseal(plan, "plan_digest")
    with pytest.raises(arms.ComparisonRefused, match="100 bootstrap"):
        arms.PairPlan.from_document(plan)


def test_full_recipe_difference_cannot_hide_behind_same_width_and_steps(inputs):
    plan, _ = inputs
    arm = plan["arms"]["candidate"]
    arm["construction"] = copy.deepcopy(arm["construction"])
    arm["construction"]["base_recipe"]["settings"]["learning_rate"] = 100
    arm["construction_digest"] = arms.digest(
        {
            "implementation_ref": arm["implementation_ref"],
            "construction": arm["construction"],
        }
    )
    reseal(plan, "plan_digest")
    with pytest.raises(arms.ComparisonRefused, match="full base recipe differs"):
        arms.PairPlan.from_document(plan)


def test_full_descriptor_identity_must_bind_implementation(inputs):
    plan, _ = inputs
    plan["arms"]["candidate"]["implementation_ref"] = "another-constructor"
    reseal(plan, "plan_digest")
    with pytest.raises(arms.ComparisonRefused, match="descriptor digest"):
        arms.PairPlan.from_document(plan)


def test_measured_model_identity_cannot_be_omitted(inputs):
    receipts = inputs[1]
    receipts[-1]["model_digest"] = None
    reseal(receipts[-1])
    with pytest.raises(arms.ComparisonRefused, match="model artifact"):
        run(inputs)


def test_duplicate_json_refuses_and_cli_reports_fixture_caveat(inputs, tmp_path):
    with pytest.raises(arms.ComparisonRefused, match="duplicate JSON"):
        arms._json('{"version":1,"version":2}')
    output = tmp_path / "pack.json"
    assert arms.main(["--standin", "--out", str(output)]) == 0
    pack = json.loads(output.read_text(encoding="utf-8"))
    assert pack["report_digest"] == arms.digest(pack["report"])
    assert pack["report"]["status"] == "SYNTHETIC_FIXTURE_RESULT"
    assert "partly-broken hunt" in pack["report"]["hunt_recovery_caveat"]
