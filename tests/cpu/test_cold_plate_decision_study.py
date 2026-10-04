"""Bounded accelerator-cooling DEVELOPMENT study and evidence path."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from carbon.cold_plate import analytic, reference_campaign
from carbon.cold_plate import customer_decision as cd
from carbon.cold_plate import decision_study as study
from scripts.dev.cold_plate.reference import run_batch

REPOSITORY = Path(__file__).resolve().parents[2]
CONFIG = (
    REPOSITORY
    / "docs"
    / "development"
    / "studies"
    / "AI_ACCELERATOR_COOLING_SYNTHETIC_V1.json"
)
FIXTURE_EVIDENCE = (
    REPOSITORY / "docs" / "development" / "evidence" / "cold-plate-decision-fixture-v2"
)
CONSTRUCTION_ID = "sha256:" + "a" * 64


def load():
    return study.load_config(CONFIG, repository=REPOSITORY)


def analytic_models(_config, *, repository):
    del repository

    def infer(inputs):
        return {
            key: {
                name: value
                for name, value in analytic.predict(case).items()
                if name in cd.exam.SHAPES
            }
            for key, case in inputs.items()
        }

    return {
        "analytic-v1": infer,
        "learned-krr-v1": infer,
    }, {
        "analytic-v1": {"kind": "ANALYTICAL_BASELINE"},
        "learned-krr-v1": {
            "kind": "TEST_DOUBLE_FOR_RUNNER_TEST_ONLY",
            "historical_training_and_tuning_cost": None,
        },
    }


def _write_completed_ledger(root, plan, records, ledger_path):
    ledger = reference_campaign.CampaignLedger(ledger_path)
    campaign_id = ledger.reserve(plan, root)
    for record in records:
        ledger.finish_execution(
            campaign_id, record["case_id"], plan["attempt"], record["status"]
        )
    ledger.finish_batch(campaign_id, plan["attempt"])
    (root / "campaign-ledger.json").write_text(json.dumps(ledger.snapshot(campaign_id)))
    return ledger


def test_config_freezes_synthetic_scope_groups_and_bounded_reference_plan():
    config = load()
    plan = study.reference_plan(config, CONSTRUCTION_ID)
    assert len(plan["cases"]) == 48
    assert len({row["case_id"] for row in plan["cases"]}) == 48
    assert plan["solver_image"] == cd.openfoam.IMAGE
    assert plan["campaign"]["initial_execution_limit"] == 48
    assert plan["campaign"]["retry_execution_limit"] == 12
    assert plan["campaign"]["total_execution_limit"] == 60
    assert plan["campaign"]["execution_backend"] == "DOCKER"
    assert plan["campaign"]["solver_image"] == cd.openfoam.IMAGE
    assert plan["campaign"]["ledger_relative_path"] == (
        ".carbon-artifacts/ai-accelerator-cooling-synthetic-v1-campaign.sqlite3"
    )
    assert plan["campaign"]["resource_policy"] == {
        "cpus_per_execution": 2,
        "parallel_executions": 6,
        "timeout_seconds_per_execution": 3600,
        "artifact_retention": "all",
    }
    assert config["budgets"]["retry_reserve"] == 12
    assert config["budgets"]["estimated_initial_core_hours"] == 19.2
    assert config["budgets"]["estimated_hard_cap_core_hours"] == 24.0
    assert config["budgets"]["configured_initial_allocated_core_hour_ceiling"] == 96
    assert config["budgets"]["configured_hard_cap_allocated_core_hour_ceiling"] == 120
    assert config["analysis"]["combined_weighting"] is None
    assert config["analysis"]["pass_threshold"] is None
    assert {row["group"] for row in config["conditions"]} == set(study.GROUPS)
    assert config["claims"]["synthetic_customer_requirement"] is True
    assert config["claims"]["customer_acceptance"] is False


def test_freeze_pins_model_search_reference_and_campaign_accounting_code():
    config = load()
    freeze = study.build_freeze(config, repository=REPOSITORY)
    pinned = freeze["search_freeze"]["code"]
    assert "carbon/cold_plate/decision_study.py" in pinned
    assert "carbon/cold_plate/reference_campaign.py" in pinned
    assert "carbon/cold_plate/openfoam.py" in pinned
    assert "carbon/cold_plate/analysis.py" in pinned
    assert "scripts/dev/cold_plate/reference/run_batch.py" in pinned
    assert freeze["reference_scope"]["global_optimality_claim"] is False


def test_committed_fixture_evidence_matches_current_frozen_code():
    config = load()
    freeze = json.loads((FIXTURE_EVIDENCE / "construction" / "freeze.json").read_text())
    construction = json.loads(
        (FIXTURE_EVIDENCE / "construction" / "construction.json").read_text()
    )
    result = json.loads((FIXTURE_EVIDENCE / "evaluation" / "result.json").read_text())
    search_freeze = freeze["search_freeze"]
    body = {
        key: value for key, value in search_freeze.items() if key != "freeze_digest"
    }
    assert study.experiment.digest(body) == search_freeze["freeze_digest"]
    # Git stores these text files with LF. Normalize a Windows checkout's CRLF
    # before comparing it with evidence generated from the exact committed tree.
    for relative, expected in {
        **search_freeze["code"],
        **search_freeze["dependencies"],
    }.items():
        content = (REPOSITORY / relative).read_bytes().replace(b"\r\n", b"\n")
        assert "sha256:" + hashlib.sha256(content).hexdigest() == expected
    assert freeze["config_digest"] == study.experiment.digest(config)
    assert result["freeze_digest"] == freeze["freeze_digest"]
    assert result["construction_digest"] == construction["construction_digest"]
    assert result["evidence_class"] == "ANALYTICAL_FIXTURE"
    assert result["cost"]["reference_executions"] == 0
    assert result["cost"]["study_end_to_end_wall_s"] == pytest.approx(
        result["cost"]["construction_wall_s"] + result["cost"]["evaluation_wall_s"]
    )
    assert result["claims"]["scientific_qualification"] is False


def test_retry_plan_contains_only_typed_failures_and_honors_reserve(tmp_path):
    config = load()
    initial = study.reference_plan(config, CONSTRUCTION_ID)
    root = tmp_path / "initial"
    root.mkdir()
    (root / "plan.json").write_text(json.dumps(initial))
    records = [
        {
            "case_id": case["case_id"],
            "status": "REFERENCE_TIMEOUT" if index < 2 else "OK",
        }
        for index, case in enumerate(initial["cases"])
    ]
    (root / "records.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records)
    )
    _write_completed_ledger(root, initial, records, tmp_path / "campaign.sqlite3")
    retry = study.reference_retry_plan(config, root)
    assert retry["attempt"] == 2
    assert [case["case_id"] for case in retry["cases"]] == [
        initial["cases"][0]["case_id"],
        initial["cases"][1]["case_id"],
    ]

    records[0]["status"] = "REFERENCE_INVALID"
    (root / "records.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records)
    )
    with pytest.raises(study.StudyError, match="campaign_ledger_execution_records"):
        study.reference_retry_plan(config, root)


def test_fixture_runner_is_descriptive_and_separates_unique_evidence_reuse(
    tmp_path, monkeypatch
):
    config = load()
    monkeypatch.setattr(study, "reconstruct_models", analytic_models)
    construction_dir = tmp_path / "construction"
    study.construct(config, repository=REPOSITORY, output=construction_dir)
    result = study.evaluate(
        config,
        repository=REPOSITORY,
        construction_directory=construction_dir,
        reference=study.fixture_reference(config),
        output=tmp_path / "evaluation",
        evidence_label="TEST_ANALYTICAL_FIXTURE_NOT_CFD",
    )
    assert result["evidence_class"] == "ANALYTICAL_FIXTURE"
    assert len(result["arms"]) == 4
    assert result["comparisons"]["model_value"]["same_declared_query_budget"]
    assert result["comparisons"]["search_method_value"]["same_declared_query_budget"]
    assert result["comparator"]["status"] == "COMPLETE_FINITE_SET"
    assert (
        result["comparator"]["best_reference_feasible_in_complete_set"]["design_id"]
        == "d03"
    )
    metrics = result["metrics"]
    assert metrics["arm_condition_uses"] == 24
    assert metrics["unique_selected_design_condition_reference_cases"] == 6
    assert metrics["selected_reference_evidence_reuses"] == 18
    assert metrics["groups"]["REPRESENTATIVE"] == {
        "arm_condition_uses": 16,
        "unique_design_condition_reference_cases": 4,
        "evidence_reuses": 12,
        "unique_reference_available": 4,
        "unique_reference_confirmed_feasible": 4,
        "unique_reference_confirmed_infeasible": 0,
        "unique_reference_unavailable": 0,
    }
    assert metrics["groups"]["BOUNDARY_STRESS"]["arm_condition_uses"] == 8
    assert "wilson" not in json.dumps(metrics).lower()
    assert (
        metrics["statistical_interpretation"][
            "population_reliability_or_generalisation_confidence"
        ]
        is False
    )
    assert result["conclusion"]["all_arms_selected_same_geometry"] is True
    assert "not evidence of a learned-model" in result["conclusion"]["observed_outcome"]
    assert result["cost"]["reference_executions"] == 0
    assert result["claims"]["scientific_qualification"] is False
    for arm in result["arms"]:
        assert arm["declared_query_budget"] == 48
        assert arm["proposal_outcome"] == "CONFIRMED_FEASIBLE"
        for row in arm["scenarios"]:
            assert row["selected_geometry"]
            assert row["operating_control"]["total_flow_lpm"] > 0
            assert row["prediction"] is not None
            assert row["reference"] is not None
            assert row["engineering_cost"]["unit"] == "W"
            assert row["baseline_comparison"]["baseline_arm"] == (
                "analytic-v1/fixed_grid"
            )
    assert (construction_dir / "construction.json").is_file()
    assert (tmp_path / "evaluation" / "result.json").is_file()
    assert (tmp_path / "evaluation" / "report.md").is_file()


def test_counted_reference_rejects_tampered_normalized_provenance():
    config = load()
    case = study.reference_plan(config, CONSTRUCTION_ID)["cases"][0]["inputs"]
    provenance = {
        "evidence_class": "COUNTED_CFD",
        "solver_image": cd.openfoam.IMAGE,
        "configuration_digest": "sha256:" + "1" * 64,
        "mesh_digest": "sha256:" + "2" * 64,
        "convergence_evidence_digest": "sha256:" + "3" * 64,
        "applicability_evidence_digest": "sha256:" + "4" * 64,
        "run_identity": "run:test:1",
        "artifact_manifest_digest": "sha256:" + "5" * 64,
        "artifact_count": 10,
        "artifact_bytes": 100,
        "execution_count": 1,
        "retry_count": 0,
        "wall_s": 1.0,
        "cpu_limit": 2,
    }
    record = cd._seal_counted_record(
        cd._REFERENCE_SESSION_TOKEN,
        status="OK",
        inputs=case,
        outputs=analytic.predict(case),
        checks={"fixture-shape-only": True},
        provenance=provenance,
    )
    tampered = {**record, "outputs": {**record["outputs"], "peak_c": 1.0}}
    with pytest.raises(cd.DecisionError, match="record_digest_mismatch"):
        cd.counted_cfd_reference(
            {cd._case_id(case): tampered},
            condition_budget=1,
            session_id="tampered-counted-evidence",
            construction_identity_digest=CONSTRUCTION_ID,
        )


def test_cfd_importer_does_not_count_plausible_records_without_solver_artifacts(
    tmp_path,
):
    config = load()
    plan = study.reference_plan(config, CONSTRUCTION_ID)
    root = tmp_path / "cfd"
    (root / "cases").mkdir(parents=True)
    (root / "plan.json").write_text(json.dumps(plan))
    (root / "host.json").write_text(
        json.dumps(
            {
                "cpus": 2,
                "parallel": 6,
                "timeout_s": 3600,
                "keep": "all",
                "solver_image": cd.openfoam.IMAGE,
            }
        )
    )
    (root / "DONE.json").write_text(
        json.dumps(
            {
                "batch": plan["batch"],
                "cases": len(plan["cases"]),
                "wall_s": 12.0,
                "counts": {"OK": len(plan["cases"]) - 1, "REFERENCE_TIMEOUT": 1},
            }
        )
    )
    records = []
    for index, entry in enumerate(plan["cases"]):
        case_dir = root / "cases" / entry["case_id"]
        case_dir.mkdir()
        _files, generated = cd.openfoam.files(entry["inputs"])
        mesh = generated["mesh"]
        outputs = analytic.predict(entry["inputs"])
        checks = {"fluid_min_c": 30.0, "fluid_max_c": 90.0, "re_outlet": 1000.0}
        (case_dir / "case.json").write_text(json.dumps(generated))
        (case_dir / "analysis.json").write_text(
            json.dumps({"outcome": "OK", "outputs": outputs, "checks": checks})
        )
        record = {
            "schema": "carbon.cold-plate.reference-record.v1",
            "batch": plan["batch"],
            "case_id": entry["case_id"],
            "inputs": entry["inputs"],
            "options": {},
            "status": "REFERENCE_TIMEOUT" if index == 0 else "OK",
            "run": "wall limit 3600 s" if index == 0 else "exit 0",
            "wall_s": 1.0,
        }
        if index != 0:
            record.update(
                image=cd.openfoam.IMAGE,
                mesh=mesh,
                outputs=outputs,
                checks=checks,
                diagnostics={"writes": ["4000"]},
            )
        records.append(record)
    (root / "records.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records)
    )
    _write_completed_ledger(root, plan, records, tmp_path / "campaign.sqlite3")

    reference = study.import_counted_cfd(config, [root])
    timeout_job, plausible_job = study._comparison_jobs(config)[:2]
    acquired, _accounting = reference.acquire(
        "sha256:" + "9" * 64,
        [timeout_job, plausible_job],
        per_commitment_budget=2,
    )
    assert acquired[timeout_job["case_id"]]["status"] == "REFERENCE_TIMEOUT"
    assert (
        acquired[plausible_job["case_id"]]["status"] == "REFERENCE_PROVENANCE_INVALID"
    )
    assert reference.metrics()["solver_executions"] == 1
    assert reference.metrics()["campaign_wall_s"] == 12.0


def _mini_comparator(status_for):
    config = load()
    config = {**config, "designs": config["designs"][:2]}
    config["conditions"] = config["conditions"][:2]
    config["budgets"] = {
        **config["budgets"],
        "comparator_condition_evaluations": 4,
    }
    contract = study.decision_contract(config)
    design_by_flow = {
        design["values"]["flow_lpm_per_kw"]: design["design_id"]
        for design in config["designs"]
    }

    def source(jobs):
        records = {}
        for job in jobs:
            design_id = design_by_flow[job["inputs"]["flow_lpm_per_kw"]]
            requested = status_for(design_id, job["scenario_id"])
            if requested == "MISSING":
                continue
            inlet = job["inputs"]["inlet_c"]
            flow = cd.domain.derived(job["inputs"])["flow_m3_s"]
            pressure = 1.0 if requested == "FEASIBLE" else 1.0 / flow
            records[job["case_id"]] = {
                "status": "OK",
                "inputs": job["inputs"],
                "outputs": {
                    "peak_c": inlet + 1.0,
                    "profile_c": [inlet + 1.0] * cd.domain.PROFILE_SEGMENTS,
                    "pressure_drop_pa": pressure,
                },
                "checks": {},
            }
        return records

    reference = cd.analytical_fixture_reference(
        source, condition_budget=4, session_id="mini-comparator"
    )
    return study._finite_comparator(
        config,
        {"freeze_digest": "sha256:" + "b" * 64},
        contract,
        reference,
    )


def _feasible_arm(worst=0.2):
    return {
        "selection": {"selected": True},
        "proposal_outcome": "CONFIRMED_FEASIBLE",
        "scenarios": [{"reference": {"hydraulic_w": worst}}],
    }


def test_unresolved_competitor_withholds_exact_regret_but_reports_observed_difference():
    comparator = _mini_comparator(
        lambda design, scenario: (
            "MISSING" if design == "d01" and scenario == "rep-01" else "FEASIBLE"
        )
    )
    assert comparator["status"] == "UNRESOLVED_COMPARISON_SET"
    assert comparator["best_observed_reference_feasible"]["design_id"] == "d02"
    assert comparator["best_reference_feasible_in_complete_set"] is None
    arm = _feasible_arm()
    study._attach_regret(arm, comparator)
    assert arm["regret"]["value_w"] is None
    assert arm["regret"]["status"] == (
        "COMPARATOR_UNRESOLVED_BEST_OBSERVED_DIFFERENCE_ONLY"
    )
    assert isinstance(arm["regret"]["difference_from_best_observed_w"], float)


def test_confirmed_infeasible_competitor_with_missing_evidence_does_not_block_best():
    def statuses(design, scenario):
        if design == "d01" and scenario == "rep-01":
            return "MISSING"
        if design == "d01" and scenario == "rep-02":
            return "INFEASIBLE"
        return "FEASIBLE"

    comparator = _mini_comparator(statuses)
    assert comparator["status"] == "COMPLETE_FINITE_SET"
    assert comparator["designs"][0]["proposal_outcome"] == "CONFIRMED_INFEASIBLE"
    assert comparator["designs"][0]["resolved_all_conditions"] is False
    assert comparator["best_reference_feasible_in_complete_set"]["design_id"] == "d02"


def test_fully_resolved_set_supports_exact_finite_regret():
    comparator = _mini_comparator(lambda _design, _scenario: "FEASIBLE")
    assert comparator["status"] == "COMPLETE_FINITE_SET"
    assert comparator["best_reference_feasible_in_complete_set"] is not None
    arm = _feasible_arm()
    study._attach_regret(arm, comparator)
    assert arm["regret"]["status"] == "DEFINED_FINITE_SET"
    assert isinstance(arm["regret"]["value_w"], float)


def test_reference_cannot_be_acquired_until_every_commitment_is_present(
    tmp_path, monkeypatch
):
    config = load()
    monkeypatch.setattr(study, "reconstruct_models", analytic_models)
    construction = tmp_path / "construction"
    document = study.construct(config, repository=REPOSITORY, output=construction)
    missing = construction / document["arms"][-1]["commitment"]["relative_path"]
    missing.unlink()
    source_calls = []

    def source(jobs):
        source_calls.append(jobs)
        return {}

    reference = cd.analytical_fixture_reference(
        source, condition_budget=72, session_id="must-not-open"
    )
    with pytest.raises(
        study.StudyError, match="complete_construction_artifact_required"
    ):
        study.evaluate(
            config,
            repository=REPOSITORY,
            construction_directory=construction,
            reference=reference,
            output=tmp_path / "evaluation",
            evidence_label="TEST",
        )
    assert source_calls == []
    assert reference.metrics()["source_calls"] == 0


def test_counted_reference_must_bind_the_exact_construction(tmp_path, monkeypatch):
    config = load()
    monkeypatch.setattr(study, "reconstruct_models", analytic_models)
    construction = tmp_path / "construction"
    study.construct(config, repository=REPOSITORY, output=construction)
    wrong = cd.counted_cfd_reference(
        {},
        condition_budget=72,
        session_id="wrong-construction",
        construction_identity_digest="sha256:" + "f" * 64,
    )
    with pytest.raises(study.StudyError, match="reference_construction_identity"):
        study.evaluate(
            config,
            repository=REPOSITORY,
            construction_directory=construction,
            reference=wrong,
            output=tmp_path / "evaluation",
            evidence_label="TEST",
        )


def test_campaign_ledger_is_durable_concurrent_and_output_bound(tmp_path):
    config = load()
    plan = study.reference_plan(config, CONSTRUCTION_ID)
    ledger_path = tmp_path / "campaign.sqlite3"

    def reserve(out):
        ledger = reference_campaign.CampaignLedger(ledger_path)
        try:
            return ("OK", ledger.reserve(plan, out))
        except reference_campaign.CampaignLedgerError as error:
            return (error.code, None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(reserve, (tmp_path / "a", tmp_path / "b")))
    assert [code for code, _value in outcomes].count("OK") == 1
    assert any(code == "campaign_attempt_bound_to_other_output" for code, _ in outcomes)
    campaign_id = next(value for code, value in outcomes if code == "OK")
    restarted = reference_campaign.CampaignLedger(ledger_path)
    snapshot = restarted.snapshot(campaign_id)
    assert snapshot["accounting"]["attempted_executions"] == 48
    assert snapshot["accounting"]["finished_executions"] == 0
    with pytest.raises(
        reference_campaign.CampaignLedgerError,
        match="campaign_attempt_bound_to_other_output",
    ):
        restarted.reserve(plan, tmp_path / "evasion")


def test_campaign_ledger_rejects_a_tampered_policy_identity(tmp_path):
    plan = json.loads(json.dumps(study.reference_plan(load(), CONSTRUCTION_ID)))
    plan["campaign"]["total_execution_limit"] = 61
    plan["campaign"]["retry_execution_limit"] = 13
    ledger = reference_campaign.CampaignLedger(tmp_path / "campaign.sqlite3")
    with pytest.raises(
        reference_campaign.CampaignLedgerError, match="campaign_id_mismatch"
    ):
        ledger.reserve(plan, tmp_path / "initial")


def test_counted_runner_rejects_an_alternate_campaign_ledger_path(tmp_path):
    plan = study.reference_plan(load(), CONSTRUCTION_ID)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    with pytest.raises(SystemExit, match="2"):
        run_batch.main(
            [
                str(plan_path),
                "--out",
                str(tmp_path / "output"),
                "--campaign-ledger",
                str(tmp_path / "alternate.sqlite3"),
                "--parallel",
                "6",
                "--cpus",
                "2",
                "--timeout-s",
                "3600",
                "--keep",
                "all",
            ]
        )


def test_counted_runner_rejects_native_before_reservation_or_dispatch(
    tmp_path, monkeypatch, capsys
):
    plan = study.reference_plan(load(), CONSTRUCTION_ID)
    plan["campaign"]["ledger_relative_path"] = "campaign.sqlite3"
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan))
    output = tmp_path / "output"
    ledger_path = tmp_path / "campaign.sqlite3"
    calls = []

    def unexpected(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("registered native rejection must precede side effects")

    monkeypatch.setattr(run_batch, "ROOT", tmp_path)
    monkeypatch.setattr(run_batch, "NATIVE", None)
    monkeypatch.setattr(reference_campaign, "CampaignLedger", unexpected)
    monkeypatch.setattr(run_batch, "run_case", unexpected)
    monkeypatch.setattr(run_batch.subprocess, "run", unexpected)
    monkeypatch.setattr(run_batch.subprocess, "Popen", unexpected)

    with pytest.raises(SystemExit, match="2"):
        run_batch.main(
            [
                str(plan_path),
                "--out",
                str(output),
                "--campaign-ledger",
                str(ledger_path),
                "--parallel",
                "6",
                "--cpus",
                "2",
                "--timeout-s",
                "3600",
                "--keep",
                "all",
                "--native",
                "test-environment",
            ]
        )

    assert "registered campaign plans require Docker" in capsys.readouterr().err
    assert calls == []
    assert run_batch.NATIVE is None
    assert not ledger_path.exists()
    assert not output.exists()


def test_campaign_ledger_allows_one_registered_retry_for_eligible_cases(tmp_path):
    config = load()
    initial = study.reference_plan(config, CONSTRUCTION_ID)
    ledger = reference_campaign.CampaignLedger(tmp_path / "campaign.sqlite3")
    campaign_id = ledger.reserve(initial, tmp_path / "initial")
    retry_cases = []
    for index, case in enumerate(initial["cases"]):
        status = "REFERENCE_TIMEOUT" if index < 2 else "OK"
        ledger.finish_execution(campaign_id, case["case_id"], 1, status)
        if index < 2:
            retry_cases.append(case["case_id"])
    ledger.finish_batch(campaign_id, 1)
    ineligible = study.reference_plan(
        config,
        CONSTRUCTION_ID,
        case_ids=[initial["cases"][2]["case_id"]],
        attempt=2,
    )
    with pytest.raises(
        reference_campaign.CampaignLedgerError, match="case_not_retry_eligible"
    ):
        ledger.reserve(ineligible, tmp_path / "ineligible-retry")
    retry = study.reference_plan(
        config, CONSTRUCTION_ID, case_ids=retry_cases, attempt=2
    )
    ledger.reserve(retry, tmp_path / "retry")
    assert ledger.snapshot(campaign_id)["accounting"] == {
        "attempted_executions": 50,
        "initial_attempts": 48,
        "retry_attempts": 2,
        "finished_executions": 48,
    }
    with pytest.raises(reference_campaign.CampaignLedgerError):
        ledger.reserve(retry, tmp_path / "retry-again")
