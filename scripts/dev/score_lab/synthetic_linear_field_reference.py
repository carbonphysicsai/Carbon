"""Measured public toy reference source for a separately registered v1.3 job.

The registered-job adapter preserves its existing caller-supplied contract.
The public measurement factory additionally names the exact published v1.3
practice batch for descriptive shape/finite conformance, MAE and timing only.
It supplies no accuracy threshold, ranking, qualified physics or hidden exam.
An operator retains the returned exact source bytes; hashes do not substitute
for an actual reference or inference run.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import math
import time
import zipfile
from pathlib import Path

import numpy as np

from carbon.challenge_kit import synthetic_linear_field_2d as fixture
from carbon.scoring import benchmark_evidence as benchmark
from carbon.scoring.private_evaluation_evidence import SOURCE_SCHEMA


class SyntheticReferenceRefused(ValueError):
    """The supplied registration, query, or measured toy reference is unusable."""


PUBLIC_MEASUREMENT_VERSION = "synthetic-linear-field-2d-1.3-public-measurement-v1"
PUBLIC_MEASUREMENT_GATES = ("public_output_shape", "public_output_finite")


def public_measurement_registration(
    *, query_bytes: bytes, model_device: str, reference_device: str
) -> dict:
    """Name the existing public batch without adopting an accuracy ceiling.

    This is one complete, already published practice query with unit weight,
    not a new population draw. Device descriptions must come from the actual
    operator. The exact input archive is supplied so retained inference bytes
    can be reused without relabelling a different query or a historical task.
    """
    if any(
        type(value) is not str or not value.strip()
        for value in (model_device, reference_device)
    ):
        raise SyntheticReferenceRefused("actual_device_descriptions_required")
    material = fixture.bundle_material_v5()
    kit = material["construction_kit"]
    if (kit["id"], kit["version"]) != ("synthetic-linear-field-2d", "1.3"):
        raise SyntheticReferenceRefused("public_measurement_challenge")
    if type(query_bytes) is not bytes or not 0 < len(query_bytes) <= 1024 * 1024:
        raise SyntheticReferenceRefused("query_bytes")
    inputs = material["practice_inputs"]
    output = {
        "quantity": material["interface_document"]["outputs"]["name"],
        "unit": "dimensionless",
        "size": int(inputs.size),
        "metric": "mean_absolute_error",
        "shape": list(inputs.shape),
    }
    reference = {
        "solver_digest": _sha(Path(fixture.__file__).read_bytes()),
        "fidelity_digest": _sha(_canonical(material["physics_contract"])),
        "applicability_digest": _sha(
            _canonical(
                {
                    "scope": "EXACT_PUBLIC_PRACTICE_BATCH_ONLY",
                    "interface_digest": kit["interface_digest"],
                    "query_sha256": _sha(query_bytes),
                    "input_shape": list(inputs.shape),
                    "input_dtype": str(inputs.dtype),
                }
            )
        ),
        "evidence_kind": benchmark.ENGINEERING_REFERENCE,
    }
    definition = {
        "schema": "carbon.synthetic-linear-field-2d.public-measurement.v1",
        "scope": "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",
        "challenge": kit["id"],
        "challenge_version": kit["version"],
        "interface_digest": kit["interface_digest"],
        "train_digest": kit["train_digest"],
        "physics_contract": material["physics_contract"],
        "query_sha256": _sha(query_bytes),
        "reference": reference,
        "output": output,
        "conformance_checks": list(PUBLIC_MEASUREMENT_GATES),
        "accuracy_ceiling": None,
        "ranking": None,
    }
    trusted_job = {
        key: definition[key]
        for key in (
            "challenge",
            "challenge_version",
            "interface_digest",
            "train_digest",
            "physics_contract",
        )
    }
    trusted_job["job_digest"] = _sha(_canonical(definition))
    registration = benchmark.register(
        {
            "schema": benchmark.SCHEMA_V3,
            "scope": "SYNTHETIC_DEVELOPMENT",
            "challenge": kit["id"],
            "job_digest": trusted_job["job_digest"],
            "train_digest": kit["train_digest"],
            "physics_contract": material["physics_contract"],
            "output": output,
            "reference": reference,
            "cases": [{"id": "public-practice-batch", "role": "P", "weight": 1.0}],
            "mandatory_gates": list(PUBLIC_MEASUREMENT_GATES),
            "timing_profile": {
                "basis": "ready_input_to_comparable_output",
                "model_device": model_device,
                "solver_device": reference_device,
                "batch_size": len(inputs),
                "query_unit": "complete_batch",
                "input_shape": list(inputs.shape),
            },
        }
    )
    _checked_query(query_bytes, material, registration)
    return {
        "schema": "carbon.challenge-evaluation-source-registration.v1",
        "evaluation_version": PUBLIC_MEASUREMENT_VERSION,
        "trusted_job": trusted_job,
        "benchmark_registration": registration,
    }


def prepare_public_measurement(
    *, query_bytes: bytes, model_device: str, reference_device: str
) -> dict:
    """Measure the real public reference and expose exact bytes to retain.

    The normal caller uses this registration with benchmark_saved_entry's
    score_pack=None path. No scored private sidecar, pool key or qualification
    is created, and missing model measurements are not manufactured here.
    Reference timing is the in-process array operation only. A caller must
    retain the actual model timing scope separately and must not advertise
    their numerical time ratio as comparable solver speed.
    """
    registration = public_measurement_registration(
        query_bytes=query_bytes,
        model_device=model_device,
        reference_device=reference_device,
    )
    prepared = prepare_reference(
        trusted_job=registration["trusted_job"],
        registration=registration["benchmark_registration"],
        query_bytes=query_bytes,
        evaluation_version=registration["evaluation_version"],
    )
    return {
        **prepared,
        "source_registration": registration,
        "source_registration_raw": _canonical(registration),
        "measurement_state": "DEVELOPMENT_UNRANKED",
        "accuracy_ceiling": None,
        "ranking": None,
        "timing_scopes": {
            "reference": "IN_PROCESS_PUBLIC_REFERENCE_ARRAY_ONLY",
            "model": None,
        },
        "speedup_comparability": "NOT_ESTABLISHED",
    }


def _canonical(value) -> bytes:
    try:
        return (
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, OverflowError) as exc:
        raise SyntheticReferenceRefused("source_canonicalization") from exc


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _registered_job(trusted_job, registration, material):
    if type(trusted_job) is not dict or set(trusted_job) != {
        "challenge",
        "challenge_version",
        "interface_digest",
        "train_digest",
        "job_digest",
        "physics_contract",
    }:
        raise SyntheticReferenceRefused("trusted_job_shape")
    kit = material["construction_kit"]
    expected = {
        "challenge": kit["id"],
        "challenge_version": kit["version"],
        "interface_digest": kit["interface_digest"],
        "train_digest": kit["train_digest"],
        "physics_contract": material["physics_contract"],
    }
    if any(trusted_job[key] != value for key, value in expected.items()):
        raise SyntheticReferenceRefused("trusted_job_public_material_mismatch")
    if (
        type(registration) is not dict
        or registration.get("schema") != benchmark.SCHEMA_V3
    ):
        raise SyntheticReferenceRefused("v3_registration_required")
    try:
        body = {
            key: value
            for key, value in registration.items()
            if key != "registration_digest"
        }
        checked = benchmark.register(body)
    except benchmark.BenchmarkRefused as exc:
        raise SyntheticReferenceRefused("registration_invalid") from exc
    if checked != registration or any(
        registration[key] != trusted_job[key]
        for key in ("challenge", "job_digest", "train_digest", "physics_contract")
    ):
        raise SyntheticReferenceRefused("registration_job_mismatch")
    if (
        registration["output"]["quantity"]
        != material["interface_document"]["outputs"]["name"]
        or registration["output"]["unit"] != "dimensionless"
    ):
        raise SyntheticReferenceRefused("public_target_measurement_mismatch")
    if (
        len(registration["cases"]) != 1
        or registration["cases"][0]["role"] != "P"
        or registration["reference"]["evidence_kind"] != benchmark.ENGINEERING_REFERENCE
    ):
        raise SyntheticReferenceRefused("single_registered_p_query_required")


def _checked_query(query_bytes: bytes, material, registration):
    if type(query_bytes) is not bytes or not 0 < len(query_bytes) <= 1024 * 1024:
        raise SyntheticReferenceRefused("query_bytes")
    try:
        with zipfile.ZipFile(io.BytesIO(query_bytes)) as container:
            members = container.infolist()
            if (
                len(members) != 1
                or members[0].filename != "inputs.npy"
                or members[0].file_size > 4096
                or members[0].compress_size > 4096
                or members[0].compress_type != zipfile.ZIP_STORED
                or members[0].flag_bits & 1
            ):
                raise SyntheticReferenceRefused("query_archive_members")
            member = container.read(members[0])
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        if isinstance(exc, SyntheticReferenceRefused):
            raise
        raise SyntheticReferenceRefused("query_archive") from exc
    expected = material["practice_inputs"]
    if len(member) != members[0].file_size or not member.startswith(b"\x93NUMPY"):
        raise SyntheticReferenceRefused("query_npy_header")
    if len(member) < 10:
        raise SyntheticReferenceRefused("query_npy_header")
    version = (member[6], member[7])
    if version == (1, 0):
        prefix, width = 8, 2
    elif version in {(2, 0), (3, 0)}:
        prefix, width = 8, 4
    else:
        raise SyntheticReferenceRefused("query_npy_version")
    if len(member) < prefix + width:
        raise SyntheticReferenceRefused("query_npy_header")
    header_size = int.from_bytes(member[prefix : prefix + width], "little")
    start = prefix + width
    if header_size > 1024 or start + header_size > len(member):
        raise SyntheticReferenceRefused("query_npy_header")
    try:
        header = ast.literal_eval(
            member[start : start + header_size].decode(
                "utf-8" if version[0] == 3 else "latin1"
            )
        )
    except (SyntaxError, ValueError, UnicodeError, MemoryError) as exc:
        raise SyntheticReferenceRefused("query_npy_header") from exc
    if (
        type(header) is not dict
        or set(header) != {"descr", "fortran_order", "shape"}
        or header["descr"] != expected.dtype.str
        or header["fortran_order"] is not False
        or header["shape"] != expected.shape
    ):
        raise SyntheticReferenceRefused("query_npy_type_or_shape")
    payload = member[start + header_size :]
    if len(payload) != expected.nbytes:
        raise SyntheticReferenceRefused("query_npy_payload")
    inputs = np.frombuffer(payload, dtype=expected.dtype).reshape(expected.shape)
    if (
        inputs.dtype != np.float32
        or inputs.shape != expected.shape
        or not np.isfinite(inputs).all()
        or not np.array_equal(inputs, expected)
        or registration["timing_profile"]["input_shape"] != list(inputs.shape)
        or registration["timing_profile"]["batch_size"] != len(inputs)
        or registration["output"]["shape"] != list(inputs.shape)
        or registration["output"]["size"] != inputs.size
    ):
        raise SyntheticReferenceRefused("registered_public_query_mismatch")
    return inputs


def prepare_reference(
    *,
    trusted_job: dict,
    registration: dict,
    query_bytes: bytes,
    evaluation_version: str,
) -> dict:
    """Time the exact public toy relation and return unpinned custody inputs.

    The reference row is engineering evidence only. The returned receipt hash
    is a *proposal*: the operator must independently register it, retain the
    raw query and row bytes, and supply its own custody path. This function
    never calls the scorer or signs a qualification decision.
    """
    if type(evaluation_version) is not str or not evaluation_version:
        raise SyntheticReferenceRefused("evaluation_version_required")
    material = fixture.bundle_material_v5()
    _registered_job(trusted_job, registration, material)
    inputs = _checked_query(query_bytes, material, registration)
    started = time.perf_counter_ns()
    targets = fixture.public_reference(inputs)
    elapsed_ns = time.perf_counter_ns() - started
    if elapsed_ns <= 0 or not math.isfinite(elapsed_ns / 1_000_000_000):
        raise SyntheticReferenceRefused("reference_elapsed_unresolved")
    elapsed_s = elapsed_ns / 1_000_000_000
    case = registration["cases"][0]
    physics = benchmark.physics_contract_identity(material["physics_contract"])
    row = {
        "id": case["id"],
        "status": "RESOLVED",
        "outputs": targets.reshape(-1).tolist(),
        "elapsed_s": elapsed_s,
        "source": "MEASURED_ENGINEERING_REFERENCE_RUN",
        "solver_digest": registration["reference"]["solver_digest"],
        "fidelity_digest": registration["reference"]["fidelity_digest"],
        "applicability_digest": registration["reference"]["applicability_digest"],
        "physics_contract_digest": physics["definition_digest"],
        "peak_memory_bytes": None,
    }
    row_raw = _canonical(row)
    source = {
        "schema": SOURCE_SCHEMA,
        "challenge": trusted_job["challenge"],
        "challenge_version": trusted_job["challenge_version"],
        "evaluation_version": evaluation_version,
        "interface_digest": trusted_job["interface_digest"],
        "train_digest": trusted_job["train_digest"],
        "job_digest": trusted_job["job_digest"],
        "registration_digest": registration["registration_digest"],
        "physics_contract": physics,
        "cases": [
            {
                "id": case["id"],
                "role": case["role"],
                "weight": case["weight"],
                "query_sha256": _sha(query_bytes),
                "reference_row_sha256": _sha(row_raw),
                "reference_status": row["status"],
            }
        ],
    }
    source_raw = _canonical(source)
    return {
        "scope": "PUBLIC_SYNTHETIC_DEVELOPMENT_ONLY",
        "status": "MEASURED_ENGINEERING_REFERENCE_UNPINNED",
        "query_bytes": query_bytes,
        "reference_row": row,
        "reference_row_raw": row_raw,
        "source_receipt_raw": source_raw,
        "proposed_source_receipt_sha256": _sha(source_raw),
        "independent_operator_registration": "REQUIRED",
        "reference_accepted": False,
        "score_or_qualification": False,
    }
