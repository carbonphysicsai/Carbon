"""Protected prospective policy graph for the bounded B-04 runtime.

This module owns policy structure only.  It selects no solver, tolerance,
fallback, comparison threshold, qualification decision, or scientific value.
All authority-bearing records remain below the ``carbon.evaluation`` package
root.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, TypeVar

from carbon.authoring.errors import AuthoringError
from carbon.authoring.evidence import EvidenceRoleBinding
from carbon.authoring.model import EvidenceRole
from carbon.authoring.primitives import (
    MAX_CANONICAL_TUPLE_ITEMS,
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_tagged_sha256,
    validate_version_token,
)
from carbon.authoring.refs import (
    ChallengeScope,
    require_owner_ref,
)
from carbon.registry.model import ChallengeKey

from .enums import (
    ReferenceAuthorityFunction,
    ReferenceAuthorityTargetKind,
    ReferenceCompositionKind,
    ReferenceIdentityKind,
    ReferenceSourceClass,
    ReferenceWitnessTargetKind,
    ResolutionReason,
    _registered_enum_member,
)
from .errors import ReferenceInputCode, ReferenceValidationError, reject
from .model import (
    OptionalBinding,
    PinnedReferenceIdentity,
    ReferenceAuthorityTarget,
    ReferenceAuthorityTargetBinding,
    ReferenceProvenance,
    ReferenceScopeBinding,
    ReferenceTruthRecord,
    ReferenceWitnessTarget,
)
from .refs import (
    PrecomputedReferenceSourceManifestRef,
    ReferenceCompositionRef,
    ReferencePolicyEntryRef,
    ReferencePolicyRef,
    reconstruct_reference_truth_ref,
)

T = TypeVar("T")


def _invalid(
    path: str, code: ReferenceInputCode = ReferenceInputCode.INVALID_VALUE
) -> ReferenceValidationError:
    return reject(code, path)


def _exact(value: object, expected: type[T], path: str) -> T:
    if type(value) is not expected:
        raise _invalid(path, ReferenceInputCode.WRONG_TYPE)
    return value


def _exact_enum(value: object, expected: type[T], path: str) -> T:
    result = _exact(value, expected, path)
    if not _registered_enum_member(result, expected):
        raise _invalid(path)
    return result


def _identifier(value: object, path: str) -> str:
    result: str | None = None
    try:
        result = validate_canonical_id(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        pass
    if result is None:
        raise _invalid(path)
    return result


def _version(value: object, path: str) -> str:
    result: str | None = None
    try:
        result = validate_version_token(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        pass
    if result is None:
        raise _invalid(path)
    return result


def _digest(value: object, path: str) -> str:
    result: str | None = None
    try:
        result = validate_tagged_sha256(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        pass
    if result is None:
        raise _invalid(path)
    return result


def _challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    result: ChallengeKey | None = None
    try:
        result = reconstruct_challenge_key(value)
    except (AuthoringError, TypeError, ValueError):
        pass
    if result is None:
        raise _invalid(path, ReferenceInputCode.WRONG_TYPE)
    return result


def _tuple(
    value: object,
    expected: type[T],
    path: str,
    *,
    nonempty: bool = False,
    minimum: int = 0,
    unique: bool = False,
) -> tuple[T, ...]:
    if type(value) is not tuple:
        raise _invalid(path, ReferenceInputCode.WRONG_TYPE)
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS:
        raise _invalid(path)
    if (nonempty and not value) or len(value) < minimum:
        raise _invalid(path, ReferenceInputCode.INCOMPLETE_BINDING)
    if any(type(item) is not expected for item in value):
        raise _invalid(path, ReferenceInputCode.WRONG_TYPE)
    copied = tuple(value)
    if unique and len(set(copied)) != len(copied):
        raise _invalid(path, ReferenceInputCode.DUPLICATE_IDENTITY)
    return copied


def _owner(value: object, kind: str, path: str, challenge_key: ChallengeKey) -> object:
    copied: object | None = None
    try:
        copied = require_owner_ref(value, kind)
    except (AuthoringError, TypeError, ValueError):
        pass
    if copied is None:
        raise _invalid(path, ReferenceInputCode.WRONG_TYPE)
    scope = copied.scope_binding
    if type(scope) is not ChallengeScope or scope.challenge_key != challenge_key:
        raise _invalid(path, ReferenceInputCode.CROSS_CHALLENGE)
    return copied


def _reference_ref(
    value: object,
    expected: type[T],
    path: str,
    challenge_key: ChallengeKey,
) -> T:
    copied: object | None = None
    try:
        copied = reconstruct_reference_truth_ref(value)
    except (ReferenceValidationError, TypeError, ValueError):
        pass
    if copied is None:
        raise _invalid(path, ReferenceInputCode.WRONG_TYPE)
    if type(copied) is not expected:
        raise _invalid(path, ReferenceInputCode.WRONG_TYPE)
    if copied.challenge_key != challenge_key:
        raise _invalid(path, ReferenceInputCode.CROSS_CHALLENGE)
    return copied


def _identity(
    value: object,
    expected_kind: ReferenceIdentityKind,
    path: str,
    challenge_key: ChallengeKey,
) -> PinnedReferenceIdentity:
    _exact(value, PinnedReferenceIdentity, path)
    copied: PinnedReferenceIdentity | None = None
    try:
        copied = PinnedReferenceIdentity(
            value.challenge_key,
            value.content_digest,
            value.identity_id,
            value.identity_kind,
            value.identity_version,
        )
    except (ReferenceValidationError, TypeError, ValueError):
        pass
    if copied is None:
        raise _invalid(path)
    if copied.challenge_key != challenge_key:
        raise _invalid(path, ReferenceInputCode.CROSS_CHALLENGE)
    if copied.identity_kind is not expected_kind:
        raise _invalid(path, ReferenceInputCode.WRONG_TYPE)
    return copied


def _scope(
    value: object, path: str, challenge_key: ChallengeKey
) -> ReferenceScopeBinding:
    _exact(value, ReferenceScopeBinding, path)
    copied: ReferenceScopeBinding | None = None
    try:
        copied = ReferenceScopeBinding(
            value.candidate_output_contract_ref,
            value.claim_scope_ref,
            value.evidence_campaign_ref,
            value.evidence_population_refs,
            value.physical_system_ref,
            value.proposal_population_ref,
            value.reference_fidelity_allocation_ref,
            value.sampling_plan_ref,
            value.target_population_ref,
            value.truth_target_ref,
        )
    except (AuthoringError, ReferenceValidationError, TypeError, ValueError):
        pass
    if copied is None:
        raise _invalid(path)
    if copied.challenge_key != challenge_key:
        raise _invalid(path, ReferenceInputCode.CROSS_CHALLENGE)
    return copied


def _provenance(
    value: object, path: str, challenge_key: ChallengeKey
) -> ReferenceProvenance:
    _exact(value, ReferenceProvenance, path)
    copied: ReferenceProvenance | None = None
    try:
        copied = ReferenceProvenance(
            value.dependency_disclosures,
            value.environment_ref,
            value.evidence_campaign_ref,
            value.generated_or_copied_code_refs,
            value.implementation_ref,
            value.method_ref,
            value.provenance_refs,
            value.reviewer_authority_refs,
            value.rights_profile_ref,
            value.source_ref,
        )
    except (AuthoringError, ReferenceValidationError, TypeError, ValueError):
        pass
    if copied is None:
        raise _invalid(path)
    if copied.challenge_key != challenge_key:
        raise _invalid(path, ReferenceInputCode.CROSS_CHALLENGE)
    return copied


def _evidence_role(
    value: object, path: str, challenge_key: ChallengeKey
) -> EvidenceRoleBinding:
    _exact(value, EvidenceRoleBinding, path)
    hybrid_ref = value.hybrid_role_ref
    if value.role is EvidenceRole.REGISTERED_HYBRID:
        hybrid_ref = _owner(
            hybrid_ref, "hybrid_evidence_role", "/hybrid_role_ref", challenge_key
        )
    copied: EvidenceRoleBinding | None = None
    try:
        copied = EvidenceRoleBinding(value.role, hybrid_ref)
    except (AuthoringError, TypeError, ValueError):
        pass
    if copied is None:
        raise _invalid(path)
    return copied


def _optional_b04_ref(
    value: object,
    expected: type[T],
    path: str,
    challenge_key: ChallengeKey,
) -> OptionalBinding:
    binding = _exact(value, OptionalBinding, path)
    if binding.is_present:
        return OptionalBinding.present(
            _reference_ref(binding.value, expected, path, challenge_key)
        )
    return OptionalBinding.absent()


def _optional_owner(
    value: object, kind: str, path: str, challenge_key: ChallengeKey
) -> OptionalBinding:
    binding = _exact(value, OptionalBinding, path)
    if binding.is_present:
        return OptionalBinding.present(_owner(binding.value, kind, path, challenge_key))
    return OptionalBinding.absent()


def _authority_target(
    value: object, path: str, challenge_key: ChallengeKey
) -> ReferenceAuthorityTarget:
    target = _exact(value, ReferenceAuthorityTarget, path)
    if target.kind is ReferenceAuthorityTargetKind.SINGLE_PRIMARY_ENTRY:
        return ReferenceAuthorityTarget.single_primary_entry(
            _reference_ref(target.value, ReferencePolicyEntryRef, path, challenge_key)
        )
    if target.kind is ReferenceAuthorityTargetKind.QUALIFIED_PRIMARY_COMPOSITION:
        return ReferenceAuthorityTarget.qualified_primary_composition(
            _reference_ref(target.value, ReferenceCompositionRef, path, challenge_key)
        )
    raise _invalid(path, ReferenceInputCode.ROLE_MISMATCH)


def _authority_target_binding(
    value: object, path: str, challenge_key: ChallengeKey
) -> ReferenceAuthorityTargetBinding:
    binding = _exact(value, ReferenceAuthorityTargetBinding, path)
    if binding.is_bound:
        return ReferenceAuthorityTargetBinding.bound(
            _authority_target(binding.value, path, challenge_key)
        )
    if binding.value not in {
        ResolutionReason.POLICY_PRIMARY_MISSING,
        ResolutionReason.POLICY_ENTRY_INCOMPLETE,
    }:
        raise _invalid(path, ReferenceInputCode.OUTCOME_REASON_MISMATCH)
    return ReferenceAuthorityTargetBinding.absent(binding.value)


def _witness_target(
    value: object, path: str, challenge_key: ChallengeKey
) -> ReferenceWitnessTarget:
    target = _exact(value, ReferenceWitnessTarget, path)
    if target.kind is ReferenceWitnessTargetKind.SINGLE_WITNESS_ENTRY:
        return ReferenceWitnessTarget.single_witness_entry(
            _reference_ref(target.value, ReferencePolicyEntryRef, path, challenge_key)
        )
    if target.kind is ReferenceWitnessTargetKind.QUALIFIED_WITNESS_COMPOSITION:
        return ReferenceWitnessTarget.qualified_witness_composition(
            _reference_ref(target.value, ReferenceCompositionRef, path, challenge_key)
        )
    raise _invalid(path, ReferenceInputCode.ROLE_MISMATCH)


@dataclass(frozen=True, slots=True, repr=False)
class PrecomputedReferenceSourceManifest(ReferenceTruthRecord):
    """Immutable provenance pin for a pre-existing reference corpus."""

    artifact_schema_ref: PinnedReferenceIdentity
    challenge_key: ChallengeKey
    manifest_id: str
    manifest_version: str
    provenance_binding: ReferenceProvenance
    representation_ref: PinnedReferenceIdentity
    rights_profile_ref: object
    scope_binding: ReferenceScopeBinding
    source_class: ReferenceSourceClass
    source_corpus_digest: str
    source_ref: PinnedReferenceIdentity
    supersedes: OptionalBinding

    OBJECT_KIND: ClassVar[str] = "precomputed_reference_source_manifest"

    def __post_init__(self) -> None:
        if type(self) is not PrecomputedReferenceSourceManifest:
            raise _invalid("/record", ReferenceInputCode.WRONG_TYPE)
        challenge = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(
            self,
            "artifact_schema_ref",
            _identity(
                self.artifact_schema_ref,
                ReferenceIdentityKind.ARTIFACT_SCHEMA,
                "/artifact_schema_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self, "manifest_id", _identifier(self.manifest_id, "/manifest_id")
        )
        object.__setattr__(
            self,
            "manifest_version",
            _version(self.manifest_version, "/manifest_version"),
        )
        object.__setattr__(
            self,
            "provenance_binding",
            _provenance(self.provenance_binding, "/provenance_binding", challenge),
        )
        object.__setattr__(
            self,
            "representation_ref",
            _identity(
                self.representation_ref,
                ReferenceIdentityKind.REPRESENTATION,
                "/representation_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "rights_profile_ref",
            _owner(
                self.rights_profile_ref,
                "rights_profile",
                "/rights_profile_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "scope_binding",
            _scope(self.scope_binding, "/scope_binding", challenge),
        )
        _exact_enum(self.source_class, ReferenceSourceClass, "/source_class")
        object.__setattr__(
            self,
            "source_corpus_digest",
            _digest(self.source_corpus_digest, "/source_corpus_digest"),
        )
        object.__setattr__(
            self,
            "source_ref",
            _identity(
                self.source_ref,
                ReferenceIdentityKind.SOURCE,
                "/source_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "supersedes",
            _optional_b04_ref(
                self.supersedes,
                PrecomputedReferenceSourceManifestRef,
                "/supersedes",
                challenge,
            ),
        )
        if (
            self.provenance_binding.source_ref != self.source_ref
            or self.provenance_binding.rights_profile_ref != self.rights_profile_ref
            or self.provenance_binding.evidence_campaign_ref
            != self.scope_binding.evidence_campaign_ref
        ):
            raise _invalid("/provenance_binding", ReferenceInputCode.STALE_BINDING)


@dataclass(frozen=True, slots=True, repr=False)
class ReferencePolicyEntry(ReferenceTruthRecord):
    """One prospective source with separate evidence, authority, and class axes."""

    applicability_policy_ref: object
    artifact_schema_ref: PinnedReferenceIdentity
    authority_function: ReferenceAuthorityFunction
    challenge_key: ChallengeKey
    conditioning_policy_ref: object
    correlation_policy_ref: object
    dependency_constraints_ref: PinnedReferenceIdentity
    disclosure_policy_ref: object
    entry_id: str
    entry_version: str
    environment_constraints_ref: PinnedReferenceIdentity
    evidence_role_binding: EvidenceRoleBinding
    expected_representation_ref: PinnedReferenceIdentity
    implementation_constraints_ref: PinnedReferenceIdentity
    method_constraints_ref: PinnedReferenceIdentity
    policy_id: str
    policy_version: str
    precomputed_source_manifest_ref: OptionalBinding
    provenance_policy_ref: object
    qualification_policy_ref: object
    resource_policy_ref: object
    rights_profile_ref: object
    scope_binding: ReferenceScopeBinding
    source_class: ReferenceSourceClass
    source_ref: PinnedReferenceIdentity
    support_boundary_ref: object
    uncertainty_policy_ref: object

    OBJECT_KIND: ClassVar[str] = "reference_policy_entry"

    def __post_init__(self) -> None:
        if type(self) is not ReferencePolicyEntry:
            raise _invalid("/record", ReferenceInputCode.WRONG_TYPE)
        challenge = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(
            self,
            "applicability_policy_ref",
            _owner(
                self.applicability_policy_ref,
                "applicability",
                "/applicability_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "conditioning_policy_ref",
            _owner(
                self.conditioning_policy_ref,
                "sensitivity_analysis",
                "/conditioning_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "correlation_policy_ref",
            _owner(
                self.correlation_policy_ref,
                "replication_dependence_policy",
                "/correlation_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "disclosure_policy_ref",
            _owner(
                self.disclosure_policy_ref,
                "disclosure_policy",
                "/disclosure_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "provenance_policy_ref",
            _owner(
                self.provenance_policy_ref,
                "provenance",
                "/provenance_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "qualification_policy_ref",
            _owner(
                self.qualification_policy_ref,
                "reference_qualification_policy",
                "/qualification_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "resource_policy_ref",
            _owner(
                self.resource_policy_ref,
                "reference_resource_limit",
                "/resource_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "rights_profile_ref",
            _owner(
                self.rights_profile_ref,
                "rights_profile",
                "/rights_profile_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "support_boundary_ref",
            _owner(
                self.support_boundary_ref,
                "support_boundary",
                "/support_boundary_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "uncertainty_policy_ref",
            _owner(
                self.uncertainty_policy_ref,
                "statistics_objective",
                "/uncertainty_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "artifact_schema_ref",
            _identity(
                self.artifact_schema_ref,
                ReferenceIdentityKind.ARTIFACT_SCHEMA,
                "/artifact_schema_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "dependency_constraints_ref",
            _identity(
                self.dependency_constraints_ref,
                ReferenceIdentityKind.DEPENDENCY_SET,
                "/dependency_constraints_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "environment_constraints_ref",
            _identity(
                self.environment_constraints_ref,
                ReferenceIdentityKind.ENVIRONMENT,
                "/environment_constraints_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "expected_representation_ref",
            _identity(
                self.expected_representation_ref,
                ReferenceIdentityKind.REPRESENTATION,
                "/expected_representation_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "implementation_constraints_ref",
            _identity(
                self.implementation_constraints_ref,
                ReferenceIdentityKind.IMPLEMENTATION,
                "/implementation_constraints_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "method_constraints_ref",
            _identity(
                self.method_constraints_ref,
                ReferenceIdentityKind.METHOD,
                "/method_constraints_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "source_ref",
            _identity(
                self.source_ref,
                ReferenceIdentityKind.SOURCE,
                "/source_ref",
                challenge,
            ),
        )
        object.__setattr__(self, "entry_id", _identifier(self.entry_id, "/entry_id"))
        object.__setattr__(
            self, "entry_version", _version(self.entry_version, "/entry_version")
        )
        object.__setattr__(self, "policy_id", _identifier(self.policy_id, "/policy_id"))
        object.__setattr__(
            self, "policy_version", _version(self.policy_version, "/policy_version")
        )
        object.__setattr__(
            self,
            "evidence_role_binding",
            _evidence_role(
                self.evidence_role_binding, "/evidence_role_binding", challenge
            ),
        )
        _exact_enum(
            self.authority_function, ReferenceAuthorityFunction, "/authority_function"
        )
        _exact_enum(self.source_class, ReferenceSourceClass, "/source_class")
        object.__setattr__(
            self,
            "scope_binding",
            _scope(self.scope_binding, "/scope_binding", challenge),
        )
        object.__setattr__(
            self,
            "precomputed_source_manifest_ref",
            _optional_b04_ref(
                self.precomputed_source_manifest_ref,
                PrecomputedReferenceSourceManifestRef,
                "/precomputed_source_manifest_ref",
                challenge,
            ),
        )
        if (
            self.evidence_role_binding.role
            is EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION
            and self.authority_function
            is not ReferenceAuthorityFunction.VERIFICATION_ANCHOR
        ):
            raise _invalid("/authority_function", ReferenceInputCode.ROLE_MISMATCH)


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceComposition(ReferenceTruthRecord):
    """Prospective ordered hybrid of distinct registered component entries."""

    applicability_policy_ref: object
    artifact_schema_ref: PinnedReferenceIdentity
    authority_function: ReferenceAuthorityFunction
    challenge_key: ChallengeKey
    combination_environment_ref: PinnedReferenceIdentity
    combination_implementation_ref: PinnedReferenceIdentity
    combination_method_ref: PinnedReferenceIdentity
    composition_id: str
    composition_kind: ReferenceCompositionKind
    composition_version: str
    conditioning_policy_ref: object
    correlation_policy_ref: object
    disclosure_policy_ref: object
    expected_representation_ref: PinnedReferenceIdentity
    member_entry_refs: tuple[ReferencePolicyEntryRef, ...]
    policy_id: str
    policy_version: str
    provenance_policy_ref: object
    qualification_policy_ref: object
    resource_policy_ref: object
    rights_profile_ref: object
    scope_binding: ReferenceScopeBinding
    uncertainty_policy_ref: object

    OBJECT_KIND: ClassVar[str] = "reference_composition"

    def __post_init__(self) -> None:
        if type(self) is not ReferenceComposition:
            raise _invalid("/record", ReferenceInputCode.WRONG_TYPE)
        challenge = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(
            self,
            "applicability_policy_ref",
            _owner(
                self.applicability_policy_ref,
                "applicability",
                "/applicability_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "conditioning_policy_ref",
            _owner(
                self.conditioning_policy_ref,
                "sensitivity_analysis",
                "/conditioning_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "correlation_policy_ref",
            _owner(
                self.correlation_policy_ref,
                "replication_dependence_policy",
                "/correlation_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "disclosure_policy_ref",
            _owner(
                self.disclosure_policy_ref,
                "disclosure_policy",
                "/disclosure_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "provenance_policy_ref",
            _owner(
                self.provenance_policy_ref,
                "provenance",
                "/provenance_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "qualification_policy_ref",
            _owner(
                self.qualification_policy_ref,
                "reference_qualification_policy",
                "/qualification_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "resource_policy_ref",
            _owner(
                self.resource_policy_ref,
                "reference_resource_limit",
                "/resource_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "rights_profile_ref",
            _owner(
                self.rights_profile_ref,
                "rights_profile",
                "/rights_profile_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "uncertainty_policy_ref",
            _owner(
                self.uncertainty_policy_ref,
                "statistics_objective",
                "/uncertainty_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "artifact_schema_ref",
            _identity(
                self.artifact_schema_ref,
                ReferenceIdentityKind.ARTIFACT_SCHEMA,
                "/artifact_schema_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "combination_environment_ref",
            _identity(
                self.combination_environment_ref,
                ReferenceIdentityKind.ENVIRONMENT,
                "/combination_environment_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "combination_implementation_ref",
            _identity(
                self.combination_implementation_ref,
                ReferenceIdentityKind.IMPLEMENTATION,
                "/combination_implementation_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "combination_method_ref",
            _identity(
                self.combination_method_ref,
                ReferenceIdentityKind.COMBINATION_METHOD,
                "/combination_method_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "expected_representation_ref",
            _identity(
                self.expected_representation_ref,
                ReferenceIdentityKind.REPRESENTATION,
                "/expected_representation_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self, "composition_id", _identifier(self.composition_id, "/composition_id")
        )
        object.__setattr__(
            self,
            "composition_version",
            _version(self.composition_version, "/composition_version"),
        )
        object.__setattr__(self, "policy_id", _identifier(self.policy_id, "/policy_id"))
        object.__setattr__(
            self, "policy_version", _version(self.policy_version, "/policy_version")
        )
        _exact_enum(
            self.authority_function, ReferenceAuthorityFunction, "/authority_function"
        )
        _exact_enum(
            self.composition_kind, ReferenceCompositionKind, "/composition_kind"
        )
        if (
            self.composition_kind
            is not ReferenceCompositionKind.REGISTERED_HYBRID_POLICY
        ):
            raise _invalid("/composition_kind")
        if self.authority_function not in {
            ReferenceAuthorityFunction.PRIMARY,
            ReferenceAuthorityFunction.CORROBORATING_WITNESS,
        }:
            raise _invalid("/authority_function", ReferenceInputCode.ROLE_MISMATCH)
        members = _tuple(
            self.member_entry_refs,
            ReferencePolicyEntryRef,
            "/member_entry_refs",
            minimum=2,
            unique=True,
        )
        object.__setattr__(
            self,
            "member_entry_refs",
            tuple(
                _reference_ref(
                    item, ReferencePolicyEntryRef, "/member_entry_refs", challenge
                )
                for item in members
            ),
        )
        object.__setattr__(
            self,
            "scope_binding",
            _scope(self.scope_binding, "/scope_binding", challenge),
        )


@dataclass(frozen=True, slots=True, repr=False)
class ReferencePolicy(ReferenceTruthRecord):
    """Complete prospective policy inventory; execution binds later records."""

    answer_key_authority_target: ReferenceAuthorityTargetBinding
    applicability_policy_ref: object
    challenge_key: ChallengeKey
    comparison_policy_ref: object
    composition_refs: tuple[ReferenceCompositionRef, ...]
    disclosure_policy_ref: object
    entry_refs: tuple[ReferencePolicyEntryRef, ...]
    fallback_policy_ref: object
    history_binding_ref: object
    policy_id: str
    policy_version: str
    provenance_policy_ref: object
    qualification_policy_ref: object
    registered_witness_targets: tuple[ReferenceWitnessTarget, ...]
    resource_policy_ref: object
    revocation_binding_ref: OptionalBinding
    rights_profile_ref: object
    scope_binding: ReferenceScopeBinding
    supersedes: OptionalBinding
    uncertainty_policy_ref: object

    OBJECT_KIND: ClassVar[str] = "reference_policy"

    def __post_init__(self) -> None:
        if type(self) is not ReferencePolicy:
            raise _invalid("/record", ReferenceInputCode.WRONG_TYPE)
        challenge = _challenge(self.challenge_key)
        object.__setattr__(self, "challenge_key", challenge)
        object.__setattr__(
            self,
            "answer_key_authority_target",
            _authority_target_binding(
                self.answer_key_authority_target,
                "/answer_key_authority_target",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "applicability_policy_ref",
            _owner(
                self.applicability_policy_ref,
                "applicability",
                "/applicability_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "comparison_policy_ref",
            _owner(
                self.comparison_policy_ref,
                "semantic_equivalence",
                "/comparison_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "disclosure_policy_ref",
            _owner(
                self.disclosure_policy_ref,
                "disclosure_policy",
                "/disclosure_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "fallback_policy_ref",
            _owner(
                self.fallback_policy_ref,
                "restriction",
                "/fallback_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "history_binding_ref",
            _owner(
                self.history_binding_ref,
                "authoring_registration",
                "/history_binding_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "provenance_policy_ref",
            _owner(
                self.provenance_policy_ref,
                "provenance",
                "/provenance_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "qualification_policy_ref",
            _owner(
                self.qualification_policy_ref,
                "reference_qualification_policy",
                "/qualification_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "resource_policy_ref",
            _owner(
                self.resource_policy_ref,
                "reference_resource_limit",
                "/resource_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "rights_profile_ref",
            _owner(
                self.rights_profile_ref,
                "rights_profile",
                "/rights_profile_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "uncertainty_policy_ref",
            _owner(
                self.uncertainty_policy_ref,
                "statistics_objective",
                "/uncertainty_policy_ref",
                challenge,
            ),
        )
        object.__setattr__(self, "policy_id", _identifier(self.policy_id, "/policy_id"))
        object.__setattr__(
            self, "policy_version", _version(self.policy_version, "/policy_version")
        )
        entry_refs = _tuple(
            self.entry_refs,
            ReferencePolicyEntryRef,
            "/entry_refs",
            unique=True,
        )
        object.__setattr__(
            self,
            "entry_refs",
            tuple(
                _reference_ref(item, ReferencePolicyEntryRef, "/entry_refs", challenge)
                for item in entry_refs
            ),
        )
        composition_refs = _tuple(
            self.composition_refs,
            ReferenceCompositionRef,
            "/composition_refs",
            unique=True,
        )
        object.__setattr__(
            self,
            "composition_refs",
            tuple(
                _reference_ref(
                    item, ReferenceCompositionRef, "/composition_refs", challenge
                )
                for item in composition_refs
            ),
        )
        targets = _tuple(
            self.registered_witness_targets,
            ReferenceWitnessTarget,
            "/registered_witness_targets",
            unique=True,
        )
        object.__setattr__(
            self,
            "registered_witness_targets",
            tuple(
                _witness_target(target, "/registered_witness_targets", challenge)
                for target in targets
            ),
        )
        object.__setattr__(
            self,
            "revocation_binding_ref",
            _optional_owner(
                self.revocation_binding_ref,
                "authoring_revocation",
                "/revocation_binding_ref",
                challenge,
            ),
        )
        object.__setattr__(
            self,
            "scope_binding",
            _scope(self.scope_binding, "/scope_binding", challenge),
        )
        object.__setattr__(
            self,
            "supersedes",
            _optional_b04_ref(
                self.supersedes,
                ReferencePolicyRef,
                "/supersedes",
                challenge,
            ),
        )


def primary_target_for_entry(entry: ReferencePolicyEntry) -> ReferenceAuthorityTarget:
    """Build the only nominal primary target authorized by a PRIMARY entry."""

    checked = _exact(entry, ReferencePolicyEntry, "/entry_ref")
    if checked.authority_function is not ReferenceAuthorityFunction.PRIMARY:
        raise _invalid("/authority_function", ReferenceInputCode.ROLE_MISMATCH)
    return ReferenceAuthorityTarget.single_primary_entry(checked.to_ref())


def primary_target_for_composition(
    composition: ReferenceComposition,
) -> ReferenceAuthorityTarget:
    """Build a primary target only from an exact PRIMARY composition."""

    checked = _exact(composition, ReferenceComposition, "/composition_refs")
    if checked.authority_function is not ReferenceAuthorityFunction.PRIMARY:
        raise _invalid("/authority_function", ReferenceInputCode.ROLE_MISMATCH)
    return ReferenceAuthorityTarget.qualified_primary_composition(checked.to_ref())


def witness_target_for_entry(entry: ReferencePolicyEntry) -> ReferenceWitnessTarget:
    """Build a witness target only from a CORROBORATING_WITNESS entry."""

    checked = _exact(entry, ReferencePolicyEntry, "/entry_ref")
    if (
        checked.authority_function
        is not ReferenceAuthorityFunction.CORROBORATING_WITNESS
    ):
        raise _invalid("/authority_function", ReferenceInputCode.ROLE_MISMATCH)
    return ReferenceWitnessTarget.single_witness_entry(checked.to_ref())


def witness_target_for_composition(
    composition: ReferenceComposition,
) -> ReferenceWitnessTarget:
    """Build a witness target only from a CORROBORATING_WITNESS composition."""

    checked = _exact(composition, ReferenceComposition, "/composition_refs")
    if (
        checked.authority_function
        is not ReferenceAuthorityFunction.CORROBORATING_WITNESS
    ):
        raise _invalid("/authority_function", ReferenceInputCode.ROLE_MISMATCH)
    return ReferenceWitnessTarget.qualified_witness_composition(checked.to_ref())


def _index_entries(
    entries: object,
) -> tuple[
    tuple[ReferencePolicyEntry, ...],
    dict[ReferencePolicyEntryRef, ReferencePolicyEntry],
]:
    checked = _tuple(entries, ReferencePolicyEntry, "/entry_refs", unique=True)
    index: dict[ReferencePolicyEntryRef, ReferencePolicyEntry] = {}
    for entry in checked:
        ref = entry.to_ref()
        if ref in index:
            raise _invalid("/entry_refs", ReferenceInputCode.DUPLICATE_IDENTITY)
        index[ref] = entry
    return checked, index


def _index_compositions(
    compositions: object,
) -> tuple[
    tuple[ReferenceComposition, ...],
    dict[ReferenceCompositionRef, ReferenceComposition],
]:
    checked = _tuple(
        compositions, ReferenceComposition, "/composition_refs", unique=True
    )
    index: dict[ReferenceCompositionRef, ReferenceComposition] = {}
    for composition in checked:
        ref = composition.to_ref()
        if ref in index:
            raise _invalid("/composition_refs", ReferenceInputCode.DUPLICATE_IDENTITY)
        index[ref] = composition
    return checked, index


def _authority_target_ref(target: ReferenceAuthorityTarget) -> object:
    checked = _exact(target, ReferenceAuthorityTarget, "/answer_key_authority_target")
    if checked.kind is ReferenceAuthorityTargetKind.SINGLE_PRIMARY_ENTRY:
        return checked.entry_ref
    if checked.kind is ReferenceAuthorityTargetKind.QUALIFIED_PRIMARY_COMPOSITION:
        return checked.composition_ref
    raise _invalid("/answer_key_authority_target", ReferenceInputCode.ROLE_MISMATCH)


def _witness_target_ref(target: ReferenceWitnessTarget) -> object:
    checked = _exact(target, ReferenceWitnessTarget, "/witness_target")
    if checked.kind is ReferenceWitnessTargetKind.SINGLE_WITNESS_ENTRY:
        return checked.entry_ref
    if checked.kind is ReferenceWitnessTargetKind.QUALIFIED_WITNESS_COMPOSITION:
        return checked.composition_ref
    raise _invalid("/witness_target", ReferenceInputCode.ROLE_MISMATCH)


def _expand_composition(
    composition: ReferenceComposition,
    entry_index: dict[ReferencePolicyEntryRef, ReferencePolicyEntry],
    expected_authority: ReferenceAuthorityFunction,
    path: str,
) -> tuple[ReferencePolicyEntryRef, ...]:
    if composition.authority_function is not expected_authority:
        raise _invalid("/authority_function", ReferenceInputCode.ROLE_MISMATCH)
    for member_ref in composition.member_entry_refs:
        member = entry_index.get(member_ref)
        if member is None:
            raise _invalid(path, ReferenceInputCode.STALE_BINDING)
        if (
            member.challenge_key != composition.challenge_key
            or member.policy_id != composition.policy_id
            or member.policy_version != composition.policy_version
            or member.scope_binding != composition.scope_binding
        ):
            raise _invalid("/member_entry_refs", ReferenceInputCode.STALE_BINDING)
        if (
            member.authority_function
            is not ReferenceAuthorityFunction.REGISTERED_COMPONENT
        ):
            raise _invalid("/member_entry_refs", ReferenceInputCode.ROLE_MISMATCH)
        if (
            member.expected_representation_ref
            != composition.expected_representation_ref
            or member.artifact_schema_ref != composition.artifact_schema_ref
        ):
            raise _invalid("/member_entry_refs", ReferenceInputCode.STALE_BINDING)
    return composition.member_entry_refs


def expand_authority_target(
    target: ReferenceAuthorityTarget,
    *,
    entries: tuple[ReferencePolicyEntry, ...],
    compositions: tuple[ReferenceComposition, ...],
) -> tuple[ReferencePolicyEntryRef, ...]:
    """Expand one primary target to its exact ordered entry inventory."""

    _, entry_index = _index_entries(entries)
    _, composition_index = _index_compositions(compositions)
    target_ref = _authority_target_ref(target)
    if type(target_ref) is ReferencePolicyEntryRef:
        entry = entry_index.get(target_ref)
        if entry is None:
            raise _invalid(
                "/answer_key_authority_target", ReferenceInputCode.STALE_BINDING
            )
        if entry.authority_function is not ReferenceAuthorityFunction.PRIMARY:
            raise _invalid("/authority_function", ReferenceInputCode.ROLE_MISMATCH)
        return (target_ref,)
    composition = composition_index.get(target_ref)
    if composition is None:
        raise _invalid("/answer_key_authority_target", ReferenceInputCode.STALE_BINDING)
    return _expand_composition(
        composition,
        entry_index,
        ReferenceAuthorityFunction.PRIMARY,
        "/answer_key_authority_target",
    )


def expand_witness_target(
    target: ReferenceWitnessTarget,
    *,
    entries: tuple[ReferencePolicyEntry, ...],
    compositions: tuple[ReferenceComposition, ...],
) -> tuple[ReferencePolicyEntryRef, ...]:
    """Expand one witness target to its exact ordered entry inventory."""

    _, entry_index = _index_entries(entries)
    _, composition_index = _index_compositions(compositions)
    target_ref = _witness_target_ref(target)
    if type(target_ref) is ReferencePolicyEntryRef:
        entry = entry_index.get(target_ref)
        if entry is None:
            raise _invalid("/witness_target", ReferenceInputCode.STALE_BINDING)
        if (
            entry.authority_function
            is not ReferenceAuthorityFunction.CORROBORATING_WITNESS
        ):
            raise _invalid("/authority_function", ReferenceInputCode.ROLE_MISMATCH)
        return (target_ref,)
    composition = composition_index.get(target_ref)
    if composition is None:
        raise _invalid("/witness_target", ReferenceInputCode.STALE_BINDING)
    return _expand_composition(
        composition,
        entry_index,
        ReferenceAuthorityFunction.CORROBORATING_WITNESS,
        "/witness_target",
    )


def _validate_entry_containment(
    policy: ReferencePolicy, entry: ReferencePolicyEntry
) -> None:
    if entry.challenge_key != policy.challenge_key:
        raise _invalid("/entry_refs", ReferenceInputCode.CROSS_CHALLENGE)
    if (
        entry.policy_id != policy.policy_id
        or entry.policy_version != policy.policy_version
        or entry.scope_binding != policy.scope_binding
    ):
        raise _invalid("/entry_refs", ReferenceInputCode.STALE_BINDING)


def _validate_composition_containment(
    policy: ReferencePolicy,
    composition: ReferenceComposition,
    entry_index: dict[ReferencePolicyEntryRef, ReferencePolicyEntry],
) -> None:
    if composition.challenge_key != policy.challenge_key:
        raise _invalid("/composition_refs", ReferenceInputCode.CROSS_CHALLENGE)
    if (
        composition.policy_id != policy.policy_id
        or composition.policy_version != policy.policy_version
        or composition.scope_binding != policy.scope_binding
    ):
        raise _invalid("/composition_refs", ReferenceInputCode.STALE_BINDING)
    _expand_composition(
        composition,
        entry_index,
        composition.authority_function,
        "/member_entry_refs",
    )


def _validate_manifest_binding(
    entry: ReferencePolicyEntry,
    manifest: PrecomputedReferenceSourceManifest,
) -> None:
    if (
        manifest.challenge_key != entry.challenge_key
        or manifest.scope_binding != entry.scope_binding
        or manifest.source_ref != entry.source_ref
        or manifest.source_class is not entry.source_class
        or manifest.artifact_schema_ref != entry.artifact_schema_ref
        or manifest.representation_ref != entry.expected_representation_ref
        or manifest.rights_profile_ref != entry.rights_profile_ref
    ):
        raise _invalid(
            "/precomputed_source_manifest_ref", ReferenceInputCode.STALE_BINDING
        )


def validate_reference_policy_graph(
    policy: ReferencePolicy,
    *,
    entries: tuple[ReferencePolicyEntry, ...],
    compositions: tuple[ReferenceComposition, ...],
    precomputed_manifests: tuple[PrecomputedReferenceSourceManifest, ...] = (),
) -> None:
    """Validate the exact closed policy graph without importing external objects.

    The tuple order is authoritative and must reproduce each ordered policy
    inventory exactly.  A successful validation confers structural consistency
    only; it does not qualify any source or make the policy LIVE.
    """

    checked_policy = _exact(policy, ReferencePolicy, "/policy_ref")
    entry_records, entry_index = _index_entries(entries)
    composition_records, _ = _index_compositions(compositions)
    if tuple(item.to_ref() for item in entry_records) != checked_policy.entry_refs:
        raise _invalid("/entry_refs", ReferenceInputCode.STALE_BINDING)
    if (
        tuple(item.to_ref() for item in composition_records)
        != checked_policy.composition_refs
    ):
        raise _invalid("/composition_refs", ReferenceInputCode.STALE_BINDING)
    for entry in entry_records:
        _validate_entry_containment(checked_policy, entry)
    for composition in composition_records:
        _validate_composition_containment(checked_policy, composition, entry_index)

    manifests = _tuple(
        precomputed_manifests,
        PrecomputedReferenceSourceManifest,
        "/precomputed_source_manifest_ref",
        unique=True,
    )
    manifest_index: dict[
        PrecomputedReferenceSourceManifestRef, PrecomputedReferenceSourceManifest
    ] = {}
    for manifest in manifests:
        ref = manifest.to_ref()
        if ref in manifest_index:
            raise _invalid(
                "/precomputed_source_manifest_ref",
                ReferenceInputCode.DUPLICATE_IDENTITY,
            )
        manifest_index[ref] = manifest
    expected_manifest_refs: list[PrecomputedReferenceSourceManifestRef] = []
    for entry in entry_records:
        binding = entry.precomputed_source_manifest_ref
        if not binding.is_present:
            continue
        manifest_ref = binding.value
        if manifest_ref not in expected_manifest_refs:
            expected_manifest_refs.append(manifest_ref)
        manifest = manifest_index.get(manifest_ref)
        if manifest is None:
            raise _invalid(
                "/precomputed_source_manifest_ref", ReferenceInputCode.STALE_BINDING
            )
        _validate_manifest_binding(entry, manifest)
    if tuple(manifest_index) != tuple(expected_manifest_refs):
        raise _invalid(
            "/precomputed_source_manifest_ref", ReferenceInputCode.STALE_BINDING
        )

    primary_expansion: tuple[ReferencePolicyEntryRef, ...] = ()
    primary_representation: PinnedReferenceIdentity | None = None
    if checked_policy.answer_key_authority_target.is_bound:
        primary_expansion = expand_authority_target(
            checked_policy.answer_key_authority_target.value,
            entries=entry_records,
            compositions=composition_records,
        )
        if not primary_expansion or len(set(primary_expansion)) != len(
            primary_expansion
        ):
            raise _invalid(
                "/answer_key_authority_target",
                ReferenceInputCode.DUPLICATE_IDENTITY,
            )
        primary_representation = entry_index[
            primary_expansion[0]
        ].expected_representation_ref

    target_keys: set[tuple[object, object]] = set()
    primary_members = set(primary_expansion)
    for target in checked_policy.registered_witness_targets:
        key = (target.kind, _witness_target_ref(target))
        if key in target_keys:
            raise _invalid(
                "/registered_witness_targets",
                ReferenceInputCode.DUPLICATE_IDENTITY,
            )
        target_keys.add(key)
        expanded = expand_witness_target(
            target,
            entries=entry_records,
            compositions=composition_records,
        )
        if not expanded or len(set(expanded)) != len(expanded):
            raise _invalid(
                "/registered_witness_targets",
                ReferenceInputCode.DUPLICATE_IDENTITY,
            )
        if primary_members.intersection(expanded):
            raise _invalid(
                "/registered_witness_targets", ReferenceInputCode.ROLE_MISMATCH
            )
        if (
            primary_representation is not None
            and entry_index[expanded[0]].expected_representation_ref
            != primary_representation
        ):
            raise _invalid("/representation_ref", ReferenceInputCode.STALE_BINDING)


__all__ = [
    "PrecomputedReferenceSourceManifest",
    "ReferenceComposition",
    "ReferencePolicy",
    "ReferencePolicyEntry",
    "expand_authority_target",
    "expand_witness_target",
    "primary_target_for_composition",
    "primary_target_for_entry",
    "validate_reference_policy_graph",
    "witness_target_for_composition",
    "witness_target_for_entry",
]
