"""Synthetic shared-benchmark path across ScoreLab and the validator scorer.

The input is a toy receipt, not a solver/model run or qualified physics result.
"""

import json
from copy import deepcopy

import pytest

from carbon.scoring.engine import ScoreEngine
from carbon.scoring.solver_benchmark_v3 import register_pack
from scripts.dev.score_lab import solver_benchmark as bench
from scripts.dev.score_lab.__main__ import main as scorelab_main
from tests.cpu.test_score_lab_solver_benchmark_acceptance import _toy_workload


def _workbench_json(tmp_path, registration, references, models, pack):
    evidence = tmp_path / "synthetic-evidence.json"
    report = tmp_path / "synthetic-report.json"
    evidence.write_text(
        json.dumps(
            {
                "registration": registration,
                "references": references,
                "models": models,
                "score_pack": pack,
            }
        ),
        encoding="utf-8",
    )
    assert (
        scorelab_main(["benchmark", "--input", str(evidence), "--out", str(report)])
        == 0
    )
    return json.loads(report.read_text(encoding="utf-8"))


def test_workbench_json_and_validator_score_one_shared_physics_contract(tmp_path):
    registration, references, models, pack = _toy_workload()
    workbench = _workbench_json(tmp_path, registration, references, models, pack)
    validator_input = bench.compare(registration, references, models)
    validator_score = ScoreEngine.score_solver_benchmark_v3(validator_input, pack)

    assert workbench["scoring"] == validator_score
    assert workbench["registration_digest"] == pack["benchmark_registration_digest"]
    assert workbench["physics_contract"] == pack["physics_contract"]
    assert workbench["output"]["unit"] == "min"
    assert [row["artifact_digest"] for row in workbench["models"]] == [
        row["artifact_digest"] for row in validator_input["models"]
    ]
    assert validator_score["ranking"] == [
        "sha256:less-accurate-faster",
        "sha256:accurate-slower",
    ]
    assert validator_score["models"][2]["status"] == "SCIENTIFIC_INADMISSIBLE"
    assert validator_score["models"][2]["performance_score"] is None

    # The compared work is the same serial batch-one roster, including all
    # four model phases and measured solver time; build time stays separate.
    assert registration["timing_profile"]["batch_size"] == 1
    for member in workbench["models"]:
        p = member["by_role"]["P"]
        assert p["attempted"] == 2
        assert p["solver_seconds"] == 20.0
        assert p["model_seconds"] == pytest.approx(
            sum(p["model_phase_seconds"].values())
        )
        assert p["solver_query_latency"]["max_s"] == 12.0
        assert p["model_query_latency"]["max_s"] > 0
        assert p["model_peak_memory_bytes"] == 128
        assert p["solver_peak_memory_bytes"] == 2048
        assert member["build_seconds"] == 60.0
    assert workbench["models"][0]["by_role"]["P"]["paired_speedup"] == 4.0
    assert workbench["models"][0]["by_role"]["Q"]["mean_absolute_error"] == 5.0


def test_changed_measurement_context_cannot_reuse_the_old_score_pack():
    registration, references, models, pack = _toy_workload()
    changed = deepcopy(registration)
    changed.pop("registration_digest")
    changed["timing_profile"]["model_device"] = "different-fixture-device"
    changed = bench.register(changed)
    assert changed["registration_digest"] != registration["registration_digest"]
    with pytest.raises(ValueError, match="benchmark_binding"):
        bench.compare(changed, references, models, score_pack=pack)
    with pytest.raises(bench.BenchmarkRefused, match="timing_profile"):
        body = deepcopy(registration)
        body.pop("registration_digest")
        body["timing_profile"]["batch_size"] = 8
        bench.register(body)


@pytest.mark.parametrize(
    ("reference_status", "expected_status"),
    [
        ("UNRESOLVED", "INDETERMINATE_EVIDENCE"),
        ("FAILED_INFRA", "FAILED_INFRA"),
    ],
)
def test_reference_failure_is_common_and_not_a_candidate_fault(
    tmp_path, reference_status, expected_status
):
    registration, references, models, pack = _toy_workload()
    references[0] = {"id": "p-cool", "status": reference_status}
    report = _workbench_json(tmp_path, registration, references, models, pack)
    assert report["scoring"]["ranking"] == []
    for model in report["models"]:
        p = model["by_role"]["P"]
        assert p["status"] == expected_status
        assert p["counts"]["candidate_invalid"] == 0
        assert p["counts"]["candidate_infra"] == 0
        assert p["mean_absolute_error"] is None
        assert p["paired_speedup"] is None
    assert {row["status"] for row in report["scoring"]["models"]} == {expected_status}


def test_absent_accuracy_criterion_is_not_ready_on_both_entry_paths(tmp_path):
    registration, references, models, pack = _toy_workload()
    unready = deepcopy(pack)
    unready.pop("pack_digest")
    unready["accuracy_ceiling"] = None
    unready = register_pack(unready)
    report = _workbench_json(tmp_path, registration, references, models, unready)
    direct = ScoreEngine.score_solver_benchmark_v3(
        bench.compare(registration, references, models), unready
    )
    assert report["scoring"] == direct
    assert direct["status"] == "PACK_NOT_READY"
    assert direct["ranking"] is None
    assert direct["models"] == []
