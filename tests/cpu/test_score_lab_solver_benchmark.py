"""Synthetic-only receiver checks; no Challenge physics or solver execution."""

import json
import subprocess
import sys
from copy import deepcopy

import pytest

from carbon.scoring.engine import ScoreEngine
from carbon.scoring.solver_benchmark_v2 import BenchmarkScoreRefused, register_pack
from scripts.dev.score_lab import solver_benchmark as bench
from scripts.dev.score_lab.__main__ import main


def fixture():
    registration = bench.register(
        {
            "schema": bench.SCHEMA,
            "scope": "SYNTHETIC_DEVELOPMENT",
            "challenge": "toy-field",
            "job_digest": "sha256:toy-job",
            "train_digest": "sha256:toy-train",
            "output": {
                "quantity": "field",
                "unit": "toy-unit",
                "size": 2,
                "metric": "mean_absolute_error",
            },
            "reference": {
                "solver_digest": "sha256:toy-solver",
                "fidelity_digest": "sha256:toy-fidelity",
                "applicability_digest": "sha256:toy-claim",
            },
            "cases": [
                {"id": "p1", "role": "P", "weight": 1},
                {"id": "p2", "role": "P", "weight": 2},
                {"id": "q1", "role": "Q", "weight": 1},
            ],
            "mandatory_gates": ["physics"],
            "timing_profile": {
                "basis": "ready_input_to_comparable_output",
                "model_device": "toy-cpu",
                "solver_device": "toy-cpu",
                "batch_size": 1,
            },
        }
    )
    references = [
        {
            "id": cid,
            "status": "RESOLVED",
            "outputs": [1.0, 3.0],
            "elapsed_s": 10.0,
            "source": "MEASURED_SOLVER_RUN",
            "applicability_digest": "sha256:toy-claim",
            "peak_memory_bytes": 1024,
        }
        for cid in ("p1", "p2", "q1")
    ]

    def model(name, prediction, seconds, gate=True):
        return {
            "artifact_digest": name,
            "train_digest": "sha256:toy-train",
            "build_seconds": 60.0,
            "cases": [
                {
                    "id": cid,
                    "status": "OK",
                    "source": "MEASURED_INFERENCE_RUN",
                    "outputs": list(prediction),
                    "gates": {"physics": gate},
                    "timing_s": {
                        "preprocess": 0.1,
                        "export": 0.1,
                        "inference": seconds - 0.3,
                        "postprocess": 0.1,
                    },
                    "peak_memory_bytes": 128,
                }
                for cid in ("p1", "p2", "q1")
            ],
        }

    return registration, references, model


def test_accuracy_and_speed_are_separate_without_a_policy_winner():
    registration, references, model = fixture()
    accurate = model("accurate", [1.0, 3.0], 2.0)
    fast = model("fast", [1.5, 3.5], 1.0)
    result = bench.compare(registration, references, [accurate, fast])
    assert result["ranking"] is None
    assert result["models"][0]["by_role"]["P"]["mean_absolute_error"] == 0.0
    assert result["models"][0]["by_role"]["P"]["paired_speedup"] == 5.0
    assert result["models"][1]["by_role"]["P"]["mean_absolute_error"] == 0.5
    assert result["models"][1]["by_role"]["P"]["paired_speedup"] == pytest.approx(10.0)
    assert result["models"][0]["by_role"]["Q"]["attempted"] == 1
    assert [m["pareto_p"] for m in result["models"]] == [True, True]


def test_mandatory_gate_failure_cannot_be_offset_by_speed():
    registration, references, model = fixture()
    unsafe = model("unsafe", [1.0, 3.0], 0.5, gate=False)
    role = bench.compare(registration, references, [unsafe])["models"][0]["by_role"][
        "P"
    ]
    assert role["status"] == "SCIENTIFIC_INADMISSIBLE"
    assert role["mandatory_gates_pass"] is False
    assert role["gate_failures"] == {"physics": 2}
    assert role["counts"]["scientific_inadmissible"] == 2
    assert role["paired_speedup"] == pytest.approx(20.0)


def test_reference_unresolved_is_common_and_never_candidate_failure():
    registration, references, model = fixture()
    references[0] = {"id": "p1", "status": "UNRESOLVED"}
    result = bench.compare(
        registration,
        references,
        [model("a", [1.0, 3.0], 2.0), model("b", [2.0, 4.0], 1.0)],
    )
    for member in result["models"]:
        role = member["by_role"]["P"]
        assert role["status"] == "INDETERMINATE_EVIDENCE"
        assert role["counts"]["reference_unresolved"] == 1
        assert role["counts"]["candidate_invalid"] == 0
        assert role["mean_absolute_error"] is None
        assert role["paired_speedup"] is None


