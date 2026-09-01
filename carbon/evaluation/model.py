"""Protected immutable value vocabulary for B-04 reference/truth records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Generic, TypeVar

from carbon.authoring.canonical import (
    CanonicalText,
    encode_value,
    owner_ref_to_canonical,
)
from carbon.authoring.errors import AuthoringError
from carbon.authoring.evidence import EvidenceRoleBinding
from carbon.authoring.model import EvidenceRole
from carbon.authoring.primitives import (
    MAX_CANONICAL_TUPLE_ITEMS,
    reconstruct_challenge_key,
    validate_canonical_id,
    validate_exact_bool,
    validate_exact_bytes,
    validate_tagged_sha256,
    validate_utf8_text,
    validate_version_token,
)
from carbon.authoring.refs import (
    CandidateOutputContractRef,
    CanonicalChallengeCaseRef,
    ChallengeScope,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    SamplingPlanRef,
    reconstruct_top_level_ref,
    require_owner_ref,
)
from carbon.registry.model import ChallengeKey

from .enums import (
    AdmissionArtifactAbsenceReason,
    BoundOrAbsentTag,
    ConditioningStatus,
    DependencyCategory,
    DependencyRelation,
    OptionalBindingTag,
    QualificationAbsenceReason,
    ReferenceArtifactOrigin,
    ReferenceAuthorityFunction,
    ReferenceAuthorityTargetKind,
    ReferenceExecutionTargetKind,
    ReferenceFailureReason,
    ReferenceGrantBindingKind,
    ReferenceIdentityKind,
    ReferenceRequestBindingKind,
    ReferenceWitnessTargetKind,
    ResolutionReason,
    SupportApplicabilityStatus,
    UncertaintyComponentKind,
    UncertaintyStatus,
    _registered_enum_member,
)
from .errors import ReferenceInputCode, ReferenceValidationError
from .refs import (
    PrimaryReferenceRequestRef,
    PrimaryRunGrantRef,
    ReferenceArtifactRef,
    ReferenceComparisonRecordRef,
    ReferenceCompositionRef,
    ReferencePolicyEntryRef,
    ReferenceRunRecordRef,
    ReferenceTruthRef,
    WitnessReferenceRequestRef,
    WitnessRunGrantRef,
    require_reference_truth_ref,
)

T = TypeVar("T")


def invalid(
    path: str, code: ReferenceInputCode = ReferenceInputCode.INVALID_VALUE
) -> ReferenceValidationError:
    return ReferenceValidationError(code, path=path)


def exact(value: object, expected: type[T], path: str) -> T:
    if type(value) is not expected:
        raise invalid(path, ReferenceInputCode.WRONG_TYPE)
    return value


def exact_enum(value: object, expected: type[T], path: str) -> T:
    result = exact(value, expected, path)
    if not _registered_enum_member(result, expected):
        raise invalid(path)
    return result


def exact_tuple(
    value: object,
    expected: type[T] | tuple[type[object], ...] | None,
    path: str,
    *,
    nonempty: bool = False,
    unique: bool = False,
) -> tuple[T, ...]:
    if type(value) is not tuple:
        raise invalid(path, ReferenceInputCode.WRONG_TYPE)
    if len(value) > MAX_CANONICAL_TUPLE_ITEMS or (nonempty and not value):
        raise invalid(path)
    allowed = expected if type(expected) is tuple else (expected,)
    if expected is not None and any(type(item) not in allowed for item in value):
        raise invalid(path, ReferenceInputCode.WRONG_TYPE)
    copied = tuple(value)
    if unique:
        try:
            distinct = len(set(copied))
        except Exception:  # noqa: BLE001 - normalize hostile exact-type hashes.
            raise invalid(path) from None
        if distinct != len(copied):
            raise invalid(path, ReferenceInputCode.DUPLICATE_IDENTITY)
    return copied


def challenge(value: object, path: str = "/challenge_key") -> ChallengeKey:
    try:
        return reconstruct_challenge_key(value)
    except (AuthoringError, TypeError, ValueError):
        raise invalid(path, ReferenceInputCode.WRONG_TYPE) from None


def identifier(value: object, path: str) -> str:
    try:
        return validate_canonical_id(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        raise invalid(path) from None


def version(value: object, path: str) -> str:
    try:
        return validate_version_token(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        raise invalid(path) from None


def digest(value: object, path: str) -> str:
    try:
        return validate_tagged_sha256(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        raise invalid(path) from None


def text(value: object, path: str) -> str:
    try:
        return validate_utf8_text(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        raise invalid(path) from None


def exact_bytes(value: object, path: str) -> bytes:
    try:
        return validate_exact_bytes(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        raise invalid(path) from None


def exact_bool(value: object, path: str) -> bool:
    try:
        return validate_exact_bool(value, path.rsplit("/", 1)[-1])
    except (AuthoringError, TypeError, ValueError):
        raise invalid(path, ReferenceInputCode.WRONG_TYPE) from None


def _require_same_challenge(
    observed: ChallengeKey, expected: ChallengeKey, path: str
) -> None:
    if observed != expected:
        raise invalid(path, ReferenceInputCode.CROSS_CHALLENGE)


def owner(
    value: object,
    kind: str,
    path: str,
    *,
    challenge_key: ChallengeKey | None = None,
) -> object:
    try:
        result = require_owner_ref(value, kind)
    except (AuthoringError, TypeError, ValueError):
        raise invalid(path, ReferenceInputCode.WRONG_TYPE) from None
    if challenge_key is not None:
        scope = object.__getattribute__(result, "scope_binding")
        if type(scope) is not ChallengeScope:
            raise invalid(path, ReferenceInputCode.CROSS_CHALLENGE)
        _require_same_challenge(scope.challenge_key, challenge_key, path)
    return result


def owner_sequence(
    value: object,
    kind: str,
    path: str,
    *,
    challenge_key: ChallengeKey,
    nonempty: bool = False,
) -> tuple[object, ...]:
    copied = exact_tuple(value, None, path, nonempty=nonempty)
    result = tuple(
        owner(item, kind, path, challenge_key=challenge_key) for item in copied
    )
    if len(set(result)) != len(result):
        raise invalid(path, ReferenceInputCode.DUPLICATE_IDENTITY)
    return result


def owner_set(
    value: object,
    kind: str,
    path: str,
    *,
    challenge_key: ChallengeKey,
    nonempty: bool = False,
) -> tuple[object, ...]:
    result = owner_sequence(
        value,
        kind,
        path,
        challenge_key=challenge_key,
        nonempty=nonempty,
    )
    return tuple(
        sorted(
            result,
            key=lambda item: encode_value(owner_ref_to_canonical(item)),
        )
    )


def top_ref(
    value: object,
    expected_type: type[T],
    path: str,
    *,
    challenge_key: ChallengeKey | None = None,
) -> T:
    if type(value) is not expected_type:
        raise invalid(path, ReferenceInputCode.WRONG_TYPE)
    try:
        result = reconstruct_top_level_ref(value)
    except (AuthoringError, TypeError, ValueError):
        raise invalid(path, ReferenceInputCode.WRONG_TYPE) from None
    if challenge_key is not None:
        _require_same_challenge(result.challenge_key, challenge_key, path)
    return result  # type: ignore[return-value]


def top_ref_sequence(
    value: object,
    expected_type: type[T],
    path: str,
    *,
    challenge_key: ChallengeKey,
    nonempty: bool = False,
) -> tuple[T, ...]:
    copied = exact_tuple(value, None, path, nonempty=nonempty)
    result = tuple(
        top_ref(
            item,
            expected_type,
            path,
            challenge_key=challenge_key,
        )
        for item in copied
    )
    if len(set(result)) != len(result):
        raise invalid(path, ReferenceInputCode.DUPLICATE_IDENTITY)
    return result


def reference_ref(
    value: object,
    expected_type: type[T],
    path: str,
    *,
    challenge_key: ChallengeKey | None = None,
) -> T:
    return require_reference_truth_ref(
        value,
        expected_type,
        challenge_key=challenge_key,
        path=path,
    )  # type: ignore[return-value]


def reference_ref_sequence(
    value: object,
    expected_type: type[T],
    path: str,
    *,
    challenge_key: ChallengeKey,
    nonempty: bool = False,
) -> tuple[T, ...]:
    copied = exact_tuple(value, None, path, nonempty=nonempty)
    result = tuple(
        reference_ref(
            item,
            expected_type,
            path,
            challenge_key=challenge_key,
        )
        for item in copied
    )
    if len(set(result)) != len(result):
        raise invalid(path, ReferenceInputCode.DUPLICATE_IDENTITY)
    return result


def pinned_identity(
    value: object,
    expected_kind: ReferenceIdentityKind,
    path: str,
    *,
    challenge_key: ChallengeKey,
) -> PinnedReferenceIdentity:
    result = exact(value, PinnedReferenceIdentity, path)
    try:
        _require_same_challenge(result.challenge_key, challenge_key, path)
        if result.identity_kind is not expected_kind:
            raise invalid(path, ReferenceInputCode.ROLE_MISMATCH)
        return PinnedReferenceIdentity(
            result.challenge_key,
            result.content_digest,
            result.identity_id,
            result.identity_kind,
            result.identity_version,
        )
    except ReferenceValidationError:
        raise
    except Exception:  # noqa: BLE001 - normalize a partial exact-type carrier.
        raise invalid(path, ReferenceInputCode.WRONG_TYPE) from None


def evidence_role_binding(
    value: object,
    path: str,
    *,
    challenge_key: ChallengeKey,
    authority_function: ReferenceAuthorityFunction | None = None,
) -> EvidenceRoleBinding:
    binding = exact(value, EvidenceRoleBinding, path)
    try:
        role = exact_enum(binding.role, EvidenceRole, path)
        reconstructed = EvidenceRoleBinding(role, binding.hybrid_role_ref)
    except ReferenceValidationError:
        raise
    except (AuthoringError, TypeError, ValueError):
        raise invalid(path, ReferenceInputCode.WRONG_TYPE) from None
    if reconstructed.role is EvidenceRole.REGISTERED_HYBRID:
        owner(
            reconstructed.hybrid_role_ref,
            "hybrid_evidence_role",
            f"{path}/hybrid_role_ref",
            challenge_key=challenge_key,
        )
    if (
        reconstructed.role is EvidenceRole.MANUFACTURED_SOLUTION_VERIFICATION
        and authority_function is not None
        and authority_function is not ReferenceAuthorityFunction.VERIFICATION_ANCHOR
    ):
        raise invalid(path, ReferenceInputCode.ROLE_MISMATCH)
    return reconstructed


class ProtectedReferenceValue:
    """Mixin preventing accidental diagnostic and pickle disclosure."""

    __slots__ = ()

    def __repr__(self) -> str:
        return f"{type(self).__name__}(<protected>)"

    __str__ = __repr__

    def __reduce__(self):
        raise TypeError("protected reference values cannot be pickled")

    def __reduce_ex__(self, protocol: int):
        del protocol
        raise TypeError("protected reference values cannot be pickled")


class ReferenceTruthRecord(ProtectedReferenceValue):
    """Mixin for one exact standalone B-04 record family."""

    __slots__ = ()
    OBJECT_KIND: ClassVar[str] = ""

    @property
    def object_kind(self) -> str:
        return self.OBJECT_KIND

    @property
    def schema_version(self) -> str:
        from .refs import REFERENCE_TRUTH_SCHEMA_VERSION

        return REFERENCE_TRUTH_SCHEMA_VERSION

    @property
    def canonicalization_profile(self) -> str:
        from .refs import REFERENCE_TRUTH_CANONICALIZATION_PROFILE

        return REFERENCE_TRUTH_CANONICALIZATION_PROFILE

    def canonical_bytes(self) -> bytes:
        from .canonical import canonical_bytes

        return canonical_bytes(self)

    def to_ref(self) -> ReferenceTruthRef:
        from .canonical import canonical_ref

        return canonical_ref(self)


@dataclass(frozen=True, slots=True, repr=False)
class PinnedReferenceIdentity(ProtectedReferenceValue):
    challenge_key: ChallengeKey
    content_digest: str
    identity_id: str
    identity_kind: ReferenceIdentityKind
    identity_version: str

    def __post_init__(self) -> None:
        if type(self) is not PinnedReferenceIdentity:
            raise invalid("/identity_kind", ReferenceInputCode.WRONG_TYPE)
        object.__setattr__(self, "challenge_key", challenge(self.challenge_key))
        object.__setattr__(
            self, "content_digest", digest(self.content_digest, "/content_digest")
        )
        object.__setattr__(
            self, "identity_id", identifier(self.identity_id, "/identity_id")
        )
        object.__setattr__(
            self,
            "identity_kind",
            exact_enum(self.identity_kind, ReferenceIdentityKind, "/identity_kind"),
        )
        object.__setattr__(
            self,
            "identity_version",
            version(self.identity_version, "/identity_version"),
        )


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceScopeBinding(ProtectedReferenceValue):
    candidate_output_contract_ref: CandidateOutputContractRef
    claim_scope_ref: object
    evidence_campaign_ref: object
    evidence_population_refs: tuple[InstanceDistributionContractRef, ...]
    physical_system_ref: PhysicalSystemSpecRef
    proposal_population_ref: InstanceDistributionContractRef
    reference_fidelity_allocation_ref: object
    sampling_plan_ref: SamplingPlanRef
    target_population_ref: InstanceDistributionContractRef
    truth_target_ref: object

    def __post_init__(self) -> None:
        if type(self) is not ReferenceScopeBinding:
            raise invalid("/scope_binding", ReferenceInputCode.WRONG_TYPE)
        candidate = top_ref(
            self.candidate_output_contract_ref,
            CandidateOutputContractRef,
            "/candidate_output_contract_ref",
        )
        scope_challenge = candidate.challenge_key
        object.__setattr__(self, "candidate_output_contract_ref", candidate)
        object.__setattr__(
            self,
            "claim_scope_ref",
            owner(
                self.claim_scope_ref,
                "claim_scope",
                "/claim_scope_ref",
                challenge_key=scope_challenge,
            ),
        )
        object.__setattr__(
            self,
            "evidence_campaign_ref",
            owner(
                self.evidence_campaign_ref,
                "evidence_campaign",
                "/evidence_campaign_ref",
                challenge_key=scope_challenge,
            ),
        )
        object.__setattr__(
            self,
            "evidence_population_refs",
            top_ref_sequence(
                self.evidence_population_refs,
                InstanceDistributionContractRef,
                "/evidence_population_refs",
                challenge_key=scope_challenge,
                nonempty=True,
            ),
        )
        object.__setattr__(
            self,
            "physical_system_ref",
            top_ref(
                self.physical_system_ref,
                PhysicalSystemSpecRef,
                "/physical_system_ref",
                challenge_key=scope_challenge,
            ),
        )
        proposal = top_ref(
            self.proposal_population_ref,
            InstanceDistributionContractRef,
            "/proposal_population_ref",
            challenge_key=scope_challenge,
        )
        if proposal.expected_population_role != "OFFICIAL_PROPOSAL_Q":
            raise invalid("/proposal_population_ref", ReferenceInputCode.ROLE_MISMATCH)
        object.__setattr__(self, "proposal_population_ref", proposal)
        object.__setattr__(
            self,
            "reference_fidelity_allocation_ref",
            owner(
                self.reference_fidelity_allocation_ref,
                "reference_fidelity_allocation",
                "/reference_fidelity_allocation_ref",
                challenge_key=scope_challenge,
            ),
        )
        object.__setattr__(
            self,
            "sampling_plan_ref",
            top_ref(
                self.sampling_plan_ref,
                SamplingPlanRef,
                "/sampling_plan_ref",
                challenge_key=scope_challenge,
            ),
        )
        target = top_ref(
            self.target_population_ref,
            InstanceDistributionContractRef,
            "/target_population_ref",
            challenge_key=scope_challenge,
        )
        if target.expected_population_role != "TARGET_WORKLOAD_P":
            raise invalid("/target_population_ref", ReferenceInputCode.ROLE_MISMATCH)
        object.__setattr__(self, "target_population_ref", target)
        object.__setattr__(
            self,
            "truth_target_ref",
            owner(
                self.truth_target_ref,
                "intended_estimand_or_reporting",
                "/truth_target_ref",
                challenge_key=scope_challenge,
            ),
        )

    @property
    def challenge_key(self) -> ChallengeKey:
        return self.candidate_output_contract_ref.challenge_key


@dataclass(frozen=True, slots=True, repr=False)
class OptionalBinding(ProtectedReferenceValue, Generic[T]):
    tag: OptionalBindingTag
    value: T | None

    def __post_init__(self) -> None:
        if type(self) is not OptionalBinding:
            raise invalid("/value", ReferenceInputCode.WRONG_TYPE)
        exact_enum(self.tag, OptionalBindingTag, "/value")
        if (self.tag is OptionalBindingTag.PRESENT) == (self.value is None):
            raise invalid("/value", ReferenceInputCode.INCOMPLETE_BINDING)

    @classmethod
    def present(cls, value: T) -> OptionalBinding[T]:
        return cls(OptionalBindingTag.PRESENT, value)

    @classmethod
    def absent(cls) -> OptionalBinding[T]:
        return cls(OptionalBindingTag.ABSENT, None)

    @property
    def is_present(self) -> bool:
        return self.tag is OptionalBindingTag.PRESENT


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceAuthorityTarget(ProtectedReferenceValue):
    kind: ReferenceAuthorityTargetKind
    value: ReferencePolicyEntryRef | ReferenceCompositionRef

    def __post_init__(self) -> None:
        if type(self) is not ReferenceAuthorityTarget:
            raise invalid("/answer_key_authority_target", ReferenceInputCode.WRONG_TYPE)
        exact_enum(
            self.kind,
            ReferenceAuthorityTargetKind,
            "/answer_key_authority_target",
        )
        expected = (
            ReferencePolicyEntryRef
            if self.kind is ReferenceAuthorityTargetKind.SINGLE_PRIMARY_ENTRY
            else ReferenceCompositionRef
        )
        object.__setattr__(
            self,
            "value",
            reference_ref(self.value, expected, "/answer_key_authority_target"),
        )

    @classmethod
    def single_primary_entry(
        cls, entry_ref: ReferencePolicyEntryRef
    ) -> ReferenceAuthorityTarget:
        return cls(ReferenceAuthorityTargetKind.SINGLE_PRIMARY_ENTRY, entry_ref)

    @classmethod
    def qualified_primary_composition(
        cls, composition_ref: ReferenceCompositionRef
    ) -> ReferenceAuthorityTarget:
        return cls(
            ReferenceAuthorityTargetKind.QUALIFIED_PRIMARY_COMPOSITION,
            composition_ref,
        )

    @property
    def challenge_key(self) -> ChallengeKey:
        return self.value.challenge_key

    @property
    def entry_ref(self) -> ReferencePolicyEntryRef | None:
        return (
            self.value
            if self.kind is ReferenceAuthorityTargetKind.SINGLE_PRIMARY_ENTRY
            else None
        )

    @property
    def composition_ref(self) -> ReferenceCompositionRef | None:
        return (
            self.value
            if self.kind is ReferenceAuthorityTargetKind.QUALIFIED_PRIMARY_COMPOSITION
            else None
        )

    @property
    def expanded_entry_refs(self) -> tuple[ReferencePolicyEntryRef, ...]:
        return (self.value,) if type(self.value) is ReferencePolicyEntryRef else ()


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceWitnessTarget(ProtectedReferenceValue):
    kind: ReferenceWitnessTargetKind
    value: ReferencePolicyEntryRef | ReferenceCompositionRef

    def __post_init__(self) -> None:
        if type(self) is not ReferenceWitnessTarget:
            raise invalid("/witness_target", ReferenceInputCode.WRONG_TYPE)
        exact_enum(self.kind, ReferenceWitnessTargetKind, "/witness_target")
        expected = (
            ReferencePolicyEntryRef
            if self.kind is ReferenceWitnessTargetKind.SINGLE_WITNESS_ENTRY
            else ReferenceCompositionRef
        )
        object.__setattr__(
            self,
            "value",
            reference_ref(self.value, expected, "/witness_target"),
        )

    @classmethod
    def single_witness_entry(
        cls, entry_ref: ReferencePolicyEntryRef
    ) -> ReferenceWitnessTarget:
        return cls(ReferenceWitnessTargetKind.SINGLE_WITNESS_ENTRY, entry_ref)

    @classmethod
    def qualified_witness_composition(
        cls, composition_ref: ReferenceCompositionRef
    ) -> ReferenceWitnessTarget:
        return cls(
            ReferenceWitnessTargetKind.QUALIFIED_WITNESS_COMPOSITION,
            composition_ref,
        )

    @property
    def challenge_key(self) -> ChallengeKey:
        return self.value.challenge_key

    @property
    def entry_ref(self) -> ReferencePolicyEntryRef | None:
        return (
            self.value
            if self.kind is ReferenceWitnessTargetKind.SINGLE_WITNESS_ENTRY
            else None
        )

    @property
    def composition_ref(self) -> ReferenceCompositionRef | None:
        return (
            self.value
            if self.kind is ReferenceWitnessTargetKind.QUALIFIED_WITNESS_COMPOSITION
            else None
        )

    @property
    def expanded_entry_refs(self) -> tuple[ReferencePolicyEntryRef, ...]:
        return (self.value,) if type(self.value) is ReferencePolicyEntryRef else ()


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceExecutionTarget(ProtectedReferenceValue):
    kind: ReferenceExecutionTargetKind
    value: ReferenceAuthorityTarget | ReferenceWitnessTarget

    def __post_init__(self) -> None:
        if type(self) is not ReferenceExecutionTarget:
            raise invalid("/execution_target", ReferenceInputCode.WRONG_TYPE)
        exact_enum(self.kind, ReferenceExecutionTargetKind, "/execution_target")
        expected = (
            ReferenceAuthorityTarget
            if self.kind is ReferenceExecutionTargetKind.PRIMARY
            else ReferenceWitnessTarget
        )
        target = exact(self.value, expected, "/execution_target")
        object.__setattr__(self, "value", expected(target.kind, target.value))

    @classmethod
    def primary(cls, target: ReferenceAuthorityTarget) -> ReferenceExecutionTarget:
        return cls(ReferenceExecutionTargetKind.PRIMARY, target)

    @classmethod
    def witness(cls, target: ReferenceWitnessTarget) -> ReferenceExecutionTarget:
        return cls(ReferenceExecutionTargetKind.WITNESS, target)

    @property
    def challenge_key(self) -> ChallengeKey:
        return self.value.challenge_key


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceRequestBinding(ProtectedReferenceValue):
    kind: ReferenceRequestBindingKind
    value: PrimaryReferenceRequestRef | WitnessReferenceRequestRef

    def __post_init__(self) -> None:
        if type(self) is not ReferenceRequestBinding:
            raise invalid("/request_binding", ReferenceInputCode.WRONG_TYPE)
        exact_enum(self.kind, ReferenceRequestBindingKind, "/request_binding")
        expected = (
            PrimaryReferenceRequestRef
            if self.kind is ReferenceRequestBindingKind.PRIMARY
            else WitnessReferenceRequestRef
        )
        object.__setattr__(
            self,
            "value",
            reference_ref(self.value, expected, "/request_binding"),
        )

    @classmethod
    def primary(cls, ref: PrimaryReferenceRequestRef) -> ReferenceRequestBinding:
        return cls(ReferenceRequestBindingKind.PRIMARY, ref)

    @classmethod
    def witness(cls, ref: WitnessReferenceRequestRef) -> ReferenceRequestBinding:
        return cls(ReferenceRequestBindingKind.WITNESS, ref)

    @property
    def challenge_key(self) -> ChallengeKey:
        return self.value.challenge_key


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceGrantBinding(ProtectedReferenceValue):
    kind: ReferenceGrantBindingKind
    value: PrimaryRunGrantRef | WitnessRunGrantRef | ResolutionReason

    def __post_init__(self) -> None:
        if type(self) is not ReferenceGrantBinding:
            raise invalid("/grant_binding", ReferenceInputCode.WRONG_TYPE)
        exact_enum(self.kind, ReferenceGrantBindingKind, "/grant_binding")
        if self.kind is ReferenceGrantBindingKind.PRIMARY:
            reconstructed: object = reference_ref(
                self.value, PrimaryRunGrantRef, "/grant_binding"
            )
        elif self.kind is ReferenceGrantBindingKind.WITNESS:
            reconstructed = reference_ref(
                self.value, WitnessRunGrantRef, "/grant_binding"
            )
        else:
            reconstructed = exact_enum(
                self.value, ResolutionReason, "/grant_binding/reason"
            )
        object.__setattr__(self, "value", reconstructed)

    @classmethod
    def primary(cls, ref: PrimaryRunGrantRef) -> ReferenceGrantBinding:
        return cls(ReferenceGrantBindingKind.PRIMARY, ref)

    @classmethod
    def witness(cls, ref: WitnessRunGrantRef) -> ReferenceGrantBinding:
        return cls(ReferenceGrantBindingKind.WITNESS, ref)

    @classmethod
    def absent(cls, reason: ResolutionReason) -> ReferenceGrantBinding:
        return cls(ReferenceGrantBindingKind.ABSENT, reason)

    @property
    def is_bound(self) -> bool:
        return self.kind is not ReferenceGrantBindingKind.ABSENT

    @property
    def challenge_key(self) -> ChallengeKey | None:
        if not self.is_bound:
            return None
        return self.value.challenge_key  # type: ignore[union-attr]


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceAuthorityTargetBinding(ProtectedReferenceValue):
    tag: BoundOrAbsentTag
    value: ReferenceAuthorityTarget | ResolutionReason

    def __post_init__(self) -> None:
        if type(self) is not ReferenceAuthorityTargetBinding:
            raise invalid("/answer_key_authority_target", ReferenceInputCode.WRONG_TYPE)
        exact_enum(self.tag, BoundOrAbsentTag, "/answer_key_authority_target")
        if self.tag is BoundOrAbsentTag.BOUND:
            target = exact(
                self.value,
                ReferenceAuthorityTarget,
                "/answer_key_authority_target",
            )
            reconstructed: object = ReferenceAuthorityTarget(
                target.kind,
                target.value,
            )
        else:
            reconstructed = exact(
                self.value,
                ResolutionReason,
                "/answer_key_authority_target",
            )
        object.__setattr__(self, "value", reconstructed)

    @classmethod
    def bound(cls, target: ReferenceAuthorityTarget) -> ReferenceAuthorityTargetBinding:
        return cls(BoundOrAbsentTag.BOUND, target)

    @classmethod
    def absent(cls, reason: ResolutionReason) -> ReferenceAuthorityTargetBinding:
        return cls(BoundOrAbsentTag.ABSENT, reason)

    @property
    def is_bound(self) -> bool:
        return self.tag is BoundOrAbsentTag.BOUND

    @property
    def challenge_key(self) -> ChallengeKey | None:
        if not self.is_bound:
            return None
        return self.value.challenge_key  # type: ignore[union-attr]


@dataclass(frozen=True, slots=True, repr=False)
class ArtifactContentBinding(ProtectedReferenceValue):
    artifact_content_digest: str
    artifact_descriptor_ref: PinnedReferenceIdentity
    artifact_origin: ReferenceArtifactOrigin

    def __post_init__(self) -> None:
        if type(self) is not ArtifactContentBinding:
            raise invalid("/artifact_binding", ReferenceInputCode.WRONG_TYPE)
        descriptor = exact(
            self.artifact_descriptor_ref,
            PinnedReferenceIdentity,
            "/artifact_descriptor_ref",
        )
        object.__setattr__(
            self,
            "artifact_content_digest",
            digest(self.artifact_content_digest, "/artifact_content_digest"),
        )
        object.__setattr__(
            self,
            "artifact_descriptor_ref",
            pinned_identity(
                descriptor,
                ReferenceIdentityKind.ARTIFACT_DESCRIPTOR,
                "/artifact_descriptor_ref",
                challenge_key=descriptor.challenge_key,
            ),
        )
        object.__setattr__(
            self,
            "artifact_origin",
            exact_enum(
                self.artifact_origin,
                ReferenceArtifactOrigin,
                "/artifact_origin",
            ),
        )

    @property
    def challenge_key(self) -> ChallengeKey:
        return self.artifact_descriptor_ref.challenge_key


@dataclass(frozen=True, slots=True, repr=False)
class RunArtifactBinding(ProtectedReferenceValue):
    tag: BoundOrAbsentTag
    value: ArtifactContentBinding | ReferenceFailureReason

    def __post_init__(self) -> None:
        if type(self) is not RunArtifactBinding:
            raise invalid("/artifact_binding", ReferenceInputCode.WRONG_TYPE)
        exact_enum(self.tag, BoundOrAbsentTag, "/artifact_binding")
        if self.tag is BoundOrAbsentTag.BOUND:
            content = exact(
                self.value,
                ArtifactContentBinding,
                "/artifact_binding",
            )
            reconstructed: object = ArtifactContentBinding(
                content.artifact_content_digest,
                content.artifact_descriptor_ref,
                content.artifact_origin,
            )
        else:
            reconstructed = exact(
                self.value,
                ReferenceFailureReason,
                "/artifact_binding",
            )
        object.__setattr__(self, "value", reconstructed)

    @classmethod
    def bound(cls, value: ArtifactContentBinding) -> RunArtifactBinding:
        return cls(BoundOrAbsentTag.BOUND, value)

    @classmethod
    def absent(cls, reason: ReferenceFailureReason) -> RunArtifactBinding:
        return cls(BoundOrAbsentTag.ABSENT, reason)

    @property
    def is_bound(self) -> bool:
        return self.tag is BoundOrAbsentTag.BOUND

    @property
    def challenge_key(self) -> ChallengeKey | None:
        if not self.is_bound:
            return None
        return self.value.challenge_key  # type: ignore[union-attr]


@dataclass(frozen=True, slots=True, repr=False)
class AdmissionArtifactBinding(ProtectedReferenceValue):
    tag: BoundOrAbsentTag
    value: ReferenceArtifactRef | AdmissionArtifactAbsenceReason

    def __post_init__(self) -> None:
        if type(self) is not AdmissionArtifactBinding:
            raise invalid("/artifact_binding", ReferenceInputCode.WRONG_TYPE)
        exact_enum(self.tag, BoundOrAbsentTag, "/artifact_binding")
        if self.tag is BoundOrAbsentTag.BOUND:
            reconstructed: object = reference_ref(
                self.value, ReferenceArtifactRef, "/artifact_ref"
            )
        else:
            reconstructed = exact_enum(
                self.value, AdmissionArtifactAbsenceReason, "/artifact_binding/reason"
            )
        object.__setattr__(self, "value", reconstructed)

    @classmethod
    def bound(cls, ref: ReferenceArtifactRef) -> AdmissionArtifactBinding:
        return cls(BoundOrAbsentTag.BOUND, ref)

    @classmethod
    def absent(cls, reason: AdmissionArtifactAbsenceReason) -> AdmissionArtifactBinding:
        return cls(BoundOrAbsentTag.ABSENT, reason)

    @property
    def is_bound(self) -> bool:
        return self.tag is BoundOrAbsentTag.BOUND

    @property
    def challenge_key(self) -> ChallengeKey | None:
        if not self.is_bound:
            return None
        return self.value.challenge_key  # type: ignore[union-attr]


@dataclass(frozen=True, slots=True, repr=False)
class QualificationBinding(ProtectedReferenceValue):
    tag: BoundOrAbsentTag
    value: object | QualificationAbsenceReason

    def __post_init__(self) -> None:
        if type(self) is not QualificationBinding:
            raise invalid("/qualification_binding", ReferenceInputCode.WRONG_TYPE)
        exact_enum(self.tag, BoundOrAbsentTag, "/qualification_binding")
        if self.tag is BoundOrAbsentTag.BOUND:
            try:
                reconstructed: object = require_owner_ref(
                    self.value, "qualification_evidence_bundle"
                )
            except (AuthoringError, TypeError, ValueError):
                raise invalid(
                    "/qualification_binding", ReferenceInputCode.WRONG_TYPE
                ) from None
        else:
            reconstructed = exact_enum(
                self.value, QualificationAbsenceReason, "/qualification_binding/reason"
            )
        object.__setattr__(self, "value", reconstructed)

    @classmethod
    def bound(cls, ref: object) -> QualificationBinding:
        return cls(BoundOrAbsentTag.BOUND, ref)

    @classmethod
    def absent(cls, reason: QualificationAbsenceReason) -> QualificationBinding:
        return cls(BoundOrAbsentTag.ABSENT, reason)

    @property
    def is_bound(self) -> bool:
        return self.tag is BoundOrAbsentTag.BOUND

    @property
    def challenge_key(self) -> ChallengeKey | None:
        if not self.is_bound:
            return None
        scope = object.__getattribute__(self.value, "scope_binding")
        return scope.challenge_key if type(scope) is ChallengeScope else None


@dataclass(frozen=True, slots=True, repr=False)
class SupportApplicabilityAssessment(ProtectedReferenceValue):
    applicability_evidence_refs: tuple[object, ...]
    limitations: tuple[object, ...]
    method_ref: PinnedReferenceIdentity
    status: SupportApplicabilityStatus
    support_boundary_ref: object

    def __post_init__(self) -> None:
        if type(self) is not SupportApplicabilityAssessment:
            raise invalid("/applicability_assessment", ReferenceInputCode.WRONG_TYPE)
        method = exact(
            self.method_ref,
            PinnedReferenceIdentity,
            "/applicability_assessment/method_ref",
        )
        assessment_challenge = method.challenge_key
        object.__setattr__(
            self,
            "applicability_evidence_refs",
            owner_set(
                self.applicability_evidence_refs,
                "applicability_evidence",
                "/applicability_evidence_refs",
                challenge_key=assessment_challenge,
            ),
        )
        object.__setattr__(
            self,
            "limitations",
            owner_set(
                self.limitations,
                "restriction",
                "/limitations",
                challenge_key=assessment_challenge,
            ),
        )
        object.__setattr__(
            self,
            "method_ref",
            pinned_identity(
                method,
                ReferenceIdentityKind.APPLICABILITY_METHOD,
                "/applicability_assessment/method_ref",
                challenge_key=assessment_challenge,
            ),
        )
        object.__setattr__(
            self,
            "status",
            exact_enum(
                self.status,
                SupportApplicabilityStatus,
                "/applicability_assessment/status",
            ),
        )
        object.__setattr__(
            self,
            "support_boundary_ref",
            owner(
                self.support_boundary_ref,
                "support_boundary",
                "/support_boundary_ref",
                challenge_key=assessment_challenge,
            ),
        )

    @property
    def challenge_key(self) -> ChallengeKey:
        return self.method_ref.challenge_key


@dataclass(frozen=True, slots=True, repr=False)
class ConditioningAssessment(ProtectedReferenceValue):
    evidence_refs: tuple[object, ...]
    limitations: tuple[object, ...]
    method_ref: PinnedReferenceIdentity
    status: ConditioningStatus

    def __post_init__(self) -> None:
        if type(self) is not ConditioningAssessment:
            raise invalid("/conditioning_assessment", ReferenceInputCode.WRONG_TYPE)
        method = exact(
            self.method_ref,
            PinnedReferenceIdentity,
            "/conditioning_assessment/method_ref",
        )
        assessment_challenge = method.challenge_key
        object.__setattr__(
            self,
            "evidence_refs",
            owner_set(
                self.evidence_refs,
                "sensitivity_analysis",
                "/evidence_refs",
                challenge_key=assessment_challenge,
            ),
        )
        object.__setattr__(
            self,
            "limitations",
            owner_set(
                self.limitations,
                "restriction",
                "/limitations",
                challenge_key=assessment_challenge,
            ),
        )
        object.__setattr__(
            self,
            "method_ref",
            pinned_identity(
                method,
                ReferenceIdentityKind.CONDITIONING_METHOD,
                "/conditioning_assessment/method_ref",
                challenge_key=assessment_challenge,
            ),
        )
        object.__setattr__(
            self,
            "status",
            exact_enum(
                self.status,
                ConditioningStatus,
                "/conditioning_assessment/status",
            ),
        )

    @property
    def challenge_key(self) -> ChallengeKey:
        return self.method_ref.challenge_key


@dataclass(frozen=True, slots=True, repr=False)
class UncertaintyRepresentation(ProtectedReferenceValue):
    component_kinds: tuple[UncertaintyComponentKind, ...]
    coverage_ref: object
    dependence_policy_ref: object
    estimand_ref: object
    evidence_refs: tuple[object, ...]
    limitations: tuple[object, ...]
    method_ref: PinnedReferenceIdentity
    representation_ref: PinnedReferenceIdentity
    status: UncertaintyStatus
    units_ref: PinnedReferenceIdentity
    use_restrictions: tuple[object, ...]

    def __post_init__(self) -> None:
        if type(self) is not UncertaintyRepresentation:
            raise invalid("/uncertainty_binding", ReferenceInputCode.WRONG_TYPE)
        representation = exact(
            self.representation_ref,
            PinnedReferenceIdentity,
            "/uncertainty_binding/representation_ref",
        )
        uncertainty_challenge = representation.challenge_key
        kinds = exact_tuple(
            self.component_kinds,
            UncertaintyComponentKind,
            "/component_kinds",
            nonempty=True,
            unique=True,
        )
        object.__setattr__(
            self,
            "component_kinds",
            tuple(
                sorted(
                    kinds,
                    key=lambda item: encode_value(CanonicalText(item.value)),
                )
            ),
        )
        object.__setattr__(
            self,
            "coverage_ref",
            owner(
                self.coverage_ref,
                "coverage_qualification",
                "/coverage_ref",
                challenge_key=uncertainty_challenge,
            ),
        )
        object.__setattr__(
            self,
            "dependence_policy_ref",
            owner(
                self.dependence_policy_ref,
                "replication_dependence_policy",
                "/dependence_policy_ref",
                challenge_key=uncertainty_challenge,
            ),
        )
        object.__setattr__(
            self,
            "estimand_ref",
            owner(
                self.estimand_ref,
                "estimand_scope",
                "/estimand_ref",
                challenge_key=uncertainty_challenge,
            ),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            owner_set(
                self.evidence_refs,
                "audit_evidence",
                "/evidence_refs",
                challenge_key=uncertainty_challenge,
            ),
        )
        object.__setattr__(
            self,
            "limitations",
            owner_set(
                self.limitations,
                "restriction",
                "/limitations",
                challenge_key=uncertainty_challenge,
            ),
        )
        object.__setattr__(
            self,
            "method_ref",
            pinned_identity(
                self.method_ref,
                ReferenceIdentityKind.UNCERTAINTY_METHOD,
                "/uncertainty_binding/method_ref",
                challenge_key=uncertainty_challenge,
            ),
        )
        object.__setattr__(
            self,
            "representation_ref",
            pinned_identity(
                representation,
                ReferenceIdentityKind.UNCERTAINTY_REPRESENTATION,
                "/uncertainty_binding/representation_ref",
                challenge_key=uncertainty_challenge,
            ),
        )
        object.__setattr__(
            self,
            "status",
            exact_enum(self.status, UncertaintyStatus, "/uncertainty_binding/status"),
        )
        object.__setattr__(
            self,
            "units_ref",
            pinned_identity(
                self.units_ref,
                ReferenceIdentityKind.UNITS,
                "/uncertainty_binding/units_ref",
                challenge_key=uncertainty_challenge,
            ),
        )
        object.__setattr__(
            self,
            "use_restrictions",
            owner_set(
                self.use_restrictions,
                "permitted_use",
                "/use_restrictions",
                challenge_key=uncertainty_challenge,
            ),
        )

    @property
    def challenge_key(self) -> ChallengeKey:
        return self.representation_ref.challenge_key


@dataclass(frozen=True, slots=True, repr=False)
class DependencyDisclosure(ProtectedReferenceValue):
    category: DependencyCategory
    evidence_refs: tuple[object, ...]
    relation: DependencyRelation

    def __post_init__(self) -> None:
        if type(self) is not DependencyDisclosure:
            raise invalid("/dependency_disclosures", ReferenceInputCode.WRONG_TYPE)
        object.__setattr__(
            self,
            "category",
            exact_enum(
                self.category,
                DependencyCategory,
                "/dependency_disclosures/category",
            ),
        )
        copied = exact_tuple(
            self.evidence_refs,
            None,
            "/dependency_disclosures/evidence_refs",
        )
        reconstructed: list[object] = []
        for item in copied:
            try:
                reconstructed.append(require_owner_ref(item, "provenance"))
            except (AuthoringError, TypeError, ValueError):
                raise invalid(
                    "/dependency_disclosures/evidence_refs",
                    ReferenceInputCode.WRONG_TYPE,
                ) from None
        if len(set(reconstructed)) != len(reconstructed):
            raise invalid(
                "/dependency_disclosures/evidence_refs",
                ReferenceInputCode.DUPLICATE_IDENTITY,
            )
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(
                sorted(
                    reconstructed,
                    key=lambda item: encode_value(owner_ref_to_canonical(item)),
                )
            ),
        )
        object.__setattr__(
            self,
            "relation",
            exact_enum(
                self.relation,
                DependencyRelation,
                "/dependency_disclosures/relation",
            ),
        )


@dataclass(frozen=True, slots=True, repr=False)
class ReferenceProvenance(ProtectedReferenceValue):
    dependency_disclosures: tuple[DependencyDisclosure, ...]
    environment_ref: PinnedReferenceIdentity
    evidence_campaign_ref: object
    generated_or_copied_code_refs: tuple[object, ...]
    implementation_ref: PinnedReferenceIdentity
    method_ref: PinnedReferenceIdentity
    provenance_refs: tuple[object, ...]
    reviewer_authority_refs: tuple[object, ...]
    rights_profile_ref: object
    source_ref: PinnedReferenceIdentity

    def __post_init__(self) -> None:
        if type(self) is not ReferenceProvenance:
            raise invalid("/provenance_binding", ReferenceInputCode.WRONG_TYPE)
        source = exact(
            self.source_ref, PinnedReferenceIdentity, "/provenance_binding/source_ref"
        )
        provenance_challenge = source.challenge_key
        supplied_disclosures = exact_tuple(
            self.dependency_disclosures,
            DependencyDisclosure,
            "/dependency_disclosures",
        )
        disclosures = tuple(
            DependencyDisclosure(
                disclosure.category,
                disclosure.evidence_refs,
                disclosure.relation,
            )
            for disclosure in supplied_disclosures
        )
        expected_categories = tuple(DependencyCategory)
        if (
            len(disclosures) != len(expected_categories)
            or tuple(item.category for item in disclosures) != expected_categories
        ):
            raise invalid("/dependency_disclosures")
        for disclosure in disclosures:
            for evidence_ref in disclosure.evidence_refs:
                owner(
                    evidence_ref,
                    "provenance",
                    "/dependency_disclosures/evidence_refs",
                    challenge_key=provenance_challenge,
                )
        object.__setattr__(self, "dependency_disclosures", tuple(disclosures))
        object.__setattr__(
            self,
            "environment_ref",
            pinned_identity(
                self.environment_ref,
                ReferenceIdentityKind.ENVIRONMENT,
                "/provenance_binding/environment_ref",
                challenge_key=provenance_challenge,
            ),
        )
        object.__setattr__(
            self,
            "implementation_ref",
            pinned_identity(
                self.implementation_ref,
                ReferenceIdentityKind.IMPLEMENTATION,
                "/provenance_binding/implementation_ref",
                challenge_key=provenance_challenge,
            ),
        )
        object.__setattr__(
            self,
            "method_ref",
            pinned_identity(
                self.method_ref,
                ReferenceIdentityKind.METHOD,
                "/provenance_binding/method_ref",
                challenge_key=provenance_challenge,
            ),
        )
        object.__setattr__(
            self,
            "source_ref",
            pinned_identity(
                source,
                ReferenceIdentityKind.SOURCE,
                "/provenance_binding/source_ref",
                challenge_key=provenance_challenge,
            ),
        )
        object.__setattr__(
            self,
            "evidence_campaign_ref",
            owner(
                self.evidence_campaign_ref,
                "evidence_campaign",
                "/evidence_campaign_ref",
                challenge_key=provenance_challenge,
            ),
        )
        object.__setattr__(
            self,
            "generated_or_copied_code_refs",
            owner_set(
                self.generated_or_copied_code_refs,
                "provenance",
                "/generated_or_copied_code_refs",
                challenge_key=provenance_challenge,
            ),
        )
        object.__setattr__(
            self,
            "provenance_refs",
            owner_set(
                self.provenance_refs,
                "provenance",
                "/provenance_refs",
                challenge_key=provenance_challenge,
            ),
        )
        object.__setattr__(
            self,
            "reviewer_authority_refs",
            owner_set(
                self.reviewer_authority_refs,
                "authority_evidence",
                "/reviewer_authority_refs",
                challenge_key=provenance_challenge,
            ),
        )
        object.__setattr__(
            self,
            "rights_profile_ref",
            owner(
                self.rights_profile_ref,
                "rights_profile",
                "/rights_profile_ref",
                challenge_key=provenance_challenge,
            ),
        )

    @property
    def challenge_key(self) -> ChallengeKey:
        return self.source_ref.challenge_key


@dataclass(frozen=True, slots=True, repr=False)
class RealizedComponentBinding(ProtectedReferenceValue):
    configuration_ref: PinnedReferenceIdentity
    entry_ref: ReferencePolicyEntryRef
    environment_ref: PinnedReferenceIdentity
    hardware_ref: PinnedReferenceIdentity
    implementation_ref: PinnedReferenceIdentity
    method_ref: PinnedReferenceIdentity
    precision_ref: PinnedReferenceIdentity

    def __post_init__(self) -> None:
        if type(self) is not RealizedComponentBinding:
            raise invalid("/component_bindings", ReferenceInputCode.WRONG_TYPE)
        entry = reference_ref(self.entry_ref, ReferencePolicyEntryRef, "/entry_ref")
        component_challenge = entry.challenge_key
        object.__setattr__(self, "entry_ref", entry)
        object.__setattr__(
            self,
            "configuration_ref",
            pinned_identity(
                self.configuration_ref,
                ReferenceIdentityKind.CONFIGURATION,
                "/configuration_ref",
                challenge_key=component_challenge,
            ),
        )
        object.__setattr__(
            self,
            "environment_ref",
            pinned_identity(
                self.environment_ref,
                ReferenceIdentityKind.ENVIRONMENT,
                "/environment_ref",
                challenge_key=component_challenge,
            ),
        )
        object.__setattr__(
            self,
            "hardware_ref",
            pinned_identity(
                self.hardware_ref,
                ReferenceIdentityKind.HARDWARE,
                "/hardware_ref",
                challenge_key=component_challenge,
            ),
        )
        object.__setattr__(
            self,
            "implementation_ref",
            pinned_identity(
                self.implementation_ref,
                ReferenceIdentityKind.IMPLEMENTATION,
                "/implementation_ref",
                challenge_key=component_challenge,
            ),
        )
        object.__setattr__(
            self,
            "method_ref",
            pinned_identity(
                self.method_ref,
                ReferenceIdentityKind.METHOD,
                "/method_ref",
                challenge_key=component_challenge,
            ),
        )
        object.__setattr__(
            self,
            "precision_ref",
            pinned_identity(
                self.precision_ref,
                ReferenceIdentityKind.PRECISION,
                "/precision_ref",
                challenge_key=component_challenge,
            ),
        )

    @property
    def challenge_key(self) -> ChallengeKey:
        return self.entry_ref.challenge_key


@dataclass(frozen=True, slots=True, repr=False)
class AdmissionAttemptBinding(ProtectedReferenceValue):
    admission_authority_ref: PinnedReferenceIdentity
    answer_key_authority_target: ReferenceAuthorityTarget
    artifact_binding: AdmissionArtifactBinding
    case_ref: CanonicalChallengeCaseRef
    comparison_refs: tuple[ReferenceComparisonRecordRef, ...]
    decision_profile_ref: PinnedReferenceIdentity
    disclosure_policy_ref: object
    primary_execution_target: ReferenceAuthorityTarget
    provenance_policy_ref: object
    qualification_binding: QualificationBinding
    rights_profile_ref: object
    run_ref: ReferenceRunRecordRef
    use_restrictions: tuple[object, ...]
    witness_targets: tuple[ReferenceWitnessTarget, ...]

    def __post_init__(self) -> None:
        if type(self) is not AdmissionAttemptBinding:
            raise invalid("/attempt_binding", ReferenceInputCode.WRONG_TYPE)
        case = top_ref(self.case_ref, CanonicalChallengeCaseRef, "/case_ref")
        attempt_challenge = case.challenge_key
        object.__setattr__(self, "case_ref", case)
        object.__setattr__(
            self,
            "admission_authority_ref",
            pinned_identity(
                self.admission_authority_ref,
                ReferenceIdentityKind.ADMISSION_AUTHORITY,
                "/admission_authority_ref",
                challenge_key=attempt_challenge,
            ),
        )
        supplied_answer_target = exact(
            self.answer_key_authority_target,
            ReferenceAuthorityTarget,
            "/answer_key_authority_target",
        )
        answer_target = ReferenceAuthorityTarget(
            supplied_answer_target.kind,
            supplied_answer_target.value,
        )
        _require_same_challenge(
            answer_target.challenge_key,
            attempt_challenge,
            "/answer_key_authority_target",
        )
        supplied_primary_target = exact(
            self.primary_execution_target,
            ReferenceAuthorityTarget,
            "/primary_execution_target",
        )
        primary_target = ReferenceAuthorityTarget(
            supplied_primary_target.kind,
            supplied_primary_target.value,
        )
        _require_same_challenge(
            primary_target.challenge_key,
            attempt_challenge,
            "/primary_execution_target",
        )
        if answer_target != primary_target:
            raise invalid("/primary_execution_target", ReferenceInputCode.STALE_BINDING)
        object.__setattr__(self, "answer_key_authority_target", answer_target)
        object.__setattr__(self, "primary_execution_target", primary_target)
        supplied_artifact = exact(
            self.artifact_binding, AdmissionArtifactBinding, "/artifact_binding"
        )
        artifact = AdmissionArtifactBinding(
            supplied_artifact.tag,
            supplied_artifact.value,
        )
        if artifact.is_bound:
            _require_same_challenge(
                artifact.challenge_key, attempt_challenge, "/artifact_binding"
            )
        object.__setattr__(self, "artifact_binding", artifact)
        object.__setattr__(
            self,
            "comparison_refs",
            reference_ref_sequence(
                self.comparison_refs,
                ReferenceComparisonRecordRef,
                "/comparison_refs",
                challenge_key=attempt_challenge,
            ),
        )
        object.__setattr__(
            self,
            "decision_profile_ref",
            pinned_identity(
                self.decision_profile_ref,
                ReferenceIdentityKind.ADMISSION_PROFILE,
                "/decision_profile_ref",
                challenge_key=attempt_challenge,
            ),
        )
        object.__setattr__(
            self,
            "disclosure_policy_ref",
            owner(
                self.disclosure_policy_ref,
                "disclosure_policy",
                "/disclosure_policy_ref",
                challenge_key=attempt_challenge,
            ),
        )
        object.__setattr__(
            self,
            "provenance_policy_ref",
            owner(
                self.provenance_policy_ref,
                "provenance",
                "/provenance_policy_ref",
                challenge_key=attempt_challenge,
            ),
        )
        object.__setattr__(
            self,
            "rights_profile_ref",
            owner(
                self.rights_profile_ref,
                "rights_profile",
                "/rights_profile_ref",
                challenge_key=attempt_challenge,
            ),
        )
        supplied_qualification = exact(
            self.qualification_binding,
            QualificationBinding,
            "/qualification_binding",
        )
        qualification = QualificationBinding(
            supplied_qualification.tag,
            supplied_qualification.value,
        )
        if qualification.is_bound:
            owner(
                qualification.value,
                "qualification_evidence_bundle",
                "/qualification_binding",
                challenge_key=attempt_challenge,
            )
        object.__setattr__(self, "qualification_binding", qualification)
        object.__setattr__(
            self,
            "run_ref",
            reference_ref(
                self.run_ref,
                ReferenceRunRecordRef,
                "/run_ref",
                challenge_key=attempt_challenge,
            ),
        )
        object.__setattr__(
            self,
            "use_restrictions",
            owner_set(
                self.use_restrictions,
                "permitted_use",
                "/use_restrictions",
                challenge_key=attempt_challenge,
            ),
        )
        supplied_witnesses = exact_tuple(
            self.witness_targets,
            ReferenceWitnessTarget,
            "/witness_targets",
            unique=True,
        )
        witnesses = tuple(
            ReferenceWitnessTarget(witness.kind, witness.value)
            for witness in supplied_witnesses
        )
        for witness in witnesses:
            _require_same_challenge(
                witness.challenge_key, attempt_challenge, "/witness_targets"
            )
        object.__setattr__(self, "witness_targets", tuple(witnesses))

    @property
    def challenge_key(self) -> ChallengeKey:
        return self.case_ref.challenge_key


def same_scope(left: object, right: object) -> bool:
    return (
        type(left) is ReferenceScopeBinding
        and type(right) is ReferenceScopeBinding
        and left == right
    )


__all__ = [
    "AdmissionArtifactBinding",
    "AdmissionAttemptBinding",
    "ArtifactContentBinding",
    "ConditioningAssessment",
    "DependencyDisclosure",
    "OptionalBinding",
    "PinnedReferenceIdentity",
    "ProtectedReferenceValue",
    "QualificationBinding",
    "RealizedComponentBinding",
    "ReferenceAuthorityTarget",
    "ReferenceAuthorityTargetBinding",
    "ReferenceExecutionTarget",
    "ReferenceGrantBinding",
    "ReferenceProvenance",
    "ReferenceRequestBinding",
    "ReferenceScopeBinding",
    "ReferenceTruthRecord",
    "ReferenceWitnessTarget",
    "RunArtifactBinding",
    "SupportApplicabilityAssessment",
    "UncertaintyRepresentation",
    "challenge",
    "digest",
    "evidence_role_binding",
    "exact",
    "exact_bool",
    "exact_bytes",
    "exact_enum",
    "exact_tuple",
    "identifier",
    "invalid",
    "owner",
    "owner_sequence",
    "owner_set",
    "pinned_identity",
    "reference_ref",
    "reference_ref_sequence",
    "same_scope",
    "text",
    "top_ref",
    "top_ref_sequence",
    "version",
]
