"""Content-bound B-E4 rehearsal evidence with no qualification authority."""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import Enum
from pathlib import Path

from carbon.construction import (
    CandidateAssemblyContract,
    ParameterCatalog,
    ParameterCatalogRef,
)
from carbon.research import ResearchServiceErrorCode

from .design import canonical_intervention_from_experiment_record
from .execution import ResearchOperationFailure
from .lifecycle import (
    LifecycleFailureKind,
    NonQualifyingLifecycleError,
    NonQualifyingLifecycleRun,
)
from .model import AgentProfile, ExperimentalArm, MatchedBudget

REHEARSAL_EVIDENCE_AUTHORITY_CEILING = (
    "DESIGN_ANALYSIS_REHEARSAL_EVIDENCE_ONLY_NOT_QUALIFYING_EVIDENCE"
)
TRANSCRIPT_CLUSTER_POLICY = "whole_profile_block_transcript_digest/v1"
PROVENANCE_CLUSTER_POLICY = "shared_fixture_and_driver_lineage/v1"
SHADOW_ALLOCATION_STATUS = "UNASSIGNED_EVALUATOR_HELD_FUTURE_CHECKPOINT"
ROLE_VERIFICATION_STATUS = "UNAVAILABLE_CURRENT_ROLE_AUTHENTICATION_CONTRACT"
EXECUTION_AUTHORIZATION_STATUS = "UNAVAILABLE_ONE_USE_AUTHORIZATION_CONTRACT"

_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z", re.ASCII)
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z", re.ASCII)
_RUN_DOMAIN = b"carbon.be4.rehearsal-run-evidence.v1\x00"
_BUDGET_DOMAIN = b"carbon.be4.rehearsal-budget.v1\x00"
_IMPLEMENTATION_DOMAIN = b"carbon.be4.rehearsal-implementation.v1\x00"
_MANIFEST_DOMAIN = b"carbon.be4.rehearsal-campaign-manifest.v1\x00"
_FAILURE_DOMAIN = b"carbon.be4.rehearsal-block-failure.v1\x00"
_REJECTION_DOMAIN = b"carbon.be4.rehearsal-rejected-operation.v1\x00"
_REPLACEMENT_DOMAIN = b"carbon.be4.rehearsal-block-replacement.v1\x00"
_CAMPAIGN_DOMAIN = b"carbon.be4.rehearsal-campaign-evidence.v1\x00"
_RUN_FACTORY_TOKEN = object()
_MANIFEST_FACTORY_TOKEN = object()
_FAILURE_FACTORY_TOKEN = object()
_REJECTION_FACTORY_TOKEN = object()
_REPLACEMENT_FACTORY_TOKEN = object()
_CAMPAIGN_FACTORY_TOKEN = object()


def _hash(domain: bytes, fields: tuple[str, ...]) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            domain + b"\x00".join(item.encode("utf-8") for item in fields)
        ).hexdigest()
    )


def _digest(value: object, name: str) -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise TypeError(f"{name} must be an exact tagged SHA-256 digest")
    return value