def test_noncommon_roster_and_cached_solver_timing_refused():
    registration, references, model = fixture()
    bad = model("bad", [1.0, 3.0], 2.0)
    bad["cases"].pop()
    with pytest.raises(bench.BenchmarkRefused, match="model_case_roster"):
        bench.compare(registration, references, [bad])
    cached = deepcopy(references)
    cached[0]["source"] = "CACHED_REFERENCE_LOOKUP"
    with pytest.raises(bench.BenchmarkRefused, match="solver_measurement_required"):
        bench.compare(registration, cached, [model("good", [1.0, 3.0], 2.0)])
    unmeasured = model("unmeasured", [1.0, 3.0], 2.0)
    unmeasured["cases"][0]["source"] = "CACHED_PREDICTION"
    with pytest.raises(bench.BenchmarkRefused, match="model_measurement_required"):
        bench.compare(registration, references, [unmeasured])


def test_changed_registration_identity_refused():
    registration, references, model = fixture()
    registration["output"]["unit"] = "different-unit"
    with pytest.raises(bench.BenchmarkRefused, match="registration_digest"):
        bench.compare(registration, references, [model("good", [1.0, 3.0], 2.0)])


def test_train_and_reference_claim_must_match_registration():
    registration, references, model = fixture()
    wrong_train = model("wrong-train", [1.0, 3.0], 2.0)
    wrong_train["train_digest"] = "sha256:other-train"
    with pytest.raises(bench.BenchmarkRefused, match="model_train_identity"):
        bench.compare(registration, references, [wrong_train])
    references[0]["applicability_digest"] = "sha256:other-claim"
    with pytest.raises(bench.BenchmarkRefused, match="solver_measurement_required"):
        bench.compare(registration, references, [model("good", [1.0, 3.0], 2.0)])


def test_nonfinite_prediction_is_candidate_invalid_not_a_dropped_case():
    registration, references, model = fixture()
    bad = model("bad", [1.0, 3.0], 2.0)
    bad["cases"][0]["outputs"][0] = float("nan")
    role = bench.compare(registration, references, [bad])["models"][0]["by_role"]["P"]
    assert role["status"] == "CANDIDATE_INVALID"
    assert role["counts"]["candidate_invalid"] == 1
    assert role["attempted"] == 2
    assert role["mean_absolute_error"] is None
    assert role["paired_speedup"] is None


def test_dominated_eligible_model_is_labelled_without_scalar_ranking():
    registration, references, model = fixture()
    good = model("good", [1.0, 3.0], 1.0)
    worse = model("worse", [1.5, 3.5], 2.0)
    result = bench.compare(registration, references, [good, worse])
    assert [m["pareto_p"] for m in result["models"]] == [True, False]
    assert result["ranking"] is None


def test_reference_and_model_infrastructure_failures_are_distinct():
    registration, references, model = fixture()
    references[0] = {"id": "p1", "status": "FAILED_INFRA"}
    candidate = model("candidate", [1.0, 3.0], 1.0)
    candidate["cases"][1] = {"id": "p2", "status": "FAILED_INFRA"}
    role = bench.compare(registration, references, [candidate])["models"][0]["by_role"][
        "P"
    ]
    assert role["status"] == "FAILED_INFRA"
    assert role["counts"]["reference_infra"] == 1
    assert role["counts"]["candidate_infra"] == 1
    assert role["counts"]["scientific_inadmissible"] == 0
    assert role["paired_speedup"] is None


def test_scorelab_and_direct_scoring_engine_use_the_same_versioned_rule():
    registration, references, model = fixture()
    pack = register_pack(
        {
            "schema": "carbon.scoring.solver-benchmark-pack.v2",
            "scope": "SYNTHETIC_DEVELOPMENT",
            "challenge": "toy-field",
            "benchmark_registration_digest": registration["registration_digest"],
            "output": {
                "quantity": "field",
                "unit": "toy-unit",
                "metric": "mean_absolute_error",
            },
            "hard_gates": ["physics"],
            "accuracy_ceiling": 0.25,
            "performance_objective": "maximize_paired_speedup",
        }
    )
    accurate = model("accurate", [1.0, 3.0], 2.0)
    too_inaccurate = model("too-inaccurate", [1.5, 3.5], 0.5)
    unsafe = model("unsafe", [1.0, 3.0], 0.5, gate=False)
    workbench = bench.compare(
        registration, references, [accurate, too_inaccurate, unsafe], score_pack=pack
    )
    unscored = bench.compare(
        registration, references, [accurate, too_inaccurate, unsafe]
    )
    direct_validator_style = ScoreEngine.score_solver_benchmark_v2(unscored, pack)
    assert workbench["scoring"] == direct_validator_style
    assert direct_validator_style["ranking"] == ["accurate"]
    assert [row["status"] for row in direct_validator_style["models"]] == [
        "SCORED_DEVELOPMENT",
        "ACCURACY_INELIGIBLE",
        "SCIENTIFIC_INADMISSIBLE",
    ]


