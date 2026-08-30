"""Canonical physical cases and audience-separated identity projections."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from carbon.registry.model import ChallengeKey

from .model import (
    ApplicabilityBinding,
    DisclosureClass,
    DisclosureContract,
    PopulationRole,
    PublicCaseFactKind,
    canonical_set_tuple,
    copied_challenge_key,
    exact,
    exact_enum,
    exact_tuple,
    owner,
    owner_tuple,
)
from .physical import _validate_common
from .refs import (
    CandidateOutputContractRef,
    CanonicalChallengeCaseRef,
    InstanceDistributionContractRef,
    PhysicalSystemSpecRef,
    SamplingPlanRef,
)


@dataclass(frozen=True, slots=True)
class RelatedPopulationBinding:
    population_ref: InstanceDistributionContractRef
    relationship_ref: object

    def __post_init__(self) -> None:
        exact(self.population_ref, InstanceDistributionContractRef, "population_ref")
        owner(self.relationship_ref, "population_relationship", "relationship_ref")


class CaseSourceKind(str, Enum):
    GENERATED = "GENERATED"
    OBSERVED = "OBSERVED"
    EXPERIMENTAL = "EXPERIMENTAL"
    INDUSTRIAL = "INDUSTRIAL"
    ANALYTIC = "ANALYTIC"
    MANUFACTURED_SOLUTION = "MANUFACTURED_SOLUTION"


@dataclass(frozen=True, slots=True)
class GeneratedCaseSource:
    generation_event_ref: object
    generator_ref: object

    def __post_init__(self) -> None:
        owner(self.generation_event_ref, "generation_event", "generation_event_ref")
        owner(self.generator_ref, "generator", "generator_ref")


@dataclass(frozen=True, slots=True)
class ObservedCaseSource:
    observation_source_ref: object

    def __post_init__(self) -> None:
        owner(self.observation_source_ref, "observation_source", "observation_source_ref")


@dataclass(frozen=True, slots=True)
class ExperimentalCaseSource:
    experiment_source_ref: object

    def __post_init__(self) -> None:
        owner(self.experiment_source_ref, "experiment_source", "experiment_source_ref")


@dataclass(frozen=True, slots=True)
class IndustrialCaseSource:
    industrial_source_ref: object

    def __post_init__(self) -> None:
        owner(self.industrial_source_ref, "industrial_source", "industrial_source_ref")


@dataclass(frozen=True, slots=True)
class AnalyticCaseSource:
    analytic_construction_ref: object

    def __post_init__(self) -> None:
        owner(
            self.analytic_construction_ref,
            "analytic_construction",
            "analytic_construction_ref",
        )


@dataclass(frozen=True, slots=True)
class ManufacturedSolutionCaseSource:
    verification_campaign_ref: object
    verification_construction_ref: object

    def __post_init__(self) -> None:
        owner(
            self.verification_campaign_ref,
            "evidence_campaign",
            "verification_campaign_ref",
        )
        owner(
            self.verification_construction_ref,
            "verification_construction",
            "verification_construction_ref",
        )


@dataclass(frozen=True, slots=True)
class CaseSourceBinding:
    kind: CaseSourceKind
    payload: (
        GeneratedCaseSource
        | ObservedCaseSource
        | ExperimentalCaseSource
        | IndustrialCaseSource
        | AnalyticCaseSource
        | ManufacturedSolutionCaseSource
    )

    def __post_init__(self) -> None:
        exact_enum(self.kind, CaseSourceKind, "case source kind")
        expected = {
            CaseSourceKind.GENERATED: GeneratedCaseSource,
            CaseSourceKind.OBSERVED: ObservedCaseSource,
            CaseSourceKind.EXPERIMENTAL: ExperimentalCaseSource,
            CaseSourceKind.INDUSTRIAL: IndustrialCaseSource,
            CaseSourceKind.ANALYTIC: AnalyticCaseSource,
            CaseSourceKind.MANUFACTURED_SOLUTION: ManufacturedSolutionCaseSource,
        }[self.kind]
        exact(self.payload, expected, "case source payload")


@dataclass(frozen=True, slots=True, repr=False)
class CanonicalChallengeCase:
    object_kind: str
    schema_version: str
    canonicalization_profile: str
    challenge_key: ChallengeKey
    object_id: str
    object_version: str
    supersedes: ApplicabilityBinding[CanonicalChallengeCaseRef]
    physical_system_ref: PhysicalSystemSpecRef
    candidate_output_ref: CandidateOutputContractRef
    primary_population_ref: InstanceDistributionContractRef
    related_population_bindings: tuple[RelatedPopulationBinding, ...]
    sampling_plan_binding: ApplicabilityBinding[SamplingPlanRef]
    case_source: CaseSourceBinding
    case_representation_ref: object
    physical_payload_ref: object
    query_population_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    observation_population_binding: ApplicabilityBinding[InstanceDistributionContractRef]
    evidence_campaign_binding: ApplicabilityBinding[object]
    intended_slot_binding: ApplicabilityBinding[object]
    prospective_censoring_policy_binding: ApplicabilityBinding[object]
    applicability_bindings: tuple[object, ...]
    disclosure_class: DisclosureClass
    disclosure_contract: DisclosureContract
    case_provenance_refs: tuple[object, ...]

    def __post_init__(self) -> None:
        if type(self) is not CanonicalChallengeCase:
            raise TypeError("CanonicalChallengeCase subclasses are rejected")
        copied = _validate_common(
            object_kind=self.object_kind,
            expected_kind="canonical_challenge_case",
            schema_version=self.schema_version,
            canonicalization_profile=self.canonicalization_profile,
            challenge_key=self.challenge_key,
            object_id=self.object_id,
            object_version=self.object_version,
            supersedes=self.supersedes,
            predecessor_type=CanonicalChallengeCaseRef,
        )
        object.__setattr__(self, "challenge_key", copied_challenge_key(copied))
        for name, ref_type in (
            ("physical_system_ref", PhysicalSystemSpecRef),
            ("candidate_output_ref", CandidateOutputContractRef),
            ("primary_population_ref", InstanceDistributionContractRef),
        ):
            ref = exact(getattr(self, name), ref_type, name)
            if ref.challenge_key != copied:
                raise ValueError(f"{name} Challenge mismatch")
        related = exact_tuple(
            self.related_population_bindings,
            RelatedPopulationBinding,
            "related_population_bindings",
            unique=True,
        )
        if len({item.population_ref for item in related}) != len(related):
            raise ValueError("related populations contain duplicate refs")
        for item in related:
            if item.population_ref.challenge_key != copied:
                raise ValueError("related population Challenge mismatch")
        object.__setattr__(
            self, "related_population_bindings", canonical_set_tuple(related)
        )
        plan = exact(self.sampling_plan_binding, ApplicabilityBinding, "sampling_plan_binding")
        if plan.is_bound:
            plan_ref = exact(plan.value, SamplingPlanRef, "sampling_plan_binding value")
            if plan_ref.challenge_key != copied:
                raise ValueError("SamplingPlan Challenge mismatch")
        exact(self.case_source, CaseSourceBinding, "case_source")
        owner(
            self.case_representation_ref,
            "representation",
            "case_representation_ref",
        )
        owner(self.physical_payload_ref, "protected_case_payload", "physical_payload_ref")
        for name, role in (
            ("query_population_binding", PopulationRole.QUERY),
            ("observation_population_binding", PopulationRole.OBSERVATION),
        ):
            binding = exact(getattr(self, name), ApplicabilityBinding, name)
            if binding.is_bound:
                ref = exact(binding.value, InstanceDistributionContractRef, f"{name} value")
                if ref.expected_population_role != role.value or ref.challenge_key != copied:
                    raise ValueError(f"{name} role or Challenge mismatch")
        for name, kind in (
            ("evidence_campaign_binding", "evidence_campaign"),
            ("intended_slot_binding", "protected_intended_slot"),
            ("prospective_censoring_policy_binding", "censoring_policy"),
        ):
            binding = exact(getattr(self, name), ApplicabilityBinding, name)
            if binding.is_bound:
                owner(binding.value, kind, name)
        if plan.is_bound:
            if not self.intended_slot_binding.is_bound:
                raise ValueError("plan-bound case requires protected intended slot")
            if not self.prospective_censoring_policy_binding.is_bound:
                raise ValueError("plan-bound case requires prospective censoring policy")
        elif (
            self.intended_slot_binding.is_bound
            or self.prospective_censoring_policy_binding.is_bound
        ):
            raise ValueError("plan-free case cannot bind slot or plan censoring policy")
        object.__setattr__(
            self,
            "applicability_bindings",
            owner_tuple(
                self.applicability_bindings,
                "applicability",
                "applicability_bindings",
                nonempty=True,
            ),
        )
        exact_enum(self.disclosure_class, DisclosureClass, "disclosure_class")
        exact(self.disclosure_contract, DisclosureContract, "disclosure_contract")
        object.__setattr__(
            self,
            "case_provenance_refs",
            owner_tuple(
                self.case_provenance_refs,
                "provenance",
                "case_provenance_refs",
                nonempty=True,
            ),
        )

    def dependency_refs(self) -> tuple[object, ...]:
        refs: list[object] = [
            self.physical_system_ref,
            self.candidate_output_ref,
            self.primary_population_ref,
        ]
        refs.extend(item.population_ref for item in self.related_population_bindings)
        for binding in (
            self.supersedes,
            self.sampling_plan_binding,
            self.query_population_binding,
            self.observation_population_binding,
        ):
            if binding.is_bound:
                refs.append(binding.value)
        return tuple(dict.fromkeys(refs))

    def to_canonical_record(self):
        from .model import authored_object_to_record

        return authored_object_to_record(self)

    def canonical_bytes(self) -> bytes:
        from .model import authored_object_canonical_bytes

        return authored_object_canonical_bytes(self)

    def to_ref(self) -> CanonicalChallengeCaseRef:
        from .model import authored_object_to_ref

        return authored_object_to_ref(self)


@dataclass(frozen=True, slots=True)
class PublicCaseFactBinding:
    fact_kind: PublicCaseFactKind
    public_value_ref: object

    def __post_init__(self) -> None:
        exact_enum(self.fact_kind, PublicCaseFactKind, "public fact kind")
        owner(self.public_value_ref, "public_case_fact", "public_value_ref")


_PROJECTION_CAPABILITY = object()
_PROJECTION_AUTHORITY_CAPABILITY = object()


@dataclass(frozen=True, slots=True, repr=False)
class CaseProjectionVerificationEcho:
    """Exact in-process echo from the separately owned projection registry.

    This is a composition contract, not authentication or durable proof.  The
    supplying authority remains responsible for consulting its protected,
    revocation-aware issuance record.
    """

    authority_ref: object
    case_ref: CanonicalChallengeCaseRef
    projection: object

    def __post_init__(self) -> None:
        owner(self.authority_ref, "projection_issuance", "authority_ref")
        exact(self.case_ref, CanonicalChallengeCaseRef, "case_ref")
        if type(self.projection) not in {
            ProtectedCaseIdentityProjection,
            InternalCaseIdentityProjection,
            PublicCaseIdentityProjection,
        }:
            raise TypeError("projection echo has an unrecognized nominal type")


class CaseProjectionRegistryAuthority(Protocol):
    """External A4/protocol-owned verifier for one exact projection pairing."""

    def verify_case_projection(
        self,
        *,
        authority_ref: object,
        case_ref: CanonicalChallengeCaseRef,
        projection: object,
    ) -> CaseProjectionVerificationEcho:
        """Return the exact immutable pairing currently held by the registry."""
        ...


class CaseProjectionAuthority:
    """Non-serializable capability backed by an external issuance registry.

    B-02A never derives public handles or pairing commitments.  The injected
    verifier must consult the durable A4/protocol-owned issuance record and
    raise when the exact projection/case pairing is absent or revoked.
    """

    __slots__ = ("_authority", "authority_ref")

    def __init__(
        self,
        *,
        _capability: object,
        authority_ref: object,
        authority: CaseProjectionRegistryAuthority,
    ) -> None:
        if _capability is not _PROJECTION_AUTHORITY_CAPABILITY:
            raise PermissionError("projection authority requires controlled issuance")
        owner(authority_ref, "projection_issuance", "authority_ref")
        if callable(authority):
            raise TypeError("projection registry authority must not be a raw callable")
        verifier = getattr(authority, "verify_case_projection", None)
        if not callable(verifier):
            raise TypeError(
                "projection registry authority must provide verify_case_projection"
            )
        self.authority_ref = authority_ref
        self._authority = authority

    def require_pairing(
        self,
        projection: object,
        case_ref: CanonicalChallengeCaseRef,
    ) -> None:
        if type(projection) not in {
            ProtectedCaseIdentityProjection,
            InternalCaseIdentityProjection,
            PublicCaseIdentityProjection,
        }:
            raise TypeError("projection has an unrecognized nominal type")
        exact(case_ref, CanonicalChallengeCaseRef, "case_ref")
        if projection.issuance_ref != self.authority_ref:
            raise ValueError("projection issuance does not match authority")
        result = self._authority.verify_case_projection(
            authority_ref=self.authority_ref,
            case_ref=case_ref,
            projection=projection,
        )
        echo = exact(result, CaseProjectionVerificationEcho, "projection verification")
        if (
            type(echo.authority_ref) is not type(self.authority_ref)
            or echo.authority_ref != self.authority_ref
        ):
            raise ValueError("projection verification authority mismatch")
        if type(echo.case_ref) is not type(case_ref) or echo.case_ref != case_ref:
            raise ValueError("projection verification case mismatch")
        if echo.projection != projection or type(echo.projection) is not type(projection):
            raise ValueError("projection verification projection mismatch")


def _issue_case_projection_authority(
    *,
    authority_ref: object,
    authority: CaseProjectionRegistryAuthority,
) -> CaseProjectionAuthority:
    """Internal adapter for a trusted durable A4/protocol issuance registry."""

    return CaseProjectionAuthority(
        _capability=_PROJECTION_AUTHORITY_CAPABILITY,
        authority_ref=authority_ref,
        authority=authority,
    )


@dataclass(frozen=True, slots=True, repr=False, init=False)
class ProtectedCaseIdentityProjection:
    schema_version: str
    case_ref: CanonicalChallengeCaseRef
    payload_ref: object
    intended_slot_ref: object
    realized_stratum_binding: ApplicabilityBinding[str]
    replacement_linkage: ApplicabilityBinding[object]
    audit_evidence_refs: tuple[object, ...]
    issuance_ref: object

    def __init__(self, *, _capability: object, **fields: object) -> None:
        if _capability is not _PROJECTION_CAPABILITY:
            raise PermissionError("protected projection requires controlled issuance")
        expected = _PROTECTED_PROJECTION_FIELDS
        if set(fields) != set(expected):
            raise TypeError("protected projection fields are closed and complete")
        for name in expected:
            object.__setattr__(self, name, fields[name])
        self.__post_init__()

    def __post_init__(self) -> None:
        from .primitives import validate_canonical_id, validate_version_token

        validate_version_token(self.schema_version, "schema_version")
        exact(self.case_ref, CanonicalChallengeCaseRef, "case_ref")
        if self.case_ref.disclosure_class != DisclosureClass.PROTECTED.value:
            raise ValueError("protected projection requires PROTECTED case ref")
        owner(self.payload_ref, "protected_case_payload", "payload_ref")
        owner(self.intended_slot_ref, "protected_intended_slot", "intended_slot_ref")
        binding = exact(
            self.realized_stratum_binding,
            ApplicabilityBinding,
            "realized_stratum_binding",
        )
        if binding.is_bound:
            validate_canonical_id(binding.value, "realized_stratum_id")
        linkage = exact(self.replacement_linkage, ApplicabilityBinding, "replacement_linkage")
        if linkage.is_bound:
            owner(
                linkage.value,
                "protected_replacement_lineage",
                "replacement_linkage",
            )
        object.__setattr__(
            self,
            "audit_evidence_refs",
            owner_tuple(
                self.audit_evidence_refs,
                "audit_evidence",
                "audit_evidence_refs",
                nonempty=True,
            ),
        )
        owner(self.issuance_ref, "projection_issuance", "issuance_ref")


@dataclass(frozen=True, slots=True, repr=False, init=False)
class InternalCaseIdentityProjection:
    schema_version: str
    case_ref: CanonicalChallengeCaseRef
    primary_population_ref: InstanceDistributionContractRef
    sampling_plan_binding: ApplicabilityBinding[SamplingPlanRef]
    evidence_campaign_binding: ApplicabilityBinding[object]
    service_scope_ref: object
    issuance_ref: object

    def __init__(self, *, _capability: object, **fields: object) -> None:
        if _capability is not _PROJECTION_CAPABILITY:
            raise PermissionError("internal projection requires controlled issuance")
        expected = _INTERNAL_PROJECTION_FIELDS
        if set(fields) != set(expected):
            raise TypeError("internal projection fields are closed and complete")
        for name in expected:
            object.__setattr__(self, name, fields[name])
        self.__post_init__()

    def __post_init__(self) -> None:
        from .primitives import validate_version_token

        validate_version_token(self.schema_version, "schema_version")
        exact(self.case_ref, CanonicalChallengeCaseRef, "case_ref")
        exact(
            self.primary_population_ref,
            InstanceDistributionContractRef,
            "primary_population_ref",
        )
        plan = exact(self.sampling_plan_binding, ApplicabilityBinding, "sampling_plan_binding")
        if plan.is_bound:
            exact(plan.value, SamplingPlanRef, "sampling_plan_binding value")
        campaign = exact(
            self.evidence_campaign_binding,
            ApplicabilityBinding,
            "evidence_campaign_binding",
        )
        if campaign.is_bound:
            owner(campaign.value, "evidence_campaign", "evidence_campaign_binding")
        owner(self.service_scope_ref, "internal_service_scope", "service_scope_ref")
        owner(self.issuance_ref, "projection_issuance", "issuance_ref")


@dataclass(frozen=True, slots=True, init=False)
class PublicCaseIdentityProjection:
    schema_version: str
    challenge_key: ChallengeKey
    opaque_public_handle: object
    disclosure_policy_ref: object
    issuance_ref: object
    public_fact_bindings: tuple[PublicCaseFactBinding, ...]

    def __init__(self, *, _capability: object, **fields: object) -> None:
        if _capability is not _PROJECTION_CAPABILITY:
            raise PermissionError("public projection requires controlled issuance")
        expected = _PUBLIC_PROJECTION_FIELDS
        if set(fields) != set(expected):
            raise TypeError("public projection fields are closed and complete")
        for name in expected:
            object.__setattr__(self, name, fields[name])
        self.__post_init__()

    def __post_init__(self) -> None:
        from .primitives import validate_version_token

        validate_version_token(self.schema_version, "schema_version")
        object.__setattr__(self, "challenge_key", copied_challenge_key(self.challenge_key))
        owner(
            self.opaque_public_handle,
            "opaque_public_case_handle",
            "opaque_public_handle",
        )
        # The working contract requires exact equality with the case's
        # disclosure-contract release-policy ref; the field name does not
        # create a second nominal policy identity.
        owner(self.disclosure_policy_ref, "release_policy", "disclosure_policy_ref")
        owner(self.issuance_ref, "projection_issuance", "issuance_ref")
        facts = exact_tuple(
            self.public_fact_bindings,
            PublicCaseFactBinding,
            "public_fact_bindings",
            unique=True,
        )
        if len({item.fact_kind for item in facts}) != len(facts):
            raise ValueError("public facts contain a duplicate fact kind")
        object.__setattr__(
            self,
            "public_fact_bindings",
            canonical_set_tuple(facts),
        )


_PROTECTED_PROJECTION_FIELDS = (
    "schema_version",
    "case_ref",
    "payload_ref",
    "intended_slot_ref",
    "realized_stratum_binding",
    "replacement_linkage",
    "audit_evidence_refs",
    "issuance_ref",
)
_INTERNAL_PROJECTION_FIELDS = (
    "schema_version",
    "case_ref",
    "primary_population_ref",
    "sampling_plan_binding",
    "evidence_campaign_binding",
    "service_scope_ref",
    "issuance_ref",
)
_PUBLIC_PROJECTION_FIELDS = (
    "schema_version",
    "challenge_key",
    "opaque_public_handle",
    "disclosure_policy_ref",
    "issuance_ref",
    "public_fact_bindings",
)


def issue_public_case_projection(
    authority: CaseProjectionAuthority,
    case: CanonicalChallengeCase,
    *,
    opaque_public_handle: object,
    disclosure_policy_ref: object,
    issuance_ref: object,
    public_fact_bindings: tuple[PublicCaseFactBinding, ...],
) -> PublicCaseIdentityProjection:
    """Issue an allow-listed view after durable exact-pair verification."""

    exact(authority, CaseProjectionAuthority, "projection authority")
    exact(case, CanonicalChallengeCase, "case")
    if disclosure_policy_ref != case.disclosure_contract.release_policy_ref:
        raise ValueError("public disclosure policy does not match the case contract")
    projection = PublicCaseIdentityProjection(
        _capability=_PROJECTION_CAPABILITY,
        schema_version=case.schema_version,
        challenge_key=case.challenge_key,
        opaque_public_handle=opaque_public_handle,
        disclosure_policy_ref=disclosure_policy_ref,
        issuance_ref=issuance_ref,
        public_fact_bindings=public_fact_bindings,
    )
    authority.require_pairing(projection, case.to_ref())
    return projection


def make_internal_case_projection(
    authority: CaseProjectionAuthority,
    case: CanonicalChallengeCase,
    *,
    primary_population_ref: InstanceDistributionContractRef,
    sampling_plan_binding: ApplicabilityBinding[SamplingPlanRef],
    evidence_campaign_binding: ApplicabilityBinding[object],
    service_scope_ref: object,
    issuance_ref: object,
) -> InternalCaseIdentityProjection:
    exact(authority, CaseProjectionAuthority, "projection authority")
    exact(case, CanonicalChallengeCase, "case")
    if primary_population_ref != case.primary_population_ref:
        raise ValueError("internal projection primary population mismatch")
    if sampling_plan_binding != case.sampling_plan_binding:
        raise ValueError("internal projection SamplingPlan mismatch")
    if evidence_campaign_binding != case.evidence_campaign_binding:
        raise ValueError("internal projection evidence campaign mismatch")
    projection = InternalCaseIdentityProjection(
        _capability=_PROJECTION_CAPABILITY,
        schema_version=case.schema_version,
        case_ref=case.to_ref(),
        primary_population_ref=primary_population_ref,
        sampling_plan_binding=sampling_plan_binding,
        evidence_campaign_binding=evidence_campaign_binding,
        service_scope_ref=service_scope_ref,
        issuance_ref=issuance_ref,
    )
    authority.require_pairing(projection, case.to_ref())
    return projection


def make_protected_case_projection(
    authority: CaseProjectionAuthority,
    case: CanonicalChallengeCase,
    *,
    payload_ref: object,
    intended_slot_ref: object,
    realized_stratum_binding: ApplicabilityBinding[str],
    replacement_linkage: ApplicabilityBinding[object],
    audit_evidence_refs: tuple[object, ...],
    issuance_ref: object,
) -> ProtectedCaseIdentityProjection:
    exact(authority, CaseProjectionAuthority, "projection authority")
    exact(case, CanonicalChallengeCase, "case")
    if case.disclosure_class is not DisclosureClass.PROTECTED:
        raise ValueError("protected projection requires PROTECTED case")
    if payload_ref != case.physical_payload_ref:
        raise ValueError("protected projection payload mismatch")
    if not case.intended_slot_binding.is_bound:
        raise ValueError("protected projection requires bound intended slot")
    if intended_slot_ref != case.intended_slot_binding.value:
        raise ValueError("protected projection intended slot mismatch")
    projection = ProtectedCaseIdentityProjection(
        _capability=_PROJECTION_CAPABILITY,
        schema_version=case.schema_version,
        case_ref=case.to_ref(),
        payload_ref=payload_ref,
        intended_slot_ref=intended_slot_ref,
        realized_stratum_binding=realized_stratum_binding,
        replacement_linkage=replacement_linkage,
        audit_evidence_refs=audit_evidence_refs,
        issuance_ref=issuance_ref,
    )
    authority.require_pairing(projection, case.to_ref())
    return projection


def projection_matches_case(
    projection: PublicCaseIdentityProjection,
    case_ref: CanonicalChallengeCaseRef,
    authority: CaseProjectionAuthority,
) -> None:
    """Require the durable non-public issuance record to bind this exact case."""

    exact(authority, CaseProjectionAuthority, "projection authority")
    authority.require_pairing(projection, case_ref)


def require_public_case_projection(value: object) -> PublicCaseIdentityProjection:
    """Reject internal/protected refs at public/miner boundaries."""

    return exact(value, PublicCaseIdentityProjection, "public case projection")