def _identifier(value: object, name: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise TypeError(f"{name} must be a bounded identifier")
    return value


def rehearsal_budget_digest(budget: MatchedBudget) -> str:
    if type(budget) is not MatchedBudget:
        raise TypeError("budget identity requires an exact matched budget")
    return _hash(
        _BUDGET_DOMAIN,
        (
            budget.profile.value,
            budget.wall_time_seconds.hex(),
            budget.compute_units.hex(),
            str(budget.attempt_limit),
        ),
    )


def rehearsal_implementation_digest() -> str:
    """Bind the exact installed source set used by the trusted rehearsal."""

    root = Path(__file__).parent
    parts = []
    for name in (
        "agents.py",
        "evidence.py",
        "execution.py",
        "harness.py",
        "lifecycle.py",
    ):
        source = (root / name).read_bytes()
        parts.append(f"{name}:sha256:{hashlib.sha256(source).hexdigest()}")
    parts.append(
        f"{sys.implementation.name}-{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    return _hash(_IMPLEMENTATION_DOMAIN, tuple(parts))


class RehearsalPurpose(str, Enum):
    DEVELOPMENT = "DEVELOPMENT"
    CALIBRATION = "CALIBRATION"


class RehearsalSlotRole(str, Enum):
    PRIMARY = "PRIMARY"
    RESERVE = "RESERVE"


@dataclass(frozen=True, slots=True)
class RehearsalBlockSlot:
    profile: AgentProfile
    role: RehearsalSlotRole
    number: int
    block_id: str

    def __post_init__(self) -> None:
        if (
            type(self) is not RehearsalBlockSlot
            or type(self.profile) is not AgentProfile
            or type(self.role) is not RehearsalSlotRole
            or type(self.number) is not int
            or self.number < 0
        ):
            raise TypeError("rehearsal slots require exact bounded values")
        _identifier(self.block_id, "block_id")


@dataclass(frozen=True, slots=True)
class RehearsalCampaignManifest:
    """Prospective matrix and later-analysis seams, frozen before any run."""

    authority_ceiling: str
    purpose: RehearsalPurpose
    design_digest: str
    implementation_digest: str
    treatment_digests: tuple[str, ...]
    driver_digests: tuple[str, ...]
    budget_digests: tuple[str, ...]
    slots: tuple[RehearsalBlockSlot, ...]
    stopping_rule: str
    failure_handling: str
    transcript_cluster_policy: str
    provenance_cluster_policy: str
    shadow_allocation_status: str
    role_verification_status: str
    execution_authorization_status: str
    content_digest: str
    _factory_token: object = dataclass_field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            type(self) is not RehearsalCampaignManifest
            or self._factory_token is not _MANIFEST_FACTORY_TOKEN
            or self.authority_ceiling != REHEARSAL_EVIDENCE_AUTHORITY_CEILING
            or type(self.purpose) is not RehearsalPurpose
            or type(self.slots) is not tuple
            or any(type(item) is not RehearsalBlockSlot for item in self.slots)
            or not self.slots
            or self.transcript_cluster_policy != TRANSCRIPT_CLUSTER_POLICY
            or self.provenance_cluster_policy != PROVENANCE_CLUSTER_POLICY
            or self.shadow_allocation_status != SHADOW_ALLOCATION_STATUS
            or self.role_verification_status != ROLE_VERIFICATION_STATUS
            or self.execution_authorization_status != EXECUTION_AUTHORIZATION_STATUS
        ):
            raise TypeError("campaign manifests require the private rehearsal factory")
        _digest(self.design_digest, "design_digest")
        _digest(self.implementation_digest, "implementation_digest")
        _digest(self.content_digest, "content_digest")
        for values, expected, name in (
            (self.treatment_digests, len(ExperimentalArm), "treatment_digests"),
            (self.driver_digests, len(AgentProfile), "driver_digests"),
            (self.budget_digests, len(AgentProfile), "budget_digests"),
        ):
            if (
                type(values) is not tuple
                or len(values) != expected
                or len(set(values)) != expected
                or any(_DIGEST.fullmatch(item) is None for item in values)
            ):
                raise TypeError(f"{name} must be one exact ordered set")
        if len({item.block_id for item in self.slots}) != len(self.slots):
            raise ValueError("campaign block ids must be unique")
        for value, name in (
            (self.stopping_rule, "stopping_rule"),
            (self.failure_handling, "failure_handling"),
        ):
            _identifier(value, name)
        if self.content_digest != _manifest_digest(self):
            raise ValueError("campaign manifest digest does not bind its content")

    @property
    def qualifying_execution_ready(self) -> bool:
        return False


def _manifest_digest(value: RehearsalCampaignManifest) -> str:
    return _hash(
        _MANIFEST_DOMAIN,
        (
            value.authority_ceiling,
            value.purpose.value,
            value.design_digest,
            value.implementation_digest,
            *value.treatment_digests,
            *value.driver_digests,
            *value.budget_digests,
            *(
                f"{item.profile.value}:{item.role.value}:{item.number}:{item.block_id}"
                for item in value.slots
            ),
            value.stopping_rule,
            value.failure_handling,
            value.transcript_cluster_policy,
            value.provenance_cluster_policy,
            value.shadow_allocation_status,
            value.role_verification_status,
            value.execution_authorization_status,
        ),
    )


def build_rehearsal_campaign_manifest(
    *,
    purpose: RehearsalPurpose,
    design_digest: str,
    implementation_digest: str,
    treatment_digests: tuple[str, ...],
    driver_digests: tuple[str, ...],
    budget_digests: tuple[str, ...],
    primary_blocks_per_profile: int,
    reserve_blocks_per_profile: int,
    campaign_id: str,
    stopping_rule: str,
    failure_handling: str,
) -> RehearsalCampaignManifest:
    if (
        type(purpose) is not RehearsalPurpose
        or type(primary_blocks_per_profile) is not int
        or not 1 <= primary_blocks_per_profile <= 10_000
        or type(reserve_blocks_per_profile) is not int
        or not 0 <= reserve_blocks_per_profile <= 10_000
    ):
        raise TypeError("campaign size requires exact bounded integers")
    _identifier(campaign_id, "campaign_id")
    slots = tuple(
        RehearsalBlockSlot(
            profile,
            role,
            number,
            f"{campaign_id}-{profile.value.lower()}-{role.value.lower()}-{number:04d}",
        )
        for profile in AgentProfile
        for role, count in (
            (RehearsalSlotRole.PRIMARY, primary_blocks_per_profile),
            (RehearsalSlotRole.RESERVE, reserve_blocks_per_profile),
        )
        for number in range(count)
    )
    digest = _hash(
        _MANIFEST_DOMAIN,
        (
            REHEARSAL_EVIDENCE_AUTHORITY_CEILING,
            purpose.value,
            design_digest,
            implementation_digest,
            *treatment_digests,
            *driver_digests,
            *budget_digests,
            *(
                f"{item.profile.value}:{item.role.value}:{item.number}:{item.block_id}"
                for item in slots
            ),
            stopping_rule,
            failure_handling,
            TRANSCRIPT_CLUSTER_POLICY,
            PROVENANCE_CLUSTER_POLICY,
            SHADOW_ALLOCATION_STATUS,
            ROLE_VERIFICATION_STATUS,
            EXECUTION_AUTHORIZATION_STATUS,
        ),
    )
    return RehearsalCampaignManifest(
        REHEARSAL_EVIDENCE_AUTHORITY_CEILING,
        purpose,
        design_digest,
        implementation_digest,
        treatment_digests,
        driver_digests,
        budget_digests,
        slots,
        stopping_rule,
        failure_handling,
        TRANSCRIPT_CLUSTER_POLICY,
        PROVENANCE_CLUSTER_POLICY,
        SHADOW_ALLOCATION_STATUS,
        ROLE_VERIFICATION_STATUS,
        EXECUTION_AUTHORIZATION_STATUS,
        digest,
        _MANIFEST_FACTORY_TOKEN,
    )


@dataclass(frozen=True, slots=True)
class RehearsalRunEvidence:
    """Trusted correlation projection of one completed non-qualifying run."""

    authority_ceiling: str
    lifecycle_digest: str
    design_digest: str
    profile: AgentProfile
    arm: ExperimentalArm
    replicate: int
    block_id: str
    plan_slot_digest: str
    driver_digest: str
    treatment_digest: str
    proposal_transcript_digest: str
    preflight_request_digests: tuple[str, ...]
    preflight_reply_digests: tuple[str, ...]
    practice_correlation_digests: tuple[str, ...]
    practice_task_ids: tuple[str, ...]
    practice_receipt_digests: tuple[str, ...]
    sampling_plan_digests: tuple[str, ...]
    worker_digests: tuple[str, ...]
    environment_digests: tuple[str, ...]
    selected_proposal_digest: str
    selection_digest: str
    submission_id: str
    submission_association_digest: str
    reconstruction_receipt_ref: str
    result_receipt_ref: str
    endpoint_receipt_ref: str
    session_binding_digest: str
    compute_digest: str
    canonical_family_ids: tuple[str, ...]
    semantic_bucket_ids: tuple[str, ...]
    lineage_root_ids: tuple[str, ...]
    experiment_record_digests: tuple[str, ...]
    transcript_cluster_digest: str
    provenance_cluster_digest: str
    content_digest: str
    _factory_token: object = dataclass_field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            type(self) is not RehearsalRunEvidence
            or self._factory_token is not _RUN_FACTORY_TOKEN
            or self.authority_ceiling != REHEARSAL_EVIDENCE_AUTHORITY_CEILING
            or type(self.profile) is not AgentProfile
            or type(self.arm) is not ExperimentalArm
            or type(self.replicate) is not int
            or self.replicate < 0
        ):
            raise TypeError("run evidence requires the private correlation factory")
        _identifier(self.block_id, "block_id")
        _identifier(self.submission_id, "submission_id")
        digest_values = (
            self.lifecycle_digest,
            self.design_digest,
            self.plan_slot_digest,
            self.driver_digest,
            self.treatment_digest,
            self.proposal_transcript_digest,
            *self.preflight_request_digests,
            *self.preflight_reply_digests,
            *self.practice_correlation_digests,
            *self.practice_receipt_digests,
            *self.sampling_plan_digests,
            *self.worker_digests,
            *self.environment_digests,
            self.selected_proposal_digest,
            self.selection_digest,
            self.submission_association_digest,
            self.reconstruction_receipt_ref,
            self.result_receipt_ref,
            self.endpoint_receipt_ref,
            self.session_binding_digest,
            self.compute_digest,
            *self.canonical_family_ids,
            *self.semantic_bucket_ids,
            *self.lineage_root_ids,
            *self.experiment_record_digests,
            self.transcript_cluster_digest,
            self.provenance_cluster_digest,
            self.content_digest,
        )
        if any(_DIGEST.fullmatch(item) is None for item in digest_values):
            raise TypeError("run evidence contains a malformed identity")
        cardinality = len(self.practice_correlation_digests)
        if (
            not cardinality
            or any(
                len(values) != cardinality
                for values in (
                    self.practice_task_ids,
                    self.practice_receipt_digests,
                    self.sampling_plan_digests,
                    self.worker_digests,
                    self.environment_digests,
                )
            )
            or any(not item.startswith("rtsk_") for item in self.practice_task_ids)
        ):
            raise ValueError("practice identities do not have exact cardinality")
        intervention_count = len(self.canonical_family_ids)
        if any(
            len(values) != intervention_count
            for values in (
                self.semantic_bucket_ids,
                self.lineage_root_ids,
                self.experiment_record_digests,
            )
        ):
            raise ValueError("canonical intervention identities are misaligned")
        if self.content_digest != _run_evidence_digest(self):
            raise ValueError("run evidence digest does not bind its content")

    @property
    def qualifying_execution_ready(self) -> bool:
        return False