def test_unready_pack_refuses_to_select_a_model():
    registration, references, model = fixture()
    pack = register_pack(
        {
            "schema": "carbon.scoring.solver-benchmark-pack.v2",
            "scope": "SYNTHETIC_DEVELOPMENT",
            "challenge": "toy-field",
            "benchmark_registration_digest": registration["registration_digest"],
            "output": {
                "quantity": "field",
                "unit": "toy-unit",
                "metric": "mean_absolute_error",
            },
            "hard_gates": ["physics"],
            "accuracy_ceiling": None,
            "performance_objective": "maximize_paired_speedup",
        }
    )
    result = bench.compare(
        registration, references, [model("fast", [1.0, 3.0], 0.5)], score_pack=pack
    )
    assert result["scoring"]["status"] == "PACK_NOT_READY"
    assert result["scoring"]["ranking"] is None


def test_direct_engine_refuses_a_forged_gate_pass():
    registration, references, model = fixture()
    pack = register_pack(
        {
            "schema": "carbon.scoring.solver-benchmark-pack.v2",
            "scope": "SYNTHETIC_DEVELOPMENT",
            "challenge": "toy-field",
            "benchmark_registration_digest": registration["registration_digest"],
            "output": {
                "quantity": "field",
                "unit": "toy-unit",
                "metric": "mean_absolute_error",
            },
            "hard_gates": ["physics"],
            "accuracy_ceiling": 0.25,
            "performance_objective": "maximize_paired_speedup",
        }
    )
    measured = bench.compare(
        registration, references, [model("unsafe", [1.0, 3.0], 0.5, gate=False)]
    )
    forged = deepcopy(measured)
    forged["models"][0]["by_role"]["P"]["status"] = "MEASURED_DEVELOPMENT"
    forged["models"][0]["by_role"]["P"]["mandatory_gates_pass"] = True
    with pytest.raises(BenchmarkScoreRefused, match="benchmark_status"):
        ScoreEngine.score_solver_benchmark_v2(forged, pack)


def test_finite_inputs_cannot_overflow_into_a_retained_result():
    registration, references, model = fixture()
    huge_time = model("huge-time", [1.0, 3.0], 2.0)
    huge_time["cases"][0]["timing_s"] = {
        "preprocess": 1e308,
        "export": 1e308,
        "inference": 1e308,
        "postprocess": 1e308,
    }
    with pytest.raises(bench.BenchmarkRefused, match="derived_nonfinite"):
        bench.compare(registration, references, [huge_time])
    huge_error = model("huge-error", [1.0, 3.0], 2.0)
    huge_error["cases"][0]["outputs"] = [1e308, -1e308]
    references[0]["outputs"] = [-1e308, 1e308]
    with pytest.raises(bench.BenchmarkRefused, match="derived_nonfinite"):
        bench.compare(registration, references, [huge_error])


def test_producer_cli_uses_the_same_receiver_without_printing_case_ids(
    tmp_path, capsys
):
    registration, references, model = fixture()
    evidence = tmp_path / "evidence.json"
    output = tmp_path / "result.json"
    evidence.write_text(
        json.dumps(
            {
                "registration": registration,
                "references": references,
                "models": [model("toy-model", [1.0, 3.0], 2.0)],
            }
        ),
        encoding="utf-8",
    )
    assert main(["benchmark", "--input", str(evidence), "--out", str(output)]) == 0
    assert (
        json.loads(output.read_text(encoding="utf-8"))["models"][0]["artifact_digest"]
        == "toy-model"
    )
    assert "p1" not in capsys.readouterr().out


def test_active_benchmark_import_does_not_load_historical_battery_lab():
    code = (
        "import sys; "
        "from scripts.dev.score_lab.__main__ import main; "
        "main(['benchmark', '--help']); "
    )
    help_run = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )
    assert help_run.returncode == 0
    assert "producer-only" in help_run.stdout.lower()
    boundary_code = (
        "import sys; from scripts.dev.score_lab.__main__ import main; "
        "from scripts.dev.score_lab import solver_benchmark; "
        "assert not any(name.startswith('carbon.battery.value') or "
        "name.startswith('scripts.dev.score_lab.campaign_') or "
        "name == 'scripts.dev.score_lab.legacy_cli' "
        "for name in sys.modules)"
    )
    boundary = subprocess.run(
        [
            sys.executable,
            "-c",
            boundary_code,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert boundary.returncode == 0, boundary.stderr
