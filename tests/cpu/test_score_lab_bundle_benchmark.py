"""Synthetic-only binding tests for retained bundle models and shared scoring."""

import json
from copy import deepcopy
from dataclasses import dataclass

import pytest
from test_public_bundle_model_custody import (
    _graph_fixture,
    _graph_retain_mutation,
    _json,
    _sha,
)

from carbon.scoring import bundle_benchmark_core as core_bundle
from carbon.scoring.engine import ScoreEngine
from carbon.scoring.solver_benchmark_v3 import register_pack
from scripts.dev.score_lab import bundle_benchmark as bundle
from scripts.dev.score_lab import public_unbound_custody as custody
from scripts.dev.score_lab import public_unbound_entry as unbound_entry
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
        "fixture_digest": "sha256:" + "f" * 64,
        "prediction_digest": "sha256:toy-predictions",
        "role_manifest_sha256": "sha256:toy-roles",
        "physics_contract": {
            "version": None,
            "definition_digest": None,
            "authenticity": "PENDING",
        },
        "roles": {
            "fixture": {
                "file": "stage/example.npz",
                "codec": "numeric_npz",
                "sha256": "sha256:" + "f" * 64,
            },
            "inputs": {
                "file": "infer/inputs.npz",
                "codec": "numeric_npz",
                "sha256": "sha256:" + "e" * 64,
            },
        },
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


def test_core_and_workbench_bundle_paths_keep_digest_and_custody_refusal():
    entry, receipt, job, registration, refs, measurement, pack = fixture()
    workbench = bundle.benchmark_saved_entry(
        entry, receipt, job, registration, refs, measurement, pack
    )
    core = core_bundle.benchmark_saved_entry(
        entry, receipt, job, registration, refs, measurement, pack
    )
    assert workbench == core
    assert workbench["result_digest"] == core["result_digest"]
    assert bundle.benchmark_saved_entry is core_bundle.benchmark_saved_entry
    with pytest.raises(bundle.BundleBenchmarkRefused, match="custody_binding"):
        core_bundle.benchmark_saved_entry(
            entry, receipt + b" ", job, registration, refs, measurement, pack
        )


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


def test_saved_v2_worker_receipt_maps_to_one_measured_v3_query():
    entry, receipt, job, serial, refs, _, _ = fixture()
    body = deepcopy(serial)
    body.pop("registration_digest")
    body["schema"] = bench.SCHEMA_V3
    body["output"].update({"size": 128, "shape": [2, 8, 8, 1]})
    body["reference"]["evidence_kind"] = bench.ENGINEERING_REFERENCE
    body["timing_profile"].update(
        {"batch_size": 2, "query_unit": "complete_batch", "input_shape": [2, 8, 8, 1]}
    )
    registration = bench.register(body)
    refs[0].update(
        {
            "outputs": [1.0] * 128,
            "source": "MEASURED_ENGINEERING_REFERENCE_RUN",
            "peak_memory_bytes": None,
        }
    )
    predictions = [[[[1.1] for _ in range(8)] for _ in range(8)] for _ in range(2)]
    prediction_bytes = bundle._canonical(predictions)[:-1]
    inference = {
        "recipe_digest": entry["recipe_digest"],
        "state_digest": entry["state_digest"],
        "predictions_digest": bundle._sha(prediction_bytes),
        "predictions": predictions,
        "worker_operation": "operation-" + "a" * 64,
        "receipt": {
            "schema": "carbon.development.bundle-inference.v2",
            "recipe_digest": entry["recipe_digest"],
            "state_digest": entry["state_digest"],
            "inputs_digest": entry["roles"]["inputs"]["sha256"],
            "predictions_digest": bundle._sha(prediction_bytes),
            "measurement": {
                "scope": "COLD_SINGLE_WORKER_QUERY_INCLUDES_GRAPH_LOAD_AND_JAX_COMPILE",
                "timing_s": {
                    "preprocess": 0.1,
                    "inference": 1.7,
                    "postprocess": 0.1,
                    "export": 0.1,
                },
                "input_shape": [2, 8, 8, 1],
                "input_dtype": "float32",
                "output_shape": [2, 8, 8, 1],
                "output_dtype": "float32",
            },
        },
    }

    @dataclass(frozen=True)
    class WorkerResult:
        recipe_digest: str
        state_digest: str
        predictions_digest: str
        predictions: list
        worker_operation: str
        receipt: dict

    measured = bundle.measurement_from_saved_inference(
        entry, registration, WorkerResult(**inference), gates={"toy_gate": True}
    )
    assert entry["fixture_digest"] != inference["receipt"]["inputs_digest"]
    assert measured["build_seconds"] is None
    assert measured["cases"][0]["peak_memory_bytes"] is None
    result = bundle.benchmark_saved_entry(
        entry, receipt, job, registration, refs, measured
    )
    assert result["status"] == "BENCHMARK_REDUCED"
    assert result["score_status"] == "PACK_NOT_READY"
    assert result["benchmark"]["models"][0]["by_role"]["P"]["paired_speedup"] == 4.0

    broken = deepcopy(inference)
    broken["receipt"]["inputs_digest"] = entry["fixture_digest"]
    with pytest.raises(bundle.BundleBenchmarkRefused, match="saved_inference_binding"):
        bundle.measurement_from_saved_inference(
            entry, registration, broken, gates={"toy_gate": True}
        )
    missing_role = deepcopy(entry)
    del missing_role["roles"]["inputs"]
    with pytest.raises(bundle.BundleBenchmarkRefused, match="saved_inference_binding"):
        bundle.measurement_from_saved_inference(
            missing_role, registration, inference, gates={"toy_gate": True}
        )
    broken = deepcopy(inference)
    broken["predictions"][0][0][0][0] = 9.0
    with pytest.raises(bundle.BundleBenchmarkRefused, match="saved_prediction_digest"):
        bundle.measurement_from_saved_inference(
            entry, registration, broken, gates={"toy_gate": True}
        )
    with pytest.raises(bundle.BundleBenchmarkRefused, match="saved_inference_shape"):
        bundle.measurement_from_saved_inference(
            entry, registration, inference, gates={}
        )


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