def _run_evidence_digest(value: RehearsalRunEvidence) -> str:
    return _hash(
        _RUN_DOMAIN,
        (
            value.authority_ceiling,
            value.lifecycle_digest,
            value.design_digest,
            value.profile.value,
            value.arm.value,
            str(value.replicate),
            value.block_id,
            value.plan_slot_digest,
            value.driver_digest,
            value.treatment_digest,
            value.proposal_transcript_digest,
            *value.preflight_request_digests,
            *value.preflight_reply_digests,
            *value.practice_correlation_digests,
            *value.practice_task_ids,
            *value.practice_receipt_digests,
            *value.sampling_plan_digests,
            *value.worker_digests,
            *value.environment_digests,
            value.selected_proposal_digest,
            value.selection_digest,
            value.submission_id,
            value.submission_association_digest,
            value.reconstruction_receipt_ref,
            value.result_receipt_ref,
            value.endpoint_receipt_ref,
            value.session_binding_digest,
            value.compute_digest,
            *value.canonical_family_ids,
            *value.semantic_bucket_ids,
            *value.lineage_root_ids,
            *value.experiment_record_digests,
            value.transcript_cluster_digest,
            value.provenance_cluster_digest,
        ),
    )


def record_rehearsal_run(
    run: NonQualifyingLifecycleRun,
    *,
    catalog: ParameterCatalog,
    candidate_assembly: CandidateAssemblyContract,
    catalog_ref: ParameterCatalogRef,
) -> RehearsalRunEvidence:
    if (
        type(run) is not NonQualifyingLifecycleRun
        or type(catalog) is not ParameterCatalog
        or type(candidate_assembly) is not CandidateAssemblyContract
        or type(catalog_ref) is not ParameterCatalogRef
    ):
        raise TypeError("rehearsal recording requires exact owner values")
    if run.qualifying_execution_ready:
        raise ValueError("qualifying input cannot enter rehearsal evidence")
    interventions = ()
    if run.plan.identity.arm is ExperimentalArm.V2_TEST_ONLY_PRIOR:
        interventions = tuple(
            canonical_intervention_from_experiment_record(
                item.experiment_record,
                catalog=catalog,
                candidate_assembly=candidate_assembly,
                catalog_ref=catalog_ref,
                run_identity=run.plan.identity,
            )
            for item in run.practice
        )
    transcript_cluster = _hash(
        b"carbon.be4.transcript-cluster.v1\x00",
        (
            TRANSCRIPT_CLUSTER_POLICY,
            run.plan.design_digest,
            run.plan.identity.profile.value,
            run.plan.block_id,
            run.prepared.transcript_digest,
            *(item.content_digest for item in run.practice),
        ),
    )
    provenance_cluster = _hash(
        b"carbon.be4.provenance-cluster.v1\x00",
        (
            PROVENANCE_CLUSTER_POLICY,
            run.driver_artifact.content_digest,
            run.prepared.strategy_domain_digest,
            *(
                item.experiment_record.sampling_plan_ref.content_digest
                for item in run.practice
            ),
        ),
    )
    fields = (
        REHEARSAL_EVIDENCE_AUTHORITY_CEILING,
        run.content_digest,
        run.plan.design_digest,
        run.plan.identity.profile,
        run.plan.identity.arm,
        run.plan.identity.replicate,
        run.plan.block_id,
        run.plan.final_submission_slot_digest,
        run.driver_artifact.content_digest,
        run.treatment_artifact.content_digest,
        run.prepared.transcript_digest,
        run.prepared.service_request_digests,
        run.prepared.service_reply_digests,
        tuple(item.content_digest for item in run.practice),
        tuple(item.experiment_record.task_id.value for item in run.practice),
        tuple(item.receipt.receipt_ref.receipt_digest for item in run.practice),
        tuple(
            item.experiment_record.sampling_plan_ref.content_digest
            for item in run.practice
        ),
        tuple(
            item.experiment_record.execution_identity.worker_implementation_digest
            for item in run.practice
        ),
        tuple(
            item.experiment_record.execution_identity.environment_digest
            for item in run.practice
        ),
        run.selection.selected_proposal_digest,
        run.selection.content_digest,
        run.official_submission.receipt.status.submission_id.value,
        run.official_submission.association_digest,
        run.official_outcome.reconstruction_receipt.receipt_ref,
        run.official_outcome.result_receipt.receipt_ref,
        run.official_outcome.endpoint_observation_receipt.receipt_ref,
        run.session_binding_digest,
        run.normalized_compute.content_digest,
        tuple(item.intervention.family_identity for item in interventions),
        tuple(item.intervention.semantic_bucket_identity for item in interventions),
        tuple(item.intervention.lineage_root_identity for item in interventions),
        tuple(item.experiment_record_digest for item in interventions),
        transcript_cluster,
        provenance_cluster,
    )
    digest = _hash(
        _RUN_DOMAIN,
        (
            fields[0],
            fields[1],
            fields[2],
            fields[3].value,
            fields[4].value,
            str(fields[5]),
            fields[6],
            *(
                item
                for value in fields[7:]
                for item in (value if type(value) is tuple else (value,))
            ),
        ),
    )
    return RehearsalRunEvidence(*fields, digest, _RUN_FACTORY_TOKEN)


