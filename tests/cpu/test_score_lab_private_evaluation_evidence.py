"""Synthetic private-evidence binding across the ScoreLab benchmark boundary.

These fixtures are inert original bytes. No model, solver, or hidden panel runs.
"""

from __future__ import annotations

import json
import struct
from copy import deepcopy

import pytest
from test_public_bundle_model_custody import (
    _fixture,
    _graph_fixture,
    _graph_retain_mutation,
    _json,
    _npz,
    _sha,
)

from carbon.scoring import private_evaluation_evidence as private
from carbon.scoring.solver_benchmark_v3 import register_pack
from scripts.dev.score_lab import bundle_benchmark as bundle
from scripts.dev.score_lab import public_unbound_custody as custody
from scripts.dev.score_lab import public_unbound_entry as unbound_entry
from scripts.dev.score_lab import solver_benchmark as benchmark


def _graph_case(tmp_path):
    root, manifest, originals = _graph_fixture(tmp_path)
    custody_receipt = custody.prepare_custody_v5(root, manifest)
    receipt_raw = _json(custody_receipt)
    receipt_path = tmp_path / "custody.json"
    receipt_path.write_bytes(receipt_raw)
    entries = tmp_path / "entries"
    entries.mkdir()
    entry = unbound_entry.create_entry_v5(root, manifest, receipt_path, entries)[
        "entry"
    ]
    physics = json.loads(manifest.read_bytes())["physics_contract"]
    job = {
        "challenge": entry["challenge"],
        "challenge_version": entry["challenge_version"],
        "interface_digest": entry["interface_digest"],
        "train_digest": entry["train_digest"],
        "job_digest": _sha(b"synthetic-evaluation-job"),
        "physics_contract": physics,
    }
    registration = benchmark.register(
        {
            "schema": benchmark.SCHEMA_V3,
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
                "solver_digest": _sha(b"synthetic-reference-solver"),
                "fidelity_digest": _sha(b"synthetic-reference-fidelity"),
                "applicability_digest": _sha(b"synthetic-reference-applicability"),
                "evidence_kind": benchmark.ENGINEERING_REFERENCE,
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
    physics_id = benchmark.physics_contract_identity(physics)
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
    worker = json.loads(originals["stage/worker-evidence.json"])
    inference = {
        "recipe_digest": entry["recipe_digest"],
        "state_digest": entry["state_digest"],
        "predictions_digest": entry["prediction_digest"],
        "predictions": json.loads(originals["infer/output/predictions.json"]),
        "worker_operation": worker["inference_operation"],
        "receipt": worker["inference_receipt"],
        "inference_receipt_raw": originals["infer/output/receipt.json"],
        "worker_evidence_raw": originals["stage/worker-evidence.json"],
    }
    measured = bundle.measurement_from_saved_inference(
        entry, registration, inference, gates={"toy_gate": True}
    )
    pack = register_pack(
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
            "accuracy_ceiling": 0.1,
            "performance_objective": "maximize_paired_speedup",
        }
    )
    graph_originals = {
        "inference_receipt_raw": originals["infer/output/receipt.json"],
        "worker_evidence_raw": originals["stage/worker-evidence.json"],
    }
    result = bundle.benchmark_saved_entry(
        entry,
        receipt_raw,
        job,
        registration,
        references,
        measured,
        score_pack=pack,
        graph_originals=graph_originals,
    )
    return {
        "root": root,
        "manifest": manifest,
        "originals": originals,
        "entry": entry,
        "custody_receipt_raw": receipt_raw,
        "job": job,
        "registration": registration,
        "references": references,
        "measured": measured,
        "pack": pack,
        "graph_originals": graph_originals,
        "ordered_query_bytes": [originals["infer/inputs.npz"]],
        "result": result,
    }


def _source_receipt(
    case, *, version="synthetic-eval-v1", references=None, queries=None
):
    registration = case["registration"]
    references = case["references"] if references is None else references
    queries = case["ordered_query_bytes"] if queries is None else queries
    reference_by_id = {row["id"]: row for row in references}
    receipt = {
        "schema": "carbon.scoring.private-evaluation-source.v1",
        "challenge": case["entry"]["challenge"],
        "challenge_version": case["entry"]["challenge_version"],
        "evaluation_version": version,
        "interface_digest": case["entry"]["interface_digest"],
        "train_digest": case["entry"]["train_digest"],
        "job_digest": case["job"]["job_digest"],
        "registration_digest": registration["registration_digest"],
        "physics_contract": benchmark.physics_contract_identity(
            case["job"]["physics_contract"]
        ),
        "cases": [
            {
                "id": registered["id"],
                "role": registered["role"],
                "weight": registered["weight"],
                "query_sha256": _sha(query),
                "reference_row_sha256": _sha(
                    _json(reference_by_id[registered["id"]]) + b"\n"
                ),
                "reference_status": reference_by_id[registered["id"]]["status"],
            }
            for registered, query in zip(registration["cases"], queries, strict=True)
        ],
    }
    raw = _json(receipt)
    return raw, _sha(raw)


def _result(case, *, references=None, measured=None, pack=None):
    return bundle.benchmark_saved_entry(
        case["entry"],
        case["custody_receipt_raw"],
        case["job"],
        case["registration"],
        case["references"] if references is None else references,
        case["measured"] if measured is None else measured,
        score_pack=case["pack"] if pack is None else pack,
        graph_originals=case["graph_originals"],
    )


def _bind(case, **overrides):
    source_raw, pin = _source_receipt(case)
    arguments = {
        "entry": case["entry"],
        "custody_receipt_raw": case["custody_receipt_raw"],
        "trusted_job": case["job"],
        "registration": case["registration"],
        "references": case["references"],
        "measured_model": case["measured"],
        "score_pack": case["pack"],
        "graph_originals": case["graph_originals"],
        "expected_result_digest": case["result"]["result_digest"],
        "ordered_query_bytes": case["ordered_query_bytes"],
        "evaluation_source_receipt_raw": source_raw,
        "registered_source_receipt_sha256": pin,
    }
    arguments.update(overrides)
    return private.bind_private_evaluation_evidence(**arguments)


def test_pinned_graph_evidence_returns_private_digest_without_changing_score(tmp_path):
    case = _graph_case(tmp_path)
    before = deepcopy(case["result"])
    sidecar = _bind(case)
    assert sidecar["schema"] == private.SIDECAR_SCHEMA
    assert sidecar["scope"] == "PRIVATE_OPERATOR_DEVELOPMENT"
    assert sidecar["status"] == "BOUND_DEVELOPMENT_ONLY"
    assert sidecar["benchmark_result_digest"] == before["result_digest"]
    assert (
        sidecar["score_compatibility"]["score_pack_digest"]
        == case["pack"]["pack_digest"]
    )
    assert sidecar["reference_coverage"] == {
        "RESOLVED": 1,
        "UNRESOLVED": 0,
        "FAILED_INFRA": 0,
    }
    assert case["result"] == before
    assert _result(case) == before
    assert "toy-case" not in _json(sidecar).decode()
    assert "0.25" not in _json(sidecar).decode()


@pytest.mark.parametrize("field,replacement", [("outputs", [0.30]), ("elapsed_s", 9.0)])
def test_stale_reference_values_refuse_even_with_same_case_and_solver_labels(
    tmp_path, field, replacement
):
    case = _graph_case(tmp_path)
    stale_source, stale_pin = _source_receipt(case)
    changed = deepcopy(case["references"])
    changed[0][field] = replacement
    new_result = _result(case, references=changed)
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="source_case_binding"
    ):
        _bind(
            case,
            references=changed,
            expected_result_digest=new_result["result_digest"],
            evaluation_source_receipt_raw=stale_source,
            registered_source_receipt_sha256=stale_pin,
        )


