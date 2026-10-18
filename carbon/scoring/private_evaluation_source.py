"""Build a private v2 evaluation source receipt from trusted run originals.

The operator selects a retained Challenge pack and owns this call. The receipt
contains identities and digests only: no protected query bytes, reference
values, or participant-controlled label. Its caller stores the returned bytes
write-once and independently registers their digest for the ScoreLab binder.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from carbon.challenge_validator.evaluation_pack import (
    PRIVATE_ROLES,
    EvaluationPackSnapshot,
)
from carbon.registry.digest import is_sha256_digest
from carbon.scoring.benchmark_evidence import (
    BenchmarkRefused,
    physics_contract_identity,
)
from carbon.scoring.dual_score import DualScoreRefused, register_pack, score

PACK_SOURCE_SCHEMA = "carbon.scoring.private-evaluation-source.v2"
DUAL_MEASUREMENT_SCHEMA = "carbon.scoring.private-dual-measurement.v1"
DUAL_MEASUREMENT_CONTRACT_SCHEMA = "carbon.scoring.dual-measurement-contract.v1"
_REFERENCE_STATUS = frozenset({"RESOLVED", "UNRESOLVED", "FAILED_INFRA"})
_REQUIRED_PUBLIC_ROLES = frozenset(
    {"construction_kit", "interface", "train", "physics_contract"}
)
_MAX_RECEIPT_BYTES = 1024 * 1024


class PrivateEvaluationSourceRefused(ValueError):
    """The trusted source material is absent, inconsistent, or too large."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PreparedPrivateEvaluationSource:
    raw: bytes
    sha256: str
    evaluation_pack_digest: str


@dataclass(frozen=True)
class PreparedPrivateDualMeasurement:
    raw: bytes
    sha256: str
    evaluation_pack_digest: str
    measured_model: dict


def produce_dual_benchmark_input(
    *,
    selected_pack: EvaluationPackSnapshot,
    public_root: Path,
    private_root: Path,
    entry: dict,
    trusted_job: dict,
    registration: dict,
    references: list[dict],
    graph_originals: dict,
    evaluation_source_receipt_raw: bytes,
) -> tuple[dict, dict, str]:
    """Resolve a fixed Carbon-owned Gate/A/D producer for one Challenge.

    No actual Challenge has an adopted measurement law here. Only a distinct,
    inert software fixture may replace this internal hook in tests. A real
    producer must compute from verified saved outputs and reference originals.
    """
    raise PrivateEvaluationSourceRefused("dual_measurement_producer_unavailable")


def produce_registered_dual_measurement(
    *,
    selected_pack: EvaluationPackSnapshot,
    public_root: Path,
    private_root: Path,
    entry: dict,
    trusted_job: dict,
    registration: dict,
    references: list[dict],
    graph_originals: dict,
    evaluation_source_receipt_raw: bytes,
) -> PreparedPrivateDualMeasurement:
    """Bind a fixed producer's output with the real source/pack receipt checks.

    The caller retains the resulting bytes and independently registers its
    SHA in owner custody. An unavailable producer leaves grading unavailable.
    """
    measured_model, benchmark, producer_digest = produce_dual_benchmark_input(
        selected_pack=selected_pack,
        public_root=public_root,
        private_root=private_root,
        entry=entry,
        trusted_job=trusted_job,
        registration=registration,
        references=references,
        graph_originals=graph_originals,
        evaluation_source_receipt_raw=evaluation_source_receipt_raw,
    )
    return build_dual_measurement_receipt(
        selected_pack=selected_pack,
        public_root=public_root,
        private_root=private_root,
        entry=entry,
        measured_model=measured_model,
        graph_originals=graph_originals,
        evaluation_source_receipt_raw=evaluation_source_receipt_raw,
        benchmark=benchmark,
        producer_digest=producer_digest,
    )


