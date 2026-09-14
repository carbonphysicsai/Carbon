"""C-10 DEVELOPMENT re-execution bindings and outcomes.

These values describe a validator-integrity observation over two C-07
executions.  They do not define a scientific tolerance, qualify independence,
or grant official, publication, network, weight, reward, or settlement
authority.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from carbon.audit.model import (
    LedgerReceiptRef,
    canonical_json,
    digest_bytes,
    validate_digest,
    validate_token,
)
from carbon.orchestration import (
    CompletedDevelopmentOrchestration,
    DevelopmentOperationalAccount,
    DevelopmentOrchestrationRequest,
)
from carbon.reconstruction.worker.model import (
    CLEANUP_CONFIRMATION_SECONDS,
    CPU_COUNT,
    GRACEFUL_CANCELLATION_SECONDS,
    MEMORY_BYTES,
    PIDS_LIMIT,
    PRODUCTIVE_DEADLINE_SECONDS,
    PROFILE_ID,
    SCRATCH_BYTES,
    SCRATCH_INODES,
    SWAP_BYTES,
)

SCHEMA = "carbon.c10.development-reexecution.v1"
OUTCOME_SCHEMA = "carbon.c10.development-reexecution-outcome.v1"
PUBLIC_SCHEMA = "carbon.c10.public-reexecution-report.v1"
REVIEWER_SCHEMA = "carbon.c10.reviewer-reexecution-report.v1"
AUTHORITY_MARKER = "DEVELOPMENT_REEXECUTION_ONLY_NOT_SCIENTIFIC_RESOLUTION"
COMPARISON_POLICY_ID = "carbon.c10.exact-scientific-state-observation.v1"
REEXECUTION_ROLE = "VALIDATOR_INTEGRITY_AUDIT"


class ReexecutionCode(StrEnum):
    INVALID = "reexecution.request.invalid"
    DENIED = "reexecution.authority.denied"
    CONFLICT = "reexecution.operation.conflict"
    STATE = "reexecution.state.invalid"
    STORE = "reexecution.store.failure"
    EVIDENCE_UNAVAILABLE = "reexecution.evidence.unavailable"
    RECONCILIATION_REQUIRED = "reexecution.reconciliation.required"


class ReexecutionFailure(RuntimeError):
    """Stable non-echoing C-10 boundary failure."""

    def __init__(self, code: ReexecutionCode) -> None:
        self.code = code if type(code) is ReexecutionCode else ReexecutionCode.INVALID
        super().__init__("Development re-execution operation failed.")


class JournalState(StrEnum):
    INTENT_RECORDED = "INTENT_RECORDED"
    RUNNING = "RUNNING"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    COMPARED = "COMPARED"
    QUARANTINED = "QUARANTINED"


class RequestWriteDisposition(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


class ComparisonDisposition(StrEnum):
    EXACT_BYTES_AGREE_DEVELOPMENT = "EXACT_BYTES_AGREE_DEVELOPMENT"
    DIFFERENT_BYTES_UNRESOLVED = "DIFFERENT_BYTES_UNRESOLVED"
    PRIMARY_EVIDENCE_UNAVAILABLE = "PRIMARY_EVIDENCE_UNAVAILABLE"
    REEXECUTION_EVIDENCE_UNAVAILABLE = "REEXECUTION_EVIDENCE_UNAVAILABLE"
    REEXECUTION_CANCELLED = "REEXECUTION_CANCELLED"
    REEXECUTION_FAILED = "REEXECUTION_FAILED"
    REEXECUTION_INFRASTRUCTURE_UNAVAILABLE = "REEXECUTION_INFRASTRUCTURE_UNAVAILABLE"
    REEXECUTION_UNRESOLVED = "REEXECUTION_UNRESOLVED"


class ResourceObservationState(StrEnum):
    MEASURED = "MEASURED"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


SCIENTIFIC_STATE_FIELDS = (
    "reconstruction_replica_0",
    "reconstruction_replica_1",
    "reconstruction_replica_2",
    "prediction",
    "reference",
    "measurement",
)


def _fail_if_not_finite(value: float) -> float:
    if type(value) is not float or not math.isfinite(value) or value < 0.0:
        raise ReexecutionFailure(ReexecutionCode.INVALID)
    return value


def _receipt_document(value: LedgerReceiptRef) -> dict[str, object]:
    return {
        "entry_digest": value.entry_digest,
        "receipt_digest": value.receipt_digest,
        "receipt_id": value.receipt_id,
        "sequence": value.sequence,
    }


@dataclass(frozen=True, slots=True)
class ReplicaAuditBinding:
    """One registered slot with the same randomness but a fresh execution."""

    slot_id: str
    randomness_digest: str
    primary_replicate_digest: str
    reexecution_replicate_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot_id", validate_token(self.slot_id))
        for name in (
            "randomness_digest",
            "primary_replicate_digest",
            "reexecution_replicate_digest",
        ):
            object.__setattr__(self, name, validate_digest(getattr(self, name)))
        if self.primary_replicate_digest == self.reexecution_replicate_digest:
            raise ReexecutionFailure(ReexecutionCode.CONFLICT)

    def document(self) -> dict[str, object]:
        return {
            "primary_replicate_digest": self.primary_replicate_digest,
            "randomness_digest": self.randomness_digest,
            "reexecution_replicate_digest": self.reexecution_replicate_digest,
            "slot_id": self.slot_id,
        }


@dataclass(frozen=True, slots=True)
class ReexecutionBudget:
    """Frozen additional-work ceiling; no replacement authority is implied."""

    resource_policy_digest: str
    worker_profile_id: str = PROFILE_ID
    reconstruction_replicas: int = 3
    maximum_worker_launches: int = 5
    maximum_concurrent_workers: int = 1
    per_worker_cpu_count: int = CPU_COUNT
    per_worker_memory_bytes: int = MEMORY_BYTES
    per_worker_swap_bytes: int = SWAP_BYTES
    per_worker_pids: int = PIDS_LIMIT
    per_worker_scratch_bytes: int = SCRATCH_BYTES
    per_worker_scratch_inodes: int = SCRATCH_INODES
    per_worker_deadline_seconds: int = PRODUCTIVE_DEADLINE_SECONDS
    cancellation_grace_seconds: int = GRACEFUL_CANCELLATION_SECONDS
    cleanup_confirmation_seconds: int = CLEANUP_CONFIRMATION_SECONDS
    automatic_replacements: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "resource_policy_digest", validate_digest(self.resource_policy_digest)
        )
        if (
            self.worker_profile_id != PROFILE_ID
            or self.reconstruction_replicas != 3
            or self.maximum_worker_launches != 5
            or self.maximum_concurrent_workers != 1
            or self.per_worker_cpu_count != CPU_COUNT
            or self.per_worker_memory_bytes != MEMORY_BYTES
            or self.per_worker_swap_bytes != SWAP_BYTES
            or self.per_worker_pids != PIDS_LIMIT
            or self.per_worker_scratch_bytes != SCRATCH_BYTES
            or self.per_worker_scratch_inodes != SCRATCH_INODES
            or self.per_worker_deadline_seconds != PRODUCTIVE_DEADLINE_SECONDS
            or self.cancellation_grace_seconds != GRACEFUL_CANCELLATION_SECONDS
            or self.cleanup_confirmation_seconds != CLEANUP_CONFIRMATION_SECONDS
            or self.automatic_replacements != 0
        ):
            raise ReexecutionFailure(ReexecutionCode.DENIED)

    def document(self) -> dict[str, object]:
        return {
            "automatic_replacements": 0,
            "cancellation_grace_seconds": self.cancellation_grace_seconds,
            "cleanup_confirmation_seconds": self.cleanup_confirmation_seconds,
            "maximum_concurrent_workers": 1,
            "maximum_worker_launches": 5,
            "per_worker": {
                "cpu_count": self.per_worker_cpu_count,
                "deadline_seconds": self.per_worker_deadline_seconds,
                "memory_bytes": self.per_worker_memory_bytes,
                "pids": self.per_worker_pids,
                "scratch_bytes": self.per_worker_scratch_bytes,
                "scratch_inodes": self.per_worker_scratch_inodes,
                "swap_bytes": self.per_worker_swap_bytes,
            },
            "reconstruction_replicas": 3,
            "resource_policy_digest": self.resource_policy_digest,
            "worker_profile_id": self.worker_profile_id,
        }

    @property
    def budget_digest(self) -> str:
        return digest_bytes(canonical_json(self.document()))


@dataclass(frozen=True, slots=True)
class ExecutionResourceObservation:
    state: ResourceObservationState
    wall_seconds: float
    cpu_seconds: float | None
    peak_memory_bytes: int | None
    scratch_high_water_bytes: int | None
    output_bytes: int | None
    oom_events: int | None

    def __post_init__(self) -> None:
        if type(self.state) is not ResourceObservationState:
            raise ReexecutionFailure(ReexecutionCode.INVALID)
        object.__setattr__(self, "wall_seconds", _fail_if_not_finite(self.wall_seconds))
        if self.cpu_seconds is not None:
            object.__setattr__(
                self, "cpu_seconds", _fail_if_not_finite(self.cpu_seconds)
            )
        for name in (
            "peak_memory_bytes",
            "scratch_high_water_bytes",
            "output_bytes",
            "oom_events",
        ):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ReexecutionFailure(ReexecutionCode.INVALID)
        available = (
            self.cpu_seconds,
            self.peak_memory_bytes,
            self.scratch_high_water_bytes,
            self.output_bytes,
            self.oom_events,
        )
        if self.state is ResourceObservationState.MEASURED and any(
            value is None for value in available
        ):
            raise ReexecutionFailure(ReexecutionCode.INVALID)
        if self.state is ResourceObservationState.UNAVAILABLE and any(
            value is not None for value in available
        ):
            raise ReexecutionFailure(ReexecutionCode.INVALID)

    def document(self) -> dict[str, object]:
        return {
            "cpu_seconds": self.cpu_seconds,
            "oom_events": self.oom_events,
            "output_bytes": self.output_bytes,
            "peak_memory_bytes": self.peak_memory_bytes,
            "scratch_high_water_bytes": self.scratch_high_water_bytes,
            "state": self.state.value,
            "wall_seconds": self.wall_seconds,
        }


@dataclass(frozen=True, slots=True)
class ExecutionProvenance:
    execution_id: str
    host_id: str
    administrator_trust_domain: str
    hardware_identity_digest: str
    source_tree_digest: str
    worker_image_digest: str
    worker_launch_digests: tuple[str, ...]
    scratch_scope_digests: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("execution_id", "host_id", "administrator_trust_domain"):
            object.__setattr__(self, name, validate_token(getattr(self, name)))
        for name in (
            "hardware_identity_digest",
            "source_tree_digest",
            "worker_image_digest",
        ):
            object.__setattr__(self, name, validate_digest(getattr(self, name)))
        if (
            type(self.worker_launch_digests) is not tuple
            or type(self.scratch_scope_digests) is not tuple
            or not 0 <= len(self.worker_launch_digests) <= 5
            or len(self.worker_launch_digests) != len(self.scratch_scope_digests)
            or len(set(self.worker_launch_digests)) != len(self.worker_launch_digests)
            or len(set(self.scratch_scope_digests)) != len(self.scratch_scope_digests)
        ):
            raise ReexecutionFailure(ReexecutionCode.INVALID)
        object.__setattr__(
            self,
            "worker_launch_digests",
            tuple(validate_digest(value) for value in self.worker_launch_digests),
        )
        object.__setattr__(
            self,
            "scratch_scope_digests",
            tuple(validate_digest(value) for value in self.scratch_scope_digests),
        )

    def document(self) -> dict[str, object]:
        return {
            "administrator_trust_domain": self.administrator_trust_domain,
            "execution_id": self.execution_id,
            "hardware_identity_digest": self.hardware_identity_digest,
            "host_id": self.host_id,
            "scratch_scope_digests": list(self.scratch_scope_digests),
            "source_tree_digest": self.source_tree_digest,
            "worker_image_digest": self.worker_image_digest,
            "worker_launch_digests": list(self.worker_launch_digests),
        }


def _material_document(request: DevelopmentOrchestrationRequest) -> dict[str, object]:
    evidence = request.evidence
    execution = request.execution
    return {
        "candidate": {
            "challenge_id": evidence.challenge_id,
            "challenge_version": evidence.challenge_version,
            "strategy_digest": evidence.strategy_digest,
            "submission_id": evidence.submission_id,
        },
        "cases": {
            "case_manifest_digest": request.case_manifest_digest,
            "reference_request_digests": list(request.reference_request_digests),
        },
        "data": {
            "generator_digest": evidence.generator_digest,
            "sampling_plan_digest": evidence.sampling_plan_digest,
            "target_population_digest": evidence.target_population_digest,
            "training_data_commitment": evidence.training_data_commitment,
        },
        "execution": {
            "environment_digest": execution.handle.environment_pin.container_digest,
            "execution_policy_digest": evidence.execution_policy_digest,
            "protected_policy_digest": execution.protected_evaluation_policy_digest,
            "reconstruction_policy_digest": execution.reconstruction_policy_digest,
            "resource_policy_digest": execution.resource_policy_digest,
            "source_tree_digest": evidence.source_tree_digest,
            "worker_image_digest": evidence.worker_image_digest,
        },
        "inference_request_digest": evidence.inference_request_digest,
        "measurement": {
            "contract_digest": evidence.measurement_contract_digest,
            "environment_digest": evidence.measurement_environment_digest,
            "implementation_digest": evidence.measurement_implementation_digest,
        },
        "reconstruction_plan_digest": evidence.reconstruction_plan_digest,
        "reference": {
            "environment_digest": evidence.reference_environment_digest,
            "implementation_digest": evidence.reference_implementation_digest,
            "policy_digest": evidence.reference_policy_digest,
        },
        "scientific_contract": {
            "dossier_digest": evidence.dossier_digest,
            "qualification_manifest_digest": evidence.qualification_manifest_digest,
            "scoring_policy_digest": evidence.scoring_policy_digest,
        },
    }


@dataclass(frozen=True, slots=True)
class LinkedReexecutionRequest:
    request_id: str
    primary_request: DevelopmentOrchestrationRequest
    primary_result: CompletedDevelopmentOrchestration
    reexecution_request: DevelopmentOrchestrationRequest
    replicas: tuple[ReplicaAuditBinding, ...]
    budget: ReexecutionBudget
    worker_id: str
    claim_id: str
    comparison_policy_id: str = COMPARISON_POLICY_ID
    role: str = REEXECUTION_ROLE
    schema: str = SCHEMA

    def __post_init__(self) -> None:
        for name in ("request_id", "worker_id", "claim_id"):
            object.__setattr__(self, name, validate_token(getattr(self, name)))
        if (
            type(self.primary_request) is not DevelopmentOrchestrationRequest
            or type(self.primary_result) is not CompletedDevelopmentOrchestration
            or type(self.reexecution_request) is not DevelopmentOrchestrationRequest
            or type(self.budget) is not ReexecutionBudget
            or type(self.replicas) is not tuple
            or len(self.replicas) != 3
            or any(type(value) is not ReplicaAuditBinding for value in self.replicas)
            or len({value.slot_id for value in self.replicas}) != 3
            or self.schema != SCHEMA
            or self.comparison_policy_id != COMPARISON_POLICY_ID
            or self.role != REEXECUTION_ROLE
        ):
            raise ReexecutionFailure(ReexecutionCode.INVALID)
        primary_account = self.primary_result.account
        primary_receipt = self.primary_result.signed_receipt.receipt
        primary_ref = self.primary_result.ledger_reference
        if (
            primary_account.request_digest != self.primary_request.request_digest
            or primary_account.submission_id
            != self.primary_request.execution.handle.submission_id.value
            or primary_account.attempt_number
            != self.primary_request.execution.handle.attempt_number
            or primary_receipt.binding != self.primary_request.evidence
            or primary_receipt.receipt_digest != primary_ref.receipt_digest
            or primary_receipt.receipt_id != primary_ref.receipt_id
        ):
            raise ReexecutionFailure(ReexecutionCode.CONFLICT)
        primary_execution = self.primary_request.execution
        reexecution = self.reexecution_request.execution
        if (
            primary_execution.handle.submission_id != reexecution.handle.submission_id
            or primary_execution.handle.attempt_number
            >= reexecution.handle.attempt_number
            or primary_execution.requester_identity != reexecution.requester_identity
            or primary_execution.scope != reexecution.scope
            or _material_document(self.primary_request)
            != _material_document(self.reexecution_request)
            or self.budget.resource_policy_digest != reexecution.resource_policy_digest
        ):
            raise ReexecutionFailure(ReexecutionCode.CONFLICT)

    def document(self) -> dict[str, object]:
        primary_ref = self.primary_result.ledger_reference
        return {
            "budget": self.budget.document(),
            "comparison_policy": {
                "id": self.comparison_policy_id,
                "qualified": False,
                "tolerance": None,
            },
            "material_binding": _material_document(self.primary_request),
            "primary": {
                "account_digest": self.primary_result.account.account_digest,
                "attempt_number": self.primary_request.execution.handle.attempt_number,
                "receipt": _receipt_document(primary_ref),
                "request_digest": self.primary_request.request_digest,
            },
            "reexecution": {
                "attempt_number": self.reexecution_request.execution.handle.attempt_number,
                "claim_id": self.claim_id,
                "request_digest": self.reexecution_request.request_digest,
                "worker_id": self.worker_id,
            },
            "replicas": [value.document() for value in self.replicas],
            "request_id": self.request_id,
            "role": self.role,
            "schema": self.schema,
        }

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json(self.document())

    @property
    def request_digest(self) -> str:
        return digest_bytes(self.canonical_bytes)


@dataclass(frozen=True, slots=True)
class ReexecutionOutcome:
    request_id: str
    request_digest: str
    disposition: ComparisonDisposition
    primary_account_digest: str
    reexecution_account_digest: str | None
    primary_receipt: LedgerReceiptRef
    reexecution_receipt: LedgerReceiptRef | None
    different_scientific_fields: tuple[str, ...]
    shared_dependency_digests: tuple[str, ...]
    primary_provenance: ExecutionProvenance
    reexecution_provenance: ExecutionProvenance
    primary_resources: ExecutionResourceObservation
    reexecution_resources: ExecutionResourceObservation
    failure_evidence_digest: str | None = None
    schema: str = OUTCOME_SCHEMA
    authority_marker: str = AUTHORITY_MARKER
    comparison_policy_qualified: bool = False
    scientific_resolution: bool = False
    official: bool = False
    publishable_winner: bool = False
    archive_eligible: bool = False
    network_eligible: bool = False
    weight_eligible: bool = False
    reward_eligible: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", validate_token(self.request_id))
        object.__setattr__(self, "request_digest", validate_digest(self.request_digest))
        object.__setattr__(
            self, "primary_account_digest", validate_digest(self.primary_account_digest)
        )
        if self.reexecution_account_digest is not None:
            object.__setattr__(
                self,
                "reexecution_account_digest",
                validate_digest(self.reexecution_account_digest),
            )
        if self.failure_evidence_digest is not None:
            object.__setattr__(
                self,
                "failure_evidence_digest",
                validate_digest(self.failure_evidence_digest),
            )
        if (
            type(self.disposition) is not ComparisonDisposition
            or type(self.primary_receipt) is not LedgerReceiptRef
            or (
                self.reexecution_receipt is not None
                and type(self.reexecution_receipt) is not LedgerReceiptRef
            )
            or type(self.different_scientific_fields) is not tuple
            or any(
                value not in SCIENTIFIC_STATE_FIELDS
                for value in self.different_scientific_fields
            )
            or len(set(self.different_scientific_fields))
            != len(self.different_scientific_fields)
            or type(self.shared_dependency_digests) is not tuple
            or not self.shared_dependency_digests
            or type(self.primary_provenance) is not ExecutionProvenance
            or type(self.reexecution_provenance) is not ExecutionProvenance
            or type(self.primary_resources) is not ExecutionResourceObservation
            or type(self.reexecution_resources) is not ExecutionResourceObservation
        ):
            raise ReexecutionFailure(ReexecutionCode.INVALID)
        object.__setattr__(
            self,
            "shared_dependency_digests",
            tuple(validate_digest(value) for value in self.shared_dependency_digests),
        )
        exact = self.disposition is ComparisonDisposition.EXACT_BYTES_AGREE_DEVELOPMENT
        different = self.disposition is ComparisonDisposition.DIFFERENT_BYTES_UNRESOLVED
        if (
            (exact and self.different_scientific_fields)
            or (different and not self.different_scientific_fields)
            or (not exact and not different and self.different_scientific_fields)
        ):
            raise ReexecutionFailure(ReexecutionCode.INVALID)
        if exact and (
            self.reexecution_account_digest is None
            or self.reexecution_receipt is None
            or self.failure_evidence_digest is not None
        ):
            raise ReexecutionFailure(ReexecutionCode.INVALID)
        if set(self.primary_provenance.worker_launch_digests) & set(
            self.reexecution_provenance.worker_launch_digests
        ) or set(self.primary_provenance.scratch_scope_digests) & set(
            self.reexecution_provenance.scratch_scope_digests
        ):
            raise ReexecutionFailure(ReexecutionCode.CONFLICT)
        if (
            self.schema != OUTCOME_SCHEMA
            or self.authority_marker != AUTHORITY_MARKER
            or any(
                value is not False
                for value in (
                    self.comparison_policy_qualified,
                    self.scientific_resolution,
                    self.official,
                    self.publishable_winner,
                    self.archive_eligible,
                    self.network_eligible,
                    self.weight_eligible,
                    self.reward_eligible,
                )
            )
        ):
            raise ReexecutionFailure(ReexecutionCode.DENIED)

    @property
    def quarantine_required(self) -> bool:
        return (
            self.disposition is not ComparisonDisposition.EXACT_BYTES_AGREE_DEVELOPMENT
        )

    def document(self) -> dict[str, object]:
        return {
            "authority": {
                "archive_eligible": False,
                "comparison_policy_qualified": False,
                "marker": self.authority_marker,
                "network_eligible": False,
                "official": False,
                "publishable_winner": False,
                "reward_eligible": False,
                "scientific_resolution": False,
                "weight_eligible": False,
            },
            "different_scientific_fields": list(self.different_scientific_fields),
            "disposition": self.disposition.value,
            "failure_evidence_digest": self.failure_evidence_digest,
            "primary": {
                "account_digest": self.primary_account_digest,
                "provenance": self.primary_provenance.document(),
                "receipt": _receipt_document(self.primary_receipt),
                "resources": self.primary_resources.document(),
            },
            "quarantine_required": self.quarantine_required,
            "reexecution": {
                "account_digest": self.reexecution_account_digest,
                "provenance": self.reexecution_provenance.document(),
                "receipt": (
                    None
                    if self.reexecution_receipt is None
                    else _receipt_document(self.reexecution_receipt)
                ),
                "resources": self.reexecution_resources.document(),
            },
            "request_digest": self.request_digest,
            "request_id": self.request_id,
            "schema": self.schema,
            "shared_dependency_digests": list(self.shared_dependency_digests),
        }

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json(self.document())

    @property
    def outcome_digest(self) -> str:
        return digest_bytes(self.canonical_bytes)


@dataclass(frozen=True, slots=True)
class ReexecutionJournalView:
    request_id: str
    request_digest: str
    state: JournalState
    outcome_digest: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", validate_token(self.request_id))
        object.__setattr__(self, "request_digest", validate_digest(self.request_digest))
        if type(self.state) is not JournalState:
            raise ReexecutionFailure(ReexecutionCode.INVALID)
        if self.outcome_digest is not None:
            object.__setattr__(
                self, "outcome_digest", validate_digest(self.outcome_digest)
            )
        terminal = self.state in {JournalState.COMPARED, JournalState.QUARANTINED}
        if terminal != (self.outcome_digest is not None):
            raise ReexecutionFailure(ReexecutionCode.INVALID)


def scientific_state_digests(
    account: DevelopmentOperationalAccount,
    request: DevelopmentOrchestrationRequest,
) -> tuple[str, ...]:
    if (
        type(account) is not DevelopmentOperationalAccount
        or type(request) is not DevelopmentOrchestrationRequest
        or account.request_digest != request.request_digest
    ):
        raise ReexecutionFailure(ReexecutionCode.CONFLICT)
    evidence = request.evidence
    return (
        *evidence.reconstruction_attempt_digests,
        evidence.prediction_digest,
        evidence.reference_artifact_digest,
        evidence.measurement_result_digest,
    )


__all__ = [
    "AUTHORITY_MARKER",
    "COMPARISON_POLICY_ID",
    "PUBLIC_SCHEMA",
    "REEXECUTION_ROLE",
    "REVIEWER_SCHEMA",
    "SCHEMA",
    "SCIENTIFIC_STATE_FIELDS",
    "ComparisonDisposition",
    "ExecutionProvenance",
    "ExecutionResourceObservation",
    "JournalState",
    "LinkedReexecutionRequest",
    "ReexecutionBudget",
    "ReexecutionCode",
    "ReexecutionFailure",
    "ReexecutionJournalView",
    "ReexecutionOutcome",
    "ReplicaAuditBinding",
    "RequestWriteDisposition",
    "ResourceObservationState",
    "scientific_state_digests",
]
