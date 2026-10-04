"""Bounded accelerator-cooling DEVELOPMENT study and evidence path."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from carbon.cold_plate import analytic
from carbon.cold_plate import customer_decision as cd
from carbon.cold_plate import decision_study as study

REPOSITORY = Path(__file__).resolve().parents[2]
CONFIG = (
    REPOSITORY
    / "docs"
    / "development"
    / "studies"
    / "AI_ACCELERATOR_COOLING_SYNTHETIC_V1.json"
)
FIXTURE_EVIDENCE = (
    REPOSITORY / "docs" / "development" / "evidence" / "cold-plate-decision-fixture-v1"
)


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


def test_config_freezes_synthetic_scope_groups_and_bounded_reference_plan():
    config = load()
    plan = study.reference_plan(config)
    assert len(plan["cases"]) == 48
    assert len({row["case_id"] for row in plan["cases"]}) == 48
    assert plan["solver_image"] == cd.openfoam.IMAGE
    assert plan["hard_solver_execution_cap"] == 60
    assert config["budgets"]["retry_reserve"] == 12
    assert config["analysis"]["combined_weighting"] is None
    assert config["analysis"]["pass_threshold"] is None
    assert {row["group"] for row in config["conditions"]} == set(study.GROUPS)
    assert config["claims"]["synthetic_customer_requirement"] is True
    assert config["claims"]["customer_acceptance"] is False


def test_freeze_pins_model_search_reference_and_analysis_code():
    config = load()
    freeze = study.build_freeze(config, repository=REPOSITORY)
    pinned = freeze["search_freeze"]["code"]
    assert "carbon/cold_plate/decision_study.py" in pinned
    assert "carbon/cold_plate/openfoam.py" in pinned
    assert "carbon/cold_plate/analysis.py" in pinned
    assert "scripts/dev/cold_plate/reference/run_batch.py" in pinned
    assert freeze["reference_scope"]["global_optimality_claim"] is False


def test_committed_fixture_evidence_matches_current_frozen_code():
    config = load()
    freeze = json.loads((FIXTURE_EVIDENCE / "freeze.json").read_text())
    result = json.loads((FIXTURE_EVIDENCE / "result.json").read_text())
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
    assert result["evidence_class"] == "ANALYTICAL_FIXTURE"
    assert result["cost"]["reference_executions"] == 0
    assert result["claims"]["scientific_qualification"] is False


def test_retry_plan_contains_only_typed_failures_and_honors_reserve(tmp_path):
    config = load()
    initial = study.reference_plan(config)
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
    retry = study.reference_retry_plan(config, root)
    assert retry["attempt"] == 2
    assert [case["case_id"] for case in retry["cases"]] == [
        initial["cases"][0]["case_id"],
        initial["cases"][1]["case_id"],
    ]

    for record in records[:13]:
        record["status"] = "REFERENCE_TIMEOUT"
    (root / "records.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records)
    )
    with pytest.raises(study.StudyError, match="retry_reserve_insufficient"):
        study.reference_retry_plan(config, root)


def test_fixture_runner_keeps_model_method_and_comparator_questions_separate(
    tmp_path, monkeypatch
):
    config = load()
    monkeypatch.setattr(study, "reconstruct_models", analytic_models)
    result = study.run(
        config,
        repository=REPOSITORY,
        reference=study.fixture_reference(config),
        output=tmp_path / "fixture",
        evidence_label="TEST_ANALYTICAL_FIXTURE_NOT_CFD",
    )
    assert result["evidence_class"] == "ANALYTICAL_FIXTURE"
    assert len(result["arms"]) == 4
    assert result["comparisons"]["model_value"]["same_declared_query_budget"]
    assert result["comparisons"]["search_method_value"]["same_declared_query_budget"]
    assert result["comparator"]["coverage"] == {
        "designs": 8,
        "conditions_per_design": 6,
        "condition_evidence": 48,
        "resolved_condition_evidence": 48,
        "fully_resolved_designs": 8,
    }
    assert result["comparator"]["best"]["design_id"] == "d03"
    assert (
        result["metrics"]["groups"]["REPRESENTATIVE"]["proposed_condition_decisions"]
        == 16
    )
    assert (
        result["metrics"]["groups"]["BOUNDARY_STRESS"]["proposed_condition_decisions"]
        == 8
    )
    assert result["cost"]["reference_executions"] == 0
    assert result["claims"]["scientific_qualification"] is False
    for arm in result["arms"]:
        assert arm["declared_query_budget"] == 48
        for row in arm["scenarios"]:
            assert row["selected_geometry"]
            assert row["operating_control"]["total_flow_lpm"] > 0
            assert row["prediction"] is not None
            assert row["reference"] is not None
            assert row["engineering_cost"]["unit"] == "W"
            assert row["baseline_comparison"]["baseline_arm"] == (
                "analytic-v1/fixed_grid"
            )
    assert (tmp_path / "fixture" / "freeze.json").is_file()
    assert (tmp_path / "fixture" / "result.json").is_file()
    assert (tmp_path / "fixture" / "report.md").is_file()


def test_counted_reference_rejects_tampered_normalized_provenance():
    config = load()
    case = study.reference_plan(config)["cases"][0]["inputs"]
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
        )


def test_cfd_importer_does_not_count_plausible_records_without_solver_artifacts(
    tmp_path,
):
    config = load()
    plan = study.reference_plan(config)
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
