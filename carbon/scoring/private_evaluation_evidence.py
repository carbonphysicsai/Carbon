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
    measurement_from_saved_inference,
    retained_bundle_receipt,
)
from carbon.scoring.solver_benchmark_v3 import BenchmarkScoreRefused

SOURCE_SCHEMA = "carbon.scoring.private-evaluation-source.v1"
SIDECAR_SCHEMA = "carbon.scoring.private-evaluation-binding.v1"
PACK_SOURCE_SCHEMA = "carbon.scoring.private-evaluation-source.v2"
PACK_SIDECAR_SCHEMA = "carbon.scoring.private-evaluation-binding.v2"
DUAL_SIDECAR_SCHEMA = "carbon.scoring.private-evaluation-binding.v3"
#: v3 plus the pinned source-free inference pair its repeat gate read.
PAIRED_SIDECAR_SCHEMA = "carbon.scoring.private-evaluation-binding.v4"
DUAL_MEASUREMENT_SCHEMA = "carbon.scoring.private-dual-measurement.v1"
PAIRED_DUAL_MEASUREMENT_SCHEMA = "carbon.scoring.private-dual-measurement.v2"
_GRADED_ORIGINALS = frozenset({"inference_receipt_raw", "worker_evidence_raw"})
_BUNDLE_ORIGINALS = frozenset(
    {"inference_receipt_raw", "predictions_raw", "bundle_evidence_raw"}
)
_PAIR_ORIGINALS = frozenset({"inference_pair_raw", "inference_pair_sha256"})
_DUAL_MEASUREMENT_FIELDS = {
    "schema",
    "source_receipt_sha256",
    "evaluation_pack_digest",
    "score_pack_digest",
    "measurement_contract_digest",
    "measurement_contract",
    "producer_digest",
    "entry_id",
    "state_digest",
    "measured_model_sha256",
    "inference_receipt_sha256",
    "worker_evidence_sha256",
    "benchmark",
}
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


def _parse_receipt_json(raw, prefix="source_receipt"):
    if type(raw) is not bytes or not 0 < len(raw) <= 1024 * 1024:
        raise PrivateEvaluationEvidenceRefused(f"{prefix}_bytes")

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise PrivateEvaluationEvidenceRefused(f"{prefix}_duplicate_key")
            result[key] = value
        return result

    def reject_constant(_value):
        raise PrivateEvaluationEvidenceRefused(f"{prefix}_nonfinite")

    try:
        result = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique_pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise PrivateEvaluationEvidenceRefused(f"{prefix}_json") from exc
    if type(result) is not dict:
        raise PrivateEvaluationEvidenceRefused(f"{prefix}_shape")
    return result


def _parse_source(raw):
    result = _parse_receipt_json(raw)
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


def _dual_source_binding(
    source, entry, trusted_job, registration, references, queries, physics
):
    expected = {
        "challenge": trusted_job["challenge"],
        "challenge_version": trusted_job["challenge_version"],
        "interface_digest": trusted_job["interface_digest"],
        "train_digest": trusted_job["train_digest"],
        "job_digest": trusted_job["job_digest"],
        "registration_digest": registration["registration_digest"],
        "physics_contract": physics,
    }
    if (
        any(source.get(key) != value for key, value in expected.items())
        or type(source["evaluation_version"]) is not str
        or not source["evaluation_version"]
    ):
        raise PrivateEvaluationEvidenceRefused("evaluation_identity")
    cases = _reference_rows(registration, references)
    if (
        type(queries) is not list
        or len(queries) != len(cases)
        or type(source["cases"]) is not list
        or len(source["cases"]) != len(cases)
    ):
        raise PrivateEvaluationEvidenceRefused("query_roster")
    for case, reference, query, original in zip(
        cases, references, queries, source["cases"], strict=True
    ):
        if type(query) is not bytes:
            raise PrivateEvaluationEvidenceRefused("query_bytes")
        if (
            type(original) is not dict
            or set(original) != _CASE_FIELDS
            or type(original["weight"]) is not type(case["weight"])
            or original
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
        or _sha(queries[0]) != roles["inputs"].get("sha256")
    ):
        raise PrivateEvaluationEvidenceRefused("graph_query_original_binding")


def _rederive_bundle_measurement(entry, registration, originals, measured_model):
    """A bundle's measured model must be exactly what its retained originals
    reduce to: the graded predictions and, when present, the pinned timed
    query's timing. No custody record exists for a bundle's worker evidence,
    so the pinned measurement is recomputed rather than trusted."""
    from carbon.scoring import private_evaluation_source as source

    try:
        gates = measured_model["cases"][0]["gates"]
        *_, inference = source._authenticated_bundle_outputs(
            entry, registration, originals
        )
        derived = measurement_from_saved_inference(
            entry,
            registration,
            inference,
            gates=gates,
            timed_query=originals.get("timed_query"),
        )
    except (
        source.PrivateEvaluationSourceRefused,
        BundleBenchmarkRefused,
        KeyError,
        TypeError,
        IndexError,
        AttributeError,
    ) as exc:
        raise PrivateEvaluationEvidenceRefused(
            "model_query_originals_unavailable"
        ) from exc
    if derived != measured_model:
        raise PrivateEvaluationEvidenceRefused("model_query_originals_unavailable")