def test_different_same_shape_query_cannot_reuse_registered_case(tmp_path):
    case = _graph_case(tmp_path)
    alternate_query = _npz(inputs=("<f4", struct.pack("<f", 2.0), (1, 1, 1, 1)))
    assert alternate_query != case["ordered_query_bytes"][0]
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="source_case_binding"
    ):
        _bind(case, ordered_query_bytes=[alternate_query])
    alternate_source, alternate_pin = _source_receipt(case, queries=[alternate_query])
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="graph_query_original_binding"
    ):
        _bind(
            case,
            ordered_query_bytes=[alternate_query],
            evaluation_source_receipt_raw=alternate_source,
            registered_source_receipt_sha256=alternate_pin,
        )


def test_missing_independent_source_pin_refuses_before_scoring(tmp_path):
    case = _graph_case(tmp_path)
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="source_pin_missing"
    ):
        _bind(case, registered_source_receipt_sha256=None)
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="source_pin_mismatch"
    ):
        _bind(case, registered_source_receipt_sha256=_sha(b"different-registration"))


def test_deeply_nested_pinned_source_receipt_refuses_with_typed_error(tmp_path):
    case = _graph_case(tmp_path)
    nested_source = b"[" * 1990 + b"0" + b"]" * 1990
    assert len(nested_source) < 4096
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="source_receipt_json"
    ):
        _bind(
            case,
            evaluation_source_receipt_raw=nested_source,
            registered_source_receipt_sha256=_sha(nested_source),
        )