@dataclass(frozen=True, slots=True)
class BlockFailureEvidence:
    slot: RehearsalBlockSlot
    failure_kind: LifecycleFailureKind
    stage: str
    content_digest: str
    _factory_token: object = dataclass_field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            type(self) is not BlockFailureEvidence
            or self._factory_token is not _FAILURE_FACTORY_TOKEN
            or type(self.slot) is not RehearsalBlockSlot
            or type(self.failure_kind) is not LifecycleFailureKind
        ):
            raise TypeError("block failures require the trusted failure factory")
        _identifier(self.stage, "stage")
        _digest(self.content_digest, "content_digest")
        expected = _hash(
            _FAILURE_DOMAIN,
            (
                self.slot.profile.value,
                self.slot.role.value,
                str(self.slot.number),
                self.slot.block_id,
                self.failure_kind.value,
                self.stage,
            ),
        )
        if self.content_digest != expected:
            raise ValueError("block failure digest does not bind its content")


def record_block_failure(
    slot: RehearsalBlockSlot, error: NonQualifyingLifecycleError
) -> BlockFailureEvidence:
    if (
        type(slot) is not RehearsalBlockSlot
        or type(error) is not NonQualifyingLifecycleError
    ):
        raise TypeError("failure recording requires exact typed values")
    digest = _hash(
        _FAILURE_DOMAIN,
        (
            slot.profile.value,
            slot.role.value,
            str(slot.number),
            slot.block_id,
            error.kind.value,
            error.stage,
        ),
    )
    return BlockFailureEvidence(
        slot, error.kind, error.stage, digest, _FAILURE_FACTORY_TOKEN
    )


