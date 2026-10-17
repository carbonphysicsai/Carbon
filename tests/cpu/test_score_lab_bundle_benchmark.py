"""Synthetic-only binding tests for retained bundle models and shared scoring."""

from copy import deepcopy

import pytest

from carbon.scoring.engine import ScoreEngine
from carbon.scoring.solver_benchmark_v3 import register_pack
from scripts.dev.score_lab import bundle_benchmark as bundle
from scripts.dev.score_lab import solver_benchmark as bench


def fixture():
    physics = {"version": "toy-v1", "definition": {"relation": "toy-only"}}
    physics_id = bench.physics_contract_identity(physics)
    job = {
        "challenge": "toy",
        "challenge_version": "toy-v1",
        "interface_digest": "sha256:toy-interface",
        "train_digest": "sha256:toy-train",
        "job_digest": "sha256:toy-job",
        "physics_contract": physics,
    }
    registration = bench.register(
        {
            "schema": bench.SCHEMA,
            "scope": "SYNTHETIC_DEVELOPMENT",
            "challenge": "toy",
            "job_digest": job["job_digest"],
            "train_digest": job["train_digest"],
            "physics_contract": physics,
            "output": {
                "quantity": "toy-field",
                "unit": "toy-unit",
                "size": 1,
                "metric": "mean_absolute_error",
            },
            "reference": {
                "solver_digest": "sha256:toy-compute",
                "fidelity_digest": "sha256:toy-fidelity",
                "applicability_digest": "sha256:toy-applicability",
            },
            "cases": [{"id": "p1", "role": "P", "weight": 1.0}],
            "mandatory_gates": ["toy_gate"],
            "timing_profile": {
                "basis": "ready_input_to_comparable_output",
                "model_device": "toy-cpu",
                "solver_device": "toy-cpu",
                "batch_size": 1,
            },
        }
    )
    receipt = {
        "schema": bundle.CUSTODY_SCHEMA,
        "source_schema": "toy-source",
        "scope": "PUBLIC_DEVELOPMENT_BUNDLE_MODEL",
        "challenge": "toy",
        "challenge_version": "toy-v1",
        "interface_digest": job["interface_digest"],
        "train_digest": job["train_digest"],
        "bundle_digest": "sha256:toy-bundle",
        "recipe_digest": "sha256:toy-recipe",
        "state_digest": "sha256:toy-state",
        "prediction_digest": "sha256:toy-predictions",
        "role_manifest_sha256": "sha256:toy-roles",
        "physics_contract": {
            "version": None,
            "definition_digest": None,
            "authenticity": "PENDING",
        },
        "roles": [],
        "original_files": [],
        "custody_state": "PUBLIC_BYTES_REHASHED",
        "official_eligible": False,
    }
    receipt_raw = bundle._canonical(receipt)
    entry = {
        **{key: receipt[key] for key in bundle._ENTRY_BINDINGS},
        "schema": bundle.ENTRY_SCHEMA,
        "custody_receipt": {
            "sha256": bundle._sha(receipt_raw),
            "bytes": len(receipt_raw),
        },
        "admission_state": "NOT_ADMITTED",
        "score_state": "NOT_COMPUTED",
        "official_eligible": False,
    }
    entry["entry_id"] = bundle._sha(bundle._canonical(entry))
    references = [
        {
            "id": "p1",
            "status": "RESOLVED",
            "outputs": [1.0],
            "elapsed_s": 8.0,
            "source": "MEASURED_SOLVER_RUN",
            "solver_digest": registration["reference"]["solver_digest"],
            "fidelity_digest": registration["reference"]["fidelity_digest"],
            "applicability_digest": registration["reference"]["applicability_digest"],
            "physics_contract_digest": physics_id["definition_digest"],
            "peak_memory_bytes": 64,
        }
    ]
    measurement = {
        "schema": bundle.MEASUREMENT_SCHEMA,
        "entry_id": entry["entry_id"],
        "challenge": entry["challenge"],
        "challenge_version": entry["challenge_version"],
        "interface_digest": entry["interface_digest"],
        "recipe_digest": entry["recipe_digest"],
        "state_digest": entry["state_digest"],
        "train_digest": entry["train_digest"],
        "batch_size": 1,
        "input_shape": [1, 1],
        "output_shape": [1, 1],
        "build_seconds": 3.0,
        "cases": [
            {
                "id": "p1",
                "status": "OK",
                "source": "MEASURED_INFERENCE_RUN",
                "outputs": [1.1],
                "gates": {"toy_gate": True},
                "timing_s": {
                    "preprocess": 0.1,
                    "export": 0.1,
                    "inference": 1.7,
                    "postprocess": 0.1,
                },
                "peak_memory_bytes": 16,
            }
        ],
    }
    pack = register_pack(
        {
            "schema": "carbon.scoring.solver-benchmark-pack.v3",
            "scope": registration["scope"],
            "challenge": registration["challenge"],
            "benchmark_registration_digest": registration["registration_digest"],
            "physics_contract": physics_id,
            "output": {
                "quantity": "toy-field",
                "unit": "toy-unit",
                "metric": "mean_absolute_error",
            },
            "hard_gates": ["toy_gate"],
            "accuracy_ceiling": 0.25,
            "performance_objective": "maximize_paired_speedup",
        }
    )
    return entry, receipt_raw, job, registration, references, measurement, pack


