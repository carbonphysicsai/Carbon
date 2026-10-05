from __future__ import annotations

import copy
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from carbon.design_search import reference_comparison
from carbon.motor import decision_study, reference_campaign
from scripts.dev.motor.reference import run_batch

REPOSITORY = Path(__file__).resolve().parents[2]
CONFIG = (
    REPOSITORY / "docs" / "development" / "studies" / "MOTOR_SYNTHETIC_DECISION_V1.json"
)
FIXTURE = (
    REPOSITORY
    / "docs"
    / "development"
    / "evidence"
    / "motor-decision-construction-fixture-v1"
)
#: V2 changes only the study identity; it exists because V1's importer refused
#: successful runs with empty solver logs (OWNER-MOTOR-COUNTED-ADOPT-01). V1 and
#: its fixture remain the historical record.
CONFIG_V2 = (
    REPOSITORY / "docs" / "development" / "studies" / "MOTOR_SYNTHETIC_DECISION_V2.json"
)
FIXTURE_V2 = (
    REPOSITORY
    / "docs"
    / "development"
    / "evidence"
    / "motor-decision-construction-fixture-v2"
)


def test_the_motor_study_is_exactly_the_owner_supplied_scenario():
    config = decision_study.load_config(CONFIG, repository=REPOSITORY)
    assert config["scenario"] == {
        "requirement_ref": "OWNER_GRAPHITE_TEST_WAVE_01_SECTION_6",
        "min_mean_torque_nm": 4.0,
        "max_ripple_fraction": 0.30,
        "approval_status": (
            "APPROVED_SYNTHETIC_DEVELOPMENT_ASSUMPTIONS_" "OWNER_GRAPHITE_TEST_WAVE_01"
        ),
        "operating_control": (
            "A fixed geometry is evaluated at six commanded peak-current-density "
            "and current-angle pairs. The command is assumed settled before each "
            "magnetostatic sweep; controller dynamics, voltage limits, speed, "
            "thermal limits and inverter feasibility are outside this study."
        ),
    }
    assert [row["values"] for row in config["conditions"]] == [
        {"current_density_a_mm2": 8.0, "current_angle_deg": 0.0},
        {"current_density_a_mm2": 10.0, "current_angle_deg": 0.0},
        {"current_density_a_mm2": 12.0, "current_angle_deg": 0.0},
        {"current_density_a_mm2": 10.0, "current_angle_deg": 15.0},
        {"current_density_a_mm2": 15.0, "current_angle_deg": 0.0},
        {"current_density_a_mm2": 12.0, "current_angle_deg": 30.0},
    ]


def test_committed_fixture_matches_current_freeze_and_stays_non_counted():
    config = decision_study.load_config(CONFIG_V2, repository=REPOSITORY)
    freeze, construction, _reconstruction, restored = decision_study.load_construction(
        config,
        repository=REPOSITORY,
        directory=FIXTURE_V2 / "construction",
    )
    result = json.loads(
        (FIXTURE_V2 / "evaluation" / "result.json").read_text(encoding="utf-8")
    )
    assert freeze == decision_study.build_freeze(config, repository=REPOSITORY)
    assert len(restored) == 4
    assert result["freeze_digest"] == freeze["freeze_digest"]
    assert (
        result["construction_identity_digest"]
        == construction["construction_identity_digest"]
    )
    assert result["evidence_class"] == "ANALYTICAL_FIXTURE"
    assert result["cost"]["reference_executions"] == 0


@pytest.mark.parametrize(
    "mutate",
    [
        lambda config: config["scenario"].update(max_ripple_fraction=0.35),
        lambda config: config["conditions"][5]["values"].update(current_angle_deg=60.0),
        lambda config: config["designs"][0]["values"].update(magnet_mm=2.1),
    ],
)
def test_owner_scenario_and_preregistered_design_rule_fail_closed(tmp_path, mutate):
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    changed = copy.deepcopy(config)
    mutate(changed)
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(decision_study.StudyError):
        decision_study.load_config(path, repository=REPOSITORY)