@dataclass(frozen=True, slots=True)
class RejectedOperationEvidence:
    """Exact public B-07S rejection correlation; never a replacement license."""

    slot: RehearsalBlockSlot
    operation: str
    outcome: ResearchServiceErrorCode
    request_digest: str
    reply_digest: str
    content_digest: str
    _factory_token: object = dataclass_field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            type(self) is not RejectedOperationEvidence
            or self._factory_token is not _REJECTION_FACTORY_TOKEN
            or type(self.slot) is not RehearsalBlockSlot
            or type(self.outcome) is not ResearchServiceErrorCode
        ):
            raise TypeError("rejected operations require the protocol failure factory")
        _identifier(self.operation, "operation")
        _digest(self.request_digest, "request_digest")
        _digest(self.reply_digest, "reply_digest")
        _digest(self.content_digest, "content_digest")
        expected = _hash(
            _REJECTION_DOMAIN,
            (
                self.slot.profile.value,
                self.slot.role.value,
                str(self.slot.number),
                self.slot.block_id,
                self.operation,
                self.outcome.value,
                self.request_digest,
                self.reply_digest,
            ),
        )
        if self.content_digest != expected:
            raise ValueError("rejected operation digest does not bind its content")


def record_rejected_operation(
    slot: RehearsalBlockSlot, error: ResearchOperationFailure
) -> RejectedOperationEvidence:
    if (
        type(slot) is not RehearsalBlockSlot
        or type(error) is not ResearchOperationFailure
    ):
        raise TypeError("rejection recording requires exact protocol failure values")
    digest = _hash(
        _REJECTION_DOMAIN,
        (
            slot.profile.value,
            slot.role.value,
            str(slot.number),
            slot.block_id,
            error.operation,
            error.code.value,
            error.request_digest,
            error.reply_digest,
        ),
    )
    return RejectedOperationEvidence(
        slot,
        error.operation,
        error.code,
        error.request_digest,
        error.reply_digest,
        digest,
        _REJECTION_FACTORY_TOKEN,
    )


