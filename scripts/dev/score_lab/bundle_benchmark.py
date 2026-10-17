"""Bind a retained public bundle model to the shared ScoreLab scorer.

This pure DEVELOPMENT reducer runs no model or reference. The trusted Challenge
supplies the job and physics definition; the execution adapter supplies whole
measured queries. Raw custody alone never creates score authority.
"""

from __future__ import annotations

import hashlib
import json
import math

from carbon.scoring.solver_benchmark_v3 import register_pack
from scripts.dev.score_lab import solver_benchmark

ENTRY_SCHEMA = "carbon.scorelab.public-model-entry.v5"
CUSTODY_SCHEMA = "carbon.scorelab.public-model-custody-receipt.v5"
MEASUREMENT_SCHEMA = "carbon.scorelab.bundle-model-measurement.v1"
RESULT_SCHEMA = "carbon.scorelab.bundle-benchmark-result.v1"
_ENTRY_BINDINGS = (
    "source_schema",
    "scope",
    "challenge",
    "challenge_version",
    "interface_digest",
    "train_digest",
    "bundle_digest",
    "recipe_digest",
    "state_digest",
    "prediction_digest",
    "role_manifest_sha256",
    "physics_contract",
    "roles",
    "original_files",
)


class BundleBenchmarkRefused(ValueError):
    """A supplied development artifact or measurement breaks its binding."""