def test_construction_commits_every_arm_before_any_reference_surface(tmp_path):
    config = decision_study.load_config(CONFIG, repository=REPOSITORY)
    result = decision_study.construct(
        config, repository=REPOSITORY, output=tmp_path / "construction"
    )
    assert result["state"] == "ALL_PROPOSALS_COMMITTED_NO_REFERENCE_ACCESSED"
    assert len(result["arms"]) == 4
    assert {row["arm_id"] for row in result["arms"]} == {
        "analytic-v1:fixed_grid",
        "analytic-v1:screen_then_confirm",
        "learned-krr-v1:fixed_grid",
        "learned-krr-v1:screen_then_confirm",
    }
    for arm in result["arms"]:
        assert arm["commitment"]["status"] in {"PROPOSAL", "ABSTAIN"}
        path = tmp_path / "construction" / arm["commitment"]["relative_path"]
        committed = json.loads(path.read_text(encoding="utf-8"))
        assert committed["commitment_digest"] == arm["commitment"]["commitment_digest"]
    # Evaluation can restore the exact bytes but cannot regenerate a proposal.
    decision_study.load_construction(
        config,
        repository=REPOSITORY,
        directory=tmp_path / "construction",
    )


def test_reference_plan_requires_pin_and_binds_exact_construction(tmp_path):
    config = decision_study.load_config(CONFIG, repository=REPOSITORY)
    construction = decision_study.construct(
        config, repository=REPOSITORY, output=tmp_path / "construction"
    )
    with pytest.raises(decision_study.StudyError, match="pinned_solver_image"):
        decision_study.reference_plan(
            config,
            construction["construction_identity_digest"],
            solver_image="carbon-motor-reference:dev",
        )
    image = "registry.example/motor@sha256:" + "a" * 64
    plan = decision_study.reference_plan(
        config,
        construction["construction_identity_digest"],
        solver_image=image,
    )
    assert len(plan["cases"]) == 48
    assert plan["solver_image"] == image
    assert plan["campaign"]["resource_policy"] == {
        "cpus_per_execution": 2,
        "parallel_executions": 6,
        "timeout_seconds_per_execution": 3600,
        "artifact_retention": "all",
    }
    assert plan["campaign"]["total_execution_limit"] == 60


def test_plan_cannot_be_generated_until_every_commitment_is_present(tmp_path):
    config = decision_study.load_config(CONFIG, repository=REPOSITORY)
    construction_dir = tmp_path / "construction"
    construction = decision_study.construct(
        config, repository=REPOSITORY, output=construction_dir
    )
    missing = construction_dir / construction["arms"][-1]["commitment"]["relative_path"]
    missing.unlink()
    with pytest.raises(
        decision_study.StudyError, match="complete_construction_artifact_required"
    ):
        decision_study.load_construction(
            config, repository=REPOSITORY, directory=construction_dir
        )