def test_v2_still_requires_numeric_memory_evidence():
    entry, receipt, job, registration, refs, measurement, pack = fixture()
    refs[0]["peak_memory_bytes"] = None
    with pytest.raises(bench.BenchmarkRefused, match="nonfinite_measurement"):
        bundle.benchmark_saved_entry(
            entry, receipt, job, registration, refs, measurement, pack
        )
    refs[0]["peak_memory_bytes"] = 64
    measurement["build_seconds"] = None
    with pytest.raises(bench.BenchmarkRefused, match="nonfinite_measurement"):
        bundle.benchmark_saved_entry(
            entry, receipt, job, registration, refs, measurement, pack
        )


def test_graph_v3_original_worker_measurement_reaches_same_unready_engine(tmp_path):
    root, manifest, originals = _graph_fixture(tmp_path)
    custody_receipt = custody.prepare_custody_v5(root, manifest)
    receipt_path = tmp_path / "custody.json"
    receipt_path.write_bytes(_json(custody_receipt))
    entries = tmp_path / "entries"
    entries.mkdir()
    graph_entry = unbound_entry.create_entry_v5(root, manifest, receipt_path, entries)[
        "entry"
    ]
    assert custody_receipt["environment_digest"] is None
    assert graph_entry["environment_digest"] is None
    assert "environment" not in graph_entry["roles"]
    physics = json.loads(manifest.read_bytes())["physics_contract"]
    job = {
        "challenge": graph_entry["challenge"],
        "challenge_version": graph_entry["challenge_version"],
        "interface_digest": graph_entry["interface_digest"],
        "train_digest": graph_entry["train_digest"],
        "job_digest": _sha(b"toy-graph-job"),
        "physics_contract": physics,
    }
    registration = bench.register(
        {
            "schema": bench.SCHEMA_V3,
            "scope": "SYNTHETIC_DEVELOPMENT",
            "challenge": job["challenge"],
            "job_digest": job["job_digest"],
            "train_digest": job["train_digest"],
            "physics_contract": physics,
            "output": {
                "quantity": "toy-output",
                "unit": "toy-unit",
                "size": 1,
                "shape": [1, 1, 1, 1],
                "metric": "mean_absolute_error",
            },
            "reference": {
                "solver_digest": _sha(b"toy-solver"),
                "fidelity_digest": _sha(b"toy-fidelity"),
                "applicability_digest": _sha(b"toy-applicability"),
                "evidence_kind": bench.ENGINEERING_REFERENCE,
            },
            "cases": [{"id": "toy-case", "role": "P", "weight": 1.0}],
            "mandatory_gates": ["toy_gate"],
            "timing_profile": {
                "basis": "ready_input_to_comparable_output",
                "model_device": "toy-model-device",
                "solver_device": "toy-solver-device",
                "batch_size": 1,
                "query_unit": "complete_batch",
                "input_shape": [1, 1, 1, 1],
            },
        }
    )
    worker = json.loads(originals["stage/worker-evidence.json"])
    inference = {
        "recipe_digest": graph_entry["recipe_digest"],
        "state_digest": graph_entry["state_digest"],
        "predictions_digest": graph_entry["prediction_digest"],
        "predictions": json.loads(originals["infer/output/predictions.json"]),
        "worker_operation": worker["inference_operation"],
        "receipt": worker["inference_receipt"],
        "inference_receipt_raw": originals["infer/output/receipt.json"],
        "worker_evidence_raw": originals["stage/worker-evidence.json"],
    }
    measured = bundle.measurement_from_saved_inference(
        graph_entry, registration, inference, gates={"toy_gate": True}
    )
    graph_originals = {
        "inference_receipt_raw": originals["infer/output/receipt.json"],
        "worker_evidence_raw": originals["stage/worker-evidence.json"],
    }
    changed_timing = deepcopy(inference)
    changed_timing["receipt"]["measurement"]["timing_s"]["inference"] += 1.0
    with pytest.raises(bundle.BundleBenchmarkRefused, match="graph"):
        bundle.measurement_from_saved_inference(
            graph_entry, registration, changed_timing, gates={"toy_gate": True}
        )
    changed_operation = deepcopy(inference)
    changed_operation["worker_operation"] = "operation-" + "f" * 64
    with pytest.raises(
        bundle.BundleBenchmarkRefused, match="graph_saved_inference_binding"
    ):
        bundle.measurement_from_saved_inference(
            graph_entry, registration, changed_operation, gates={"toy_gate": True}
        )
    changed_original = deepcopy(inference)
    changed_original["inference_receipt_raw"] = _json(changed_timing["receipt"])
    with pytest.raises(
        bundle.BundleBenchmarkRefused, match="graph_saved_original_binding"
    ):
        bundle.measurement_from_saved_inference(
            graph_entry, registration, changed_original, gates={"toy_gate": True}
        )
    physics_id = bench.physics_contract_identity(physics)
    references = [
        {
            "id": "toy-case",
            "status": "RESOLVED",
            "outputs": [0.25],
            "elapsed_s": 8.0,
            "source": "MEASURED_ENGINEERING_REFERENCE_RUN",
            "solver_digest": registration["reference"]["solver_digest"],
            "fidelity_digest": registration["reference"]["fidelity_digest"],
            "applicability_digest": registration["reference"]["applicability_digest"],
            "physics_contract_digest": physics_id["definition_digest"],
            "peak_memory_bytes": None,
        }
    ]
    forged_receipt = deepcopy(custody_receipt)
    forged_receipt["environment_digest"] = _sha(b"forged-environment")
    forged_entry = deepcopy(graph_entry)
    forged_entry["environment_digest"] = forged_receipt["environment_digest"]
    forged_receipt_raw = _json(forged_receipt)
    forged_entry["custody_receipt"]["sha256"] = _sha(forged_receipt_raw)
    forged_entry["custody_receipt"]["bytes"] = len(forged_receipt_raw)
    forged_entry["entry_id"] = _sha(
        _json({key: value for key, value in forged_entry.items() if key != "entry_id"})
        + b"\n"
    )
    with pytest.raises(bundle.BundleBenchmarkRefused, match="graph_custody_binding"):
        bundle.benchmark_saved_entry(
            forged_entry,
            forged_receipt_raw,
            job,
            registration,
            references,
            measured,
            graph_originals=graph_originals,
        )
    reduced = bundle.benchmark_saved_entry(
        graph_entry,
        _json(custody_receipt),
        job,
        registration,
        references,
        measured,
        graph_originals=graph_originals,
    )
    assert reduced["status"] == "BENCHMARK_REDUCED"
    assert reduced["score_status"] == "PACK_NOT_READY"
    assert reduced["benchmark"]["models"][0]["by_role"]["P"]["status"] == (
        "MEASURED_DEVELOPMENT"
    )
    assert reduced["benchmark"]["models"][0]["by_role"]["P"]["paired_speedup"] == 16.0
    assert "graph_originals" not in reduced
    with pytest.raises(
        bundle.BundleBenchmarkRefused, match="graph_measurement_originals"
    ):
        bundle.benchmark_saved_entry(
            graph_entry, _json(custody_receipt), job, registration, references, measured
        )

    alternate_dir = tmp_path / "alternate"
    alternate_dir.mkdir()
    alt_root = alternate_dir / "producer"
    alt_root.mkdir()
    alt_manifest = alternate_dir / "roles.json"
    alt_manifest.write_bytes(manifest.read_bytes())
    alt_originals = dict(originals)
    for path, raw in alt_originals.items():
        destination = alt_root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
    alt_receipt = json.loads(alt_originals["infer/output/receipt.json"])
    alt_receipt["measurement"]["timing_s"]["inference"] += 1.0
    alt_worker = json.loads(alt_originals["stage/worker-evidence.json"])
    alt_worker["inference_receipt"] = alt_receipt
    alt_originals["infer/output/receipt.json"] = _json(alt_receipt)
    alt_originals["stage/worker-evidence.json"] = _json(alt_worker)
    _graph_retain_mutation(
        alt_root,
        alt_manifest,
        "inference_receipt",
        alt_originals["infer/output/receipt.json"],
    )
    _graph_retain_mutation(
        alt_root,
        alt_manifest,
        "worker_evidence",
        alt_originals["stage/worker-evidence.json"],
    )
    alt_custody = custody.prepare_custody_v5(alt_root, alt_manifest)
    alt_receipt_path = alternate_dir / "custody.json"
    alt_receipt_path.write_bytes(_json(alt_custody))
    alt_entries = alternate_dir / "entries"
    alt_entries.mkdir()
    alt_entry = unbound_entry.create_entry_v5(
        alt_root, alt_manifest, alt_receipt_path, alt_entries
    )["entry"]
    assert alt_entry["entry_id"] != graph_entry["entry_id"]
    assert alt_entry["recipe_digest"] == graph_entry["recipe_digest"]
    assert alt_entry["state_digest"] == graph_entry["state_digest"]
    alt_inference = {
        **inference,
        "receipt": alt_receipt,
        "inference_receipt_raw": alt_originals["infer/output/receipt.json"],
        "worker_evidence_raw": alt_originals["stage/worker-evidence.json"],
    }
    alt_measured = bundle.measurement_from_saved_inference(
        alt_entry, registration, alt_inference, gates={"toy_gate": True}
    )
    swapped = {**alt_measured, "entry_id": graph_entry["entry_id"]}
    with pytest.raises(
        bundle.BundleBenchmarkRefused, match="graph_saved_original_binding"
    ):
        bundle.benchmark_saved_entry(
            graph_entry,
            _json(custody_receipt),
            job,
            registration,
            references,
            swapped,
            graph_originals={
                "inference_receipt_raw": alt_originals["infer/output/receipt.json"],
                "worker_evidence_raw": alt_originals["stage/worker-evidence.json"],
            },
        )
    assert reduced["benchmark"]["scoring"] == ScoreEngine.score_solver_benchmark_v3(
        reduced["benchmark"],
        register_pack(
            {
                "schema": "carbon.scoring.solver-benchmark-pack.v3",
                "scope": registration["scope"],
                "challenge": registration["challenge"],
                "benchmark_registration_digest": registration["registration_digest"],
                "physics_contract": physics_id,
                "output": {
                    "quantity": "toy-output",
                    "unit": "toy-unit",
                    "metric": "mean_absolute_error",
                },
                "hard_gates": ["toy_gate"],
                "accuracy_ceiling": None,
                "performance_objective": "maximize_paired_speedup",
            }
        ),
    )
    infra = bundle.benchmark_saved_entry(
        graph_entry,
        _json(custody_receipt),
        job,
        registration,
        [{"id": "toy-case", "status": "FAILED_INFRA"}],
        measured,
        graph_originals=graph_originals,
    )
    role = infra["benchmark"]["models"][0]["by_role"]["P"]
    assert role["status"] == "FAILED_INFRA"
    assert role["counts"]["reference_infra"] == 1
    assert role["counts"]["candidate_invalid"] == 0