@dataclass(frozen=True, slots=True)
class RetainedBlockMapping:
    failed: BlockFailureEvidence
    replacement: RehearsalBlockSlot
    content_digest: str
    _factory_token: object = dataclass_field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            type(self) is not RetainedBlockMapping
            or self._factory_token is not _REPLACEMENT_FACTORY_TOKEN
            or type(self.failed) is not BlockFailureEvidence
            or type(self.replacement) is not RehearsalBlockSlot
            or self.failed.slot.role is not RehearsalSlotRole.PRIMARY
            or self.replacement.role is not RehearsalSlotRole.RESERVE
            or self.failed.slot.profile is not self.replacement.profile
            or self.failed.failure_kind
            not in (LifecycleFailureKind.INFRASTRUCTURE, LifecycleFailureKind.REFERENCE)
        ):
            raise ValueError("replacement is not authorized by the typed failure rule")
        _digest(self.content_digest, "content_digest")
        expected = _hash(
            _REPLACEMENT_DOMAIN,
            (
                self.failed.content_digest,
                self.replacement.profile.value,
                str(self.replacement.number),
                self.replacement.block_id,
            ),
        )
        if self.content_digest != expected:
            raise ValueError("replacement mapping digest does not bind its content")


def authorize_replacement(
    *, failed: BlockFailureEvidence, replacement: RehearsalBlockSlot
) -> RetainedBlockMapping:
    if (
        type(failed) is not BlockFailureEvidence
        or type(replacement) is not RehearsalBlockSlot
    ):
        raise TypeError("replacement requires exact retained records")
    digest = _hash(
        _REPLACEMENT_DOMAIN,
        (
            failed.content_digest,
            replacement.profile.value,
            str(replacement.number),
            replacement.block_id,
        ),
    )
    return RetainedBlockMapping(failed, replacement, digest, _REPLACEMENT_FACTORY_TOKEN)