def _sha(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _canonical(value: object) -> bytes:
    try:
        return (
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, OverflowError, RecursionError) as exc:
        raise PrivateEvaluationSourceRefused("source_json") from exc


def build_pack_source_receipt(
    *,
    selected_pack: EvaluationPackSnapshot,
    entry: dict,
    trusted_job: dict,
    registration: dict,
    references: list,
    ordered_query_bytes: list[bytes],
    evaluation_version: str,
) -> PreparedPrivateEvaluationSource:
    """Prepare v2 bytes for one selected, frozen pack and registered case list.

    ``selected_pack`` must come from the operator's retained ``load_pack``
    result. The trusted caller must verify role bytes against the actual run
    using each role's existing validator before this function is called. This
    function checks used role availability, the TRAIN pin, and supplied
    original identities; it cannot attest caller custody or prove the other
    pack role relationships by itself. The task path retains ``raw`` and
    registers ``sha256`` independently.
    """
    if type(selected_pack) is not EvaluationPackSnapshot or not is_sha256_digest(
        selected_pack.manifest_digest
    ):
        raise PrivateEvaluationSourceRefused("selected_pack_missing")
    missing = selected_pack.missing_roles()
    if _REQUIRED_PUBLIC_ROLES.intersection(
        missing["public"]
    ) or PRIVATE_ROLES.intersection(missing["private"]):
        raise PrivateEvaluationSourceRefused("selected_pack_incomplete")
    if type(evaluation_version) is not str or not evaluation_version:
        raise PrivateEvaluationSourceRefused("evaluation_version_missing")
    if any(type(value) is not dict for value in (entry, trusted_job, registration)):
        raise PrivateEvaluationSourceRefused("source_identity")
    challenge = selected_pack.challenge_id
    version = selected_pack.challenge_version
    if (
        entry.get("challenge") != challenge
        or entry.get("challenge_version") != version
        or trusted_job.get("challenge") != challenge
        or trusted_job.get("challenge_version") != version
        or registration.get("challenge") != challenge
        or registration.get("job_digest") != trusted_job.get("job_digest")
        or registration.get("train_digest") != trusted_job.get("train_digest")
        or entry.get("train_digest") != trusted_job.get("train_digest")
        or entry.get("interface_digest") != trusted_job.get("interface_digest")
        or not is_sha256_digest(registration.get("registration_digest"))
        or not all(
            is_sha256_digest(value)
            for value in (
                entry.get("interface_digest"),
                entry.get("train_digest"),
                trusted_job.get("job_digest"),
            )
        )
    ):
        raise PrivateEvaluationSourceRefused("source_identity")
    if selected_pack.public["train"]["sha256"] != entry["train_digest"]:
        raise PrivateEvaluationSourceRefused("selected_pack_train_mismatch")
    try:
        physics = physics_contract_identity(trusted_job["physics_contract"])
    except (BenchmarkRefused, KeyError, TypeError, ValueError) as exc:
        raise PrivateEvaluationSourceRefused("physics_contract") from exc
    if registration.get("physics_contract") != trusted_job["physics_contract"]:
        raise PrivateEvaluationSourceRefused("physics_contract")
    cases = registration.get("cases")
    if (
        type(cases) is not list
        or not cases
        or type(references) is not list
        or type(ordered_query_bytes) is not list
        or len(cases) != len(references)
        or len(cases) != len(ordered_query_bytes)
    ):
        raise PrivateEvaluationSourceRefused("source_roster")
    source_cases = []
    seen = set()
    for case, reference, query in zip(
        cases, references, ordered_query_bytes, strict=True
    ):
        weight = case.get("weight") if type(case) is dict else None
        try:
            finite_weight = type(weight) in (int, float) and math.isfinite(weight)
        except (OverflowError, ValueError, TypeError):
            finite_weight = False
        if (
            type(case) is not dict
            or type(reference) is not dict
            or type(query) is not bytes
            or not query
            or type(case.get("id")) is not str
            or not case["id"]
            or case["id"] in seen
            or reference.get("id") != case["id"]
            or type(reference.get("status")) is not str
            or reference.get("status") not in _REFERENCE_STATUS
            or type(case.get("role")) is not str
            or not case["role"]
            or not finite_weight
        ):
            raise PrivateEvaluationSourceRefused("source_case")
        seen.add(case["id"])
        source_cases.append(
            {
                "id": case["id"],
                "role": case["role"],
                "weight": case["weight"],
                "query_sha256": _sha(query),
                "reference_row_sha256": _sha(_canonical(reference)),
                "reference_status": reference["status"],
            }
        )
    body = {
        "schema": PACK_SOURCE_SCHEMA,
        "challenge": challenge,
        "challenge_version": version,
        "evaluation_version": evaluation_version,
        "interface_digest": entry["interface_digest"],
        "train_digest": entry["train_digest"],
        "job_digest": trusted_job["job_digest"],
        "registration_digest": registration["registration_digest"],
        "physics_contract": physics,
        "cases": source_cases,
        "evaluation_pack_digest": selected_pack.manifest_digest,
    }
    raw = _canonical(body)
    if len(raw) > _MAX_RECEIPT_BYTES:
        raise PrivateEvaluationSourceRefused("source_receipt_too_large")
    return PreparedPrivateEvaluationSource(
        raw=raw,
        sha256=_sha(raw),
        evaluation_pack_digest=selected_pack.manifest_digest,
    )


def _parse_pack_source(raw: bytes) -> dict:
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_RECEIPT_BYTES:
        raise PrivateEvaluationSourceRefused("dual_source_bytes")

    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise PrivateEvaluationSourceRefused("dual_source_duplicate_key")
            value[key] = item
        return value

    def reject_constant(_value):
        raise PrivateEvaluationSourceRefused("dual_source_nonfinite")

    try:
        source = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=reject_constant,
        )
    except PrivateEvaluationSourceRefused:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise PrivateEvaluationSourceRefused("dual_source_json") from exc
    if (
        type(source) is not dict
        or source.get("schema") != PACK_SOURCE_SCHEMA
        or set(source)
        != {
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
            "evaluation_pack_digest",
        }
        or _canonical(source) != raw
    ):
        raise PrivateEvaluationSourceRefused("dual_source_shape")
    return source


