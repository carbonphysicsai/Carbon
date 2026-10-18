"""Bounded public engineering reference source; never an official score."""

import hashlib
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pytest

from carbon.challenge_kit import synthetic_linear_field_2d as fixture
from carbon.scoring import benchmark_evidence as benchmark
from carbon.scoring.private_evaluation_evidence import SOURCE_SCHEMA
from scripts.dev.score_lab import synthetic_linear_field_reference as source


def _registered_public_query():
    material = fixture.bundle_material_v5()
    kit = material["construction_kit"]
    trusted_job = {
        "challenge": kit["id"],
        "challenge_version": kit["version"],
        "interface_digest": kit["interface_digest"],
        "train_digest": kit["train_digest"],
        "job_digest": "sha256:" + "a" * 64,
        "physics_contract": material["physics_contract"],
    }
    registration = benchmark.register(
        {
            "schema": benchmark.SCHEMA_V3,
            "scope": "SYNTHETIC_DEVELOPMENT",
            "challenge": trusted_job["challenge"],
            "job_digest": trusted_job["job_digest"],
            "train_digest": trusted_job["train_digest"],
            "physics_contract": trusted_job["physics_contract"],
            "output": {
                "quantity": material["interface_document"]["outputs"]["name"],
                "unit": "dimensionless",
                "size": int(material["practice_inputs"].size),
                "metric": "mean_absolute_error",
                "shape": list(material["practice_inputs"].shape),
            },
            "reference": {
                "solver_digest": "sha256:" + "b" * 64,
                "fidelity_digest": "sha256:" + "c" * 64,
                "applicability_digest": "sha256:" + "d" * 64,
                "evidence_kind": benchmark.ENGINEERING_REFERENCE,
            },
            "cases": [{"id": "fixture-practice-batch", "role": "P", "weight": 1.0}],
            "mandatory_gates": ["fixture_gate_not_qualified"],
            "timing_profile": {
                "basis": "ready_input_to_comparable_output",
                "model_device": "fixture_cpu",
                "solver_device": "fixture_cpu",
                "batch_size": len(material["practice_inputs"]),
                "query_unit": "complete_batch",
                "input_shape": list(material["practice_inputs"].shape),
            },
        }
    )
    stream = io.BytesIO()
    np.savez(stream, inputs=material["practice_inputs"])
    return trusted_job, registration, stream.getvalue(), material


def test_measured_public_reference_emits_unpinned_raw_source(monkeypatch):
    job, registration, query, material = _registered_public_query()
    ticks = iter((1_000_000_000, 2_000_000_000))
    monkeypatch.setattr(source.time, "perf_counter_ns", lambda: next(ticks))
    prepared = source.prepare_reference(
        trusted_job=job,
        registration=registration,
        query_bytes=query,
        evaluation_version="fixture-only-v1",
    )
    row = prepared["reference_row"]
    assert row["source"] == "MEASURED_ENGINEERING_REFERENCE_RUN"
    assert row["elapsed_s"] == 1.0
    assert row["peak_memory_bytes"] is None
    np.testing.assert_array_equal(
        np.asarray(row["outputs"], dtype=np.float32).reshape(
            material["practice_inputs"].shape
        ),
        fixture.public_reference(material["practice_inputs"]),
    )
    receipt = json.loads(prepared["source_receipt_raw"])
    assert receipt["schema"] == SOURCE_SCHEMA
    assert receipt["registration_digest"] == registration["registration_digest"]
    assert receipt["cases"] == [
        {
            "id": registration["cases"][0]["id"],
            "role": "P",
            "weight": 1.0,
            "query_sha256": source._sha(query),
            "reference_row_sha256": source._sha(prepared["reference_row_raw"]),
            "reference_status": "RESOLVED",
        }
    ]
    assert prepared["proposed_source_receipt_sha256"] == (
        "sha256:" + hashlib.sha256(prepared["source_receipt_raw"]).hexdigest()
    )
    assert prepared["independent_operator_registration"] == "REQUIRED"
    assert "registered_source_receipt_sha256" not in prepared
    assert prepared["reference_accepted"] is False
    assert prepared["score_or_qualification"] is False


def test_changed_query_or_registration_refuses_before_reference():
    job, registration, query, material = _registered_public_query()
    changed = material["practice_inputs"].copy()
    changed[0, 0, 0, 0] += np.float32(0.125)
    stream = io.BytesIO()
    np.savez(stream, inputs=changed)
    with pytest.raises(source.SyntheticReferenceRefused, match="public_query_mismatch"):
        source.prepare_reference(
            trusted_job=job,
            registration=registration,
            query_bytes=stream.getvalue(),
            evaluation_version="fixture-only-v1",
        )
    registration = {**registration, "job_digest": "sha256:" + "0" * 64}
    with pytest.raises(
        source.SyntheticReferenceRefused, match="registration_job_mismatch"
    ):
        source.prepare_reference(
            trusted_job=job,
            registration=registration,
            query_bytes=query,
            evaluation_version="fixture-only-v1",
        )


def test_registered_quantity_cannot_relabel_public_target():
    job, registration, query, _ = _registered_public_query()
    body = {
        key: value
        for key, value in registration.items()
        if key != "registration_digest"
    }
    body["output"] = {**body["output"], "quantity": "unrelated_quantity"}
    relabeled = benchmark.register(body)
    with pytest.raises(source.SyntheticReferenceRefused, match="target_measurement"):
        source.prepare_reference(
            trusted_job=job,
            registration=relabeled,
            query_bytes=query,
            evaluation_version="fixture-only-v1",
        )


