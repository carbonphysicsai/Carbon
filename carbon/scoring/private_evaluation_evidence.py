"""Private DEVELOPMENT binding for a scored, reference-covered evaluation.

This reducer executes no model or reference. Current evidence-link support
requires a graph entry whose original worker evidence authenticates its one
measured query. Other artifact forms need original per-case query and worker
bindings before this reducer can attest them. Its source pin must come
from an independently registered operator record; a caller supplied label is
not a pin. The returned sidecar stays in operator custody and grants neither
scientific acceptance nor public scoring authority.
"""

from __future__ import annotations

import hashlib
import json
import re

from carbon.scoring.benchmark_evidence import BenchmarkRefused
from carbon.scoring.bundle_benchmark_core import (
    BundleBenchmarkRefused,
    benchmark_saved_entry,
)
from carbon.scoring.solver_benchmark_v3 import BenchmarkScoreRefused

SOURCE_SCHEMA = "carbon.scoring.private-evaluation-source.v1"
SIDECAR_SCHEMA = "carbon.scoring.private-evaluation-binding.v1"
PACK_SOURCE_SCHEMA = "carbon.scoring.private-evaluation-source.v2"
PACK_SIDECAR_SCHEMA = "carbon.scoring.private-evaluation-binding.v2"
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SOURCE_FIELDS = {
    "schema",
    "challenge",
    "challenge_version",
    "evaluation_version",
    "interface_digest",
    "train_digest",
    "job_digest",
    "registration_digest",
    "physics_contract",
    "cases",
}
_CASE_FIELDS = {
    "id",
    "role",
    "weight",
    "query_sha256",
    "reference_row_sha256",
    "reference_status",
}


class PrivateEvaluationEvidenceRefused(ValueError):
    """The private source, score, or retained model binding is incomplete."""


def _canonical(value):
    try:
        return (
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, OverflowError, RecursionError) as exc:
        raise PrivateEvaluationEvidenceRefused("noncanonical_evidence") from exc