def _canonical(value):
    try:
        return (
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
            + "\n"
        ).encode()
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise BundleBenchmarkRefused("noncanonical_input") from exc


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _parse_receipt(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= 1024 * 1024:
        raise BundleBenchmarkRefused("custody_receipt_bytes")

    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise BundleBenchmarkRefused("custody_receipt_duplicate_key")
            value[key] = item
        return value

    try:
        value = json.loads(raw, object_pairs_hook=unique_pairs)
    except (UnicodeError, ValueError) as exc:
        raise BundleBenchmarkRefused("custody_receipt_json") from exc
    if type(value) is not dict:
        raise BundleBenchmarkRefused("custody_receipt_shape")
    return value


def _entry_and_job(entry, custody_receipt_raw, trusted_job, registration):
    if type(entry) is not dict or entry.get("schema") != ENTRY_SCHEMA:
        raise BundleBenchmarkRefused("entry_schema")
    if entry.get("entry_id") != _sha(
        _canonical({key: value for key, value in entry.items() if key != "entry_id"})
    ):
        raise BundleBenchmarkRefused("entry_id")
    if (
        entry.get("scope") != "PUBLIC_DEVELOPMENT_BUNDLE_MODEL"
        or entry.get("official_eligible") is not False
        or entry.get("admission_state") != "NOT_ADMITTED"
        or entry.get("score_state") != "NOT_COMPUTED"
    ):
        raise BundleBenchmarkRefused("entry_authority")
    receipt = _parse_receipt(custody_receipt_raw)
    if (
        receipt.get("schema") != CUSTODY_SCHEMA
        or type(entry.get("custody_receipt")) is not dict
        or entry["custody_receipt"].get("sha256") != _sha(custody_receipt_raw)
        or entry["custody_receipt"].get("bytes") != len(custody_receipt_raw)
        or receipt.get("custody_state") != "PUBLIC_BYTES_REHASHED"
        or receipt.get("official_eligible") is not False
        or any(entry.get(field) != receipt.get(field) for field in _ENTRY_BINDINGS)
    ):
        raise BundleBenchmarkRefused("custody_binding")
    required = {
        "challenge",
        "challenge_version",
        "interface_digest",
        "train_digest",
        "job_digest",
        "physics_contract",
    }
    if type(trusted_job) is not dict or set(trusted_job) != required:
        raise BundleBenchmarkRefused("trusted_job_shape")
    physics = solver_benchmark.physics_contract_identity(
        trusted_job["physics_contract"]
    )
    for field in ("challenge", "challenge_version", "interface_digest", "train_digest"):
        if trusted_job[field] != entry.get(field):
            raise BundleBenchmarkRefused("trusted_job_entry_binding")
    declared_physics = entry.get("physics_contract")
    if type(declared_physics) is not dict or set(declared_physics) != {
        "version",
        "definition_digest",
        "authenticity",
    }:
        raise BundleBenchmarkRefused("entry_physics_state")
    if declared_physics["authenticity"] == "PENDING":
        if (
            declared_physics["version"] is not None
            or declared_physics["definition_digest"] is not None
        ):
            raise BundleBenchmarkRefused("entry_physics_state")
    elif declared_physics["authenticity"] == "DECLARED_UNVERIFIED":
        if {key: declared_physics[key] for key in physics} != physics:
            raise BundleBenchmarkRefused("entry_physics_mismatch")
    else:
        raise BundleBenchmarkRefused("entry_physics_state")
    if (
        type(registration) is not dict
        or registration.get("challenge") != trusted_job["challenge"]
        or registration.get("job_digest") != trusted_job["job_digest"]
        or registration.get("train_digest") != trusted_job["train_digest"]
        or registration.get("physics_contract") != trusted_job["physics_contract"]
    ):
        raise BundleBenchmarkRefused("registration_job_binding")
    # The existing receiver checks the registration digest and complete roster.
    solver_benchmark.register(
        {
            key: value
            for key, value in registration.items()
            if key != "registration_digest"
        }
    )
    if registration.get("registration_digest") != solver_benchmark._digest(
        {
            key: value
            for key, value in registration.items()
            if key != "registration_digest"
        }
    ):
        raise BundleBenchmarkRefused("registration_digest")
    return physics


def _measurement_model(measurement, entry, trusted_job, registration, physics):
    required = {
        "schema",
        "entry_id",
        "challenge",
        "challenge_version",
        "interface_digest",
        "recipe_digest",
        "state_digest",
        "train_digest",
        "batch_size",
        "input_shape",
        "output_shape",
        "build_seconds",
        "cases",
    }
    if (
        type(measurement) is not dict
        or set(measurement) != required
        or measurement["schema"] != MEASUREMENT_SCHEMA
    ):
        raise BundleBenchmarkRefused("measurement_shape")
    for field in (
        "entry_id",
        "challenge",
        "challenge_version",
        "interface_digest",
        "recipe_digest",
        "state_digest",
        "train_digest",
    ):
        expected = entry["entry_id"] if field == "entry_id" else entry[field]
        if measurement[field] != expected:
            raise BundleBenchmarkRefused("measurement_entry_binding")
    batch = measurement["batch_size"]
    input_shape = measurement["input_shape"]
    output_shape = measurement["output_shape"]
    if (
        type(batch) is not int
        or batch < 1
        or type(input_shape) is not list
        or type(output_shape) is not list
        or not input_shape
        or not output_shape
        or any(type(n) is not int or n < 1 for n in input_shape + output_shape)
        or input_shape[0] != batch
        or output_shape[0] != batch
        or math.prod(output_shape) != registration["output"]["size"]
        or batch != registration["timing_profile"]["batch_size"]
    ):
        raise BundleBenchmarkRefused("measurement_batch_shape")
    profile = registration["timing_profile"]
    if "input_shape" in profile and (
        input_shape != profile["input_shape"]
        or output_shape != registration["output"]["shape"]
    ):
        raise BundleBenchmarkRefused("measurement_registered_shape")
    return {
        "artifact_digest": entry["entry_id"],
        "job_digest": trusted_job["job_digest"],
        "train_digest": entry["train_digest"],
        "physics_contract_digest": physics["definition_digest"],
        "build_seconds": measurement["build_seconds"],
        "cases": measurement["cases"],
    }


def benchmark_saved_entry(
    entry,
    custody_receipt_raw,
    trusted_job,
    registration,
    references,
    measured_model,
    score_pack=None,
):
    """Reduce complete measured queries through the validator's ScoreEngine.

    `trusted_job` and reference rows come from Challenge/evaluation custody,
    never from the model. A missing reference or per-query measurement stays
    typed NOT_READY rather than becoming a candidate failure or fake timing.
    """
    physics = _entry_and_job(entry, custody_receipt_raw, trusted_job, registration)
    pack_source = "REGISTERED" if score_pack is not None else "DERIVED_UNREADY"
    if score_pack is None:
        score_pack = register_pack(
            {
                "schema": "carbon.scoring.solver-benchmark-pack.v3",
                "scope": registration["scope"],
                "challenge": registration["challenge"],
                "benchmark_registration_digest": registration["registration_digest"],
                "physics_contract": physics,
                "output": {
                    key: registration["output"][key]
                    for key in ("quantity", "unit", "metric")
                },
                "hard_gates": registration["mandatory_gates"],
                "accuracy_ceiling": None,
                "performance_objective": "maximize_paired_speedup",
            }
        )
    else:
        if type(score_pack) is not dict or score_pack != register_pack(
            {key: value for key, value in score_pack.items() if key != "pack_digest"}
        ):
            raise BundleBenchmarkRefused("score_pack_digest")
    reasons = []
    if references is None:
        reasons.append("REFERENCE_MEASUREMENTS_MISSING")
    if measured_model is None:
        reasons.append("MODEL_PER_QUERY_MEASUREMENTS_MISSING")
    body = {
        "schema": RESULT_SCHEMA,
        "scope": registration["scope"],
        "entry_id": entry["entry_id"],
        "state_digest": entry["state_digest"],
        "custody_receipt_sha256": _sha(custody_receipt_raw),
        "trusted_job_digest": _sha(_canonical(trusted_job)),
        "registration_digest": registration["registration_digest"],
        "physics_contract": physics,
        "score_pack_digest": score_pack["pack_digest"],
        "score_pack_source": pack_source,
        "status": "NOT_READY" if reasons else "BENCHMARK_REDUCED",
        "score_status": "NOT_COMPUTED",
        "not_ready_reasons": reasons,
        "benchmark": None,
    }
    if not reasons:
        model = _measurement_model(
            measured_model, entry, trusted_job, registration, physics
        )
        body["benchmark"] = solver_benchmark.compare(
            registration, references, [model], score_pack=score_pack
        )
        body["score_status"] = body["benchmark"]["scoring"]["status"]
    return {**body, "result_digest": _sha(_canonical(body))}
