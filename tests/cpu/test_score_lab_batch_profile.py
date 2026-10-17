"""Synthetic complete-batch timing contract; no solver or model execution."""

from copy import deepcopy

import pytest

from carbon.scoring.engine import ScoreEngine
from carbon.scoring.solver_benchmark_v3 import register_pack
from scripts.dev.score_lab import solver_benchmark as bench

PHYSICS = {"version": "toy-v1", "definition": {"relation": "synthetic identity"}}
PHYSICS_ID = bench.physics_contract_identity(PHYSICS)
SHAPE = [2, 8, 8, 1]


def fixture():
    registration = bench.register(
        {
            "schema": bench.SCHEMA_V3,
            "scope": "SYNTHETIC_DEVELOPMENT",
            "challenge": "toy-batch",
            "job_digest": "sha256:toy-job",
            "train_digest": "sha256:toy-train",
            "physics_contract": PHYSICS,
            "output": {
                "quantity": "toy-field",
                "unit": "toy-unit",
                "size": 128,
                "shape": SHAPE,
                "metric": "mean_absolute_error",
            },
            "reference": {
                "solver_digest": "sha256:toy-engineering-compute",
                "fidelity_digest": "sha256:toy-fidelity",
                "applicability_digest": "sha256:toy-applicability",
                "evidence_kind": bench.ENGINEERING_REFERENCE,
            },
            "cases": [
                {"id": "p1", "role": "P", "weight": 1},
                {"id": "p2", "role": "P", "weight": 1},
            ],
            "mandatory_gates": ["toy-gate"],
            "timing_profile": {
                "basis": "ready_input_to_comparable_output",
                "model_device": "toy-cpu",
                "solver_device": "toy-cpu",
                "batch_size": 2,
                "query_unit": "complete_batch",
                "input_shape": SHAPE,
            },
        }
    )
    references = [
        {
            "id": cid,
            "status": "RESOLVED",
            "outputs": [1.0] * 128,
            "elapsed_s": 10.0,
            "source": "MEASURED_ENGINEERING_REFERENCE_RUN",
            "solver_digest": "sha256:toy-engineering-compute",
            "fidelity_digest": "sha256:toy-fidelity",
            "applicability_digest": "sha256:toy-applicability",
            "physics_contract_digest": PHYSICS_ID["definition_digest"],
            "peak_memory_bytes": 1024,
        }
        for cid in ("p1", "p2")
    ]
    model = {
        "artifact_digest": "sha256:toy-model",
        "job_digest": "sha256:toy-job",
        "train_digest": "sha256:toy-train",
        "physics_contract_digest": PHYSICS_ID["definition_digest"],
        "build_seconds": 1.0,
        "cases": [
            {
                "id": cid,
                "status": "OK",
                "source": "MEASURED_INFERENCE_RUN",
                "outputs": [1.0] * 128,
                "gates": {"toy-gate": True},
                "timing_s": {
                    "preprocess": 0.1,
                    "export": 0.1,
                    "inference": 1.7,
                    "postprocess": 0.1,
                },
                "peak_memory_bytes": 512,
            }
            for cid in ("p1", "p2")
        ],
    }
    return registration, references, model


def test_complete_batches_are_whole_queries_not_divided_by_batch_size():
    registration, references, model = fixture()
    result = bench.compare(registration, references, [model])
    role = result["models"][0]["by_role"]["P"]
    assert result["measurement_profile"] == {
        "registration_schema": bench.SCHEMA_V3,
        "query_unit": "complete_batch",
        "batch_size": 2,
        "input_shape": SHAPE,
        "output_shape": SHAPE,
        "reference_evidence_kind": bench.ENGINEERING_REFERENCE,
        "reference_physics_qualified": False,
    }
    assert role["solver_seconds"] == 20.0
    assert role["model_seconds"] == pytest.approx(4.0)
    assert role["paired_speedup"] == pytest.approx(5.0)
    assert role["observed_serial_queries_per_second"] == pytest.approx(0.5)
    assert role["solver_query_latency"]["median_s"] == 10.0
    assert role["model_query_latency"]["median_s"] == pytest.approx(2.0)


def test_v3_unmeasured_peak_memory_does_not_block_measured_accuracy_and_speed():
    registration, references, model = fixture()
    for row in references:
        row["peak_memory_bytes"] = None
    for row in model["cases"]:
        row["peak_memory_bytes"] = None
    model["build_seconds"] = None
    result = bench.compare(registration, references, [model])
    p = result["models"][0]["by_role"]["P"]
    assert result["models"][0]["build_seconds"] is None
    assert p["status"] == "MEASURED_DEVELOPMENT"
    assert p["mean_absolute_error"] == 0.0
    assert p["paired_speedup"] == pytest.approx(5.0)
    assert p["model_peak_memory_bytes"] is None
    assert p["solver_peak_memory_bytes"] is None


def test_complete_batch_result_keeps_score_engine_v3_parity():
    registration, references, model = fixture()
    pack = register_pack(
        {
            "schema": "carbon.scoring.solver-benchmark-pack.v3",
            "scope": "SYNTHETIC_DEVELOPMENT",
            "challenge": "toy-batch",
            "benchmark_registration_digest": registration["registration_digest"],
            "physics_contract": PHYSICS_ID,
            "output": {
                "quantity": "toy-field",
                "unit": "toy-unit",
                "metric": "mean_absolute_error",
            },
            "hard_gates": ["toy-gate"],
            "accuracy_ceiling": 0.1,
            "performance_objective": "maximize_paired_speedup",
        }
    )
    report = bench.compare(registration, references, [model], score_pack=pack)
    direct = ScoreEngine.score_solver_benchmark_v3(
        bench.compare(registration, references, [model]), pack
    )
    assert report["scoring"] == direct
    assert direct["models"][0]["status"] == "SCORED_DEVELOPMENT"


@pytest.mark.parametrize(
    "path,value",
    [
        (("output", "size"), 64),
        (("output", "shape"), [2, 8, 8, 0]),
        (("output", "shape"), [1, 8, 8, 2]),
        (("timing_profile", "input_shape"), [1, 8, 8, 1]),
        (("timing_profile", "query_unit"), "per_sample"),
        (("reference", "evidence_kind"), "PHYSICALLY_QUALIFIED"),
    ],
)
def test_profile_refuses_shape_or_reference_overclaim(path, value):
    registration, _, _ = fixture()
    body = {
        k: deepcopy(v) for k, v in registration.items() if k != "registration_digest"
    }
    body[path[0]][path[1]] = value
    with pytest.raises(bench.BenchmarkRefused):
        bench.register(body)


def test_cached_or_solver_label_cannot_stand_in_for_engineering_run():
    registration, references, model = fixture()
    for label in ("CACHED_REFERENCE", "MEASURED_SOLVER_RUN"):
        changed = deepcopy(references)
        changed[0]["source"] = label
        with pytest.raises(
            bench.BenchmarkRefused,
            match="engineering_reference_measurement_required",
        ):
            bench.compare(registration, changed, [model])


def test_partial_batch_outputs_are_refused():
    registration, references, model = fixture()
    references[0]["outputs"] = [1.0] * 64
    with pytest.raises(bench.BenchmarkRefused, match="output_shape"):
        bench.compare(registration, references, [model])