def test_tiny_npy_member_with_huge_declared_shape_refuses_before_allocation(
    monkeypatch,
):
    _, registration, _, material = _registered_public_query()
    header = (
        b"{'descr': '<f4', 'fortran_order': False, "
        b"'shape': (1000000000, 8, 8, 1), }\n"
    )
    member = (
        b"\x93NUMPY\x01\x00" + len(header).to_bytes(2, "little") + header + b"\x00" * 4
    )
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as saved:
        saved.writestr("inputs.npy", member)
    assert len(archive.getvalue()) < 4096
    monkeypatch.setattr(
        source.np, "frombuffer", lambda *_args, **_kwargs: pytest.fail("allocated")
    )
    with pytest.raises(
        source.SyntheticReferenceRefused, match="query_npy_type_or_shape"
    ):
        source._checked_query(archive.getvalue(), material, registration)


def test_unmeasured_elapsed_refuses_without_receipt(monkeypatch):
    job, registration, query, _ = _registered_public_query()
    monkeypatch.setattr(source.time, "perf_counter_ns", lambda: 10)
    with pytest.raises(source.SyntheticReferenceRefused, match="elapsed_unresolved"):
        source.prepare_reference(
            trusted_job=job,
            registration=registration,
            query_bytes=query,
            evaluation_version="fixture-only-v1",
        )


def test_public_measurement_registration_binds_actual_kit_query_and_source():
    _, _, query, material = _registered_public_query()
    args = {
        "query_bytes": query,
        "model_device": "synthetic-test-model-cpu",
        "reference_device": "synthetic-test-reference-cpu",
    }
    envelope = source.public_measurement_registration(**args)
    assert envelope == source.public_measurement_registration(**args)
    assert set(envelope) == {
        "schema",
        "evaluation_version",
        "trusted_job",
        "benchmark_registration",
    }
    assert envelope["schema"] == "carbon.challenge-evaluation-source-registration.v1"
    job = envelope["trusted_job"]
    kit = material["construction_kit"]
    assert job["challenge"] == kit["id"]
    assert job["challenge_version"] == kit["version"] == "1.3"
    assert job["train_digest"] == kit["train_digest"]
    assert job["interface_digest"] == kit["interface_digest"]
    registration = envelope["benchmark_registration"]
    assert registration["output"] == {
        "quantity": "target",
        "unit": "dimensionless",
        "metric": "mean_absolute_error",
        "size": 128,
        "shape": [2, 8, 8, 1],
    }
    assert registration["cases"] == [
        {"id": "public-practice-batch", "role": "P", "weight": 1.0}
    ]
    assert registration["mandatory_gates"] == list(source.PUBLIC_MEASUREMENT_GATES)
    assert registration["reference"]["solver_digest"] == source._sha(
        Path(fixture.__file__).read_bytes()
    )
    assert "accuracy_ceiling" not in registration
    assert "score_pack" not in envelope
    changed_device = source.public_measurement_registration(
        **{**args, "model_device": "synthetic-test-other-model-cpu"}
    )
    assert changed_device["trusted_job"] == job
    assert changed_device["benchmark_registration"] != registration


@pytest.mark.parametrize("device", [None, "", "  ", 1])
def test_public_measurement_requires_operator_device_descriptions(device):
    _, _, query, _ = _registered_public_query()
    with pytest.raises(source.SyntheticReferenceRefused, match="device_descriptions"):
        source.public_measurement_registration(
            query_bytes=query, model_device=device, reference_device="test-cpu"
        )
    with pytest.raises(source.SyntheticReferenceRefused, match="device_descriptions"):
        source.public_measurement_registration(
            query_bytes=query, model_device="test-cpu", reference_device=device
        )


def test_public_measurement_rejects_different_query_before_reference(monkeypatch):
    _, _, _, material = _registered_public_query()
    changed = material["practice_inputs"].copy()
    changed[0, 0, 0, 0] += np.float32(0.125)
    stream = io.BytesIO()
    np.savez(stream, inputs=changed)
    monkeypatch.setattr(
        source.time, "perf_counter_ns", lambda: pytest.fail("reference must not run")
    )
    with pytest.raises(source.SyntheticReferenceRefused, match="public_query_mismatch"):
        source.prepare_public_measurement(
            query_bytes=stream.getvalue(),
            model_device="test-cpu",
            reference_device="test-cpu",
        )


def test_public_factory_preserves_actual_elapsed_and_explicit_unranked_state(
    monkeypatch,
):
    _, _, query, _ = _registered_public_query()
    ticks = iter((1_000_000_000, 1_500_000_000))
    monkeypatch.setattr(source.time, "perf_counter_ns", lambda: next(ticks))
    prepared = source.prepare_public_measurement(
        query_bytes=query, model_device="test-cpu", reference_device="test-cpu"
    )
    assert prepared["reference_row"]["elapsed_s"] == 0.5
    assert prepared["reference_row"]["source"] == "MEASURED_ENGINEERING_REFERENCE_RUN"
    assert prepared["query_bytes"] == query
    envelope = prepared["source_registration"]
    assert json.loads(prepared["source_registration_raw"]) == envelope
    receipt = json.loads(prepared["source_receipt_raw"])
    assert receipt["job_digest"] == envelope["trusted_job"]["job_digest"]
    assert (
        receipt["registration_digest"]
        == envelope["benchmark_registration"]["registration_digest"]
    )
    assert receipt["cases"][0]["query_sha256"] == source._sha(query)
    assert prepared["measurement_state"] == "DEVELOPMENT_UNRANKED"
    assert prepared["accuracy_ceiling"] is None
    assert prepared["ranking"] is None
    assert prepared["score_or_qualification"] is False