def test_registered_native_rejection_precedes_reservation_artifacts_and_processes(
    tmp_path, monkeypatch, capsys
):
    config = decision_study.load_config(CONFIG, repository=REPOSITORY)
    plan = decision_study.reference_plan(
        config,
        "sha256:" + "b" * 64,
        solver_image="registry.example/motor@sha256:" + "c" * 64,
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    calls = []

    def unexpected(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("native rejection must precede side effects")

    monkeypatch.setattr(run_batch, "NATIVE", None)
    monkeypatch.setattr(reference_campaign, "CampaignLedger", unexpected)
    monkeypatch.setattr(run_batch, "run_case", unexpected)
    monkeypatch.setattr(run_batch.subprocess, "run", unexpected)
    monkeypatch.setattr(run_batch.subprocess, "Popen", unexpected)
    output = tmp_path / "output"
    ledger = tmp_path / "campaign.sqlite3"
    with pytest.raises(SystemExit, match="2"):
        run_batch.main(
            [
                str(plan_path),
                "--out",
                str(output),
                "--campaign-ledger",
                str(ledger),
                "--parallel",
                "6",
                "--cpus",
                "2",
                "--timeout-s",
                "3600",
                "--keep",
                "all",
                "--native",
                "pod",
            ]
        )
    assert "registered campaign plans require Docker" in capsys.readouterr().err
    assert calls == []
    assert not ledger.exists()
    assert not output.exists()


def test_campaign_ledger_is_durable_and_allows_only_one_eligible_retry(tmp_path):
    config = decision_study.load_config(CONFIG, repository=REPOSITORY)
    plan = decision_study.reference_plan(
        config,
        "sha256:" + "d" * 64,
        solver_image="registry.example/motor@sha256:" + "e" * 64,
    )
    ledger_path = tmp_path / "campaign.sqlite3"
    ledger = reference_campaign.CampaignLedger(ledger_path)
    campaign_id = ledger.reserve(plan, tmp_path / "initial")
    retry_ids = []
    for index, case in enumerate(plan["cases"]):
        status = "REFERENCE_TIMEOUT" if index < 2 else "OK"
        ledger.finish_execution(campaign_id, case["case_id"], 1, status)
        if index < 2:
            retry_ids.append(case["case_id"])
    ledger.finish_batch(campaign_id, 1)
    restarted = reference_campaign.CampaignLedger(ledger_path)
    retry = decision_study.reference_plan(
        config,
        plan["construction_identity_digest"],
        solver_image=plan["solver_image"],
        case_ids=retry_ids,
        attempt=2,
    )
    restarted.reserve(retry, tmp_path / "retry")
    assert restarted.snapshot(campaign_id)["accounting"] == {
        "attempted_executions": 50,
        "initial_attempts": 48,
        "retry_attempts": 2,
        "finished_executions": 48,
    }
    with pytest.raises(reference_campaign.CampaignLedgerError):
        restarted.reserve(retry, tmp_path / "different-retry-output")


def test_concurrent_launchers_cannot_oversubscribe_one_campaign(tmp_path):
    config = decision_study.load_config(CONFIG, repository=REPOSITORY)
    plan = decision_study.reference_plan(
        config,
        "sha256:" + "f" * 64,
        solver_image="registry.example/motor@sha256:" + "0" * 64,
    )
    ledger_path = tmp_path / "campaign.sqlite3"

    def reserve(index):
        try:
            reference_campaign.CampaignLedger(ledger_path).reserve(
                plan, tmp_path / f"output-{index}"
            )
        except reference_campaign.CampaignLedgerError as error:
            return error.code
        return "RESERVED"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(reserve, range(2)))
    assert outcomes.count("RESERVED") == 1
    assert len(outcomes) == 2
    ledger = reference_campaign.CampaignLedger(ledger_path)
    assert ledger.snapshot(plan["campaign"]["campaign_id"])["accounting"] == {
        "attempted_executions": 48,
        "initial_attempts": 48,
        "retry_attempts": 0,
        "finished_executions": 0,
    }


def test_fixture_evaluation_reports_descriptive_groups_and_finite_regret(tmp_path):
    config = decision_study.load_config(CONFIG, repository=REPOSITORY)
    construction = tmp_path / "construction"
    decision_study.construct(config, repository=REPOSITORY, output=construction)
    result = decision_study.evaluate(
        config,
        repository=REPOSITORY,
        construction_directory=construction,
        reference=decision_study.fixture_reference(config),
        output=tmp_path / "evaluation",
        evidence_label="TEST_FIXTURE",
    )
    assert result["evidence_class"] == "ANALYTICAL_FIXTURE"
    assert result["comparator"]["status"] == "COMPLETE_FINITE_SET"
    assert result["metrics"]["statistical_interpretation"] == {
        "mode": "DESCRIPTIVE_FIXED_PILOT",
        "population_reliability_or_generalisation_confidence": False,
        "reason": (
            "The four arms share one decision problem and may reuse the same "
            "design-condition evidence; uses are not independent samples."
        ),
        "future_uncertainty_requirement": (
            "An approved sampling design and a justified independent-observation unit."
        ),
    }
    assert set(result["metrics"]["groups"]) == {
        "REPRESENTATIVE",
        "BOUNDARY_STRESS",
    }
    assert result["comparisons"]["model_value_same_fixed_grid"][
        "same_declared_query_budget"
    ]
    assert (
        result["comparisons"]["search_value_learned_model"][
            "query_attempt_difference_right_minus_left"
        ]
        == -5
    )
    assert (
        result["cost"]["study_end_to_end_wall_s"]
        >= result["cost"]["construction_wall_s"]
    )
    assert all(
        arm["regret"]["status"]
        in {
            "DEFINED_FINITE_SET",
            "INFEASIBLE_SELECTION",
            "REFERENCE_UNRESOLVED",
            "ABSTAIN",
        }
        for arm in result["arms"]
    )


def test_design_rule_is_the_recorded_two_by_two_by_two_grid():
    config = decision_study.load_config(CONFIG, repository=REPOSITORY)
    designs = [row["values"] for row in config["designs"]]
    assert {row["magnet_mm"] for row in designs} == {2.0, 3.5}
    assert {row["embrace"] for row in designs} == {0.65, 0.85}
    assert {row["airgap_mm"] for row in designs} == {0.4, 0.8}
    assert {
        (row["slot_open_deg"], row["tooth_mm"], row["slot_bottom_mm"])
        for row in designs
    } == {(3.7, 3.5, 38.16)}
    assert len({tuple(row.items()) for row in designs}) == 8


def _comparator(verdicts_by_design):
    designs = [
        {"design_id": design_id, "values": {"x": index}}
        for index, design_id in enumerate(verdicts_by_design)
    ]
    rows = []
    for design_id, verdicts in verdicts_by_design.items():
        for index, verdict in enumerate(verdicts):
            rows.append(
                {
                    "design_id": design_id,
                    "verdict": verdict,
                    "reference": (
                        {"ripple_fraction": 0.1 + 0.1 * index}
                        if verdict == "FEASIBLE"
                        else None
                    ),
                }
            )
    return reference_comparison.finite_comparator(
        designs=designs,
        rows=rows,
        conditions_per_design=2,
        objective=lambda evidence: max(
            row["reference"]["ripple_fraction"] for row in evidence
        ),
        objective_field="worst_reference_ripple_fraction",
        definition="test",
        limitations="test",
        accounting={},
    )


def test_unresolved_competitor_prevents_exact_finite_regret():
    comparator = _comparator(
        {
            "d01": ["FEASIBLE", "FEASIBLE"],
            "d02": ["FEASIBLE", "REFERENCE_UNAVAILABLE"],
        }
    )
    assert comparator["status"] == "UNRESOLVED_COMPARISON_SET"
    assert comparator["best_observed_reference_feasible"]["design_id"] == "d01"
    assert comparator["best_reference_feasible_in_complete_set"] is None


def test_known_violation_excludes_competitor_even_with_missing_evidence():
    comparator = _comparator(
        {
            "d01": ["FEASIBLE", "FEASIBLE"],
            "d02": ["INFEASIBLE", "REFERENCE_UNAVAILABLE"],
        }
    )
    assert comparator["status"] == "COMPLETE_FINITE_SET"
    d02 = next(row for row in comparator["designs"] if row["design_id"] == "d02")
    assert d02["proposal_outcome"] == "CONFIRMED_INFEASIBLE"


def test_fully_resolved_set_supports_exact_finite_regret():
    comparator = _comparator(
        {
            "d01": ["FEASIBLE", "FEASIBLE"],
            "d02": ["INFEASIBLE", "FEASIBLE"],
        }
    )
    result = reference_comparison.regret(
        proposal_outcome="CONFIRMED_FEASIBLE",
        selected_objective=0.3,
        comparator=comparator,
        objective_field="worst_reference_ripple_fraction",
        value_field="value_fraction",
        selected_field="selected",
        comparator_field="comparator",
        difference_field="difference",
    )
    assert result["status"] == "DEFINED_FINITE_SET"
    assert result["value_fraction"] == pytest.approx(0.1)


def test_v2_differs_from_v1_only_in_study_identity():
    v1 = decision_study.load_config(CONFIG, repository=REPOSITORY)
    v2 = decision_study.load_config(CONFIG_V2, repository=REPOSITORY)
    assert v2["study_id"] == "motor-synthetic-decision-v2"
    assert {k: v for k, v in v1.items() if k != "study_id"} == {
        k: v for k, v in v2.items() if k != "study_id"
    }
    assert decision_study.study_config_path(v2["study_id"]) == (
        CONFIG_V2.relative_to(REPOSITORY).as_posix()
    )


@pytest.mark.parametrize("study_id", ["motor-synthetic-decision", "x-v2", 2])
def test_an_unregistered_study_id_is_refused(tmp_path, study_id):
    config = json.loads(CONFIG_V2.read_text(encoding="utf-8"))
    config["study_id"] = study_id
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(decision_study.StudyError, match="config_identity"):
        decision_study.load_config(path, repository=REPOSITORY)


def test_v1_fixture_remains_a_consistent_historical_record():
    _freeze, construction = decision_study._historical_construction(
        FIXTURE / "construction"
    )
    assert construction["study_id"] == "motor-synthetic-decision-v1"
    assert construction["construction_identity_digest"] == (
        "sha256:81e76d3997d47be89abf3c1c63da4415cc492cfb24c921238df6f1c1c78ac0fc"
    )


def _ok_case(directory, *, logs="", torque_files=61):
    directory.mkdir(parents=True)
    for name in ("params.json", "machine.pro", "mesh.py"):
        (directory / name).write_text("x", encoding="utf-8")
    mesh = {"elements": 10, "nodes": 6}
    (directory / "mesh.json").write_text(
        json.dumps({"steps": {"0": mesh}}), encoding="utf-8"
    )
    for name in ("log.mesh", "log.getdp"):
        if logs is not None:
            (directory / name).write_text(logs, encoding="utf-8")
    (directory / "res").mkdir()
    for k in range(torque_files):
        (directory / "res" / f"torque_{k}.txt").write_text("1.0", encoding="utf-8")
    return {"run": "exit 0", "checks": {"not_converged": 0}, "mesh": mesh}


def test_empty_solver_logs_do_not_invalidate_a_successful_case(tmp_path):
    record = _ok_case(tmp_path / "case")
    assert decision_study._ok_case_artifacts_valid(tmp_path / "case", record)


@pytest.mark.parametrize(
    "change",
    [
        "missing_logs",
        "short_torque",
        "empty_torque",
        "bad_exit",
        "not_converged",
        "mesh_mismatch",
        "empty_params",
    ],
)
def test_case_artifact_rule_still_refuses_unsupported_evidence(tmp_path, change):
    case = tmp_path / "case"
    if change == "missing_logs":
        record = _ok_case(case, logs=None)
    elif change == "short_torque":
        record = _ok_case(case, torque_files=60)
    else:
        record = _ok_case(case)
    if change == "empty_torque":
        (case / "res" / "torque_0.txt").write_text("", encoding="utf-8")
    elif change == "bad_exit":
        record["run"] = "exit 1"
    elif change == "not_converged":
        record["checks"]["not_converged"] = 1
    elif change == "mesh_mismatch":
        record["mesh"] = {"elements": 11, "nodes": 6}
    elif change == "empty_params":
        (case / "params.json").write_text("", encoding="utf-8")
    assert not decision_study._ok_case_artifacts_valid(case, record)


def test_v2_construction_decides_exactly_what_v1_sealed(tmp_path):
    v1 = decision_study.load_config(CONFIG, repository=REPOSITORY)
    v2 = decision_study.load_config(CONFIG_V2, repository=REPOSITORY)
    _, predecessor = decision_study._historical_construction(FIXTURE / "construction")
    _, construction, _, _ = decision_study.load_construction(
        v2, repository=REPOSITORY, directory=FIXTURE_V2 / "construction"
    )
    fields = decision_study.adoption_check(v2, construction, v1, predecessor)
    assert "selection" in fields and "predicted_conditions" in fields
    with pytest.raises(decision_study.StudyError, match="needs_a_predecessor"):
        decision_study.adoption_check(v2, construction, v2, predecessor)
    changed = copy.deepcopy(predecessor)
    changed["arms"][0]["selection"] = {"design_id": "elsewhere"}
    with pytest.raises(decision_study.StudyError, match="adopted_decisions_differ"):
        decision_study.adoption_check(v2, construction, v1, changed)
    other = copy.deepcopy(v1)
    other["budgets"]["retry_reserve"] = 11
    with pytest.raises(decision_study.StudyError, match="differ_beyond_identity"):
        decision_study.adoption_check(v2, construction, other, predecessor)


def test_an_altered_predecessor_commitment_is_refused(tmp_path):
    copy_dir = tmp_path / "construction"
    shutil.copytree(FIXTURE / "construction", copy_dir)
    commitment = next(copy_dir.rglob("*.commitment.json"))
    commitment.write_text(
        commitment.read_text(encoding="utf-8") + " ", encoding="utf-8"
    )
    with pytest.raises(decision_study.StudyError, match="predecessor_commitment"):
        decision_study._historical_construction(copy_dir)


def test_committed_counted_v2_evidence_is_bound_and_consistent():
    counted = REPOSITORY / "docs/development/evidence/motor-decision-counted-v2"
    config = decision_study.load_config(CONFIG_V2, repository=REPOSITORY)
    _, construction, _, restored = decision_study.load_construction(
        config, repository=REPOSITORY, directory=counted / "construction"
    )
    fixture = json.loads(
        (FIXTURE_V2 / "construction" / "construction.json").read_text(encoding="utf-8")
    )
    assert construction["construction_identity_digest"] == (
        fixture["construction_identity_digest"]
    )
    result = json.loads((counted / "evaluation/result.json").read_text("utf-8"))
    adoption = json.loads((counted / "adoption.json").read_text("utf-8"))
    completion = json.loads((counted / "completion.json").read_text("utf-8"))
    identity = construction["construction_identity_digest"]
    assert result["construction_identity_digest"] == identity
    assert result["evidence_class"] == "COUNTED_GETDP"
    assert result["cost"]["reference_executions"] == 48
    assert result["comparator"]["status"] == "COMPLETE_FINITE_SET"
    body = {k: v for k, v in adoption.items() if k != "adoption_digest"}
    assert adoption["adoption_digest"] == decision_study.experiment.digest(body)
    assert adoption["construction_identity_digest"] == identity
    assert adoption["predecessor_construction_identity_digest"] == (
        completion["campaign"]["construction_identity_digest"]
    )
    assert completion["campaign"]["status_counts"] == {"OK": 48}
    assert len(restored) == 4