@dataclass(frozen=True, slots=True)
class RehearsalCampaignEvidence:
    manifest: RehearsalCampaignManifest
    runs: tuple[RehearsalRunEvidence, ...]
    failures: tuple[BlockFailureEvidence, ...]
    rejected_operations: tuple[RejectedOperationEvidence, ...]
    replacements: tuple[RetainedBlockMapping, ...]
    unique_experiment_record_digests: tuple[str, ...]
    content_digest: str
    _factory_token: object = dataclass_field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if (
            type(self) is not RehearsalCampaignEvidence
            or self._factory_token is not _CAMPAIGN_FACTORY_TOKEN
            or type(self.manifest) is not RehearsalCampaignManifest
            or type(self.runs) is not tuple
            or any(type(item) is not RehearsalRunEvidence for item in self.runs)
            or type(self.failures) is not tuple
            or any(type(item) is not BlockFailureEvidence for item in self.failures)
            or type(self.rejected_operations) is not tuple
            or any(
                type(item) is not RejectedOperationEvidence
                for item in self.rejected_operations
            )
            or type(self.replacements) is not tuple
            or any(type(item) is not RetainedBlockMapping for item in self.replacements)
        ):
            raise TypeError("campaign evidence requires exact rehearsal records")
        if len({item.content_digest for item in self.runs}) != len(self.runs):
            raise ValueError("duplicate run evidence is rejected")
        slots = {item.block_id: item for item in self.manifest.slots}
        if any(
            item.design_digest != self.manifest.design_digest
            or item.block_id not in slots
            or slots[item.block_id].profile is not item.profile
            or item.driver_digest not in self.manifest.driver_digests
            or item.treatment_digest not in self.manifest.treatment_digests
            for item in self.runs
        ):
            raise ValueError("run evidence does not belong to the frozen manifest")
        run_keys = tuple((item.profile, item.block_id, item.arm) for item in self.runs)
        if len(set(run_keys)) != len(run_keys):
            raise ValueError("campaign contains a duplicate profile/block/arm slot")
        if any(
            item.slot.block_id not in slots or slots[item.slot.block_id] != item.slot
            for item in self.failures
        ) or any(
            item.slot.block_id not in slots or slots[item.slot.block_id] != item.slot
            for item in self.rejected_operations
        ):
            raise ValueError("failure evidence does not belong to the frozen manifest")
        expected_unique = tuple(
            dict.fromkeys(
                digest for run in self.runs for digest in run.experiment_record_digests
            )
        )
        if self.unique_experiment_record_digests != expected_unique:
            raise ValueError("copied experiment records were not collapsed")
        failures = {item.content_digest: item for item in self.failures}
        if any(
            item.failed.content_digest not in failures
            or item.replacement.block_id not in slots
            or slots[item.replacement.block_id] != item.replacement
            for item in self.replacements
        ) or len({item.replacement.block_id for item in self.replacements}) != len(
            self.replacements
        ):
            raise ValueError("replacement mappings do not retain unique failures")
        _digest(self.content_digest, "content_digest")
        expected = _hash(
            _CAMPAIGN_DOMAIN,
            (
                self.manifest.content_digest,
                *(item.content_digest for item in self.runs),
                *(item.content_digest for item in self.failures),
                *(item.content_digest for item in self.rejected_operations),
                *(item.content_digest for item in self.replacements),
                *self.unique_experiment_record_digests,
                REHEARSAL_EVIDENCE_AUTHORITY_CEILING,
            ),
        )
        if self.content_digest != expected:
            raise ValueError("campaign evidence digest does not bind its content")

    @property
    def qualifying_execution_ready(self) -> bool:
        return False

    @property
    def primary_matrix_complete(self) -> bool:
        """Whether every prospective primary is complete or retained as failed.

        This is descriptive rehearsal completeness only.  A true value cannot
        authorize or qualify an execution.
        """

        completed = {
            (run.profile, run.block_id)
            for run in self.runs
            if {
                item.arm
                for item in self.runs
                if item.profile is run.profile and item.block_id == run.block_id
            }
            == set(ExperimentalArm)
        }
        failed = {
            (item.slot.profile, item.slot.block_id)
            for item in (*self.failures, *self.rejected_operations)
        }
        expected = {
            (item.profile, item.block_id)
            for item in self.manifest.slots
            if item.role is RehearsalSlotRole.PRIMARY
        }
        return expected <= completed | failed


