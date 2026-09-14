"""Nominal C-06 DEVELOPMENT evidence and receipt values.

These values commit to already-produced public-development evidence. They
cannot represent a qualified, protected, score-authoritative, archived,
network-eligible, or settling result.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import StrEnum

SCHEMA = "carbon.c06.development-evaluation-receipt.v1"
PUBLIC_SCHEMA = "carbon.c06.public-development-receipt.v1"
REVIEWER_SCHEMA = "carbon.c06.reviewer-development-receipt.v1"
LEDGER_SCHEMA = "carbon.c06.development-evidence-ledger.v1"
AUTHORITY_MARKER = "DEVELOPMENT_EVIDENCE_ONLY_NOT_OFFICIAL"
SIGNING_SCOPE = "DEVELOPMENT_NON_OFFICIAL"
SIGNATURE_ALGORITHM = "Ed25519"

_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[._:-][A-Za-z0-9]+)*\Z", re.ASCII)
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z", re.ASCII)


class AuditCode(StrEnum):
    INVALID = "audit.request.invalid"
    DENIED = "audit.authority.denied"
    SIGNATURE = "audit.signature.invalid"
    STALE_KEY = "audit.signing_key.stale"
    MISSING_EVIDENCE = "audit.evidence.missing"
    CONFLICT = "audit.ledger.conflict"
    STORE = "audit.ledger.store_failure"
    STATE = "audit.ledger.state_invalid"


class AuditFailure(RuntimeError):
    """Stable non-echoing C-06 failure."""

    def __init__(self, code: AuditCode) -> None:
        self.code = code if type(code) is AuditCode else AuditCode.INVALID
        super().__init__("Evaluation evidence operation failed.")


class DevelopmentRunStatus(StrEnum):
    COMPLETE_UNRESOLVED = "COMPLETE_UNRESOLVED"
    FAILED_INFRASTRUCTURE = "FAILED_INFRASTRUCTURE"
    FAILED_REFERENCE = "FAILED_REFERENCE"
    FAILED_MEASUREMENT = "FAILED_MEASUREMENT"
    CANCELLED = "CANCELLED"
    INDETERMINATE = "INDETERMINATE"


class ScientificDecisionState(StrEnum):
    UNRESOLVED_UNQUALIFIED = "UNRESOLVED_UNQUALIFIED"


class ReceiptWriteDisposition(StrEnum):
    APPENDED = "APPENDED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


class LedgerEventKind(StrEnum):
    RECEIPT_APPENDED = "RECEIPT_APPENDED"
    RECEIPT_SUPERSEDED = "RECEIPT_SUPERSEDED"
    RECEIPT_REVOKED = "RECEIPT_REVOKED"


class ReceiptLifecycleState(StrEnum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"


def canonical_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError):
        raise AuditFailure(AuditCode.INVALID) from None


def digest_bytes(value: bytes) -> str:
    if type(value) is not bytes:
        raise AuditFailure(AuditCode.INVALID)
    return "sha256:" + hashlib.sha256(value).hexdigest()


def validate_digest(value: object) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise AuditFailure(AuditCode.INVALID)
    return value


def validate_token(value: object) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value) <= 160
        or _TOKEN.fullmatch(value) is None
    ):
        raise AuditFailure(AuditCode.INVALID)
    return value


@dataclass(frozen=True, slots=True)
class DevelopmentEvidenceBinding:
    """Digest-only provenance for one non-official public numerical result."""

    submission_id: str
    strategy_digest: str
    challenge_id: str
    challenge_version: str
    generator_digest: str
    target_population_digest: str
    sampling_plan_digest: str
    training_data_commitment: str
    reconstruction_plan_digest: str
    repeat_plan_digest: str
    resource_policy_digest: str
    reconstruction_outcome_digest: str
    reconstruction_attempt_digests: tuple[str, ...]
    inference_request_digest: str
    prediction_digest: str
    reference_policy_digest: str
    reference_implementation_digest: str
    reference_environment_digest: str
    reference_artifact_digest: str
    measurement_contract_digest: str
    measurement_implementation_digest: str
    measurement_environment_digest: str
    measurement_result_digest: str
    scoring_policy_digest: str
    dossier_digest: str
    qualification_manifest_digest: str
    source_tree_digest: str
    worker_image_digest: str
    execution_policy_digest: str
    uncertainty_state: ScientificDecisionState = (
        ScientificDecisionState.UNRESOLVED_UNQUALIFIED
    )
    scientific_qualification_state: ScientificDecisionState = (
        ScientificDecisionState.UNRESOLVED_UNQUALIFIED
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "submission_id", validate_token(self.submission_id))
        object.__setattr__(self, "challenge_id", validate_token(self.challenge_id))
        object.__setattr__(
            self, "challenge_version", validate_token(self.challenge_version)
        )
        digest_fields = (
            "strategy_digest",
            "generator_digest",
            "target_population_digest",
            "sampling_plan_digest",
            "training_data_commitment",
            "reconstruction_plan_digest",
            "repeat_plan_digest",
            "resource_policy_digest",
            "reconstruction_outcome_digest",
            "inference_request_digest",
            "prediction_digest",
            "reference_policy_digest",
            "reference_implementation_digest",
            "reference_environment_digest",
            "reference_artifact_digest",
            "measurement_contract_digest",
            "measurement_implementation_digest",
            "measurement_environment_digest",
            "measurement_result_digest",
            "scoring_policy_digest",
            "dossier_digest",
            "qualification_manifest_digest",
            "source_tree_digest",
            "worker_image_digest",
            "execution_policy_digest",
        )
        for name in digest_fields:
            object.__setattr__(self, name, validate_digest(getattr(self, name)))
        attempts = self.reconstruction_attempt_digests
        if type(attempts) is not tuple or len(attempts) != 3 or len(set(attempts)) != 3:
            raise AuditFailure(AuditCode.INVALID)
        object.__setattr__(
            self,
            "reconstruction_attempt_digests",
            tuple(validate_digest(value) for value in attempts),
        )
        if (
            self.uncertainty_state is not ScientificDecisionState.UNRESOLVED_UNQUALIFIED
            or self.scientific_qualification_state
            is not ScientificDecisionState.UNRESOLVED_UNQUALIFIED
        ):
            raise AuditFailure(AuditCode.DENIED)

    def document(self) -> dict[str, object]:
        return {
            "challenge": {
                "id": self.challenge_id,
                "version": self.challenge_version,
            },
            "dossier_digest": self.dossier_digest,
            "execution": {
                "execution_policy_digest": self.execution_policy_digest,
                "source_tree_digest": self.source_tree_digest,
                "worker_image_digest": self.worker_image_digest,
            },
            "generator_digest": self.generator_digest,
            "inference": {
                "prediction_digest": self.prediction_digest,
                "request_digest": self.inference_request_digest,
            },
            "measurement": {
                "contract_digest": self.measurement_contract_digest,
                "environment_digest": self.measurement_environment_digest,
                "implementation_digest": self.measurement_implementation_digest,
                "result_digest": self.measurement_result_digest,
            },
            "qualification_manifest_digest": self.qualification_manifest_digest,
            "reconstruction": {
                "attempt_digests": list(self.reconstruction_attempt_digests),
                "outcome_digest": self.reconstruction_outcome_digest,
                "plan_digest": self.reconstruction_plan_digest,
                "repeat_plan_digest": self.repeat_plan_digest,
                "resource_policy_digest": self.resource_policy_digest,
            },
            "reference": {
                "artifact_digest": self.reference_artifact_digest,
                "environment_digest": self.reference_environment_digest,
                "implementation_digest": self.reference_implementation_digest,
                "policy_digest": self.reference_policy_digest,
            },
            "sampling_plan_digest": self.sampling_plan_digest,
            "scientific_qualification_state": self.scientific_qualification_state.value,
            "scoring_policy_digest": self.scoring_policy_digest,
            "strategy_digest": self.strategy_digest,
            "submission_id": self.submission_id,
            "target_population_digest": self.target_population_digest,
            "training_data_commitment": self.training_data_commitment,
            "uncertainty_state": self.uncertainty_state.value,
        }

    def required_evidence_digests(self) -> tuple[str, ...]:
        """Return the exact closure that must resolve before ledger append."""

        values = {
            value
            for value in _walk_digests(self.document())
            if value != self.training_data_commitment
        }
        # TRAIN is commitment-only: a receipt must not require or expose its bytes.
        return tuple(sorted(values))


def _walk_digests(value: object) -> tuple[str, ...]:
    if type(value) is str:
        return (value,) if _DIGEST.fullmatch(value) is not None else ()
    if type(value) is list:
        return tuple(item for child in value for item in _walk_digests(child))
    if type(value) is dict:
        return tuple(item for child in value.values() for item in _walk_digests(child))
    return ()


@dataclass(frozen=True, slots=True)
class DevelopmentEvaluationReceipt:
    receipt_id: str
    binding: DevelopmentEvidenceBinding
    run_status: DevelopmentRunStatus
    started_at_micros: int
    finished_at_micros: int
    signing_key_id: str
    signing_public_key_digest: str
    supersedes_receipt_id: str | None = None
    receipt_schema_version: str = SCHEMA
    authority_marker: str = AUTHORITY_MARKER
    signing_scope: str = SIGNING_SCOPE
    protected_execution_eligible: bool = False
    score_eligible: bool = False
    archive_acknowledged: bool = False
    network_eligible: bool = False
    reward_eligible: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", validate_token(self.receipt_id))
        if type(self.binding) is not DevelopmentEvidenceBinding:
            raise AuditFailure(AuditCode.INVALID)
        if type(self.run_status) is not DevelopmentRunStatus:
            raise AuditFailure(AuditCode.INVALID)
        if (
            type(self.started_at_micros) is not int
            or type(self.finished_at_micros) is not int
            or not 0 <= self.started_at_micros <= self.finished_at_micros < 2**63
        ):
            raise AuditFailure(AuditCode.INVALID)
        object.__setattr__(self, "signing_key_id", validate_token(self.signing_key_id))
        object.__setattr__(
            self,
            "signing_public_key_digest",
            validate_digest(self.signing_public_key_digest),
        )
        if self.supersedes_receipt_id is not None:
            object.__setattr__(
                self,
                "supersedes_receipt_id",
                validate_token(self.supersedes_receipt_id),
            )
            if self.supersedes_receipt_id == self.receipt_id:
                raise AuditFailure(AuditCode.INVALID)
        if (
            self.receipt_schema_version != SCHEMA
            or self.authority_marker != AUTHORITY_MARKER
            or self.signing_scope != SIGNING_SCOPE
            or self.protected_execution_eligible is not False
            or self.score_eligible is not False
            or self.archive_acknowledged is not False
            or self.network_eligible is not False
            or self.reward_eligible is not False
        ):
            raise AuditFailure(AuditCode.DENIED)

    def document(self) -> dict[str, object]:
        return {
            "authority": {
                "archive_acknowledged": False,
                "marker": self.authority_marker,
                "network_eligible": False,
                "protected_execution_eligible": False,
                "reward_eligible": False,
                "score_eligible": False,
                "signing_scope": self.signing_scope,
            },
            "binding": self.binding.document(),
            "finished_at_micros": self.finished_at_micros,
            "receipt_id": self.receipt_id,
            "receipt_schema_version": self.receipt_schema_version,
            "run_status": self.run_status.value,
            "signer": {
                "algorithm": SIGNATURE_ALGORITHM,
                "key_id": self.signing_key_id,
                "public_key_digest": self.signing_public_key_digest,
            },
            "started_at_micros": self.started_at_micros,
            "supersedes_receipt_id": self.supersedes_receipt_id,
        }

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json(self.document())

    @property
    def receipt_digest(self) -> str:
        return digest_bytes(self.canonical_bytes)


@dataclass(frozen=True, slots=True)
class SignedDevelopmentEvaluationReceipt:
    receipt: DevelopmentEvaluationReceipt
    signature: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (
            type(self.receipt) is not DevelopmentEvaluationReceipt
            or type(self.signature) is not bytes
            or len(self.signature) != 64
        ):
            raise AuditFailure(AuditCode.INVALID)


@dataclass(frozen=True, slots=True)
class LedgerReceiptRef:
    sequence: int
    receipt_id: str
    receipt_digest: str
    entry_digest: str

    def __post_init__(self) -> None:
        if type(self.sequence) is not int or not 0 < self.sequence < 2**63:
            raise AuditFailure(AuditCode.INVALID)
        object.__setattr__(self, "receipt_id", validate_token(self.receipt_id))
        object.__setattr__(self, "receipt_digest", validate_digest(self.receipt_digest))
        object.__setattr__(self, "entry_digest", validate_digest(self.entry_digest))


@dataclass(frozen=True, slots=True)
class LedgerCheckpoint:
    event_sequence: int
    entry_digest: str
    receipt_count: int

    def __post_init__(self) -> None:
        if (
            type(self.event_sequence) is not int
            or type(self.receipt_count) is not int
            or self.event_sequence < 0
            or self.receipt_count < 0
        ):
            raise AuditFailure(AuditCode.INVALID)
        object.__setattr__(self, "entry_digest", validate_digest(self.entry_digest))


GENESIS_ENTRY_DIGEST = digest_bytes(b"carbon.c06.development-ledger.genesis.v1")