def build_dual_measurement_receipt(
    *,
    selected_pack: EvaluationPackSnapshot,
    public_root: Path,
    private_root: Path,
    entry: dict,
    measured_model: dict,
    graph_originals: dict,
    evaluation_source_receipt_raw: bytes,
    benchmark: dict,
    producer_digest: str,
) -> PreparedPrivateDualMeasurement:
    """Pin a trusted producer's DEVELOPMENT A/D measurements to saved originals.

    The Carbon-owned caller must run the selected producer and independently
    register this receipt's SHA. This pure builder checks identities and exact
    pack bytes; it cannot attest producer execution or scientific adequacy.
    The private binder verifies the saved query, reference, model and worker
    originals before the shared scoring core may consume ``benchmark``.
    """
    if type(selected_pack) is not EvaluationPackSnapshot or not is_sha256_digest(
        selected_pack.manifest_digest
    ):
        raise PrivateEvaluationSourceRefused("selected_pack_missing")
    source = _parse_pack_source(evaluation_source_receipt_raw)
    if source["evaluation_pack_digest"] != selected_pack.manifest_digest:
        raise PrivateEvaluationSourceRefused("dual_pack_mismatch")
    missing = selected_pack.missing_roles()
    if (
        any(
            role in missing["public"]
            for role in (
                "accuracy_definition",
                "important_limit_definition",
                "design_objective",
            )
        )
        or "score_pack" in missing["private"]
    ):
        raise PrivateEvaluationSourceRefused("dual_pack_incomplete")
    if (
        type(entry) is not dict
        or type(measured_model) is not dict
        or type(benchmark) is not dict
        or type(graph_originals) is not dict
        or set(graph_originals) != {"inference_receipt_raw", "worker_evidence_raw"}
        or not all(type(value) is bytes and value for value in graph_originals.values())
        or not is_sha256_digest(producer_digest)
        or not is_sha256_digest(entry.get("entry_id"))
        or not is_sha256_digest(entry.get("state_digest"))
        or entry.get("challenge") != source["challenge"]
        or entry.get("challenge_version") != source["challenge_version"]
        or entry.get("interface_digest") != source["interface_digest"]
        or entry.get("train_digest") != source["train_digest"]
        or measured_model.get("entry_id") != entry["entry_id"]
        or measured_model.get("state_digest") != entry["state_digest"]
        or selected_pack.challenge_id != source["challenge"]
        or selected_pack.challenge_version != source["challenge_version"]
    ):
        raise PrivateEvaluationSourceRefused("dual_model_identity")
    try:
        accuracy = selected_pack.read_json_role(
            public_root, "public", "accuracy_definition", max_bytes=1024 * 1024
        )
        limits = selected_pack.read_json_role(
            public_root,
            "public",
            "important_limit_definition",
            max_bytes=1024 * 1024,
        )
        design = selected_pack.read_json_role(
            public_root, "public", "design_objective", max_bytes=1024 * 1024
        )
        pack_body = selected_pack.read_json_role(
            private_root, "private", "score_pack", max_bytes=1024 * 1024
        )
    except ValueError as exc:
        raise PrivateEvaluationSourceRefused("dual_pack_role") from exc
    if (
        type(accuracy) is not dict
        or type(limits) is not dict
        or type(design) is not dict
        or accuracy.get("producer_digest") != producer_digest
    ):
        raise PrivateEvaluationSourceRefused("dual_producer_pin")
    basis = {
        "schema": DUAL_MEASUREMENT_CONTRACT_SCHEMA,
        "producer_digest": producer_digest,
        "accuracy_definition_sha256": selected_pack.public["accuracy_definition"][
            "sha256"
        ],
        "important_limit_definition_sha256": selected_pack.public[
            "important_limit_definition"
        ]["sha256"],
        "design_objective_sha256": selected_pack.public["design_objective"]["sha256"],
    }
    contract_digest = _sha(_canonical(basis))
    if type(pack_body) is not dict or "pack_digest" not in pack_body:
        raise PrivateEvaluationSourceRefused("dual_score_pack")
    try:
        pack = register_pack(
            {key: value for key, value in pack_body.items() if key != "pack_digest"}
        )
    except DualScoreRefused as exc:
        raise PrivateEvaluationSourceRefused("dual_score_pack") from exc
    if (
        pack != pack_body
        or pack["measurement_contract_digest"] != contract_digest
        or pack["challenge"] != source["challenge"]
        or type(source["physics_contract"]) is not dict
        or pack["physics_contract_digest"]
        != source["physics_contract"].get("definition_digest")
    ):
        raise PrivateEvaluationSourceRefused("dual_score_pack_binding")
    cases = source.get("cases")
    if (
        type(cases) is not list
        or len(cases) != 1
        or type(cases[0]) is not dict
        or cases[0].get("role") not in {"P", "Q"}
        or benchmark.get("common_mask_digest") != _sha(_canonical(cases))
        or benchmark.get("population_role") != cases[0]["role"]
        or type(benchmark.get("models")) is not list
        or len(benchmark["models"]) != 1
        or type(benchmark["models"][0]) is not dict
        or benchmark["models"][0].get("artifact_digest") != entry["entry_id"]
    ):
        raise PrivateEvaluationSourceRefused("dual_common_mask")
    try:
        score(benchmark, pack)
    except DualScoreRefused as exc:
        raise PrivateEvaluationSourceRefused("dual_benchmark") from exc
    detached_measured_model = json.loads(_canonical(measured_model))
    body = {
        "schema": DUAL_MEASUREMENT_SCHEMA,
        "source_receipt_sha256": _sha(evaluation_source_receipt_raw),
        "evaluation_pack_digest": selected_pack.manifest_digest,
        "score_pack_digest": pack["pack_digest"],
        "measurement_contract": basis,
        "measurement_contract_digest": contract_digest,
        "producer_digest": producer_digest,
        "entry_id": entry["entry_id"],
        "state_digest": entry["state_digest"],
        "measured_model_sha256": _sha(_canonical(detached_measured_model)),
        "inference_receipt_sha256": _sha(graph_originals["inference_receipt_raw"]),
        "worker_evidence_sha256": _sha(graph_originals["worker_evidence_raw"]),
        "benchmark": benchmark,
    }
    raw = _canonical(body)
    if len(raw) > _MAX_RECEIPT_BYTES:
        raise PrivateEvaluationSourceRefused("dual_receipt_too_large")
    return PreparedPrivateDualMeasurement(
        raw, _sha(raw), selected_pack.manifest_digest, detached_measured_model
    )
