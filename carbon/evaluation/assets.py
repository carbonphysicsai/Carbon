"""Produced reference artifacts and permanently non-authoritative fixtures."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ClassVar

from carbon.authoring.canonical import tagged_sha256
from carbon.authoring.primitives import validate_tagged_sha256
from carbon.authoring.refs import CanonicalChallengeCaseRef
from carbon.registry.model import ChallengeKey

from .enums import (
    ReferenceArtifactOrigin,
    ReferenceIdentityKind,
    ReferenceRunOutcome,
)
from .errors import ReferenceInputCode
from .execution import ReferenceRunRecord
from .model import (
    ConditioningAssessment,
    DependencyDisclosure,
    PinnedReferenceIdentity,
    ReferenceExecutionTarget,
    ReferenceProvenance,
    ReferenceScopeBinding,
    ReferenceTruthRecord,
    SupportApplicabilityAssessment,
    UncertaintyRepresentation,
    challenge,
    exact,
    exact_bool,
    exact_bytes,
    exact_enum,
    identifier,
    invalid,
    owner,
    pinned_identity,
    reference_ref,
    top_ref,
    version,
)
from .refs import (
    ReferenceArtifactRef,
    ReferencePolicyRef,
    ReferenceRunRecordRef,
)

_ARTIFACT_TOKEN = object()
_FIXTURE_TOKEN = object()


def _copy_nested_binding(value: object, expected: type, path: str):
    """Defensively reconstruct one retained subordinate value and its children."""

    checked = exact(value, expected, path)
    try:
        if expected is ReferenceExecutionTarget:
            return replace(checked, value=replace(checked.value))
        if expected is ReferenceProvenance:
            disclosures = tuple(
                replace(exact(item, DependencyDisclosure, path))
                for item in checked.dependency_disclosures
            )
            return replace(checked, dependency_disclosures=disclosures)
        return replace(checked)
    except (AttributeError, TypeError, ValueError):
        raise invalid(path, ReferenceInputCode.INVALID_VALUE) from None


@dataclass(frozen=True, slots=True, repr=False, init=False)
class ReferenceArtifact(ReferenceTruthRecord):
    """A structurally valid produced result; never an admission decision."""

    applicability_assessment: SupportApplicabilityAssessment
    artifact_content_digest: str
    artifact_descriptor_ref: PinnedReferenceIdentity
    artifact_id: str
    artifact_origin: ReferenceArtifactOrigin
    artifact_version: str
    case_ref: CanonicalChallengeCaseRef
    challenge_key: ChallengeKey
    conditioning_assessment: ConditioningAssessment
    configuration_ref: PinnedReferenceIdentity
    environment_ref: PinnedReferenceIdentity
    execution_target: ReferenceExecutionTarget
    hardware_ref: PinnedReferenceIdentity
    implementation_ref: PinnedReferenceIdentity
    method_ref: PinnedReferenceIdentity
    policy_ref: ReferencePolicyRef
    precision_ref: PinnedReferenceIdentity
    provenance_binding: ReferenceProvenance
    representation_ref: PinnedReferenceIdentity
    run_ref: ReferenceRunRecordRef
    scope_binding: ReferenceScopeBinding
    uncertainty_binding: UncertaintyRepresentation

    OBJECT_KIND: ClassVar[str] = "reference_artifact"

    def __init__(
        self,
        *,
        applicability_assessment: SupportApplicabilityAssessment,
        artifact_content_digest: str,
        artifact_descriptor_ref: PinnedReferenceIdentity,
        artifact_id: str,
        artifact_origin: ReferenceArtifactOrigin,
        artifact_version: str,
        case_ref: CanonicalChallengeCaseRef,
        challenge_key: ChallengeKey,
        conditioning_assessment: ConditioningAssessment,
        configuration_ref: PinnedReferenceIdentity,
        environment_ref: PinnedReferenceIdentity,
        execution_target: ReferenceExecutionTarget,
        hardware_ref: PinnedReferenceIdentity,
        implementation_ref: PinnedReferenceIdentity,
        method_ref: PinnedReferenceIdentity,
        policy_ref: ReferencePolicyRef,
        precision_ref: PinnedReferenceIdentity,
        provenance_binding: ReferenceProvenance,
        representation_ref: PinnedReferenceIdentity,
        run_ref: ReferenceRunRecordRef,
        scope_binding: ReferenceScopeBinding,
        uncertainty_binding: UncertaintyRepresentation,
        _token: object,
    ) -> None:
        if type(self) is not ReferenceArtifact or _token is not _ARTIFACT_TOKEN:
            raise TypeError("reference artifacts require the supported-run factory")
        object.__setattr__(self, "applicability_assessment", applicability_assessment)
        object.__setattr__(self, "artifact_content_digest", artifact_content_digest)
        object.__setattr__(self, "artifact_descriptor_ref", artifact_descriptor_ref)
        object.__setattr__(self, "artifact_id", artifact_id)
        object.__setattr__(self, "artifact_origin", artifact_origin)
        object.__setattr__(self, "artifact_version", artifact_version)
        object.__setattr__(self, "case_ref", case_ref)
        object.__setattr__(self, "challenge_key", challenge_key)
        object.__setattr__(self, "conditioning_assessment", conditioning_assessment)
        object.__setattr__(self, "configuration_ref", configuration_ref)
        object.__setattr__(self, "environment_ref", environment_ref)
        object.__setattr__(self, "execution_target", execution_target)
        object.__setattr__(self, "hardware_ref", hardware_ref)
        object.__setattr__(self, "implementation_ref", implementation_ref)
        object.__setattr__(self, "method_ref", method_ref)
        object.__setattr__(self, "policy_ref", policy_ref)
        object.__setattr__(self, "precision_ref", precision_ref)
        object.__setattr__(self, "provenance_binding", provenance_binding)
        object.__setattr__(self, "representation_ref", representation_ref)
        object.__setattr__(self, "run_ref", run_ref)
        object.__setattr__(self, "scope_binding", scope_binding)
        object.__setattr__(self, "uncertainty_binding", uncertainty_binding)
        self.__post_init__()

    def __post_init__(self) -> None:
        key = challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", key)
        object.__setattr__(
            self,
            "case_ref",
            top_ref(
                self.case_ref,
                CanonicalChallengeCaseRef,
                "/case_ref",
                challenge_key=key,
            ),
        )
        object.__setattr__(
            self,
            "policy_ref",
            reference_ref(
                self.policy_ref,
                ReferencePolicyRef,
                "/policy_ref",
                challenge_key=key,
            ),
        )
        object.__setattr__(
            self,
            "run_ref",
            reference_ref(
                self.run_ref,
                ReferenceRunRecordRef,
                "/run_ref",
                challenge_key=key,
            ),
        )
        object.__setattr__(
            self, "artifact_id", identifier(self.artifact_id, "/artifact_id")
        )
        object.__setattr__(
            self,
            "artifact_version",
            version(self.artifact_version, "/artifact_version"),
        )
        object.__setattr__(
            self,
            "artifact_content_digest",
            validate_tagged_sha256(
                self.artifact_content_digest, "artifact_content_digest"
            ),
        )
        object.__setattr__(
            self,
            "artifact_origin",
            exact_enum(
                self.artifact_origin, ReferenceArtifactOrigin, "/artifact_origin"
            ),
        )
        for name, kind in (
            ("artifact_descriptor_ref", ReferenceIdentityKind.ARTIFACT_DESCRIPTOR),
            ("configuration_ref", ReferenceIdentityKind.CONFIGURATION),
            ("environment_ref", ReferenceIdentityKind.ENVIRONMENT),
            ("hardware_ref", ReferenceIdentityKind.HARDWARE),
            ("implementation_ref", ReferenceIdentityKind.IMPLEMENTATION),
            ("method_ref", ReferenceIdentityKind.METHOD),
            ("precision_ref", ReferenceIdentityKind.PRECISION),
            ("representation_ref", ReferenceIdentityKind.REPRESENTATION),
        ):
            object.__setattr__(
                self,
                name,
                pinned_identity(
                    getattr(self, name), kind, f"/{name}", challenge_key=key
                ),
            )
        for name, expected in (
            ("applicability_assessment", SupportApplicabilityAssessment),
            ("conditioning_assessment", ConditioningAssessment),
            ("execution_target", ReferenceExecutionTarget),
            ("provenance_binding", ReferenceProvenance),
            ("scope_binding", ReferenceScopeBinding),
            ("uncertainty_binding", UncertaintyRepresentation),
        ):
            copied = _copy_nested_binding(getattr(self, name), expected, f"/{name}")
            if copied.challenge_key != key:
                raise invalid(f"/{name}", ReferenceInputCode.CROSS_CHALLENGE)
            object.__setattr__(self, name, copied)
        if (
            self.provenance_binding.environment_ref != self.environment_ref
            or self.provenance_binding.implementation_ref != self.implementation_ref
            or self.provenance_binding.method_ref != self.method_ref
        ):
            raise invalid("/provenance_binding", ReferenceInputCode.STALE_BINDING)


def _new_reference_artifact(**fields: object) -> ReferenceArtifact:
    return ReferenceArtifact(**fields, _token=_ARTIFACT_TOKEN)  # type: ignore[arg-type]


def create_reference_artifact(
    run: ReferenceRunRecord,
    *,
    artifact_id: str,
    artifact_version: str,
) -> ReferenceArtifact:
    """Create an artifact only from one exact supported, artifact-bearing run."""

    checked = exact(run, ReferenceRunRecord, "/run_ref")
    if checked.outcome is not ReferenceRunOutcome.SUPPORTED:
        raise invalid("/run_ref", ReferenceInputCode.OUTCOME_REASON_MISMATCH)
    binding = checked.artifact_binding
    if not binding.is_bound:
        raise invalid("/artifact_binding", ReferenceInputCode.INCOMPLETE_BINDING)
    content = binding.value
    return _new_reference_artifact(
        applicability_assessment=checked.applicability_assessment,
        artifact_content_digest=content.artifact_content_digest,
        artifact_descriptor_ref=content.artifact_descriptor_ref,
        artifact_id=artifact_id,
        artifact_origin=content.artifact_origin,
        artifact_version=artifact_version,
        case_ref=checked.case_ref,
        challenge_key=checked.challenge_key,
        conditioning_assessment=checked.conditioning_assessment,
        configuration_ref=checked.configuration_ref,
        environment_ref=checked.environment_ref,
        execution_target=checked.execution_target,
        hardware_ref=checked.hardware_ref,
        implementation_ref=checked.implementation_ref,
        method_ref=checked.method_ref,
        policy_ref=checked.policy_ref,
        precision_ref=checked.precision_ref,
        provenance_binding=checked.provenance_binding,
        representation_ref=checked.representation_ref,
        run_ref=checked.to_ref(),
        scope_binding=checked.scope_binding,
        uncertainty_binding=checked.uncertainty_binding,
    )


def validate_reference_artifact(
    artifact: ReferenceArtifact,
    run: ReferenceRunRecord,
) -> None:
    checked = exact(artifact, ReferenceArtifact, "/artifact_ref")
    reconstructed = create_reference_artifact(
        run,
        artifact_id=checked.artifact_id,
        artifact_version=checked.artifact_version,
    )
    if reconstructed != checked:
        raise invalid("/artifact_ref", ReferenceInputCode.STALE_BINDING)


@dataclass(frozen=True, slots=True, repr=False, init=False)
class FixtureReferenceAsset(ReferenceTruthRecord):
    """Conspicuous fixed test bytes with permanent non-LIVE eligibility."""

    artifact_ref: ReferenceArtifactRef
    case_ref: CanonicalChallengeCaseRef
    challenge_key: ChallengeKey
    fixture_asset_id: str
    fixture_asset_version: str
    fixture_provenance_ref: object
    live_eligible: bool
    payload_bytes: bytes
    policy_ref: ReferencePolicyRef
    run_ref: ReferenceRunRecordRef
    scientific_qualification_eligible: bool

    OBJECT_KIND: ClassVar[str] = "fixture_reference_asset"

    def __init__(
        self,
        *,
        artifact_ref: ReferenceArtifactRef,
        case_ref: CanonicalChallengeCaseRef,
        challenge_key: ChallengeKey,
        fixture_asset_id: str,
        fixture_asset_version: str,
        fixture_provenance_ref: object,
        live_eligible: bool,
        payload_bytes: bytes,
        policy_ref: ReferencePolicyRef,
        run_ref: ReferenceRunRecordRef,
        scientific_qualification_eligible: bool,
        _token: object,
    ) -> None:
        if type(self) is not FixtureReferenceAsset or _token is not _FIXTURE_TOKEN:
            raise TypeError("fixture assets require the fixture-only factory")
        object.__setattr__(self, "artifact_ref", artifact_ref)
        object.__setattr__(self, "case_ref", case_ref)
        object.__setattr__(self, "challenge_key", challenge_key)
        object.__setattr__(self, "fixture_asset_id", fixture_asset_id)
        object.__setattr__(self, "fixture_asset_version", fixture_asset_version)
        object.__setattr__(self, "fixture_provenance_ref", fixture_provenance_ref)
        object.__setattr__(self, "live_eligible", live_eligible)
        object.__setattr__(self, "payload_bytes", payload_bytes)
        object.__setattr__(self, "policy_ref", policy_ref)
        object.__setattr__(self, "run_ref", run_ref)
        object.__setattr__(
            self,
            "scientific_qualification_eligible",
            scientific_qualification_eligible,
        )
        self.__post_init__()

    def __post_init__(self) -> None:
        key = challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", key)
        for name, expected in (
            ("artifact_ref", ReferenceArtifactRef),
            ("policy_ref", ReferencePolicyRef),
            ("run_ref", ReferenceRunRecordRef),
        ):
            object.__setattr__(
                self,
                name,
                reference_ref(
                    getattr(self, name),
                    expected,
                    f"/{name}",
                    challenge_key=key,
                ),
            )
        object.__setattr__(
            self,
            "case_ref",
            top_ref(
                self.case_ref,
                CanonicalChallengeCaseRef,
                "/case_ref",
                challenge_key=key,
            ),
        )
        object.__setattr__(
            self,
            "fixture_asset_id",
            identifier(self.fixture_asset_id, "/fixture_asset_id"),
        )
        object.__setattr__(
            self,
            "fixture_asset_version",
            version(self.fixture_asset_version, "/fixture_asset_version"),
        )
        object.__setattr__(
            self,
            "fixture_provenance_ref",
            owner(
                self.fixture_provenance_ref,
                "fixture_registration",
                "/fixture_provenance_ref",
                challenge_key=key,
            ),
        )
        object.__setattr__(
            self, "payload_bytes", exact_bytes(self.payload_bytes, "/payload_bytes")
        )
        if exact_bool(self.live_eligible, "/live_eligible"):
            raise invalid("/live_eligible")
        if exact_bool(
            self.scientific_qualification_eligible,
            "/scientific_qualification_eligible",
        ):
            raise invalid("/scientific_qualification_eligible")


def _new_fixture_reference_asset(**fields: object) -> FixtureReferenceAsset:
    return FixtureReferenceAsset(**fields, _token=_FIXTURE_TOKEN)  # type: ignore[arg-type]


def create_fixture_reference_asset(
    artifact: ReferenceArtifact,
    run: ReferenceRunRecord,
    *,
    fixture_asset_id: str,
    fixture_asset_version: str,
    fixture_provenance_ref: object,
    payload_bytes: bytes,
) -> FixtureReferenceAsset:
    """Bind deterministic fixture bytes without acquiring truth authority."""

    checked = exact(artifact, ReferenceArtifact, "/artifact_ref")
    validate_reference_artifact(checked, run)
    if checked.artifact_origin is not ReferenceArtifactOrigin.FIXTURE_ONLY:
        raise invalid("/artifact_origin", ReferenceInputCode.ROLE_MISMATCH)
    payload = exact_bytes(payload_bytes, "/payload_bytes")
    if tagged_sha256(payload) != checked.artifact_content_digest:
        raise invalid("/artifact_content_digest", ReferenceInputCode.STALE_BINDING)
    return _new_fixture_reference_asset(
        artifact_ref=checked.to_ref(),
        case_ref=checked.case_ref,
        challenge_key=checked.challenge_key,
        fixture_asset_id=fixture_asset_id,
        fixture_asset_version=fixture_asset_version,
        fixture_provenance_ref=fixture_provenance_ref,
        live_eligible=False,
        payload_bytes=payload,
        policy_ref=checked.policy_ref,
        run_ref=checked.run_ref,
        scientific_qualification_eligible=False,
    )


__all__ = [
    "FixtureReferenceAsset",
    "ReferenceArtifact",
    "create_fixture_reference_asset",
    "create_reference_artifact",
    "validate_reference_artifact",
]