def test_complete_bundle_uses_the_shared_validator_score_engine():
    entry, receipt, job, registration, refs, measurement, pack = fixture()
    result = bundle.benchmark_saved_entry(
        entry, receipt, job, registration, refs, measurement, pack
    )
    assert result["status"] == "BENCHMARK_REDUCED"
    assert result["score_status"] == "DEVELOPMENT_ONLY"
    assert result["scope"] == "SYNTHETIC_DEVELOPMENT"
    assert result["score_pack_digest"] == pack["pack_digest"]
    shared = ScoreEngine.score_solver_benchmark_v3(
        bench.compare(
            registration,
            refs,
            [
                bundle._measurement_model(
                    measurement,
                    entry,
                    job,
                    registration,
                    bench.physics_contract_identity(job["physics_contract"]),
                )
            ],
        ),
        pack,
    )
    assert result["benchmark"]["scoring"] == shared
    assert result["result_digest"] == bundle._sha(
        bundle._canonical({k: v for k, v in result.items() if k != "result_digest"})
    )


def test_missing_inputs_are_typed_not_ready_and_not_candidate_failures():
    entry, receipt, job, registration, _, _, _ = fixture()
    result = bundle.benchmark_saved_entry(entry, receipt, job, registration, None, None)
    assert result["status"] == "NOT_READY"
    assert result["score_status"] == "NOT_COMPUTED"
    assert result["benchmark"] is None
    assert result["not_ready_reasons"] == [
        "REFERENCE_MEASUREMENTS_MISSING",
        "MODEL_PER_QUERY_MEASUREMENTS_MISSING",
    ]
    assert result["score_pack_source"] == "DERIVED_UNREADY"


def test_pending_physics_only_accepts_a_trusted_matching_job():
    entry, receipt, job, registration, refs, measurement, pack = fixture()
    changed = deepcopy(job)
    changed["physics_contract"]["definition"]["relation"] = "different"
    with pytest.raises(bundle.BundleBenchmarkRefused, match="registration_job_binding"):
        bundle.benchmark_saved_entry(
            entry, receipt, changed, registration, refs, measurement, pack
        )
    changed = deepcopy(measurement)
    changed["state_digest"] = "sha256:other-state"
    with pytest.raises(
        bundle.BundleBenchmarkRefused, match="measurement_entry_binding"
    ):
        bundle.benchmark_saved_entry(
            entry, receipt, job, registration, refs, changed, pack
        )


def test_batch_two_cannot_be_reported_under_serial_registration():
    entry, receipt, job, registration, refs, measurement, pack = fixture()
    measurement["batch_size"] = 2
    measurement["input_shape"] = [2, 1]
    measurement["output_shape"] = [2, 1]
    with pytest.raises(bundle.BundleBenchmarkRefused, match="measurement_batch_shape"):
        bundle.benchmark_saved_entry(
            entry, receipt, job, registration, refs, measurement, pack
        )


def test_registered_batch_two_is_one_measured_engineering_query():
    entry, receipt, job, serial, refs, measurement, _ = fixture()
    body = deepcopy(serial)
    body.pop("registration_digest")
    body["schema"] = bench.SCHEMA_V3
    body["output"]["size"] = 128
    body["output"]["shape"] = [2, 8, 8, 1]
    body["reference"]["evidence_kind"] = bench.ENGINEERING_REFERENCE
    body["timing_profile"].update(
        {
            "batch_size": 2,
            "query_unit": "complete_batch",
            "input_shape": [2, 8, 8, 1],
        }
    )
    registration = bench.register(body)
    refs[0]["outputs"] = [1.0] * 128
    refs[0]["source"] = "MEASURED_ENGINEERING_REFERENCE_RUN"
    measurement["batch_size"] = 2
    measurement["input_shape"] = [2, 8, 8, 1]
    measurement["output_shape"] = [2, 8, 8, 1]
    measurement["cases"][0]["outputs"] = [1.1] * 128
    result = bundle.benchmark_saved_entry(
        entry, receipt, job, registration, refs, measurement
    )
    assert result["status"] == "BENCHMARK_REDUCED"
    assert result["benchmark"]["measurement_profile"]["batch_size"] == 2
    assert (
        result["benchmark"]["measurement_profile"]["reference_physics_qualified"]
        is False
    )
    p = result["benchmark"]["models"][0]["by_role"]["P"]
    assert p["solver_seconds"] == 8.0
    assert p["model_seconds"] == pytest.approx(2.0)
    assert p["paired_speedup"] == pytest.approx(4.0)
    assert result["benchmark"]["scoring"]["status"] == "PACK_NOT_READY"
    assert result["score_status"] == "PACK_NOT_READY"


def test_forged_custody_or_score_pack_is_refused():
    entry, receipt, job, registration, refs, measurement, pack = fixture()
    with pytest.raises(bundle.BundleBenchmarkRefused, match="custody_binding"):
        bundle.benchmark_saved_entry(
            entry, receipt + b" ", job, registration, refs, measurement, pack
        )
    changed = deepcopy(pack)
    changed["accuracy_ceiling"] = 9.0
    with pytest.raises(bundle.BundleBenchmarkRefused, match="score_pack_digest"):
        bundle.benchmark_saved_entry(
            entry, receipt, job, registration, refs, measurement, changed
        )
