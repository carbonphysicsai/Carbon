"""Closed runtime types for the C-EA1 synthetic evidence archive."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from carbon.execution import DurableExecutionBinding, ExecutionScope
from carbon.fees import AdmissionKind

SCHEMA_VERSION = "carbon.evidence-archive.v1"
SYNTHETIC_PROFILE_ID = "carbon.synthetic-evidence-archive.dev.v1"
SYNTHETIC_TENANT_ID = "carbon-synthetic-ci"
SYNTHETIC_DURABILITY_POLICY_REF = "policy:carbon.synthetic-durability.dev.v1"
SYNTHETIC_CAPTURE_POLICY_REF = "policy:carbon.synthetic-capture.dev.v1"
SYNTHETIC_CUSTODY_POLICY_REF = "policy:carbon.synthetic-custody.dev.v1"
SYNTHETIC_USE_POLICY_REF = "policy:carbon.synthetic-internal-audit.dev.v1"
AEAD_ALGORITHM = "AES-256-GCM"

_TOKEN = re.compile(r"[a-zA-Z0-9]+(?:[._:-][a-zA-Z0-9]+)*\Z", re.ASCII)
_ARTIFACT = re.compile(r"[a-z][a-z0-9_]{0,63}\Z", re.ASCII)
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}\Z", re.ASCII)


class ArchiveCode(StrEnum):
    INVALID = "archive.request.invalid"
    DENIED = "archive.authorization.denied"
    CONFLICT = "archive.content.conflict"
    CAPACITY = "archive.capacity.exceeded"
    STORE = "archive.store.unavailable"
    INTEGRITY = "archive.integrity.failed"
    KEY_UNAVAILABLE = "archive.key.unavailable"
    STATE = "archive.state.invalid"


class ArchiveFailure(RuntimeError):
    """Stable non-echoing archive error; payloads and keys never enter messages."""

    def __init__(self, code: ArchiveCode) -> None:
        self.code = code if type(code) is ArchiveCode else ArchiveCode.INVALID
        super().__init__("Evidence archive operation failed.")


class AttemptRelationKind(StrEnum):
    INITIAL = "INITIAL"
    RETRY_OF = "RETRY_OF"
    REEXECUTION_OF = "REEXECUTION_OF"


class ExecutionDisposition(StrEnum):
    NOT_DISPATCHED = "NOT_DISPATCHED"
    RUNNING = "RUNNING"
    INTERRUPTED = "INTERRUPTED"
    CANCELLED = "CANCELLED"
    EARLY_STOPPED = "EARLY_STOPPED"
    COMPLETED = "COMPLETED"


class ScientificResultState(StrEnum):
    NOT_AVAILABLE = "NOT_AVAILABLE"
    SOURCE_RESULT_REF = "SOURCE_RESULT_REF"


class SourceFailureClass(StrEnum):
    NONE = "NONE"
    STRATEGY = "STRATEGY"
    GENERATOR = "GENERATOR"
    REFERENCE = "REFERENCE"
    MEASUREMENT = "MEASUREMENT"
    VALIDATOR = "VALIDATOR"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    UNKNOWN = "UNKNOWN"


class EvidenceCompleteness(StrEnum):
    UNASSESSED = "UNASSESSED"
    COMPLETE = "COMPLETE"
    PARTIAL_EXPLICIT_MISSINGNESS = "PARTIAL_EXPLICIT_MISSINGNESS"
    UNAVAILABLE = "UNAVAILABLE"


class QualificationOrigin(StrEnum):
    FIXTURE = "FIXTURE"
    PRACTICE = "PRACTICE"
    NON_OFFICIAL = "NON_OFFICIAL"
    OFFICIAL_UNQUALIFIED = "OFFICIAL_UNQUALIFIED"
    QUALIFIED_CONTRACT_REF = "QUALIFIED_CONTRACT_REF"


class NamedUse(StrEnum):
    INTERNAL_AUDIT = "INTERNAL_AUDIT"
    LANDSCAPE_RESEARCH = "LANDSCAPE_RESEARCH"
    RELEASE_CANDIDATE = "RELEASE_CANDIDATE"
    EXTERNAL_RELEASE = "EXTERNAL_RELEASE"
    COMMERCIAL_USE = "COMMERCIAL_USE"


class UseEligibility(StrEnum):
    UNASSESSED = "UNASSESSED"
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    BLOCKED_UNKNOWN = "BLOCKED_UNKNOWN"


class EpistemicValue(StrEnum):
    OBSERVED = "OBSERVED"
    ABSENT = "ABSENT"
    UNKNOWN = "UNKNOWN"


class DependenceKind(StrEnum):
    SHARED_CASE = "SHARED_CASE"
    SHARED_REFERENCE = "SHARED_REFERENCE"
    ANCESTRY = "ANCESTRY"
    CHECKPOINT = "CHECKPOINT"
    RECONSTRUCTION_REPEAT = "RECONSTRUCTION_REPEAT"
    OTHER_DECLARED = "OTHER_DECLARED"
    UNKNOWN = "UNKNOWN"


class CustodyZone(StrEnum):
    TENANT_ISOLATED_RESEARCH_STORE = "TENANT_ISOLATED_RESEARCH_STORE"


class RetentionClass(StrEnum):
    REQUIRED_SCIENTIFIC_RECORD = "REQUIRED_SCIENTIFIC_RECORD"
    REQUIRED_ORIGINAL_ARTIFACT = "REQUIRED_ORIGINAL_ARTIFACT"
    OPTIONAL_DEBUG = "OPTIONAL_DEBUG"
    REBUILDABLE_DERIVATIVE = "REBUILDABLE_DERIVATIVE"


class PolicyKind(StrEnum):
    DURABILITY = "DURABILITY"
    CAPTURE = "CAPTURE"
    CUSTODY = "CUSTODY"
    USE = "USE"


class CurrentAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    WITHDRAWN = "WITHDRAWN"
    UNAVAILABLE_KEY = "UNAVAILABLE_KEY"
    CORRUPT = "CORRUPT"


class ArtifactRequirement(StrEnum):
    REQUIRED = "REQUIRED"
    OPTIONAL_DEBUG = "OPTIONAL_DEBUG"
    REBUILDABLE_DERIVATIVE = "REBUILDABLE_DERIVATIVE"


class ArtifactState(StrEnum):
    EXPECTED = "EXPECTED"
    WRITTEN = "WRITTEN"
    VERIFIED = "VERIFIED"
    MISSING = "MISSING"
    INTENTIONALLY_ABSENT = "INTENTIONALLY_ABSENT"
    WITHDRAWN = "WITHDRAWN"
    UNAVAILABLE_KEY = "UNAVAILABLE_KEY"


class AcknowledgementState(StrEnum):
    NOT_ACKNOWLEDGED = "NOT_ACKNOWLEDGED"
    PENDING = "PENDING"
    VERIFIED_DURABLE = "VERIFIED_DURABLE"
    REJECTED = "REJECTED"


class AcknowledgementReason(StrEnum):
    VERIFIED = "VERIFIED"
    PROFILE_NOT_APPROVED = "PROFILE_NOT_APPROVED"
    SOURCE_BINDING_INVALID = "SOURCE_BINDING_INVALID"
    REQUIRED_ARTIFACT_PENDING = "REQUIRED_ARTIFACT_PENDING"
    REQUIRED_ARTIFACT_UNAVAILABLE = "REQUIRED_ARTIFACT_UNAVAILABLE"
    MANIFEST_NOT_VERIFIED = "MANIFEST_NOT_VERIFIED"
    CATALOGUE_NOT_COMMITTED = "CATALOGUE_NOT_COMMITTED"
    OBJECT_UNAVAILABLE = "OBJECT_UNAVAILABLE"
    KEY_UNAVAILABLE = "KEY_UNAVAILABLE"
    CUSTODY_POLICY_NOT_APPROVED = "CUSTODY_POLICY_NOT_APPROVED"
    SYNTHETIC_SCOPE_ONLY = "SYNTHETIC_SCOPE_ONLY"


@dataclass(frozen=True, slots=True)
class PolicyReference:
    kind: PolicyKind
    ref: str
    profile_id: str = SYNTHETIC_PROFILE_ID

    def __post_init__(self) -> None:
        if type(self.kind) is not PolicyKind or self.profile_id != SYNTHETIC_PROFILE_ID:
            raise ArchiveFailure(ArchiveCode.DENIED)
        object.__setattr__(self, "ref", validate_token(self.ref))


@dataclass(frozen=True, slots=True)
class DependenceLink:
    kind: DependenceKind
    source_ref: str | None

    def __post_init__(self) -> None:
        if type(self.kind) is not DependenceKind:
            raise ArchiveFailure(ArchiveCode.INVALID)
        if self.kind is DependenceKind.UNKNOWN:
            if self.source_ref is not None:
                raise ArchiveFailure(ArchiveCode.INVALID)
        else:
            object.__setattr__(self, "source_ref", validate_token(self.source_ref))


@dataclass(frozen=True, slots=True)
class AvailabilityAssessment:
    artifact_name: str
    availability: CurrentAvailability
    reason_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "artifact_name", validate_artifact_name(self.artifact_name)
        )
        if type(self.availability) is not CurrentAvailability:
            raise ArchiveFailure(ArchiveCode.INVALID)
        object.__setattr__(self, "reason_ref", validate_token(self.reason_ref))


@dataclass(frozen=True, slots=True)
class AppendOnlyArchiveEvent:
    schema_version: str
    archive_entry_id: str
    event_kind: str
    body_digest: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise ArchiveFailure(ArchiveCode.INVALID)
        object.__setattr__(
            self, "archive_entry_id", validate_digest(self.archive_entry_id)
        )
        object.__setattr__(self, "event_kind", validate_token(self.event_kind))
        object.__setattr__(self, "body_digest", validate_digest(self.body_digest))


def validate_token(value: object, *, maximum: int = 128) -> str:
    if (
        type(value) is not str
        or not 1 <= len(value) <= maximum
        or _TOKEN.fullmatch(value) is None
    ):
        raise ArchiveFailure(ArchiveCode.INVALID)
    return value


def validate_digest(value: object) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ArchiveFailure(ArchiveCode.INVALID)
    return value


def validate_artifact_name(value: object) -> str:
    if type(value) is not str or _ARTIFACT.fullmatch(value) is None:
        raise ArchiveFailure(ArchiveCode.INVALID)
    return value


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError):
        raise ArchiveFailure(ArchiveCode.INVALID) from None


def content_digest(domain: str, value: bytes) -> str:
    return (
        "sha256:" + hashlib.sha256(domain.encode("ascii") + b"\0" + value).hexdigest()
    )


@dataclass(frozen=True, slots=True)
class AttemptRelation:
    kind: AttemptRelationKind
    previous_archive_entry_id: str | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not AttemptRelationKind:
            raise ArchiveFailure(ArchiveCode.INVALID)
        if self.kind is AttemptRelationKind.INITIAL:
            if self.previous_archive_entry_id is not None:
                raise ArchiveFailure(ArchiveCode.INVALID)
        else:
            object.__setattr__(
                self,
                "previous_archive_entry_id",
                validate_digest(self.previous_archive_entry_id),
            )


@dataclass(frozen=True, slots=True)
class SourceBinding:
    tenant_id: str
    submission_id: str
    challenge_id: str
    challenge_version: str
    candidate_digest: str
    execution_id: str
    physical_attempt_id: str
    attempt_number: int

    def __post_init__(self) -> None:
        for name in (
            "tenant_id",
            "submission_id",
            "challenge_id",
            "challenge_version",
            "execution_id",
            "physical_attempt_id",
        ):
            object.__setattr__(self, name, validate_token(getattr(self, name)))
        object.__setattr__(
            self, "candidate_digest", validate_digest(self.candidate_digest)
        )
        if type(self.attempt_number) is not int or not 1 <= self.attempt_number < 2**63:
            raise ArchiveFailure(ArchiveCode.INVALID)
        if self.tenant_id != SYNTHETIC_TENANT_ID:
            raise ArchiveFailure(ArchiveCode.DENIED)

    @classmethod
    def from_execution_binding(
        cls,
        binding: DurableExecutionBinding,
        *,
        execution_id: str,
        physical_attempt_id: str,
    ) -> SourceBinding:
        if (
            type(binding) is not DurableExecutionBinding
            or binding.scope is not ExecutionScope.FIXTURE_DEVELOPMENT
            or binding.handle.admission_kind is not AdmissionKind.FIXTURE
        ):
            raise ArchiveFailure(ArchiveCode.DENIED)
        pin = binding.handle.seed_pin
        return cls(
            tenant_id=SYNTHETIC_TENANT_ID,
            submission_id=binding.handle.submission_id.value,
            challenge_id=pin.challenge_key.challenge_id,
            challenge_version=pin.challenge_key.version,
            candidate_digest=binding.strategy_hash.value,
            execution_id=execution_id,
            physical_attempt_id=physical_attempt_id,
            attempt_number=binding.handle.attempt_number,
        )

    def payload(self) -> dict[str, object]:
        return {
            "tenant_id": self.tenant_id,
            "submission_id": self.submission_id,
            "challenge_id": self.challenge_id,
            "challenge_version": self.challenge_version,
            "candidate_digest": self.candidate_digest,
            "execution_id": self.execution_id,
            "physical_attempt_id": self.physical_attempt_id,
            "attempt_number": self.attempt_number,
        }


@dataclass(frozen=True, slots=True)
class ArtifactRule:
    name: str
    requirement: ArtifactRequirement
    required_for: tuple[ExecutionDisposition, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", validate_artifact_name(self.name))
        if type(self.requirement) is not ArtifactRequirement:
            raise ArchiveFailure(ArchiveCode.INVALID)
        if (
            type(self.required_for) is not tuple
            or any(
                type(value) is not ExecutionDisposition for value in self.required_for
            )
            or len(set(self.required_for)) != len(self.required_for)
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)

    def is_required(self, disposition: ExecutionDisposition) -> bool:
        return (
            self.requirement is ArtifactRequirement.REQUIRED
            and disposition in self.required_for
        )

    @property
    def retention_class(self) -> RetentionClass:
        if self.requirement is ArtifactRequirement.REQUIRED:
            return RetentionClass.REQUIRED_ORIGINAL_ARTIFACT
        if self.requirement is ArtifactRequirement.OPTIONAL_DEBUG:
            return RetentionClass.OPTIONAL_DEBUG
        return RetentionClass.REBUILDABLE_DERIVATIVE


@dataclass(frozen=True, slots=True)
class EvidenceCaptureProfile:
    schema_version: str
    profile_id: str
    challenge_id: str
    execution_class: str
    durability_policy_ref: str
    capture_policy_ref: str
    custody_policy_ref: str
    use_policy_ref: str
    artifact_rules: tuple[ArtifactRule, ...]
    synthetic_only: bool = True

    def __post_init__(self) -> None:
        if (
            self.schema_version != SCHEMA_VERSION
            or self.profile_id != SYNTHETIC_PROFILE_ID
            or self.synthetic_only is not True
        ):
            raise ArchiveFailure(ArchiveCode.DENIED)
        for name in (
            "challenge_id",
            "execution_class",
            "durability_policy_ref",
            "capture_policy_ref",
            "custody_policy_ref",
            "use_policy_ref",
        ):
            object.__setattr__(self, name, validate_token(getattr(self, name)))
        if (
            self.durability_policy_ref != SYNTHETIC_DURABILITY_POLICY_REF
            or self.capture_policy_ref != SYNTHETIC_CAPTURE_POLICY_REF
            or self.custody_policy_ref != SYNTHETIC_CUSTODY_POLICY_REF
            or self.use_policy_ref != SYNTHETIC_USE_POLICY_REF
            or type(self.artifact_rules) is not tuple
            or not self.artifact_rules
            or any(type(rule) is not ArtifactRule for rule in self.artifact_rules)
            or len({rule.name for rule in self.artifact_rules})
            != len(self.artifact_rules)
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)

    @property
    def policy_references(self) -> tuple[PolicyReference, ...]:
        return (
            PolicyReference(PolicyKind.DURABILITY, self.durability_policy_ref),
            PolicyReference(PolicyKind.CAPTURE, self.capture_policy_ref),
            PolicyReference(PolicyKind.CUSTODY, self.custody_policy_ref),
            PolicyReference(PolicyKind.USE, self.use_policy_ref),
        )

    @property
    def custody_zone(self) -> CustodyZone:
        return CustodyZone.TENANT_ISOLATED_RESEARCH_STORE

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "challenge_id": self.challenge_id,
            "execution_class": self.execution_class,
            "durability_policy_ref": self.durability_policy_ref,
            "capture_policy_ref": self.capture_policy_ref,
            "custody_policy_ref": self.custody_policy_ref,
            "use_policy_ref": self.use_policy_ref,
            "custody_zone": self.custody_zone.value,
            "synthetic_only": self.synthetic_only,
            "artifact_rules": [
                {
                    "name": rule.name,
                    "requirement": rule.requirement.value,
                    "retention_class": rule.retention_class.value,
                    "required_for": [value.value for value in rule.required_for],
                }
                for rule in self.artifact_rules
            ],
        }

    @property
    def digest(self) -> str:
        return content_digest(
            "carbon.evidence.capture-profile.v1", canonical_bytes(self.payload())
        )


def synthetic_capture_profile(
    *, challenge_id: str = "burgers"
) -> EvidenceCaptureProfile:
    terminal = (
        ExecutionDisposition.CANCELLED,
        ExecutionDisposition.EARLY_STOPPED,
        ExecutionDisposition.COMPLETED,
        ExecutionDisposition.INTERRUPTED,
    )
    completed = (ExecutionDisposition.EARLY_STOPPED, ExecutionDisposition.COMPLETED)
    return EvidenceCaptureProfile(
        schema_version=SCHEMA_VERSION,
        profile_id=SYNTHETIC_PROFILE_ID,
        challenge_id=challenge_id,
        execution_class="SYNTHETIC_FIXTURE",
        durability_policy_ref=SYNTHETIC_DURABILITY_POLICY_REF,
        capture_policy_ref=SYNTHETIC_CAPTURE_POLICY_REF,
        custody_policy_ref=SYNTHETIC_CUSTODY_POLICY_REF,
        use_policy_ref=SYNTHETIC_USE_POLICY_REF,
        artifact_rules=(
            ArtifactRule("source_binding", ArtifactRequirement.REQUIRED, terminal),
            ArtifactRule("manifest_input", ArtifactRequirement.REQUIRED, terminal),
            ArtifactRule(
                "representative_output", ArtifactRequirement.REQUIRED, completed
            ),
            ArtifactRule("execution_log", ArtifactRequirement.REQUIRED, terminal),
            ArtifactRule("checkpoint", ArtifactRequirement.REQUIRED, completed),
            ArtifactRule("debug_trace", ArtifactRequirement.OPTIONAL_DEBUG),
            ArtifactRule("derived_summary", ArtifactRequirement.REBUILDABLE_DERIVATIVE),
        ),
    )


@dataclass(frozen=True, slots=True)
class ArchiveEntry:
    archive_entry_id: str
    source: SourceBinding
    relation: AttemptRelation
    capture_profile_digest: str
    execution_disposition: ExecutionDisposition
    scientific_result_state: ScientificResultState
    scientific_result_ref: str | None
    qualification_origin: QualificationOrigin = QualificationOrigin.FIXTURE
    source_failure_class: SourceFailureClass = SourceFailureClass.NONE
    guidance_exposure: EpistemicValue = EpistemicValue.UNKNOWN
    dependence_links: tuple[DependenceLink, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "archive_entry_id", validate_digest(self.archive_entry_id)
        )
        if (
            type(self.source) is not SourceBinding
            or type(self.relation) is not AttemptRelation
            or type(self.execution_disposition) is not ExecutionDisposition
            or type(self.scientific_result_state) is not ScientificResultState
            or self.qualification_origin is not QualificationOrigin.FIXTURE
            or type(self.source_failure_class) is not SourceFailureClass
            or type(self.guidance_exposure) is not EpistemicValue
            or type(self.dependence_links) is not tuple
            or any(type(link) is not DependenceLink for link in self.dependence_links)
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)
        object.__setattr__(
            self, "capture_profile_digest", validate_digest(self.capture_profile_digest)
        )
        if self.scientific_result_state is ScientificResultState.NOT_AVAILABLE:
            if self.scientific_result_ref is not None:
                raise ArchiveFailure(ArchiveCode.INVALID)
        else:
            object.__setattr__(
                self,
                "scientific_result_ref",
                validate_token(self.scientific_result_ref),
            )


@dataclass(frozen=True, slots=True)
class ArtifactInput:
    name: str
    state: ArtifactState
    payload: bytes | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", validate_artifact_name(self.name))
        if type(self.state) is not ArtifactState:
            raise ArchiveFailure(ArchiveCode.INVALID)
        if self.state is ArtifactState.WRITTEN:
            if type(self.payload) is not bytes or not self.payload:
                raise ArchiveFailure(ArchiveCode.INVALID)
        elif self.payload is not None:
            raise ArchiveFailure(ArchiveCode.INVALID)


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    name: str
    requirement: ArtifactRequirement
    state: ArtifactState
    plaintext_digest: str | None
    plaintext_size: int
    object_key: str | None
    key_id: str | None
    algorithm: str | None
    nonce_hex: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", validate_artifact_name(self.name))
        if (
            type(self.requirement) is not ArtifactRequirement
            or type(self.state) is not ArtifactState
            or type(self.plaintext_size) is not int
            or self.plaintext_size < 0
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)
        metadata = (
            self.plaintext_digest,
            self.object_key,
            self.key_id,
            self.algorithm,
            self.nonce_hex,
        )
        if self.state is ArtifactState.VERIFIED:
            if any(value is None for value in metadata) or self.plaintext_size < 1:
                raise ArchiveFailure(ArchiveCode.INVALID)
            object.__setattr__(
                self, "plaintext_digest", validate_digest(self.plaintext_digest)
            )
            object.__setattr__(self, "key_id", validate_token(self.key_id))
            if self.algorithm != AEAD_ALGORITHM:
                raise ArchiveFailure(ArchiveCode.INVALID)
            try:
                nonce = bytes.fromhex(self.nonce_hex or "")
            except ValueError:
                raise ArchiveFailure(ArchiveCode.INVALID) from None
            if len(nonce) != 12:
                raise ArchiveFailure(ArchiveCode.INVALID)
        elif any(value is not None for value in metadata) or self.plaintext_size != 0:
            raise ArchiveFailure(ArchiveCode.INVALID)


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    schema_version: str
    archive_entry_id: str
    capture_profile_digest: str
    artifacts: tuple[ArtifactRecord, ...]
    content_identity: str

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_VERSION or type(self.artifacts) is not tuple:
            raise ArchiveFailure(ArchiveCode.INVALID)
        object.__setattr__(
            self, "archive_entry_id", validate_digest(self.archive_entry_id)
        )
        object.__setattr__(
            self, "capture_profile_digest", validate_digest(self.capture_profile_digest)
        )
        object.__setattr__(
            self, "content_identity", validate_digest(self.content_identity)
        )
        if any(
            type(artifact) is not ArtifactRecord for artifact in self.artifacts
        ) or len({artifact.name for artifact in self.artifacts}) != len(self.artifacts):
            raise ArchiveFailure(ArchiveCode.INVALID)


@dataclass(frozen=True, slots=True)
class EvidenceUseAssessment:
    archive_entry_id: str
    named_use: NamedUse
    eligibility: UseEligibility
    policy_ref: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "archive_entry_id", validate_digest(self.archive_entry_id)
        )
        if (
            type(self.named_use) is not NamedUse
            or type(self.eligibility) is not UseEligibility
            or self.policy_ref != SYNTHETIC_USE_POLICY_REF
            or (
                self.named_use is NamedUse.INTERNAL_AUDIT
                and self.eligibility is not UseEligibility.ELIGIBLE
            )
            or (
                self.named_use is not NamedUse.INTERNAL_AUDIT
                and self.eligibility is not UseEligibility.INELIGIBLE
            )
        ):
            raise ArchiveFailure(ArchiveCode.DENIED)

    @classmethod
    def for_synthetic_profile(
        cls, archive_entry_id: str, named_use: NamedUse
    ) -> EvidenceUseAssessment:
        if type(named_use) is not NamedUse:
            raise ArchiveFailure(ArchiveCode.INVALID)
        return cls(
            validate_digest(archive_entry_id),
            named_use,
            (
                UseEligibility.ELIGIBLE
                if named_use is NamedUse.INTERNAL_AUDIT
                else UseEligibility.INELIGIBLE
            ),
            SYNTHETIC_USE_POLICY_REF,
        )


@dataclass(frozen=True, slots=True)
class ArchiveAcknowledgement:
    acknowledgement_ref: str
    archive_entry_id: str
    manifest_identity: str | None
    capture_profile_digest: str
    durability_policy_ref: str
    custody_policy_ref: str
    state: AcknowledgementState
    reason: AcknowledgementReason
    synthetic_only: bool = True
    eligible_for_real_finalization: bool = False
    eligible_for_network_use: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "acknowledgement_ref", validate_digest(self.acknowledgement_ref)
        )
        object.__setattr__(
            self, "archive_entry_id", validate_digest(self.archive_entry_id)
        )
        object.__setattr__(
            self, "capture_profile_digest", validate_digest(self.capture_profile_digest)
        )
        if self.manifest_identity is not None:
            object.__setattr__(
                self, "manifest_identity", validate_digest(self.manifest_identity)
            )
        if (
            type(self.state) is not AcknowledgementState
            or type(self.reason) is not AcknowledgementReason
            or self.synthetic_only is not True
            or self.eligible_for_real_finalization is not False
            or self.eligible_for_network_use is not False
        ):
            raise ArchiveFailure(ArchiveCode.INVALID)


def derive_archive_entry_id(
    source: SourceBinding, relation: AttemptRelation, profile_digest: str
) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "source": source.payload(),
        "relation": {
            "kind": relation.kind.value,
            "previous_archive_entry_id": relation.previous_archive_entry_id,
        },
        "capture_profile_digest": validate_digest(profile_digest),
    }
    return content_digest("carbon.evidence.archive-entry.v1", canonical_bytes(payload))
