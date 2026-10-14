"""PKT-19: synthetic law-gate controls, coverage and counterfactual sweeps.

Registered operators execute; no solver, hidden data, production threshold
selection, model training, deployment or scientific qualification.
"""

import copy
import json
import math

import pytest

from carbon.battery import exam
from scripts.dev import physics_law_gates as harness


@pytest.fixture(scope="module")
def result():
    return harness.report()


def test_every_control_exercises_the_actual_registered_operator(result):
    assert len(result["checks"]) == 12
    assert result["controls_passed"] and all(result["checks"].values())
    assert result["classification"] == "DOCUMENTATION_LAG"
    assert result["scope"] == "SYNTHETIC_CONTROLS_NOT_QUALIFICATION"
    assert set(result["source_sha256"]) == set(harness.SOURCES)
    for digest in result["source_sha256"].values():
        assert len(digest) == 64 and int(digest, 16) >= 0


def test_mean_gate_rejects_the_better_scoring_bad_control(result):
    control = result["burgers"]["score_cannot_compensate"]
    assert control["challenger_score"] > control["baseline_score"]
    assert control["disposition"] == "REJECTED_MANDATORY"
    assert not control["accepted_improvement"]
    judged = result["burgers"]["actual_registered_judge"]
    assert judged["exact"]["failed_mandatory"] == []
    assert any(
        x.endswith(":conserved_mean") for x in judged["mean_drift"]["failed_mandatory"]
    )
    assert any(
        x.endswith(":initial_condition")
        for x in judged["wrong_initial"]["failed_mandatory"]
    )


def test_same_mean_and_initial_condition_do_not_certify_the_dynamics(result):
    laws = result["burgers"]["laws"]
    # Frozen initial fields satisfy these two constraints, but the real
    # registered judge still catches their wrong energy trajectory.
    assert laws["conserved_mean"]["readings"]["frozen_initial"] < 1e-12
    assert laws["initial_condition"]["readings"]["frozen_initial"] == 0.0
    failed = result["burgers"]["actual_registered_judge"]["frozen_initial"][
        "failed_mandatory"
    ]
    assert any(x.endswith(":energy_path_max") for x in failed)


def test_battery_boundary_and_inventory_controls_reach_real_gates(result):
    judged = result["battery"]["actual_registered_judge"]
    assert judged["compliant_fixture"]["state"] == exam.SCORABLE
    assert (
        judged["wrong_initial_temperature"]["gates"]["initial_temperature"] == exam.FAIL
    )
    assert judged["over_inventory"]["gates"]["capacity_bound"] == exam.FAIL
    assert judged["zero_capacity"]["gates"]["capacity_bound"] == exam.FAIL
    assert judged["missing_capacity"] == {
        "state": exam.GATE_FAILED,
        "gates": {"schema_finite": exam.FAIL},
    }
    perfect = result["battery"]["perfect_error_cannot_compensate"]
    assert perfect["score"] == 0.0 and not perfect["eligible"]
    assert perfect["gate_failures"]["initial_temperature"] == 1


def test_reference_and_infrastructure_failure_keep_their_typed_meaning(result):
    failure = result["battery"]["failure_classification_controls"]
    assert failure["reference_invalid"] == {
        "state": exam.REFERENCE_INVALID,
        "gates": {},
    }
    assert failure["infra_failed"] == {"state": exam.FAILED_INFRA, "gates": {}}


def test_missing_adoption_tolerance_or_reading_cannot_pass(result):
    policy = result["new_scientific_scope"]
    assert policy["adoption"] == "HUMAN_INPUT" and not policy["admissible"]
    assert all(
        policy[key] is None
        for key in ("law", "observable", "challenge", "applicability", "tolerance")
    )
    for law in result["burgers"]["laws"].values():
        undecided = law["unconfigured"]
        assert undecided["state"] == "HUMAN_INPUT"
        assert undecided["n_checked"] == 0
        assert not undecided["counterfactual_all_pass"]
        assert undecided["unresolved"] == ["missing_observation"]
    missing = harness.hypothetical_gate({"good": 0.0, "missing": None}, threshold=1.0)
    assert missing["admitted"] == ["good"] and missing["unresolved"] == ["missing"]
    assert missing["state"] == "UNRESOLVED" and not missing["counterfactual_all_pass"]


@pytest.mark.parametrize("strict", [False, True])
def test_hypothetical_gate_has_a_positive_and_negative_control(strict):
    good = harness.hypothetical_gate({"good": 0.0}, threshold=0.1, strict=strict)
    bad = harness.hypothetical_gate({"bad": 0.2}, threshold=0.1, strict=strict)
    assert (
        good["counterfactual_all_pass"] and good["state"] == "HELD_COUNTERFACTUAL_ONLY"
    )
    assert not bad["counterfactual_all_pass"] and bad["state"] == "BREACHED"
    edge = harness.hypothetical_gate({"edge": 0.1}, threshold=0.1, strict=strict)
    assert edge["counterfactual_all_pass"] is (not strict)
    assert good["adoption"] == bad["adoption"] == "HUMAN_INPUT"


