"""Bind a retained public bundle model to the shared ScoreLab scorer.

This pure DEVELOPMENT reducer runs no model or reference. The trusted Challenge
supplies the job and physics definition; the execution adapter supplies whole
measured queries. Raw custody alone never creates score authority.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import re
from dataclasses import asdict, is_dataclass

from carbon.scoring import benchmark_evidence as solver_benchmark
from carbon.scoring.solver_benchmark_v3 import register_pack

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
    "fixture_digest",
    "prediction_digest",
    "role_manifest_sha256",
    "physics_contract",
    "roles",
    "original_files",
)
_GRAPH_SOURCE_SCHEMA = "carbon.development.graph-source-state.v1"
_GRAPH_ROLE_SCHEMA = "carbon.scorelab.public-model-artifact-roles.v3"
_GRAPH_ROLE_CODECS = {
    "recipe": "json",
    "construction_kit": "json",
    "train": "numeric_npz",
    "state": "bundle_graph_npz",
    "source": "json",
    "image": "json",
    "allowlist": "json",
    "build_receipt": "json",
    "worker_evidence": "json",
    "inputs": "numeric_npz",
    "predictions": "json",
    "inference_receipt": "json",
    "fixture": "numeric_npz",
    "seed": "json",
    "task_receipt": "raw_bytes",
}
_GRAPH_REQUIRED_ROLES = frozenset(_GRAPH_ROLE_CODECS) - {
    "fixture",
    "seed",
    "task_receipt",
}
_GRAPH_ENTRY_BINDINGS = (
    "source_kind",
    "role_schema",
    "submission_digest",
    "environment_ref_digest",
    "source_digest",
    "environment_digest",
    "image_digest",
    "fixture_evidence",
    "prediction_evidence",
    "seed_digest",
    "seed_provenance",
    "state_members",
    "provenance_state",
    "replay_state",
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


def _parse_graph_original(raw, label, *, object_required=True):
    if type(raw) is not bytes or not 0 < len(raw) <= 4 * 1024 * 1024:
        raise BundleBenchmarkRefused(f"{label}_bytes")

    def unique_pairs(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise BundleBenchmarkRefused(f"{label}_duplicate_key")
            value[key] = item
        return value

    def finite_float(value):
        number = float(value)
        if not math.isfinite(number):
            raise BundleBenchmarkRefused(f"{label}_nonfinite")
        return number

    def refuse_constant(_value):
        raise BundleBenchmarkRefused(f"{label}_nonfinite")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique_pairs,
            parse_float=finite_float,
            parse_constant=refuse_constant,
        )
    except (UnicodeError, ValueError) as exc:
        raise BundleBenchmarkRefused(f"{label}_json") from exc
    if object_required and type(value) is not dict:
        raise BundleBenchmarkRefused(f"{label}_shape")
    return value


def _graph_saved_inference_binding(entry, inference):
    if (
        entry.get("source_schema") != _GRAPH_SOURCE_SCHEMA
        or entry.get("source_kind") != "graph"
        or entry.get("role_schema") != _GRAPH_ROLE_SCHEMA
        or type(entry.get("roles")) is not dict
    ):
        raise BundleBenchmarkRefused("graph_saved_entry")
    roles = entry["roles"]
    for name, raw_field in (
        ("inference_receipt", "inference_receipt_raw"),
        ("worker_evidence", "worker_evidence_raw"),
    ):
        role = roles.get(name)
        raw = inference[raw_field]
        if (
            type(role) is not dict
            or set(role) != {"file", "codec", "sha256"}
            or role["codec"] != "json"
            or type(raw) is not bytes
            or _sha(raw) != role["sha256"]
        ):
            raise BundleBenchmarkRefused("graph_saved_original_binding")
    retained_receipt = _parse_graph_original(
        inference["inference_receipt_raw"], "graph_inference_receipt"
    )
    worker = _parse_graph_original(
        inference["worker_evidence_raw"], "graph_worker_evidence"
    )
    if (
        retained_receipt != inference["receipt"]
        or worker.get("schema") != "carbon.direct-private-attempt.graph.v1"
        or worker.get("inference_receipt") != retained_receipt
        or worker.get("inference_operation") != inference["worker_operation"]
        or worker.get("submission_digest") != entry.get("submission_digest")
        or worker.get("state_digest") != entry.get("state_digest")
        or worker.get("predictions_digest") != entry.get("prediction_digest")
    ):
        raise BundleBenchmarkRefused("graph_saved_inference_binding")
    return retained_receipt, worker


def _graph_measurement_binding(measurement, entry, originals):
    if type(originals) is not dict or set(originals) != {
        "inference_receipt_raw",
        "worker_evidence_raw",
    }:
        raise BundleBenchmarkRefused("graph_measurement_originals")
    receipt, worker = _graph_saved_inference_binding(
        entry,
        {
            **originals,
            "receipt": _parse_graph_original(
                originals["inference_receipt_raw"], "graph_inference_receipt"
            ),
            "worker_operation": _parse_graph_original(
                originals["worker_evidence_raw"], "graph_worker_evidence"
            ).get("inference_operation"),
        },
    )
    encoded = worker.get("predictions_raw_base64")
    try:
        predictions_raw = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (AttributeError, UnicodeError, ValueError, binascii.Error) as exc:
        raise BundleBenchmarkRefused("graph_measurement_predictions") from exc
    if (
        base64.b64encode(predictions_raw).decode("ascii") != encoded
        or _sha(predictions_raw) != entry["roles"]["predictions"]["sha256"]
        or receipt.get("predictions_digest") != _sha(predictions_raw)
    ):
        raise BundleBenchmarkRefused("graph_measurement_predictions")
    predictions = _parse_graph_original(
        predictions_raw, "graph_predictions", object_required=False
    )
    source_measurement = receipt.get("measurement")
    cases = measurement["cases"]
    if (
        type(source_measurement) is not dict
        or type(cases) is not list
        or len(cases) != 1
        or type(cases[0]) is not dict
        or source_measurement.get("input_shape") != measurement["input_shape"]
        or source_measurement.get("output_shape") != measurement["output_shape"]
        or cases[0].get("timing_s") != source_measurement.get("timing_s")
        or measurement["build_seconds"] is not None
        or cases[0].get("peak_memory_bytes") is not None
    ):
        raise BundleBenchmarkRefused("graph_measurement_binding")
    outputs = _flat_tensor(predictions, measurement["output_shape"])
    if cases[0].get("outputs") != outputs:
        raise BundleBenchmarkRefused("graph_measurement_outputs")


def _graph_custody_binding(entry, receipt):
    """Bind the prospective graph role-v3 variant without changing bundle v5."""
    discriminators = {"source_kind", "role_schema", "submission_digest"}
    graph_claimed = (
        entry.get("source_schema") == _GRAPH_SOURCE_SCHEMA
        or receipt.get("source_schema") == _GRAPH_SOURCE_SCHEMA
        or bool(discriminators & (entry.keys() | receipt.keys()))
    )
    if not graph_claimed:
        return
    if (
        entry.get("source_schema") != _GRAPH_SOURCE_SCHEMA
        or receipt.get("source_schema") != _GRAPH_SOURCE_SCHEMA
        or entry.get("source_kind") != "graph"
        or receipt.get("source_kind") != "graph"
        or entry.get("role_schema") != _GRAPH_ROLE_SCHEMA
        or receipt.get("role_schema") != _GRAPH_ROLE_SCHEMA
        or any(
            field not in entry or field not in receipt
            for field in _GRAPH_ENTRY_BINDINGS
        )
        or any(entry[field] != receipt[field] for field in _GRAPH_ENTRY_BINDINGS)
        or "bundle_digest" not in entry
        or "bundle_digest" not in receipt
        or entry["bundle_digest"] is not None
        or receipt["bundle_digest"] is not None
        or entry["environment_ref_digest"] is not None
        or entry["environment_digest"] is not None
        or type(entry["submission_digest"]) is not str
        or re.fullmatch(r"sha256:[0-9a-f]{64}", entry["submission_digest"]) is None
    ):
        raise BundleBenchmarkRefused("graph_custody_binding")

    roles = entry["roles"]
    originals = entry["original_files"]
    if (
        type(roles) is not dict
        or not _GRAPH_REQUIRED_ROLES <= set(roles) <= set(_GRAPH_ROLE_CODECS)
        or type(originals) is not dict
        or len(originals) < len(roles)
    ):
        raise BundleBenchmarkRefused("graph_role_binding")
    if any(
        type(path) is not str
        or not path
        or type(original) is not dict
        or set(original) != {"sha256", "bytes"}
        or type(original["sha256"]) is not str
        or re.fullmatch(r"sha256:[0-9a-f]{64}", original["sha256"]) is None
        or type(original["bytes"]) is not int
        or original["bytes"] < 1
        for path, original in originals.items()
    ):
        raise BundleBenchmarkRefused("graph_original_binding")
    paths = set()
    for role, record in roles.items():
        if (
            type(record) is not dict
            or set(record) != {"file", "codec", "sha256"}
            or record["codec"] != _GRAPH_ROLE_CODECS[role]
            or type(record["file"]) is not str
            or not record["file"]
            or record["file"] in paths
            or type(record["sha256"]) is not str
            or re.fullmatch(r"sha256:[0-9a-f]{64}", record["sha256"]) is None
        ):
            raise BundleBenchmarkRefused("graph_role_binding")
        paths.add(record["file"])
        original = originals.get(record["file"])
        if (
            type(original) is not dict
            or set(original) != {"sha256", "bytes"}
            or original["sha256"] != record["sha256"]
            or type(original["bytes"]) is not int
            or original["bytes"] < 1
        ):
            raise BundleBenchmarkRefused("graph_original_binding")
    for field, role in (
        ("train_digest", "train"),
        ("recipe_digest", "recipe"),
        ("state_digest", "state"),
        ("source_digest", "source"),
        ("image_digest", "image"),
        ("prediction_digest", "predictions"),
    ):
        if entry.get(field) != roles[role]["sha256"]:
            raise BundleBenchmarkRefused("graph_digest_binding")
    for field, role in (("fixture_digest", "fixture"), ("seed_digest", "seed")):
        expected = roles[role]["sha256"] if role in roles else None
        if entry.get(field) != expected:
            raise BundleBenchmarkRefused("graph_digest_binding")


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
    _graph_custody_binding(entry, receipt)
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


def _measurement_model(
    measurement, entry, trusted_job, registration, physics, *, graph_originals=None
):
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
    if entry.get("source_kind") == "graph":
        _graph_measurement_binding(measurement, entry, graph_originals)
    return {
        "artifact_digest": entry["entry_id"],
        "job_digest": trusted_job["job_digest"],
        "train_digest": entry["train_digest"],
        "physics_contract_digest": physics["definition_digest"],
        "build_seconds": measurement["build_seconds"],
        "cases": measurement["cases"],
    }


def _flat_tensor(value, shape):
    if not shape:
        if type(value) not in (int, float) or not math.isfinite(value):
            raise BundleBenchmarkRefused("saved_prediction_nonfinite")
        return [float(value)]
    if type(value) is not list or len(value) != shape[0]:
        raise BundleBenchmarkRefused("saved_prediction_shape")
    return [number for item in value for number in _flat_tensor(item, shape[1:])]


def measurement_from_saved_inference(
    entry, registration, inference, *, gates, build_seconds=None
):
    """Map one trusted, measured v2 worker receipt to one v3 batch query.

    The caller supplies Challenge-owned gate verdicts. This reducer verifies
    worker output, measurement shape and custody digests; it does not infer
    physical validity or estimate missing build and peak-memory telemetry.
    Graph role-v3 entries also require the original inference receipt and
    worker-evidence bytes to bind timing and operation to retained custody.
    """
    if is_dataclass(inference) and not isinstance(inference, type):
        inference = asdict(inference)
    required = {
        "recipe_digest",
        "state_digest",
        "predictions_digest",
        "predictions",
        "worker_operation",
        "receipt",
    }
    graph_measurement = type(entry) is dict and (
        entry.get("source_schema") == _GRAPH_SOURCE_SCHEMA
        or entry.get("source_kind") == "graph"
        or "role_schema" in entry
    )
    if graph_measurement:
        required |= {"inference_receipt_raw", "worker_evidence_raw"}
    if (
        type(inference) is not dict
        or set(inference) != required
        or type(registration) is not dict
        or registration.get("schema") != solver_benchmark.SCHEMA_V3
        or len(registration.get("cases", [])) != 1
        or type(entry) is not dict
        or type(gates) is not dict
        or set(gates) != set(registration["mandatory_gates"])
        or any(type(passed) is not bool for passed in gates.values())
        or type(inference["worker_operation"]) is not str
        or re.fullmatch(r"operation-[0-9a-f]{64}", inference["worker_operation"])
        is None
    ):
        raise BundleBenchmarkRefused("saved_inference_shape")
    if graph_measurement:
        _graph_saved_inference_binding(entry, inference)
        if build_seconds is not None:
            raise BundleBenchmarkRefused("graph_build_seconds_unverified")
    receipt = inference["receipt"]
    roles = entry.get("roles")
    input_role = roles.get("inputs") if type(roles) is dict else None
    if (
        type(input_role) is not dict
        or set(input_role) != {"file", "codec", "sha256"}
        or input_role["codec"] != "numeric_npz"
        or type(input_role["file"]) is not str
        or not input_role["file"]
        or type(input_role["sha256"]) is not str
        or re.fullmatch(r"sha256:[0-9a-f]{64}", input_role["sha256"]) is None
        or type(receipt) is not dict
        or set(receipt)
        != {
            "schema",
            "recipe_digest",
            "state_digest",
            "inputs_digest",
            "predictions_digest",
            "measurement",
        }
        or receipt["schema"] != "carbon.development.bundle-inference.v2"
        or any(
            inference[field] != entry.get(field) or receipt[field] != inference[field]
            for field in ("recipe_digest", "state_digest")
        )
        or receipt["inputs_digest"] != input_role["sha256"]
        or receipt["predictions_digest"] != inference["predictions_digest"]
        or (
            graph_measurement
            and (
                type(roles.get("predictions")) is not dict
                or roles["predictions"].get("sha256") != inference["predictions_digest"]
            )
        )
    ):
        raise BundleBenchmarkRefused("saved_inference_binding")
    measured = receipt["measurement"]
    if (
        type(measured) is not dict
        or set(measured)
        != {
            "scope",
            "timing_s",
            "input_shape",
            "input_dtype",
            "output_shape",
            "output_dtype",
        }
        or measured["scope"]
        != "COLD_SINGLE_WORKER_QUERY_INCLUDES_GRAPH_LOAD_AND_JAX_COMPILE"
        or measured["input_shape"] != registration["timing_profile"]["input_shape"]
        or measured["output_shape"] != registration["output"]["shape"]
        or any(
            type(measured[field]) is not str or not measured[field]
            for field in ("input_dtype", "output_dtype")
        )
        or type(measured["timing_s"]) is not dict
        or set(measured["timing_s"])
        != {"preprocess", "export", "inference", "postprocess"}
        or any(
            type(value) not in (int, float) or not math.isfinite(value) or value < 0
            for value in measured["timing_s"].values()
        )
        or math.fsum(measured["timing_s"].values()) <= 0
    ):
        raise BundleBenchmarkRefused("saved_inference_measurement")
    try:
        raw = json.dumps(
            inference["predictions"], allow_nan=False, separators=(",", ":")
        ).encode()
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise BundleBenchmarkRefused("saved_prediction_encoding") from exc
    if _sha(raw) != receipt["predictions_digest"]:
        raise BundleBenchmarkRefused("saved_prediction_digest")
    outputs = _flat_tensor(inference["predictions"], measured["output_shape"])
    if len(outputs) != registration["output"]["size"]:
        raise BundleBenchmarkRefused("saved_prediction_shape")
    return {
        "schema": MEASUREMENT_SCHEMA,
        "entry_id": entry["entry_id"],
        "challenge": entry["challenge"],
        "challenge_version": entry["challenge_version"],
        "interface_digest": entry["interface_digest"],
        "recipe_digest": entry["recipe_digest"],
        "state_digest": entry["state_digest"],
        "train_digest": entry["train_digest"],
        "batch_size": registration["timing_profile"]["batch_size"],
        "input_shape": measured["input_shape"],
        "output_shape": measured["output_shape"],
        "build_seconds": build_seconds,
        "cases": [
            {
                "id": registration["cases"][0]["id"],
                "status": "OK",
                "source": "MEASURED_INFERENCE_RUN",
                "outputs": outputs,
                "gates": gates,
                "timing_s": measured["timing_s"],
                "peak_memory_bytes": None,
            }
        ],
    }


def benchmark_saved_entry(
    entry,
    custody_receipt_raw,
    trusted_job,
    registration,
    references,
    measured_model,
    score_pack=None,
    *,
    graph_originals=None,
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
            measured_model,
            entry,
            trusted_job,
            registration,
            physics,
            graph_originals=graph_originals,
        )
        body["benchmark"] = solver_benchmark.compare(
            registration, references, [model], score_pack=score_pack
        )
        body["score_status"] = body["benchmark"]["scoring"]["status"]
    return {**body, "result_digest": _sha(_canonical(body))}
