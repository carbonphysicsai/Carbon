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

from carbon.challenge_validator.evaluation_pack import EvaluationPackSnapshot
from carbon.registry.digest import is_sha256_digest
from carbon.scoring.benchmark_evidence import (
    BenchmarkRefused,
    physics_contract_identity,
)

PACK_SOURCE_SCHEMA = "carbon.scoring.private-evaluation-source.v2"
_REFERENCE_STATUS = frozenset({"RESOLVED", "UNRESOLVED", "FAILED_INFRA"})
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
    result. This function validates the relationship of supplied originals; it
    cannot by itself attest the caller's custody of that object. The trusted
    task path retains ``raw`` and registers ``sha256`` independently.
    """
    if type(selected_pack) is not EvaluationPackSnapshot or not is_sha256_digest(
        selected_pack.manifest_digest
    ):
        raise PrivateEvaluationSourceRefused("selected_pack_missing")
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