def test_saved_result_digest_is_recomputed_from_unchanged_evidence(tmp_path):
    case = _graph_case(tmp_path)
    assert _bind(case)["benchmark_result_digest"] == case["result"]["result_digest"]
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="result_digest_mismatch"
    ):
        _bind(case, expected_result_digest=_sha(b"different-saved-result"))


def test_candidate_gate_and_pack_changes_do_not_redefine_shared_evaluation(tmp_path):
    case = _graph_case(tmp_path)
    accepted = _bind(case)
    rejected_measurement = deepcopy(case["measured"])
    rejected_measurement["cases"][0]["gates"]["toy_gate"] = False
    rejected_result = _result(case, measured=rejected_measurement)
    rejected = _bind(
        case,
        measured_model=rejected_measurement,
        expected_result_digest=rejected_result["result_digest"],
    )
    assert (
        accepted["evaluation_version_digest"] == rejected["evaluation_version_digest"]
    )
    assert accepted["model_result_digest"] != rejected["model_result_digest"]
    assert accepted["model_p"]["measurement_status"] == "MEASURED_DEVELOPMENT"
    assert rejected["model_p"]["measurement_status"] == "SCIENTIFIC_INADMISSIBLE"
    assert accepted["score_compatibility"] == rejected["score_compatibility"]

    revised_pack = register_pack(
        {
            **{
                key: value
                for key, value in case["pack"].items()
                if key != "pack_digest"
            },
            "accuracy_ceiling": 0.2,
        }
    )
    revised_result = _result(case, pack=revised_pack)
    rescored = _bind(
        case,
        score_pack=revised_pack,
        expected_result_digest=revised_result["result_digest"],
    )
    assert (
        rescored["evaluation_version_digest"] == accepted["evaluation_version_digest"]
    )
    assert rescored["score_compatibility"] != accepted["score_compatibility"]
    assert rescored["model_result_digest"] != accepted["model_result_digest"]


@pytest.mark.parametrize(
    "reference_status,model_status",
    [
        ("UNRESOLVED", "INDETERMINATE_EVIDENCE"),
        ("FAILED_INFRA", "FAILED_INFRA"),
    ],
)
def test_reference_coverage_is_shared_and_new_resolution_changes_identity(
    tmp_path, reference_status, model_status
):
    case = _graph_case(tmp_path)
    resolved = _bind(case)
    incomplete = [{"id": "toy-case", "status": reference_status}]
    source_raw, source_pin = _source_receipt(case, references=incomplete)
    result = _result(case, references=incomplete)
    first = _bind(
        case,
        references=incomplete,
        expected_result_digest=result["result_digest"],
        evaluation_source_receipt_raw=source_raw,
        registered_source_receipt_sha256=source_pin,
    )
    adverse_measurement = deepcopy(case["measured"])
    adverse_measurement["cases"][0]["gates"]["toy_gate"] = False
    adverse_result = _result(case, references=incomplete, measured=adverse_measurement)
    second = _bind(
        case,
        references=incomplete,
        measured_model=adverse_measurement,
        expected_result_digest=adverse_result["result_digest"],
        evaluation_source_receipt_raw=source_raw,
        registered_source_receipt_sha256=source_pin,
    )
    assert first["evaluation_version_digest"] == second["evaluation_version_digest"]
    assert first["evaluation_version_digest"] != resolved["evaluation_version_digest"]
    assert first["reference_coverage"][reference_status] == 1
    assert first["model_p"]["measurement_status"] == model_status
    assert second["model_p"]["measurement_status"] == model_status
    assert first["model_result_digest"] != second["model_result_digest"]
    for reduced in (result, adverse_result):
        counts = reduced["benchmark"]["models"][0]["by_role"]["P"]["counts"]
        assert counts["candidate_invalid"] == 0
        assert counts["candidate_infra"] == 0