def _sha(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _parse_source(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= 1024 * 1024:
        raise PrivateEvaluationEvidenceRefused("source_receipt_bytes")

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise PrivateEvaluationEvidenceRefused("source_receipt_duplicate_key")
            result[key] = value
        return result

    def reject_constant(_value):
        raise PrivateEvaluationEvidenceRefused("source_receipt_nonfinite")

    try:
        result = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique_pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise PrivateEvaluationEvidenceRefused("source_receipt_json") from exc
    if type(result) is not dict:
        raise PrivateEvaluationEvidenceRefused("source_receipt_shape")
    schema = result.get("schema")
    if type(schema) is not str or schema not in {SOURCE_SCHEMA, PACK_SOURCE_SCHEMA}:
        raise PrivateEvaluationEvidenceRefused("source_receipt_shape")
    fields = (
        _SOURCE_FIELDS | {"evaluation_pack_digest"}
        if schema == PACK_SOURCE_SCHEMA
        else _SOURCE_FIELDS
    )
    if set(result) != fields:
        raise PrivateEvaluationEvidenceRefused("source_receipt_shape")
    return result


def _reference_rows(registration, references):
    cases = registration.get("cases")
    if type(cases) is not list or type(references) is not list:
        raise PrivateEvaluationEvidenceRefused("reference_roster")
    if len(cases) != len(references):
        raise PrivateEvaluationEvidenceRefused("reference_roster")
    for case, reference in zip(cases, references, strict=True):
        if (
            type(case) is not dict
            or type(reference) is not dict
            or reference.get("id") != case.get("id")
            or reference.get("status") not in {"RESOLVED", "UNRESOLVED", "FAILED_INFRA"}
        ):
            raise PrivateEvaluationEvidenceRefused("reference_roster")
    return cases


def bind_private_evaluation_evidence(
    *,
    entry,
    custody_receipt_raw,
    trusted_job,
    registration,
    references,
    measured_model,
    score_pack,
    graph_originals,
    expected_result_digest,
    ordered_query_bytes,
    evaluation_source_receipt_raw,
    registered_source_receipt_sha256,
    expected_evaluation_pack_digest=None,
):
    """Bind one already reduced result to an independently pinned source.

    ``registered_source_receipt_sha256`` must be read from trusted operator
    registration, not copied from ``evaluation_source_receipt_raw``. The
    function verifies equality but cannot attest that caller provenance.
    A selected evaluation pack requires a v2 source and the exact trusted
    manifest pin retained by the receiver; a public result label is not a pin.
    No raw cases, query bytes, or reference values enter the returned sidecar.
    """
    if (
        type(registered_source_receipt_sha256) is not str
        or _SHA256.fullmatch(registered_source_receipt_sha256) is None
    ):
        raise PrivateEvaluationEvidenceRefused("source_pin_missing")
    if (
        type(evaluation_source_receipt_raw) is not bytes
        or _sha(evaluation_source_receipt_raw) != registered_source_receipt_sha256
    ):
        raise PrivateEvaluationEvidenceRefused("source_pin_mismatch")
    source = _parse_source(evaluation_source_receipt_raw)
    pack_bound = source["schema"] == PACK_SOURCE_SCHEMA
    if expected_evaluation_pack_digest is not None and (
        type(expected_evaluation_pack_digest) is not str
        or _SHA256.fullmatch(expected_evaluation_pack_digest) is None
    ):
        raise PrivateEvaluationEvidenceRefused("evaluation_pack_pin_invalid")
    if pack_bound:
        if expected_evaluation_pack_digest is None:
            raise PrivateEvaluationEvidenceRefused("evaluation_pack_pin_missing")
        if source["evaluation_pack_digest"] != expected_evaluation_pack_digest:
            raise PrivateEvaluationEvidenceRefused("evaluation_pack_pin_mismatch")
    elif expected_evaluation_pack_digest is not None:
        raise PrivateEvaluationEvidenceRefused("evaluation_pack_source_missing")
    if type(score_pack) is not dict:
        raise PrivateEvaluationEvidenceRefused("score_compatibility_unavailable")
    if (
        type(expected_result_digest) is not str
        or _SHA256.fullmatch(expected_result_digest) is None
    ):
        raise PrivateEvaluationEvidenceRefused("result_digest_missing")
    if (
        type(entry) is not dict
        or entry.get("source_kind") != "graph"
        or type(registration) is not dict
        or type(registration.get("cases")) is not list
        or len(registration["cases"]) != 1
        or type(graph_originals) is not dict
        or set(graph_originals) != {"inference_receipt_raw", "worker_evidence_raw"}
    ):
        raise PrivateEvaluationEvidenceRefused("model_query_originals_unavailable")
    try:
        result = benchmark_saved_entry(
            entry,
            custody_receipt_raw,
            trusted_job,
            registration,
            references,
            measured_model,
            score_pack,
            graph_originals=graph_originals,
        )
    except (
        BundleBenchmarkRefused,
        BenchmarkRefused,
        BenchmarkScoreRefused,
        KeyError,
        TypeError,
        ValueError,
        OverflowError,
    ) as exc:
        raise PrivateEvaluationEvidenceRefused("benchmark_reduction_refused") from exc
    if result["result_digest"] != expected_result_digest:
        raise PrivateEvaluationEvidenceRefused("result_digest_mismatch")
    if (
        result["status"] != "BENCHMARK_REDUCED"
        or result["score_status"] != "DEVELOPMENT_ONLY"
        or result["score_pack_source"] != "REGISTERED"
        or result["score_pack_digest"] != score_pack.get("pack_digest")
        or score_pack.get("schema") != "carbon.scoring.solver-benchmark-pack.v3"
    ):
        raise PrivateEvaluationEvidenceRefused("score_compatibility_unavailable")
    benchmark = result.get("benchmark")
    scoring = benchmark.get("scoring") if type(benchmark) is dict else None
    benchmark_models = benchmark.get("models") if type(benchmark) is dict else None
    scoring_models = scoring.get("models") if type(scoring) is dict else None
    if (
        type(scoring) is not dict
        or scoring.get("status") != "DEVELOPMENT_ONLY"
        or scoring.get("pack_digest") != score_pack["pack_digest"]
        or type(benchmark_models) is not list
        or len(benchmark_models) != 1
        or type(scoring_models) is not list
        or len(scoring_models) != 1
        or benchmark_models[0].get("artifact_digest") != result["entry_id"]
        or scoring_models[0].get("artifact_digest") != result["entry_id"]
        or type(benchmark_models[0].get("by_role")) is not dict
        or type(benchmark_models[0]["by_role"].get("P")) is not dict
    ):
        raise PrivateEvaluationEvidenceRefused("score_result_unavailable")
    p_role = benchmark_models[0]["by_role"]["P"]
    if (
        type(p_role.get("status")) is not str
        or type(p_role.get("gate_failures")) is not dict
        or type(scoring_models[0].get("status")) is not str
    ):
        raise PrivateEvaluationEvidenceRefused("score_result_unavailable")
    if type(trusted_job) is not dict:
        raise PrivateEvaluationEvidenceRefused("evaluation_identity")
    expected_identity = {
        "schema": source["schema"],
        "challenge": trusted_job["challenge"],
        "challenge_version": trusted_job["challenge_version"],
        "interface_digest": trusted_job["interface_digest"],
        "train_digest": trusted_job["train_digest"],
        "job_digest": trusted_job["job_digest"],
        "registration_digest": registration["registration_digest"],
        "physics_contract": result["physics_contract"],
    }
    if (
        any(source.get(key) != value for key, value in expected_identity.items())
        or type(source["evaluation_version"]) is not str
        or not source["evaluation_version"]
    ):
        raise PrivateEvaluationEvidenceRefused("evaluation_identity")
    cases = _reference_rows(registration, references)
    if (
        type(ordered_query_bytes) is not list
        or len(ordered_query_bytes) != len(cases)
        or type(source["cases"]) is not list
        or len(source["cases"]) != len(cases)
    ):
        raise PrivateEvaluationEvidenceRefused("query_roster")
    for case, reference, query, source_case in zip(
        cases, references, ordered_query_bytes, source["cases"], strict=True
    ):
        if type(query) is not bytes:
            raise PrivateEvaluationEvidenceRefused("query_bytes")
        if (
            type(source_case) is not dict
            or set(source_case) != _CASE_FIELDS
            or type(source_case["weight"]) is not type(case["weight"])
            or source_case
            != {
                "id": case["id"],
                "role": case["role"],
                "weight": case["weight"],
                "query_sha256": _sha(query),
                "reference_row_sha256": _sha(_canonical(reference)),
                "reference_status": reference["status"],
            }
        ):
            raise PrivateEvaluationEvidenceRefused("source_case_binding")
    roles = entry.get("roles")
    if (
        type(roles) is not dict
        or type(roles.get("inputs")) is not dict
        or _sha(ordered_query_bytes[0]) != roles["inputs"].get("sha256")
    ):
        raise PrivateEvaluationEvidenceRefused("graph_query_original_binding")

    evaluation_version_digest = _sha(_canonical(source))
    compatibility = {
        "score_pack_digest": result["score_pack_digest"],
        "scoring_version": score_pack["schema"],
        "execution_profile_digest": _sha(_canonical(registration["timing_profile"])),
    }
    reference_coverage = {
        status: sum(row["status"] == status for row in references)
        for status in ("RESOLVED", "UNRESOLVED", "FAILED_INFRA")
    }
    query_material_digest = _sha(
        _canonical([_sha(query) for query in ordered_query_bytes])
    )
    reference_rows_digest = _sha(_canonical(references))
    reference_coverage_digest = _sha(
        _canonical([{"id": row["id"], "status": row["status"]} for row in references])
    )
    score_result_digest = _sha(_canonical(scoring))
    model_result_digest = _sha(
        _canonical(
            {
                "evaluation_version_digest": evaluation_version_digest,
                "entry_id": result["entry_id"],
                "state_digest": result["state_digest"],
                "measured_model": measured_model,
                "score_pack": score_pack,
                "score_compatibility": compatibility,
                "benchmark_result": result,
            }
        )
    )
    return {
        "schema": PACK_SIDECAR_SCHEMA if pack_bound else SIDECAR_SCHEMA,
        **(
            {"evaluation_pack_digest": expected_evaluation_pack_digest}
            if pack_bound
            else {}
        ),
        "scope": "PRIVATE_OPERATOR_DEVELOPMENT",
        "status": "BOUND_DEVELOPMENT_ONLY",
        "source_receipt_sha256": registered_source_receipt_sha256,
        "challenge": source["challenge"],
        "challenge_version": source["challenge_version"],
        "evaluation_version": source["evaluation_version"],
        "registration_digest": registration["registration_digest"],
        "evaluation_version_digest": evaluation_version_digest,
        "ordered_query_material_digest": query_material_digest,
        "reference_rows_digest": reference_rows_digest,
        "reference_coverage_digest": reference_coverage_digest,
        "reference_coverage": reference_coverage,
        "entry_id": result["entry_id"],
        "state_digest": result["state_digest"],
        "score_compatibility": compatibility,
        "benchmark_result_digest": result["result_digest"],
        "score_result_digest": score_result_digest,
        "model_p": {
            "measurement_status": p_role["status"],
            "gate_failures": p_role["gate_failures"],
            "score_status": scoring_models[0]["status"],
            "performance_score": scoring_models[0].get("performance_score"),
        },
        "model_result_digest": model_result_digest,
    }