def record_rehearsal_campaign(
    *,
    manifest: RehearsalCampaignManifest,
    runs: tuple[RehearsalRunEvidence, ...],
    failures: tuple[BlockFailureEvidence, ...] = (),
    rejected_operations: tuple[RejectedOperationEvidence, ...] = (),
    replacements: tuple[RetainedBlockMapping, ...] = (),
) -> RehearsalCampaignEvidence:
    if type(manifest) is not RehearsalCampaignManifest:
        raise TypeError("campaign recording requires an exact manifest")
    unique = tuple(
        dict.fromkeys(
            digest for run in runs for digest in run.experiment_record_digests
        )
    )
    digest = _hash(
        _CAMPAIGN_DOMAIN,
        (
            manifest.content_digest,
            *(item.content_digest for item in runs),
            *(item.content_digest for item in failures),
            *(item.content_digest for item in rejected_operations),
            *(item.content_digest for item in replacements),
            *unique,
            REHEARSAL_EVIDENCE_AUTHORITY_CEILING,
        ),
    )
    return RehearsalCampaignEvidence(
        manifest,
        runs,
        failures,
        rejected_operations,
        replacements,
        unique,
        digest,
        _CAMPAIGN_FACTORY_TOKEN,
    )


__all__ = (
    "EXECUTION_AUTHORIZATION_STATUS",
    "PROVENANCE_CLUSTER_POLICY",
    "REHEARSAL_EVIDENCE_AUTHORITY_CEILING",
    "ROLE_VERIFICATION_STATUS",
    "SHADOW_ALLOCATION_STATUS",
    "TRANSCRIPT_CLUSTER_POLICY",
    "BlockFailureEvidence",
    "RehearsalBlockSlot",
    "RehearsalCampaignEvidence",
    "RehearsalCampaignManifest",
    "RehearsalPurpose",
    "RehearsalRunEvidence",
    "RehearsalSlotRole",
    "RejectedOperationEvidence",
    "RetainedBlockMapping",
    "authorize_replacement",
    "build_rehearsal_campaign_manifest",
    "record_block_failure",
    "record_rehearsal_campaign",
    "record_rehearsal_run",
    "record_rejected_operation",
    "rehearsal_budget_digest",
    "rehearsal_implementation_digest",
)