def test_unavailable_original_model_query_evidence_refuses(tmp_path):
    case = _graph_case(tmp_path)
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused,
        match="model_query_originals_unavailable",
    ):
        _bind(case, graph_originals=None)


def test_historical_bundle_entry_cannot_claim_private_query_binding(tmp_path):
    graph_dir = tmp_path / "graph"
    graph_dir.mkdir()
    case = _graph_case(graph_dir)
    bundle_dir = tmp_path / "historical"
    bundle_dir.mkdir()
    root, manifest, _ = _fixture(bundle_dir)
    receipt = custody.prepare_custody_v5(root, manifest)
    receipt_path = bundle_dir / "custody.json"
    receipt_path.write_bytes(_json(receipt))
    entries = bundle_dir / "entries"
    entries.mkdir()
    historical = unbound_entry.create_entry_v5(root, manifest, receipt_path, entries)[
        "entry"
    ]
    assert historical.get("source_kind") != "graph"
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused,
        match="model_query_originals_unavailable",
    ):
        _bind(case, entry=historical, graph_originals=None)


def test_self_consistent_other_model_measurement_cannot_be_reassociated(tmp_path):
    case = _graph_case(tmp_path)
    alternate_dir = tmp_path / "alternate"
    alternate_dir.mkdir()
    alt_root = alternate_dir / "producer"
    alt_root.mkdir()
    alt_manifest = alternate_dir / "roles.json"
    alt_manifest.write_bytes(case["manifest"].read_bytes())
    alt_originals = dict(case["originals"])
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
    alt_custody_path = alternate_dir / "custody.json"
    alt_custody_path.write_bytes(_json(alt_custody))
    alt_entries = alternate_dir / "entries"
    alt_entries.mkdir()
    alt_entry = unbound_entry.create_entry_v5(
        alt_root, alt_manifest, alt_custody_path, alt_entries
    )["entry"]
    assert alt_entry["entry_id"] != case["entry"]["entry_id"]
    assert alt_entry["state_digest"] == case["entry"]["state_digest"]
    alt_inference = {
        "recipe_digest": alt_entry["recipe_digest"],
        "state_digest": alt_entry["state_digest"],
        "predictions_digest": alt_entry["prediction_digest"],
        "predictions": json.loads(alt_originals["infer/output/predictions.json"]),
        "worker_operation": alt_worker["inference_operation"],
        "receipt": alt_receipt,
        "inference_receipt_raw": alt_originals["infer/output/receipt.json"],
        "worker_evidence_raw": alt_originals["stage/worker-evidence.json"],
    }
    alt_measured = bundle.measurement_from_saved_inference(
        alt_entry, case["registration"], alt_inference, gates={"toy_gate": True}
    )
    swapped = {**alt_measured, "entry_id": case["entry"]["entry_id"]}
    with pytest.raises(
        private.PrivateEvaluationEvidenceRefused, match="benchmark_reduction_refused"
    ):
        _bind(
            case,
            measured_model=swapped,
            graph_originals={
                "inference_receipt_raw": alt_originals["infer/output/receipt.json"],
                "worker_evidence_raw": alt_originals["stage/worker-evidence.json"],
            },
        )