@pytest.mark.parametrize("value", [None, True, "0", float("nan"), float("inf"), -0.1])
def test_invalid_reading_is_unresolved_not_silently_excluded(value):
    verdict = harness.hypothetical_gate({"case": value}, threshold=0.1)
    assert verdict["state"] == "UNRESOLVED" and verdict["unresolved"] == ["case"]
    assert verdict["n_cases"] == 1 and verdict["n_checked"] == 0
    assert not verdict["counterfactual_all_pass"]


@pytest.mark.parametrize("value", [True, "0", float("nan"), float("inf"), -0.1])
def test_invalid_threshold_is_refused(value):
    with pytest.raises(ValueError, match="threshold"):
        harness.hypothetical_gate({"case": 0.0}, threshold=value)


def test_empty_basis_and_arithmetic_overflow_cannot_pass():
    with pytest.raises(ValueError, match="basis"):
        harness.hypothetical_gate({}, threshold=0.1)
    overflow = harness.hypothetical_gate(
        {"case": 1e308}, threshold=1e308, arithmetic_floor=1e308
    )
    assert overflow["state"] == "UNRESOLVED" and not overflow["counterfactual_all_pass"]


def test_curves_keep_every_case_and_expose_which_bad_specimen_gets_admitted(result):
    for law in result["burgers"]["laws"].values():
        limits = [row["threshold"] for row in law["curve"]]
        assert limits == sorted(set(limits))
        for row in law["curve"]:
            groups = [set(row[k]) for k in ("admitted", "excluded", "unresolved")]
            assert set.union(*groups) == set(law["readings"])
            assert sum(map(len, groups)) == row["n_cases"]
            assert row["unresolved"] == ["missing_observation"]
            assert row["adoption"] == "HUMAN_INPUT"
    boundary = result["battery"]["initial_temperature"]["curve"]
    assert any("wrong_initial_temperature" in row["excluded"] for row in boundary)
    assert any("wrong_initial_temperature" in row["admitted"] for row in boundary)
    for row in boundary:
        expected = row["actual_initial_temperature_verdicts"]
        assert row["admitted"] == sorted(
            k for k, v in expected.items() if v == exam.PASS
        )
        assert row["excluded"] == sorted(
            k for k, v in expected.items() if v == exam.FAIL
        )
        assert row["unresolved"] == sorted(
            k for k, v in expected.items() if v == "UNRESOLVED"
        )
    inventory = result["battery"]["capacity_inventory_bound"]["curve"]
    assert any("over_inventory" in row["excluded"] for row in inventory)
    assert any("over_inventory" in row["admitted"] for row in inventory)
    assert all(
        "zero_capacity" in row["excluded"] and "missing_capacity" in row["unresolved"]
        for row in inventory
    )


def test_making_the_battery_checker_always_pass_breaks_the_controls(monkeypatch):
    monkeypatch.setattr(
        exam,
        "evaluate_case",
        lambda *a, **k: {
            "state": exam.SCORABLE,
            "gates": {g.gate_id: exam.PASS for g in exam.GATES},
        },
    )
    observed = harness.report()
    assert not observed["checks"]["battery_initial_condition_caught"]
    assert not observed["checks"]["battery_inventory_control_caught"]
    assert not observed["checks"]["battery_perfect_error_cannot_compensate"]
    assert not observed["controls_passed"]


def test_reporting_no_burgers_gate_failure_breaks_the_controls(monkeypatch):
    original = harness.scoring.summarize

    def ignored_law(rows):
        out = original(rows)
        out["failed_mandatory"] = []
        return out

    monkeypatch.setattr(harness.scoring, "summarize", ignored_law)
    observed = harness.report()
    assert not observed["checks"]["burgers_mean_drift_caught"]
    assert not observed["checks"]["burgers_initial_condition_caught"]
    assert not observed["controls_passed"]


def test_generated_artifact_and_cli_check_use_current_operator_bytes(tmp_path):
    destination = tmp_path / "curves.json"
    harness.main(["--output", str(destination)])
    expected = harness.encoded_report()
    assert destination.read_bytes() == expected
    assert json.loads(expected)["controls_passed"]
    harness.main(["--check", str(destination)])
    changed = json.loads(expected)
    changed["checks"]["burgers_mean_drift_caught"] = False
    destination.write_text(json.dumps(changed), encoding="utf-8", newline="\n")
    with pytest.raises(SystemExit, match="differ"):
        harness.main(["--check", str(destination)])


def test_committed_synthetic_curves_match_current_sources():
    harness.main(
        [
            "--check",
            str(
                harness.ROOT
                / "docs/development/physics-law-gates/synthetic-curves.json"
            ),
        ]
    )


def test_harness_never_mutates_registered_rules_or_contracts(result):
    before = copy.deepcopy(harness.scoring.RULE)
    harness.report()
    assert before == harness.scoring.RULE
    contract = json.loads(
        (harness.ROOT / "carbon/battery/physics_contract.v2.json").read_text(
            encoding="utf-8"
        )
    )
    laws = {law["id"]: law for law in contract["laws"]}
    assert laws["B15"]["adoption"] == "ADOPTED"
    assert laws["B16"]["role"] == "MODEL_CARD_METRIC_ONLY"
    assert laws["B9"]["role"] == "DIAGNOSTIC_ONLY"
    assert laws["B8"].get("adoption") != "ADOPTED"
    assert all(
        math.isfinite(x)
        for law in result["burgers"]["laws"].values()
        for row in law["curve"]
        for x in [row["threshold"]]
    )