def _bind_dual_evaluation(
    *,
    source,
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
    registered_source_receipt_sha256,
    expected_evaluation_pack_digest,
    dual_measurement_receipt_raw,
    registered_dual_measurement_sha256,
    selected_evaluation_pack,
):
    """Authenticate operator-produced measurements, then use the same v4 core.

    The independently registered receipt pin must come from the normal trusted
    producer's write-once operator custody. Hash equality cannot attest that
    caller provenance, producer execution, or scientific adequacy by itself.
    No participant-supplied measurement/gate dictionary is accepted as a pin.
    """
    from carbon.challenge_validator.evaluation_pack import (
        PRIVATE_ROLES,
        PUBLIC_ROLES,
        EvaluationPackSnapshot,
    )
    from carbon.scoring.engine import ScoreEngine

    if (
        source["schema"] != PACK_SOURCE_SCHEMA
        or expected_evaluation_pack_digest is None
    ):
        raise PrivateEvaluationEvidenceRefused("evaluation_pack_source_missing")
    if (
        type(selected_evaluation_pack) is not EvaluationPackSnapshot
        or selected_evaluation_pack.manifest_digest != expected_evaluation_pack_digest
        or selected_evaluation_pack.challenge_id != source["challenge"]
        or selected_evaluation_pack.challenge_version != source["challenge_version"]
    ):
        raise PrivateEvaluationEvidenceRefused("dual_selected_pack_binding")
    missing = selected_evaluation_pack.missing_roles()
    if PUBLIC_ROLES.intersection(missing["public"]) or PRIVATE_ROLES.intersection(
        missing["private"]
    ):
        raise PrivateEvaluationEvidenceRefused("dual_selected_pack_unavailable")
    if (
        type(dual_measurement_receipt_raw) is not bytes
        or type(registered_dual_measurement_sha256) is not str
        or _SHA256.fullmatch(registered_dual_measurement_sha256) is None
    ):
        raise PrivateEvaluationEvidenceRefused("dual_measurement_unavailable")
    if _sha(dual_measurement_receipt_raw) != registered_dual_measurement_sha256:
        raise PrivateEvaluationEvidenceRefused("dual_measurement_pin_mismatch")
    evidence = _parse_receipt_json(dual_measurement_receipt_raw, "dual_measurement")
    paired = type(graph_originals) is dict and _PAIR_ORIGINALS <= set(graph_originals)
    if paired != (evidence.get("schema") == PAIRED_DUAL_MEASUREMENT_SCHEMA) or set(
        evidence
    ) != _DUAL_MEASUREMENT_FIELDS | ({"inference_pair_sha256"} if paired else set()):
        raise PrivateEvaluationEvidenceRefused("dual_measurement_shape")
    if not paired and evidence["schema"] != DUAL_MEASUREMENT_SCHEMA:
        raise PrivateEvaluationEvidenceRefused("dual_measurement_shape")
    graph = type(entry) is dict and entry.get("source_kind") == "graph"
    graded_keys = _GRADED_ORIGINALS if graph else _BUNDLE_ORIGINALS
    # A bundle's per-case graded query may carry its pinned batched timed query.
    timed = (
        {"timed_query"}
        if not graph
        and type(graph_originals) is dict
        and "timed_query" in graph_originals
        else set()
    )
    if (
        type(entry) is not dict
        or type(registration) is not dict
        or type(registration.get("cases")) is not list
        or len(registration["cases"]) != 1
        or type(graph_originals) is not dict
        or set(graph_originals) - _PAIR_ORIGINALS - timed != graded_keys
        or (paired and set(graph_originals) != graded_keys | _PAIR_ORIGINALS | timed)
        or any(type(graph_originals[k]) is not bytes for k in graded_keys)
        or (
            paired
            and (
                type(graph_originals["inference_pair_raw"]) is not bytes
                or _sha(graph_originals["inference_pair_raw"])
                != graph_originals["inference_pair_sha256"]
                or evidence["inference_pair_sha256"]
                != graph_originals["inference_pair_sha256"]
            )
        )
    ):
        raise PrivateEvaluationEvidenceRefused("model_query_originals_unavailable")
    if not graph and (
        _sha(graph_originals["predictions_raw"]) != entry.get("prediction_digest")
        or not retained_bundle_receipt(entry, graph_originals["inference_receipt_raw"])
        or (
            timed
            and not retained_bundle_receipt(
                entry, (graph_originals["timed_query"] or {}).get("receipt_raw")
            )
        )
    ):
        raise PrivateEvaluationEvidenceRefused("model_query_originals_unavailable")
    if not graph:
        _rederive_bundle_measurement(
            entry, registration, graph_originals, measured_model
        )
    graded_originals = (
        {k: graph_originals[k] for k in _GRADED_ORIGINALS} if graph else None
    )
    # This existing reducer authenticates retained originals and raw reference
    # rows. Its descriptive MAE/speed outputs are never used as A or D here.
    try:
        raw_result = benchmark_saved_entry(
            entry,
            custody_receipt_raw,
            trusted_job,
            registration,
            references,
            measured_model,
            None,
            graph_originals=graded_originals,
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
    if raw_result["status"] != "BENCHMARK_REDUCED":
        raise PrivateEvaluationEvidenceRefused("model_query_originals_unavailable")
    _dual_source_binding(
        source,
        entry,
        trusted_job,
        registration,
        references,
        ordered_query_bytes,
        raw_result["physics_contract"],
    )
    basis = evidence["measurement_contract"]
    basis_fields = {
        "schema",
        "producer_digest",
        "accuracy_definition_sha256",
        "important_limit_definition_sha256",
        "design_objective_sha256",
    }
    if (
        type(basis) is not dict
        or set(basis) != basis_fields
        or basis["schema"] != "carbon.scoring.dual-measurement-contract.v1"
        or any(
            type(basis[key]) is not str or _SHA256.fullmatch(basis[key]) is None
            for key in basis_fields - {"schema"}
        )
        or _sha(_canonical(basis)) != score_pack.get("measurement_contract_digest")
        or evidence["producer_digest"] != basis["producer_digest"]
    ):
        raise PrivateEvaluationEvidenceRefused("dual_measurement_contract")
    for role in (
        "accuracy_definition",
        "important_limit_definition",
        "design_objective",
    ):
        selected = selected_evaluation_pack.public[role]
        if type(selected) is str or basis[role + "_sha256"] != selected.get("sha256"):
            raise PrivateEvaluationEvidenceRefused("dual_selected_definition_binding")
    expected = {
        "source_receipt_sha256": registered_source_receipt_sha256,
        "evaluation_pack_digest": expected_evaluation_pack_digest,
        "score_pack_digest": score_pack.get("pack_digest"),
        "measurement_contract_digest": score_pack.get("measurement_contract_digest"),
        "entry_id": entry["entry_id"],
        "state_digest": entry["state_digest"],
        "measured_model_sha256": _sha(_canonical(measured_model)),
        "inference_receipt_sha256": _sha(graph_originals["inference_receipt_raw"]),
        "worker_evidence_sha256": _sha(
            graph_originals["worker_evidence_raw" if graph else "bundle_evidence_raw"]
        ),
    }
    if any(evidence.get(key) != value for key, value in expected.items()):
        raise PrivateEvaluationEvidenceRefused("dual_measurement_original_binding")
    benchmark = evidence["benchmark"]
    models = benchmark.get("models") if type(benchmark) is dict else None
    mask = _sha(_canonical(source["cases"]))
    if (
        type(benchmark) is not dict
        or type(models) is not list
        or len(models) != 1
        or type(models[0]) is not dict
        or models[0].get("artifact_digest") != entry["entry_id"]
        or benchmark.get("challenge") != source["challenge"]
        or benchmark.get("scope") != registration["scope"]
        or benchmark.get("physics_contract_digest")
        != raw_result["physics_contract"]["definition_digest"]
        or benchmark.get("common_mask_digest") != mask
        or benchmark.get("population_role") != source["cases"][0]["role"]
    ):
        raise PrivateEvaluationEvidenceRefused("dual_benchmark_binding")
    gates = models[0].get("gates")
    if type(gates) is not dict or not set(registration["mandatory_gates"]) <= set(
        gates
    ):
        raise PrivateEvaluationEvidenceRefused("dual_gate_original_binding")
    if references[0]["status"] == "RESOLVED":
        native = measured_model["cases"][0].get("gates")
        if type(native) is not dict or any(
            gates[name] != ("PASS" if native[name] else "FAIL")
            for name in registration["mandatory_gates"]
        ):
            raise PrivateEvaluationEvidenceRefused("dual_gate_original_binding")
    try:
        scoring = ScoreEngine.score_dual_benchmark_v4(benchmark, score_pack)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise PrivateEvaluationEvidenceRefused("dual_reduction_refused") from exc
    row = scoring["models"][0]
    expected_reference = {
        "UNRESOLVED": "INDETERMINATE_EVIDENCE",
        "FAILED_INFRA": "FAILED_INFRA",
    }
    if (
        references[0]["status"] in expected_reference
        and row["status"] != expected_reference[references[0]["status"]]
    ):
        raise PrivateEvaluationEvidenceRefused("dual_reference_status_binding")
    score_digest = _sha(_canonical(scoring))
    if score_digest != expected_result_digest:
        raise PrivateEvaluationEvidenceRefused("result_digest_mismatch")
    coverage = {
        status: sum(ref["status"] == status for ref in references)
        for status in ("RESOLVED", "UNRESOLVED", "FAILED_INFRA")
    }
    return {
        "schema": PAIRED_SIDECAR_SCHEMA if paired else DUAL_SIDECAR_SCHEMA,
        "scope": "PRIVATE_OPERATOR_DEVELOPMENT",
        "status": "BOUND_DEVELOPMENT_ONLY",
        "official_score": False,
        "official_eligible": False,
        **{
            key: source[key]
            for key in (
                "challenge",
                "challenge_version",
                "evaluation_version",
                "registration_digest",
            )
        },
        "evaluation_pack_digest": expected_evaluation_pack_digest,
        "source_receipt_sha256": registered_source_receipt_sha256,
        "dual_measurement_receipt_sha256": registered_dual_measurement_sha256,
        **(
            {"inference_pair_sha256": graph_originals["inference_pair_sha256"]}
            if paired
            else {}
        ),
        "evaluation_version_digest": _sha(_canonical(source)),
        "entry_id": entry["entry_id"],
        "state_digest": entry["state_digest"],
        "measurement_contract_digest": score_pack["measurement_contract_digest"],
        "producer_digest": basis["producer_digest"],
        "common_mask_digest": mask,
        "ordered_query_material_digest": _sha(
            _canonical([_sha(query) for query in ordered_query_bytes])
        ),
        "reference_rows_digest": _sha(_canonical(references)),
        "reference_coverage": coverage,
        "reference_coverage_digest": _sha(
            _canonical(
                [{"id": ref["id"], "status": ref["status"]} for ref in references]
            )
        ),
        "score_compatibility": {
            "score_pack_digest": score_pack["pack_digest"],
            "scoring_version": score_pack["schema"],
            "execution_profile_digest": _sha(
                _canonical(registration["timing_profile"])
            ),
        },
        "score_result_digest": score_digest,
        "model_result_digest": _sha(
            _canonical(
                {
                    "source": source,
                    "entry_id": entry["entry_id"],
                    "state_digest": entry["state_digest"],
                    "measurement_receipt": evidence,
                    "scoring": scoring,
                }
            )
        ),
        "scoring": scoring,
        "model_p": {
            "measurement_status": raw_result["benchmark"]["models"][0]["by_role"]["P"][
                "status"
            ],
            "gate_outcomes": row["gates"],
            "score_status": row["status"],
            "physics_benefit": row["legs"]["A"],
            "design_benefit": row["legs"]["D"],
            "total_score": row["score"],
            "decision_outcome": row["decision_outcome"],
        },
    }


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
    dual_measurement_receipt_raw=None,
    registered_dual_measurement_sha256=None,
    selected_evaluation_pack=None,
):
    """Bind one already reduced result to an independently pinned source.

    ``registered_source_receipt_sha256`` must be read from trusted operator
    registration, not copied from ``evaluation_source_receipt_raw``. The
    function verifies equality but cannot attest that caller provenance.
    A selected evaluation pack requires a v2 source and the exact trusted
    manifest pin retained by the receiver; a public result label is not a pin.
    A prospective v4 pack additionally requires the independent operator pin
    of its trusted dual-measurement receipt. For v4, expected_result_digest is
    SHA256 of the same core's scoring result, canonical JSON plus LF; v3 keeps
    its existing bundle-result digest. The returned v4 binding remains private
    and nonofficial even when its measured candidate passes the rule.
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
    if score_pack.get("schema") == "carbon.scoring.dual-benchmark-pack.v4":
        return _bind_dual_evaluation(
            source=source,
            entry=entry,
            custody_receipt_raw=custody_receipt_raw,
            trusted_job=trusted_job,
            registration=registration,
            references=references,
            measured_model=measured_model,
            score_pack=score_pack,
            graph_originals=graph_originals,
            expected_result_digest=expected_result_digest,
            ordered_query_bytes=ordered_query_bytes,
            registered_source_receipt_sha256=registered_source_receipt_sha256,
            expected_evaluation_pack_digest=expected_evaluation_pack_digest,
            dual_measurement_receipt_raw=dual_measurement_receipt_raw,
            registered_dual_measurement_sha256=registered_dual_measurement_sha256,
            selected_evaluation_pack=selected_evaluation_pack,
        )
    if (
        dual_measurement_receipt_raw is not None
        or registered_dual_measurement_sha256 is not None
    ):
        raise PrivateEvaluationEvidenceRefused("dual_measurements_for_nondual_pack")
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
