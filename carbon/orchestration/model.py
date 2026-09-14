"""C-07 durable DEVELOPMENT orchestration values.

The types in this module describe one non-official operational account.  They
do not define scientific score semantics and cannot represent archive,
network, reward, protected-execution, or LIVE authority.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum

from carbon.audit import (
    DevelopmentEvidenceBinding,
    LedgerReceiptRef,
    SignedDevelopmentEvaluationReceipt,
)
from carbon.execution import DurableExecutionBinding, ExecutionStage, PartialWorkRef

SCHEMA = "carbon.c07.development-operational-account.v1"
PUBLIC_SCHEMA = "carbon.c07.public-operational-account.v1"
REVIEWER_SCHEMA = "carbon.c07.reviewer-operational-account.v1"
AUTHORITY_MARKER = "DEVELOPMENT_ORCHESTRATION_ONLY_NOT_OFFICIAL"


class OrchestrationCode(StrEnum):
    INVALID = "orchestration.request.invalid"
    CONFLICT = "orchestration.operation.conflict"
    STATE = "orchestration.state.invalid"
    RECONCILIATION_REQUIRED = "orchestration.reconciliation.required"
    DENIED = "orchestration.authority.denied"


class OrchestrationFailure(RuntimeError):
    """Stable non-echoing C-07 boundary error."""

    def __init__(self, code: OrchestrationCode) -> None:
        self.code = (
            code if type(code) is OrchestrationCode else OrchestrationCode.INVALID
        )
        super().__init__("Development orchestration operation failed.")


class StageDisposition(StrEnum):
    COMPLETE = "COMPLETE"
    UNRESOLVED_NO_QUALIFIED_SCORE = "UNRESOLVED_NO_QUALIFIED_SCORE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INDETERMINATE = "INDETERMINATE"


class OperationalDisposition(StrEnum):
    COMPLETE_UNRESOLVED = "COMPLETE_UNRESOLVED"
    FAILED_GENERATOR = "FAILED_GENERATOR"
    FAILED_RECONSTRUCTION = "FAILED_RECONSTRUCTION"
    FAILED_REFERENCE = "FAILED_REFERENCE"
    FAILED_MEASUREMENT = "FAILED_MEASUREMENT"
    FAILED_INFRASTRUCTURE = "FAILED_INFRASTRUCTURE"
    CANCELLED = "CANCELLED"
    CONTESTED = "CONTESTED"
    INDETERMINATE = "INDETERMINATE"


_TERMINAL_STAGE = {
    OperationalDisposition.FAILED_GENERATOR: ExecutionStage.GENERATOR,
    OperationalDisposition.FAILED_RECONSTRUCTION: ExecutionStage.RECONSTRUCTION,
    OperationalDisposition.FAILED_REFERENCE: ExecutionStage.REFERENCE,
    OperationalDisposition.FAILED_MEASUREMENT: ExecutionStage.MEASUREMENT,
    OperationalDisposition.FAILED_INFRASTRUCTURE: None,
    OperationalDisposition.CANCELLED: None,
    OperationalDisposition.CONTESTED: ExecutionStage.SCORE,
    OperationalDisposition.INDETERMINATE: None,
}
_ACCOUNT_ORDER = (
    ExecutionStage.GENERATOR,
    ExecutionStage.RECONSTRUCTION,
    ExecutionStage.PREDICTION,
    ExecutionStage.REFERENCE,
    ExecutionStage.MEASUREMENT,
    ExecutionStage.SCORE,
    ExecutionStage.RECEIPT,
    ExecutionStage.ARCHIVE,
)


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError):
        raise OrchestrationFailure(OrchestrationCode.INVALID) from None


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _valid_digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


@dataclass(frozen=True, slots=True)
class DevelopmentOrchestrationRequest:
    """Cross-binding between the C-01 attempt and C-06 evidence closure."""

    execution: DurableExecutionBinding
    evidence: DevelopmentEvidenceBinding
    case_manifest_digest: str
    reference_request_digests: tuple[str, ...]
    measurement_request_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            type(self.execution) is not DurableExecutionBinding
            or type(self.evidence) is not DevelopmentEvidenceBinding
            or not _valid_digest(self.case_manifest_digest)
            or type(self.reference_request_digests) is not tuple
            or type(self.measurement_request_digests) is not tuple
            or not 1 <= len(self.reference_request_digests) <= 12
            or len(self.measurement_request_digests)
            != len(self.reference_request_digests)
            or len(set(self.reference_request_digests))
            != len(self.reference_request_digests)
            or len(set(self.measurement_request_digests))
            != len(self.measurement_request_digests)
            or any(
                not _valid_digest(value)
                for value in self.reference_request_digests
                + self.measurement_request_digests
            )
        ):
            raise OrchestrationFailure(OrchestrationCode.INVALID)
        pin = self.execution.handle.seed_pin
        if (
            self.execution.handle.submission_id.value != self.evidence.submission_id
            or self.execution.strategy_hash.value != self.evidence.strategy_digest
            or pin.challenge_key.challenge_id != self.evidence.challenge_id
            or pin.challenge_key.version != self.evidence.challenge_version
            or pin.generator_digest != self.evidence.generator_digest
            or pin.scoring_digest != self.evidence.scoring_policy_digest
            or self.execution.resolved_plan_digest
            != self.evidence.reconstruction_plan_digest
            or self.execution.resource_policy_digest
            != self.evidence.resource_policy_digest
        ):
            raise OrchestrationFailure(OrchestrationCode.CONFLICT)

    @property
    def request_digest(self) -> str:
        return _digest(
            _canonical(
                {
                    "schema": "carbon.c07.development-request.v1",
                    "attempt": {
                        "submission_id": self.execution.handle.submission_id.value,
                        "attempt_number": self.execution.handle.attempt_number,
                    },
                    "binding": self.evidence.document(),
                    "cases": {
                        "manifest_digest": self.case_manifest_digest,
                        "measurement_request_digests": list(
                            self.measurement_request_digests
                        ),
                        "reference_request_digests": list(
                            self.reference_request_digests
                        ),
                    },
                    "execution": {
                        "environment": self.execution.handle.environment_pin.container_digest,
                        "protected_policy": self.execution.protected_evaluation_policy_digest,
                        "reconstruction_policy": self.execution.reconstruction_policy_digest,
                        "scope": self.execution.scope.value,
                    },
                }
            )
        )


@dataclass(frozen=True, slots=True)
class StageAccount:
    stage: ExecutionStage
    disposition: StageDisposition
    artifact_ref: str
    evidence_digest: str

    def __post_init__(self) -> None:
        try:
            owned = PartialWorkRef(self.stage, self.artifact_ref, self.evidence_digest)
        except Exception:  # noqa: BLE001 - normalize source boundary failures.
            raise OrchestrationFailure(OrchestrationCode.INVALID) from None
        object.__setattr__(self, "stage", owned.stage)
        object.__setattr__(self, "artifact_ref", owned.artifact_ref)
        object.__setattr__(self, "evidence_digest", owned.artifact_digest)
        if type(self.disposition) is not StageDisposition:
            raise OrchestrationFailure(OrchestrationCode.INVALID)

    def document(self) -> dict[str, object]:
        return {
            "artifact_ref": self.artifact_ref,
            "disposition": self.disposition.value,
            "evidence_digest": self.evidence_digest,
            "stage": self.stage.value,
        }


@dataclass(frozen=True, slots=True)
class DevelopmentOperationalAccount:
    request_digest: str
    submission_id: str
    attempt_number: int
    disposition: OperationalDisposition
    stages: tuple[StageAccount, ...]
    missing_stages: tuple[ExecutionStage, ...]
    started_at_micros: int
    finished_at_micros: int
    receipt_id: str | None = None
    receipt_digest: str | None = None
    schema: str = SCHEMA
    authority_marker: str = AUTHORITY_MARKER
    official: bool = False
    protected_execution_eligible: bool = False
    score_eligible: bool = False
    archive_acknowledged: bool = False
    network_eligible: bool = False
    reward_eligible: bool = False

    def __post_init__(self) -> None:
        if (
            not _valid_digest(self.request_digest)
            or type(self.submission_id) is not str
            or not self.submission_id
            or type(self.attempt_number) is not int
            or self.attempt_number < 1
            or type(self.disposition) is not OperationalDisposition
            or type(self.stages) is not tuple
            or any(type(item) is not StageAccount for item in self.stages)
            or type(self.missing_stages) is not tuple
            or any(type(item) is not ExecutionStage for item in self.missing_stages)
            or type(self.started_at_micros) is not int
            or type(self.finished_at_micros) is not int
            or not 0 <= self.started_at_micros <= self.finished_at_micros < 2**63
        ):
            raise OrchestrationFailure(OrchestrationCode.INVALID)
        observed = tuple(item.stage for item in self.stages)
        if (
            len(observed) != len(set(observed))
            or len(self.missing_stages) != len(set(self.missing_stages))
            or observed != _ACCOUNT_ORDER[: len(observed)]
            or self.missing_stages != _ACCOUNT_ORDER[len(observed) :]
        ):
            raise OrchestrationFailure(OrchestrationCode.INVALID)
        complete = self.disposition is OperationalDisposition.COMPLETE_UNRESOLVED
        if complete != (
            self.receipt_id is not None and self.receipt_digest is not None
        ):
            raise OrchestrationFailure(OrchestrationCode.INVALID)
        if self.receipt_id is not None:
            try:
                PartialWorkRef(
                    ExecutionStage.RECEIPT, self.receipt_id, self.receipt_digest
                )
            except Exception:  # noqa: BLE001
                raise OrchestrationFailure(OrchestrationCode.INVALID) from None
        if (
            self.schema != SCHEMA
            or self.authority_marker != AUTHORITY_MARKER
            or any(
                value is not False
                for value in (
                    self.official,
                    self.protected_execution_eligible,
                    self.score_eligible,
                    self.archive_acknowledged,
                    self.network_eligible,
                    self.reward_eligible,
                )
            )
        ):
            raise OrchestrationFailure(OrchestrationCode.DENIED)

    def document(self) -> dict[str, object]:
        return {
            "attempt": {
                "attempt_number": self.attempt_number,
                "submission_id": self.submission_id,
            },
            "authority": {
                "archive_acknowledged": False,
                "marker": self.authority_marker,
                "network_eligible": False,
                "official": False,
                "protected_execution_eligible": False,
                "reward_eligible": False,
                "score_eligible": False,
            },
            "disposition": self.disposition.value,
            "finished_at_micros": self.finished_at_micros,
            "missing_stages": [item.value for item in self.missing_stages],
            "receipt": (
                None
                if self.receipt_id is None
                else {"digest": self.receipt_digest, "id": self.receipt_id}
            ),
            "request_digest": self.request_digest,
            "schema": self.schema,
            "stages": [item.document() for item in self.stages],
            "started_at_micros": self.started_at_micros,
        }

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical(self.document())

    @property
    def account_digest(self) -> str:
        return _digest(self.canonical_bytes)


@dataclass(frozen=True, slots=True)
class ResultOwnerRefs:
    card_record_ref: str
    transcript_ref: str
    transcript_digest: str

    def __post_init__(self) -> None:
        try:
            PartialWorkRef(
                ExecutionStage.SCORE, self.card_record_ref, self.transcript_digest
            )
            PartialWorkRef(
                ExecutionStage.SCORE, self.transcript_ref, self.transcript_digest
            )
        except Exception:  # noqa: BLE001
            raise OrchestrationFailure(OrchestrationCode.INVALID) from None


@dataclass(frozen=True, slots=True)
class CompletedDevelopmentOrchestration:
    account: DevelopmentOperationalAccount
    signed_receipt: SignedDevelopmentEvaluationReceipt = field(repr=False)
    ledger_reference: LedgerReceiptRef

    def __post_init__(self) -> None:
        if (
            type(self.account) is not DevelopmentOperationalAccount
            or type(self.signed_receipt) is not SignedDevelopmentEvaluationReceipt
            or type(self.ledger_reference) is not LedgerReceiptRef
            or self.account.receipt_digest != self.signed_receipt.receipt.receipt_digest
            or self.account.receipt_digest != self.ledger_reference.receipt_digest
        ):
            raise OrchestrationFailure(OrchestrationCode.INVALID)


def terminal_stage(disposition: OperationalDisposition) -> ExecutionStage | None:
    if type(disposition) is not OperationalDisposition or disposition is (
        OperationalDisposition.COMPLETE_UNRESOLVED
    ):
        raise OrchestrationFailure(OrchestrationCode.INVALID)
    return _TERMINAL_STAGE[disposition]


__all__ = [
    "AUTHORITY_MARKER",
    "PUBLIC_SCHEMA",
    "REVIEWER_SCHEMA",
    "SCHEMA",
    "CompletedDevelopmentOrchestration",
    "DevelopmentOperationalAccount",
    "DevelopmentOrchestrationRequest",
    "OperationalDisposition",
    "OrchestrationCode",
    "OrchestrationFailure",
    "ResultOwnerRefs",
    "StageAccount",
    "StageDisposition",
    "terminal_stage",
]
